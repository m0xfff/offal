import typer
from typing import Optional, List
from dataclasses import dataclass
from functools import lru_cache
from rich.console import Console
from rich.syntax import Syntax
import git
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from offal.pinned import get_pinned_item
import re

app = typer.Typer()
console = Console()


@dataclass
class Commit:
    hash: str
    date: str
    author: str
    message: str


class OffalError(Exception):
    """Base exception for Offal-specific errors."""


class FileNotFoundError(OffalError):
    """Raised when a file is not found in the repository."""


class NoCommitHistoryError(OffalError):
    """Raised when no commit history is found."""


@lru_cache(maxsize=32)
def get_repo():
    try:
        return Repo(search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise OffalError("Not a valid git repository.")


def parse_log_output(log_output: str) -> List[Commit]:
    commits = []
    pattern = r"(\w+)\s+(\d{4}-\d{2}-\d{2})\s+<(.+?)>\s+(.+)$"
    for line in log_output.splitlines():
        match = re.match(pattern, line)
        if match:
            hash, date, author, message = match.groups()
            commits.append(Commit(hash=hash[:7], date=date, author=author, message=message))
        else:
            console.print(f"Warning: Unable to parse commit line: {line}")
    return commits


def get_file_history(repo: Repo, file_path: str, line_number: Optional[int] = None) -> List[Commit]:
    try:
        log_format = "%H %ad <%an> %s"  # Use <%an> to wrap the author name
        if line_number:
            log_output = repo.git.log(
                L=f"{line_number},{line_number}:{file_path}", format=log_format, date="short", no_patch=True
            )
        else:
            log_output = repo.git.log(file_path, format=log_format, date="short", no_patch=True)

        commits = parse_log_output(log_output)
        if not commits:
            raise NoCommitHistoryError(
                f"No commit history found for the specified file{' and line' if line_number else ''}."
            )
        return commits
    except GitCommandError as e:
        if "no such path" in str(e).lower():
            raise FileNotFoundError(f"The file '{file_path}' does not exist in the repository.")
        raise OffalError(f"An error occurred while fetching commit history: {str(e)}")


def print_commits(commits: List[Commit], file_path: str, line_number: Optional[int] = None):
    console.print(f"[bold]Commit History for {file_path}{f' (line {line_number})' if line_number else ''}:[/bold]\n")
    for commit in commits:
        console.print(f"[yellow]{commit.hash}[/yellow] {commit.date} [green]{commit.author}[/green] {commit.message}")


@app.callback(invoke_without_command=True)
def history(
    ctx: typer.Context,
    file_path: str = typer.Option(None, "--file", "-f", help="Path to the file to show history for"),
    line_number: int = typer.Option(None, "--line", "-L", help="Line number to show history for"),
    ignore_line_number: bool = typer.Option(
        False, "--ignore-line-number", "-i", help="Ignore the pinned line number and show full file history"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Limit the number of commits shown"),
):
    """Show commit history for the pinned file or a specified file."""
    try:
        file_path, pinned_line = get_file_info(file_path)
        use_line_number = line_number or (None if ignore_line_number else pinned_line)

        repo = get_repo()
        commits = get_file_history(repo, file_path, use_line_number)
        print_commits(commits[:limit], file_path, use_line_number)

        if len(commits) > limit:
            console.print(f"\nShowing {limit} of {len(commits)} commits. Use --limit option to see more.")

        if pinned_line and not use_line_number and not ignore_line_number:
            console.print(
                f"\nNote: The file is pinned to line {pinned_line}. Use '--line {pinned_line}' to see line-specific history or '--ignore-line-number' to see full file history."
            )

    except OffalError as e:
        console.print(f"Error: {str(e)}")
    except Exception as e:
        console.print(f"An unexpected error occurred: {str(e)}")
        if e.__traceback__:
            console.print(f"Error details: {type(e).__name__} at line {e.__traceback__.tb_lineno}")


def get_file_info(file_path: Optional[str]) -> tuple[str, Optional[int]]:
    if not file_path:
        pinned_item = get_pinned_item("file")
        if not pinned_item:
            raise OffalError(
                "No file is currently pinned. Use 'offal pin file' to pin a file or provide a file path with --file option."
            )
        if isinstance(pinned_item, str) and "#" in pinned_item:
            file_path, pinned_line = pinned_item.split("#")
            return file_path, int(pinned_line)
        if isinstance(pinned_item, str):
            return pinned_item, None
        raise OffalError("Invalid pinned item type")
    return file_path, None
