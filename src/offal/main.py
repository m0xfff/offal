from collections import Counter

import git
import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

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
