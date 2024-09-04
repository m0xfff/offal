import typer
from typing import Optional, List, Tuple, Union
from dataclasses import dataclass
from functools import lru_cache
from rich.console import Console
from rich.syntax import Syntax
import git
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Commit
from offal.pinned import get_pinned_item
import re
from datetime import datetime, timezone

app = typer.Typer()
console = Console()


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


def get_revisions(repo: Repo, file_path: str, line_number: Optional[int] = None, reverse: bool = False, author: Optional[str] = None, before: Optional[datetime] = None, after: Optional[datetime] = None) -> List[Commit]:
    try:
        if line_number:
            blame_result = repo.blame("HEAD", file_path, L=f"{line_number},{line_number}")
            if not blame_result:
                raise ValueError(f"No blame information found for line {line_number} in file {file_path}")

            # Extract the first item from blame_result
            blame_item = next(iter(blame_result), None)
            if not blame_item:
                raise ValueError(f"No blame information found for line {line_number} in file {file_path}")

            if isinstance(blame_item, (tuple, list)) and len(blame_item) >= 1:
                commit = blame_item[0]
            else:
                # If it's not a tuple/list, it might be a BlameEntry object
                commit = getattr(blame_item, 'commit', None)

            if not isinstance(commit, Commit):
                raise TypeError(f"Expected Commit object, got {type(commit)}")

            revisions = []
            current_commit: Commit = commit

            while True:
                if not current_commit.parents:
                    revisions.append(current_commit)
                    break

                parent_commit = current_commit.parents[0]
                diffs = current_commit.diff(parent_commit, paths=file_path, create_patch=True)

                line_modified = False
                for diff in diffs:
                    if diff.a_path == file_path:
                        diff_lines = diff.diff.decode("utf-8").splitlines()
                        line_offset = 0
                        for line in diff_lines:
                            if line.startswith("+"):
                                line_offset += 1
                            elif line.startswith("-"):
                                line_offset -= 1
                                if line_offset + line_number == 0:
                                    line_modified = True
                            elif not line.startswith("@"):
                                if line_offset < 0:
                                    line_number += 1
                                elif line_offset > 0:
                                    line_number -= 1

                if line_modified:
                    revisions.append(current_commit)

                current_commit = parent_commit
            else:
                raise NoCommitHistoryError(f"No commit history found for line {line_number} in file {file_path}")
        else:
            revisions = list(repo.iter_commits(paths=file_path))

        if author:
            revisions = [
                commit for commit in revisions
                if author.lower() in (commit.author.name.lower() if commit.author.name else '') or
                   author.lower() in (commit.author.email.lower() if commit.author.email else '')
            ]

        if before or after:
            revisions = [
                commit for commit in revisions
                if (not before or commit.committed_datetime <= before) and
                   (not after or commit.committed_datetime >= after)
            ]

        if reverse:
            revisions.reverse()
        return revisions
    except GitCommandError as e:
        if "no such path" in str(e).lower():
            raise FileNotFoundError(f"The file '{file_path}' does not exist in the repository.")
        raise OffalError(f"An error occurred while fetching commit history: {str(e)}")


def print_commits(commits: List[Commit], file_path: str, line_number: Optional[int] = None, reverse: bool = False):
    console.print(f"[bold]Commit History for {file_path}{f' (line {line_number})' if line_number else ''}:[/bold]\n")
    for commit in commits:
        console.print(
            f"[yellow]{commit.hexsha[:7]}[/yellow] {commit.committed_datetime.strftime('%Y-%m-%d')} [green]{commit.author.name}[/green] {commit.message.strip()}"
        )

    if line_number and commits:
        if reverse:
            console.print(f"\nLine {line_number} was first introduced in commit {commits[-1].hexsha[:7]}")
        else:
            console.print(f"\nLine {line_number} was last modified in commit {commits[0].hexsha[:7]}")


def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise typer.BadParameter("Date must be in the format YYYY-MM-DD")


@app.callback(invoke_without_command=True)
def history(
    ctx: typer.Context,
    file_path: str = typer.Option(None, "--file", "-f", help="Path to the file to show history for"),
    line_number: int = typer.Option(None, "--line", "-L", help="Line number to show history for"),
    ignore_line_number: bool = typer.Option(
        False, "--ignore-line-number", "-i", help="Ignore the pinned line number and show full file history"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Limit the number of commits shown"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="List commits from oldest to latest"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Show commits by a specific author"),
    before: Optional[str] = typer.Option(None, "--before", help="Show revisions before a given date (YYYY-MM-DD)"),
    after: Optional[str] = typer.Option(None, "--after", help="Show revisions after a given date (YYYY-MM-DD)"),
):
    """Show commit history for the pinned file or a specified file."""
    try:
        file_path, pinned_line = get_file_info(file_path)
        use_line_number = line_number or (None if ignore_line_number else pinned_line)

        try:
            before_date = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc) if before else None
            after_date = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=timezone.utc) if after else None
        except ValueError:
            console.print("Error: Date must be in the format YYYY-MM-DD")
            return

        repo = get_repo()
        commits = get_revisions(repo, file_path, use_line_number, reverse, author, before_date, after_date)

        if author and not commits:
            console.print(f"No commits found for author: {author}")
            return

        if before or after:
            date_info = []
            if after:
                date_info.append(f"after {after}")
            if before:
                date_info.append(f"before {before}")
            console.print(f"Showing commits {' and '.join(date_info)}")

        if not commits:
            console.print("No commits found matching the specified criteria.")
            return

        print_commits(commits[:limit], file_path, use_line_number, reverse)

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
