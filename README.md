A python project to get data from a specific database.  
If you don't know what this is, it's not for you.

Executables are available in the releases section.

All dependencies are listed in the `requirements.txt` file.

Notes:

- If the production order part number being retrieved has _no released version_, the client receives an error.
- If the production order part number is currently under an open engineering change, the user is allowed to proceed but a warning is attached that they should contact engineering first.

# Config (Mandatory):

The configuration file is named `bom_retreiver.ini` can be located in various places.

In order of priority:  
All of these will be loaded, but higher priority ones will override lower priority ones.

1. The config file in the same directory as the executable.
2. The config file in the current working directory.
3. Depending on OS:
   - Linux: `$XDG_CONFIG_DIR/bom_retriever/bom_retriever.ini` or `~/.config/bom_retriever/bom_retriever.ini`
   - Windows: `%USERPROFILE%\AppData\Local\bom_retriever\bom_retriever.ini`
   - macOS: `~/Library/Application Support/bom_retriever/bom_retriever.ini`

Example file:

```ini
[config]
port = 8080
server = "<server name>"
db = "<database name>"
omnify_url = "http://<some url>/omnify5"
```
