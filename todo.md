errors/warnings:

1. If the production order part number being retrieved has no released version, the user receives an error and is not allowed to proceed.
2. If the production order part number is currently under an open engineering change, the user is allowed to proceed but is given a warning that they should contact engineering first.
3. I didn’t take the time to put the same warning and error triggers in the BOM, so this demo does allow retrieval of attachments for all items in the BOM. For the Lynq code though, they should have the same checks. Users should get an error when trying to pull attachments for BOM items which aren’t released, and a warning for BOM items that are under an open ECO.

todo:
One thing to pass along- this was a quick & dirty demonstration, and in the process I hard-coded in some of the network locations.
Those locations should be replaced with variables, in case of server migrations or domain changes in the future. Values to be set in a configuration file, style points added if the file can be modified via a web interface.
