import sys
import pyodbc
from contextlib import closing
from dataclasses import dataclass, is_dataclass, asdict
import json


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
    bom_attachments: list[BomAttachment]


@dataclass(kw_only=True)
class Output:
    """Class for an item in Omnify"""

    desc: str
    status: int
    under_eco: bool
    rev_letter: str
    bill_of_materials: list[BomItem]


class BOMRetriever:
    # This is the main class
    def __init__(self, cnxn):
        self.cursor = cnxn.cursor()

    def check_item_existence(self, pn) -> bool:
        query = "SELECT Rev FROM EntryInfo WHERE PartNumber = ?"
        self.cursor.execute(query, (pn,))
        row = self.cursor.fetchone()
        return row is not None

    def get_item_info(self, rev_ID) -> OmnifyEntry:
        # Fetch the highest revision of an item with released status
        query = "SELECT Description,Status,UnderECO FROM EntryInfo WHERE Rev = ?"
        self.cursor.execute(query, (rev_ID,))
        item_row = self.cursor.fetchone()
        if not item_row:
            return  # TODO: return http error, something went wrong

        # Get revision letter matching the revision ID
        query = "SELECT Rev FROM Rev WHERE ID = ?"
        self.cursor.execute(query, (int(rev_ID),))
        rev_letter = self.cursor.fetchone()[0]

        return OmnifyEntry(
            desc=item_row[0],
            status=item_row[1],
            under_eco=item_row[2],
            rev_letter=rev_letter,
        )

    def load_toplevel_item(self, part_num) -> Output:
        # Error if attempting to load an empty part number
        if not part_num:
            # TODO: return http error, Part Number Required; please enter a part number
            return

        # Check if any the item exists, error out if not.
        existence = self.check_item_existence(part_num)
        if not existence:
            # TODO: return http error, Part Number Incorrect; Part number entered does not exist
            return

        # Fetch the highest revision of an item with released status
        query = "SELECT TOP 1 Rev FROM EntryInfo WHERE (Status=1 AND PartNumber = ?) ORDER BY Rev DESC"
        self.cursor.execute(query, (part_num,))
        row = self.cursor.fetchone()
        # Check if any the item is released, error out if not.
        if not row:
            # TODO: return http error, Unreleased Item; Part number entered is not released
            return
        toplevel_rev_id = row[0]

        # TODO: add tl_item to json output
        info = self.get_item_info(toplevel_rev_id)
        warnings = []

        # After confirming item is released, check if it is currently on an open ECO.
        # If so, warn the user but allow to proceed.
        if info.under_eco:
            warnings.append(
                "Item Under ECO: Part number is under an engineering change. Consult engineering before proceeding."
            )
        bom_attachments = self.load_bom(toplevel_rev_id)
        return Output(
            warnings=warnings,
            desc=info.desc,
            status=info.status,
            under_eco=info.under_eco,
            rev_letter=info.rev_letter,
            bom_attachments=bom_attachments,
        )

    def load_bom_attachments(self, toplevel_rev_id) -> BomItem:
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
                    "http://omnify.kissgroupllc.net/omnify5/Apps/OpenDocument.aspx?obj=0&docid="
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
            bom_attachments=attachments,
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


if __name__ == "__main__":
    if sys.version_info[0] < 3:
        print("Requires Python 3")
        sys.exit()

    # HACK: testing
    debug_pn = sys.argv[1]
    print(f"Loading toplevel item for {debug_pn}")

    # Open a connection to the Omnify database, create the cursor object for data retrieval
    with closing(
        pyodbc.connect(
            r"Driver=SQL Server;Server=TX01AS01;Database=omnify50;Trusted_Connection=yes;"
        )
    ) as cnxn:
        print("Starting server")
        retreiver = BOMRetriever(cnxn)
        result = retreiver.load_toplevel_item(debug_pn)
        print(jsonify(result))
        # TODO: Start server and call load_toplevel_item on request
