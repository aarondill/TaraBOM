Errors/warnings:

- Users should get an error when trying to pull attachments for BOM items which aren’t released, and a warning for BOM items that are under an open ECO.

To-do:

- Hard-coded in some of the network locations.
  - Those locations should be replaced with variables, in case of server migrations or domain changes in the future.
  - Values to be set in a configuration file, style points added if the file can be modified via a web interface.
