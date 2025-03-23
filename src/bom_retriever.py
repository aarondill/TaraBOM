import time
import os
import sys
import configparser
from typing import List, Union
from functools import lru_cache
import pyodbc
from contextlib import closing
from dataclasses import dataclass, is_dataclass, asdict
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from platformdirs import user_config_dir


@dataclass(kw_only=True)
class Config:
    port: int
    server: str
    db: str
    omnify_url: str


def read_config() -> Config:
    config_file_names = [
        os.path.join(os.path.dirname(__file__), "bom_retreiver.ini"),
        os.path.join(user_config_dir("bom_retreiver", False), "bom_retreiver.ini"),
        "./bom_retreiver.ini",
    ]
    config = configparser.ConfigParser(allow_unnamed_section=True)
    found_files = config.read(config_file_names)
    if not found_files:
        desc = (
            "This file can be in one of these locations (later override earlier):\n"
            + config_file_names.join("\n")
        )
        raise FileNotFoundError("bom_retreiver.ini not found.\n" + desc)
    port = config.get(configparser.UNNAMED_SECTION, "port", fallback=8080)
    server = config.get(configparser.UNNAMED_SECTION, "server")
    db = config.get(configparser.UNNAMED_SECTION, "db")
    omnify_url = config.get(configparser.UNNAMED_SECTION, "omnify_url")
    return Config(port=port, server=server, db=db, omnify_url=omnify_url)


@dataclass(kw_only=True)
class OmnifyEntry:
    """Class for an item in Omnify"""

    desc: str
    status: int
    under_eco: bool
    rev_letter: str


@dataclass(kw_only=True)
class BomAttachment:
    """Class for an attachment in Omnify"""

    url: str
    file_name: str


@dataclass(kw_only=True)
class BomItem:
    """Class for an item in Omnify"""

    ItemNum: int
    ItemRevID: int
    ItemRevStr: str
    ItemPN: str
    ItemDesc: str
    ItemStatus: str
    QtyStr: str
    attachments: List[BomAttachment]


@dataclass(kw_only=True)
class Output:
    """Class for an item in Omnify"""

    desc: str
    warnings: List[str]
    status: int
    under_eco: bool
    rev_letter: str
    bill_of_materials: List[BomItem]


class BOMRetriever:
    def __init__(self, cnxn, omnify_url: str):
        """
        Args:
            cnxn: Database connection
            omnify_url (str): The URL of the Omnify server, used for constructing attachment URLs
        """
        self.cursor = cnxn.cursor()
        self.omnify_url = omnify_url

    def check_item_existence(self, pn: str) -> bool:
        query = "SELECT Rev FROM EntryInfo WHERE PartNumber = ?"
        self.cursor.execute(query, (pn,))
        row = self.cursor.fetchone()
        return row is not None

    def get_item_info(self, rev_ID: int) -> OmnifyEntry | None:
        # Fetch the highest revision of an item with released status
        query = "SELECT Description,Status,UnderECO FROM EntryInfo WHERE Rev = ?"
        self.cursor.execute(query, (rev_ID,))
        item_row = self.cursor.fetchone()
        if not item_row:
            return None

        # Get revision letter matching the revision ID
        query = "SELECT Rev FROM Rev WHERE ID = ?"
        self.cursor.execute(query, (int(rev_ID),))
        rev_letter = self.cursor.fetchone()[0]

        return OmnifyEntry(
            desc=item_row[0],
            status=item_row[1],
            under_eco=bool(item_row[2]),
            rev_letter=rev_letter,
        )

    def _get_ttl_hash(self):
        """Return the same value withing `seconds` time period"""
        expiration_time = 60 * 30  # 30 minutes
        return round(time.time() / expiration_time)

    @lru_cache()
    def load_toplevel_item(self, part_num, ttl_hash) -> Union[Output, tuple[int, str]]:
        del ttl_hash  # This isn't used! only here to void old caches!
        # Error if attempting to load an empty part number
        if not part_num:
            return (400, "Part Number Required: please enter a part number")

        # Check if any the item exists, error out if not.
        existence = self.check_item_existence(part_num)
        if not existence:
            return (
                400,
                "Part Number Incorrect: Part number entered does not exist",
            )

        # Fetch the highest revision of an item with released status
        query = "SELECT TOP 1 Rev FROM EntryInfo WHERE (Status=1 AND PartNumber = ?) ORDER BY Rev DESC"
        self.cursor.execute(query, (part_num,))
        row = self.cursor.fetchone()
        # Check if any the item is released, error out if not.
        if not row:
            return (403, "Unreleased Item: Part number entered is not released")
        toplevel_rev_id = row[0]

        info = self.get_item_info(toplevel_rev_id)
        if not info:
            return (500, "Something went wrong")  # this should never happen
        warnings = []

        # After confirming item is released, check if it is currently on an open ECO.
        # If so, warn the user but allow to proceed.
        if info.under_eco:
            warnings.append(
                "Item Under ECO: Part number is under an engineering change. Consult engineering before proceeding."
            )
        bom = self.load_bom(toplevel_rev_id)
        return Output(
            warnings=warnings,
            desc=info.desc,
            status=info.status,
            under_eco=info.under_eco,
            rev_letter=info.rev_letter,
            bill_of_materials=bom,
        )

    def load_bom(self, toplevel_rev_id) -> BomItem:
        query = "SELECT ItemNum,ItemRevID,ItemRevStr,ItemPN,ItemDesc,ItemStatus,QtyStr FROM PartsList WHERE RevID = ? ORDER BY ItemNum ASC"
        self.cursor.execute(query, (toplevel_rev_id,))
        rows = self.cursor.fetchall()
        bom_items = []
        for row in rows:
            attachment_query = (  # Get ID's and file names for all "Public" (VaultID=0) attachments for the current BOM item, build a list of Omnify retrieval links
                "SELECT ID,FileURL FROM Attachment WHERE (VaultID=0 AND RevID = ?)"
            )
            self.cursor.execute(attachment_query, (row[1],))
            attachments = []
            while attachment_row := self.cursor.fetchone():
                url = (
                    self.omnify_url
                    + "/Apps/OpenDocument.aspx?obj=0&docid="
                    + str(attachment_row[0])
                )
                attachments.append(BomAttachment(url=url, file_name=attachment_row[1]))
            item = BomItem(
                ItemNum=row[0],
                ItemRevID=row[1],
                ItemRevStr=row[2],
                ItemPN=row[3],
                ItemDesc=row[4],
                ItemStatus=row[5],
                QtyStr=row[6],
                attachments=attachments,
            )
            bom_items.append(item)
        return bom_items


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


# Note that the returned values can *not* be parsed by json.loads, since it will return dicts
def jsonify(o, **kwargs):
    return json.dumps(o, cls=DataclassJSONEncoder, indent=4, sort_keys=True, **kwargs)


class Serv(BaseHTTPRequestHandler):
    def do_GET(self):
        part_num = self.path.split("/")[1]
        retreiver: BOMRetriever = self.server.retreiver
        try:
            result = retreiver.load_toplevel_item(part_num, retreiver._get_ttl_hash())
        except Exception as e:
            print(e)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(bytes(str(e), "utf-8"))
            return
        if isinstance(result, tuple):  # error case
            self.send_response(result[0])
            self.end_headers()
            self.wfile.write(bytes(result[1], "utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(bytes(jsonify(result), "utf-8"))


if __name__ == "__main__":
    if sys.version_info[0] < 3:
        print("Requires Python 3")
        sys.exit()

    config = read_config()
    try:
        port = int(config.port)
    except ValueError:
        print("Invalid port number: ", port)
        sys.exit(1)
    if port < 0 or port > 65535:
        print("Port number out of range")
        sys.exit(1)

    # Open a connection to the Omnify database, create the cursor object for data retrieval
    with closing(
        pyodbc.connect(
            f"Driver=SQL Server;Server={config.server};Database={config.db};Trusted_Connection=yes;"
        )
    ) as cnxn:
        retreiver = BOMRetriever(cnxn, config.omnify_url)
        print("Starting server on port", port)
        with ThreadingHTTPServer(("localhost", port), Serv) as httpd:
            httpd.retreiver = retreiver  # make this accessible to the request handler
            httpd.serve_forever()
