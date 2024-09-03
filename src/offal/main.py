import hashlib
import json
from collections import Counter
from pathlib import Path

import git
import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

import offal.commands.pin
import offal.commands.related
from offal.pinned import get_pinned_item

app = typer.Typer()
console = Console()

APP_NAME = "offal"


app.add_typer(offal.commands.pin.app, name="pin")
app.add_typer(offal.commands.related.app, name="related")


@app.command()
def status():
    pinned_file = get_pinned_item("file")

    if pinned_file:
        console.print("Pinned file:")
        if "#" in pinned_file:
            file_path, line_number = pinned_file.split("#")
            console.print(f"- {file_path} (line {line_number})")
        else:
            console.print(f"- {pinned_file}")
        console.print("")
        console.print("You can clear the pinned file using the 'offal pin --clear' command.")
    else:
        console.print("No file is currently pinned.")
        console.print("You can pin a file using the 'offal pin file' command.")
