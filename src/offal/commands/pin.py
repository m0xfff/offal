import typer
from typing_extensions import Annotated

from offal.pinned import clear_pinned_items, remove_pinned_item, set_pinned_item

app = typer.Typer()


@app.command()
def author(author: Annotated[str, typer.Argument(help="The name of the author")]):
    set_pinned_item("author", author)
    typer.echo(f"Author pinned to {author}")


@app.command()
def commit(commit: Annotated[str, typer.Argument(help="The commit hash")]):
    set_pinned_item("commit", commit)
    typer.echo(f"Commit pinned to {commit}")


@app.command()
def entity(entity: Annotated[str, typer.Argument(help="The entity to pin")]):
    set_pinned_item("entity", entity)
    typer.echo(f"Entity pinned to {entity}")


@app.command()
def clear(pin: Annotated[str, typer.Argument(help="The pinned item to clear")]):
    remove_pinned_item(pin)
    typer.echo(f"{pin} pin cleared")


@app.command()
def clear_all():
    clear_pinned_items()
