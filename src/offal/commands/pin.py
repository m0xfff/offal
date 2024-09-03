import typer
from typing_extensions import Annotated, Optional

from offal.pinned import remove_pinned_item, set_pinned_item

app = typer.Typer()

@app.callback(invoke_without_command=True)
def pin(
    file_path: Annotated[Optional[str], typer.Argument(help="The file path to pin")] = None,
    line_number: Annotated[Optional[int], typer.Option(help="The line number to pin")] = None,
    clear: Annotated[bool, typer.Option("--clear", "-c", help="Clear the current file pin")] = False,
):
    if clear:
        remove_pinned_item("file")
        typer.echo("File pin cleared")
    elif file_path:
        if line_number is not None:
            pin_value = f"{file_path}#{line_number}"
            set_pinned_item("file", pin_value)
            typer.echo(f"Pinned to file {file_path} at line {line_number}")
        else:
            set_pinned_item("file", file_path)
            typer.echo(f"Pinned to file {file_path}")
    else:
        typer.echo("Please provide a file path to pin or use --clear option")
