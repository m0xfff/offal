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
from offal.pinned import get_pinned_item

app = typer.Typer()
console = Console()

APP_NAME = "offal"


app.add_typer(offal.commands.pin.app, name="pin")


@app.command()
def status():
    author = get_pinned_item("author")
    commit = get_pinned_item("commit")
    entity = get_pinned_item("entity")

    console.print("Pinned to: ")
    console.print(f"- Author: {author}")
    console.print(f"- Commit: {commit}")
    console.print(f"- Entity: {entity}")
    console.print("")
    if any([author, commit, entity]):
        console.print("You can clear the pinned items using the 'offal pin clear' command.")
    else:
        console.print("You can set the pinned items using the 'offal pin' command.")


@app.command()
def config():
    # app_dir = typer.get_app_dir(APP_NAME)
    config_path = get_config_path()

    with config_path.open("r") as file:
        data = json.load(file)

    for key, value in data.items():
        console.print(f"{key}: {value}")


def get_config_path():
    app_dir = typer.get_app_dir(APP_NAME)
    config_path = Path(app_dir) / "config.json"

    if not config_path.is_file():
        config_path.parent.mkdir(exist_ok=True, parents=True)
        config_path.write_text("{}")

    return config_path


def get_project_hash(repo: git.Repo):
    return hashlib.sha256(str(repo.working_tree_dir).encode()).hexdigest()


@app.command()
def summary():
    repo = git.Repo(search_parent_directories=True)
    commit_count = get_commit_count(repo)
    entity_count = get_entity_count(repo)
    author_count = get_author_count(repo)
    table = Table("Statistic", "Value")
    table.add_row("Number of Commits", str(commit_count))
    table.add_row("Number of Entities", str(entity_count))
    table.add_row("Number of Authors", str(author_count))
    console.print(table)


def get_author_count(repo: git.Repo) -> int:
    return len(repo.git.shortlog("-s", "-n", "--all", "--no-merges").splitlines())


def get_entity_count(repo: git.Repo) -> int:
    return len(repo.git.ls_files().splitlines())


def get_commit_count(repo: git.Repo) -> int:
    return repo.git.rev_list("--count", "HEAD")


@app.command()
def revisions():
    repo = git.Repo(search_parent_directories=True)
    files = repo.git.log("--pretty=format:", "--name-only").splitlines()
    revisions = Counter(file for file in files if file)
    top_5_revised = revisions.most_common(5)

    for file, count in top_5_revised:
        console.print(f"{file}, {count}")


@app.command()
def friends(
    file_path_with_line_number: str,
    branch: Annotated[str, typer.Option(help="Branch name")] = "",
    commit_hash: Annotated[str, typer.Option(help="Commit hash")] = "",
    author: Annotated[str, typer.Option(help="Author name")] = "",
):
    repo = git.Repo(search_parent_directories=True)

    file_path, line_number = extract_line_number(file_path_with_line_number)

    if line_number is None:
        line_number = get_most_recent_change_line(repo, file_path)

    commit_hash = get_commit_for_line(repo, file_path, line_number)

    files_changed = get_files_changed_in_commit(repo, commit_hash)

    for file in files_changed:
        console.print(f"{file}, {get_revision_count_for_file(repo, file)}")


def get_commit_for_line(repo, file_path, line_number):
    # Get the commit hash that last modified the given line number in the file
    blame = repo.git.blame("-L", f"{line_number},{line_number}", "--porcelain", file_path)
    commit_hash = blame.split()[0]
    return commit_hash


def get_files_changed_in_commit(repo, commit_hash):
    # Get the files changed in the commit
    files_changed = repo.git.show("--name-only", "--pretty=format:", commit_hash).splitlines()
    return files_changed


def extract_line_number(file_path_with_line_number):
    if "#" in file_path_with_line_number:
        file_path, line_str = file_path_with_line_number.split("#", 1)
        line_number = int(line_str) if line_str.isdigit() else 1
    else:
        file_path = file_path_with_line_number
        line_number = None

    return file_path, line_number


def get_most_recent_change_line(repo, file_path):
    blame_output = repo.git.blame("-L", "1,100000", "--porcelain", file_path).splitlines()

    most_recent_commit = None
    most_recent_line = None

    for i in range(0, len(blame_output), 12):  # Each block of blame output for a line is 12 lines long
        commit_hash = blame_output[i].split()[0]
        line_number = i // 12 + 1

        if (
            most_recent_commit is None
            or repo.git.show(f"{commit_hash}").splitlines()[4] > repo.git.show(f"{most_recent_commit}").splitlines()[4]
        ):
            most_recent_commit = commit_hash
            most_recent_line = line_number

    return most_recent_line if most_recent_line is not None else 1


def get_revision_count_for_file(repo, file_path, branch_name=None, commit_hash="HEAD", author=None):
    command = ["--count"]

    if branch_name:
        command.append(branch_name)
    else:
        command.append(commit_hash)

    if author:
        command.append(f"--author={author}")

    command.extend(["--", file_path])

    return repo.git.rev_list(*command)
