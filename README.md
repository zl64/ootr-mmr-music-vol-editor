# ootrs-mmrs-vol-editor
Simple .ootrs and .mmrs file volume editor

## Usage
> [!IMPORTANT]
> The `seq` folder must be in the same location as the `vol_editor.py` script in order for the script to work.

Open a terminal in the script's location, then use the following command:
```
python -m vol_editor <path to file> <volume>
```
#### Arguments

| Argument | Description |
| --- | --- |
| `<path to file>` | The path to the `.ootrs` or `.mmrs` file you want to edit. |
| `<volume>` | The new volume of the `.ootrs` or `.mmrs` file.<br>*The input must be decimal 0-255, hexadecimal 0x00-0xFF, or percent 0%-200%.* |

> [!TIP]
> You can drag and drop the file you want to edit onto the terminal to append its path to the terminal's text entry.