import git
import typer
from rich.console import Console
from rich.table import Table
from collections import Counter

app = typer.Typer()
console = Console()


@app.command()
def status():
    repo = git.Repo(search_parent_directories=True)
    commit_count = str(repo.git.rev_list("--count", "HEAD"))
    entity_count = str(len(repo.git.ls_files().splitlines()))
    author_count = str(len(repo.git.shortlog("-s", "-n", "--all", "--no-merges").splitlines()))
    table = Table("Statistic", "Value")
    table.add_row("Number of Commits", str(commit_count))
    table.add_row("Number of Entities", str(entity_count))
    table.add_row("Number of Authors", str(author_count))
    console.print(table)

@app.command()
def revisions():
    repo = git.Repo(search_parent_directories=True)
    files = repo.git.log('--pretty=format:', '--name-only').splitlines()
    revisions = Counter(file for file in files if file)
    top_5_revised = revisions.most_common(5)

    for file, count in top_5_revised:
        console.print(f"{file}, {count}")
