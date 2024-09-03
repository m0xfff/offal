import typer
from typing_extensions import Annotated, Optional

from offal.pinned import remove_pinned_item, set_pinned_item

app = typer.Typer()

@app.callback(invoke_without_command=True)
def pin(
    file_path: Annotated[Optional[str], typer.Argument(help="The file path to pin (with optional line number, e.g., 'path/to/file.py#10')")] = None,
    clear: Annotated[bool, typer.Option("--clear", "-c", help="Clear the current file pin")] = False,
):
    if clear:
        remove_pinned_item("file")
        typer.echo("File pin cleared")
    elif file_path:
        if '#' in file_path:
            file_part, line_part = file_path.split('#')
            try:
                line_number = int(line_part)
                pin_value = f"{file_part}#{line_number}"
                set_pinned_item("file", pin_value)
                typer.echo(f"Pinned to file {file_part} at line {line_number}")
            except ValueError:
                typer.echo("Invalid line number. Using the entire path as is.")
                set_pinned_item("file", file_path)
                typer.echo(f"Pinned to file {file_path}")
        else:
            set_pinned_item("file", file_path)
            typer.echo(f"Pinned to file {file_path}")
    else:
        typer.echo("Please provide a file path to pin or use --clear option")
