import sys
import pyodbc
from contextlib import closing
from dataclasses import dataclass


@dataclass(kw_only=True)
class OmnifyEntry:
    """Class for an item in Omnify"""

    item_desc: str
    item_status: int
    item_under_eco: bool
    rev_letter: str


class BOMRetriever:
    # This is the main class
    def __init__(self):
        self.cursor = self.cnxn.cursor()

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
            item_desc=item_row[0],
            item_status=item_row[1],
            item_under_eco=item_row[2],
            rev_letter=rev_letter,
        )

    def load_toplevel_item(self, part_num) -> str:
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
        tl_item = self.get_item_info(toplevel_rev_id)

        # After confirming item is released, check if it is currently on an open ECO.
        # If so, warn the user but allow to proceed.
        if tl_item.item_under_eco:
            # TODO: add to json output, Item Under ECO; Part number is under an engineering change. Consult engineering before proceeding.
            print("Warning: Item is currently under an ECO")
        # TODO: handle load_bom
        # TODO: return json

    def load_bom(self, toplevel_rev_id):
        query = "SELECT ItemNum,ItemRevID,ItemRevStr,ItemPN,ItemDesc,ItemStatus,QtyStr FROM PartsList WHERE RevID = ? ORDER BY ItemNum ASC"
        self.cursor.execute(query, (toplevel_rev_id,))
        rows = self.cursor.fetchall()
        for row in rows:
            print(row)  # TODO: json output the row

            # Get ID's and file names for all "Public" (VaultID=0) attachments for the current BOM item, build a list of Omnify retrieval links
            attachment_query = (
                "SELECT ID,FileURL FROM Attachment WHERE (VaultID=0 AND RevID = ?)"
            )
            self.cursor.execute(attachment_query, (row[1],))
            while attachment_row := self.cursor.fetchone():
                attachment_link = (
                    "http://omnify.kissgroupllc.net/omnify5/Apps/OpenDocument.aspx?obj=0&docid="
                    + str(attachment_row[0])
                )
                # TODO: add to json output, link: attachment_link, file_name: attachment_row[1]
                print(attachment_link)


if __name__ == "__main__":
    if sys.version_info[0] < 3:
        print("Requires Python 3")
        sys.exit()
    # Open a connection to the Omnify database, create the cursor object for data retrieval
    with closing(
        pyodbc.connect(
            r"Driver=SQL Server;Server=TX01AS01;Database=omnify50;Trusted_Connection=yes;"
        )
    ) as cnxn:
        retreiver = BOMRetriever()
        print("Starting server")
        # TODO: Start server and call load_toplevel_item on request
