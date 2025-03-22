A python project to get data from a specific database.  
If you don't know what this is, it's not for you.

Executables are available in the releases section.

All dependencies are listed in the requirements.txt file.

Notes:

- If the production order part number being retrieved has _no released version_, the client receives an error.
- If the production order part number is currently under an open engineering change, the user is allowed to proceed but a warning is attached that they should contact engineering first.

Still to do:

- I didn’t take the time to put the same warning and error triggers in the BOM, so this demo does allow retrieval of attachments for all items in the BOM.
  - For the Lynq code though, they should have the same checks. Users should get an error when trying to pull attachments for BOM items which aren’t released, and a warning for BOM items that are under an open ECO.
