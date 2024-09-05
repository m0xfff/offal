import sys
import termios
import tty
from datetime import datetime, timezone
from typing import Optional, List
import git
from git import Repo, Commit, GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from dataclasses import dataclass
from functools import lru_cache
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.syntax import Syntax
import typer

from offal.pinned import get_pinned_item

app = typer.Typer()
console = Console()


@dataclass
class CommitDetails:
    commit: Commit
    summary: str
    author_name: str
    author_email: str
    date: datetime


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


def get_revisions(
    repo: Repo,
    file_path: str,
    line_number: Optional[int] = None,
    reverse: bool = False,
    author: Optional[str] = None,
    before: Optional[datetime] = None,
    after: Optional[datetime] = None,
) -> List[Commit]:
    if line_number:
        revisions = get_line_specific_revisions(repo, file_path, line_number)
    else:
        revisions = get_file_revisions(repo, file_path)

    revisions = filter_revisions(revisions, author, before, after)

    if reverse:
        revisions.reverse()

    return revisions

def get_line_specific_revisions(repo: Repo, file_path: str, start_line: int, end_line: Optional[int] = None) -> List[Commit]:
    try:
        end_line = end_line or start_line
        # limit_arg = f'-n {limit}'

        output = repo.git.log(f'-L {start_line},{end_line}:{file_path}', '--no-patch', '--pretty=format:"%H"')
        commit_hashes = output.strip().split("\n")
        hashes = [hash.strip('"') for hash in commit_hashes]
        return [repo.commit(hash) for hash in hashes]
    except GitCommandError as e:
        if "no such path" in str(e).lower():
            raise FileNotFoundError(f"The file '{file_path}' does not exist in the repository.")
        raise OffalError(f"An error occurred while fetching commit history: {str(e)}")


def get_file_revisions(repo: Repo, file_path: str) -> List[Commit]:
    try:
        return list(repo.iter_commits(paths=file_path))
    except GitCommandError as e:
        if "no such path" in str(e).lower():
            raise FileNotFoundError(f"The file '{file_path}' does not exist in the repository.")
        raise OffalError(f"An error occurred while fetching commit history: {str(e)}")


def filter_revisions(
    revisions: List[Commit], author: Optional[str], before: Optional[datetime], after: Optional[datetime]
) -> List[Commit]:
    if author:
        revisions = filter_by_author(revisions, author)
    if before or after:
        revisions = filter_by_date(revisions, before, after)
    return revisions


def get_blame_item(repo: Repo, file_path: str, line_number: int):
    blame_result = repo.blame("HEAD", file_path, L=f"{line_number},{line_number}")
    if not blame_result:
        raise ValueError(f"No blame information found for line {line_number} in file {file_path}")
    return next(iter(blame_result))


def extract_commit_from_blame(blame_item) -> Commit:
    if isinstance(blame_item, (tuple, list)) and len(blame_item) >= 1:
        commit = blame_item[0]
    else:
        commit = getattr(blame_item, "commit", None)
    if not isinstance(commit, Commit):
        raise TypeError(f"Expected Commit object, got {type(commit)}")
    return commit


def trace_line_history(repo: Repo, file_path: str, line_number: int, initial_commit: Commit) -> List[Commit]:
    revisions = []
    current_commit = initial_commit
    while True:
        if not current_commit.parents:
            revisions.append(current_commit)
            break
        parent_commit = current_commit.parents[0]
        if line_modified(repo, file_path, line_number, current_commit, parent_commit):
            revisions.append(current_commit)
        current_commit = parent_commit
    return revisions


def line_modified(repo: Repo, file_path: str, line_number: int, commit: Commit, parent_commit: Commit) -> bool:
    diffs = commit.diff(parent_commit, paths=file_path, create_patch=True)
    for diff in diffs:
        if diff.a_path == file_path:
            return check_line_in_diff(diff, line_number)
    return False


def check_line_in_diff(diff, line_number: int) -> bool:
    diff_lines = diff.diff.decode("utf-8").splitlines()
    line_offset = 0
    for line in diff_lines:
        if line.startswith("+"):
            line_offset += 1
        elif line.startswith("-"):
            line_offset -= 1
            if line_offset + line_number == 0:
                return True
        elif not line.startswith("@"):
            if line_offset < 0:
                line_number += 1
            elif line_offset > 0:
                line_number -= 1
    return False


def filter_by_author(revisions: List[Commit], author: str) -> List[Commit]:
    return [
        commit
        for commit in revisions
        if author.lower() in (commit.author.name.lower() if commit.author.name else "")
        or author.lower() in (commit.author.email.lower() if commit.author.email else "")
    ]


def filter_by_date(revisions: List[Commit], before: Optional[datetime], after: Optional[datetime]) -> List[Commit]:
    return [
        commit
        for commit in revisions
        if (not before or commit.committed_datetime <= before) and (not after or commit.committed_datetime >= after)
    ]


def print_commits(commits: List[Commit], file_path: str, line_number: Optional[int] = None, reverse: bool = False):
    console.print(f"[bold]Commit History for {file_path}{f' (line {line_number})' if line_number else ''}:[/bold]\n")
    for commit in commits:
        # Get only the first line of the commit message
        first_line = commit.message.strip().splitlines()[0]

        console.print(
            f"[yellow]{commit.hexsha[:7]}[/yellow] {commit.committed_datetime.strftime('%Y-%m-%d')} [green]{commit.author.name}[/green] {first_line}"
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
    traverse: bool = typer.Option(False, "--traverse", "-t", help="Traverse each revision in detail"),
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

        if traverse:
            traverse_commits(commits, file_path, use_line_number)
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


def traverse_commits(commits: List[Commit], file_path: str, line_number: Optional[int] = None):
    index = 0
    while index < len(commits):
        commit = commits[index]
        display_commit_details(commit, file_path, line_number)
        console.print("\nPress [bold yellow]'c'[/bold yellow] to continue, [bold yellow]'b'[/bold yellow] to go back, [bold red]'q'[/bold red] to quit.")
        user_input = get_user_input()

        if user_input == 'q':
            break
        elif user_input == 'c':
            index += 1
        elif user_input == 'b' and index > 0:
            index -= 1
    console.print("Traversal finished.")

def display_commit_details(commit: Commit, file_path: str, line_number: Optional[int] = None):
    commit_details = Text()
    commit_details.append(f"Commit: {commit.hexsha}\n", style="bold blue")

    # Explicitly ensure string conversion
    author_name = commit.author.name or 'Unknown'
    author_email = commit.author.email or 'Unknown'
    commit_message = commit.message

    if isinstance(commit_message, bytes):
        commit_message = commit_message.decode('utf-8')
    commit_message = commit_message or ''

    commit_details.append(f"Author: {author_name} <{author_email}>\n", style="bold green")
    commit_details.append(f"Date: {commit.committed_datetime}\n\n")
    commit_details.append(commit_message, style="yellow")

    console.print(Panel(commit_details, title="Commit Details"))

    # Fetch and display diff
    diff = get_commit_diff(commit, file_path)
    if diff:
        # Ensure proper panel rendering with fixed size
        syntax = Syntax(diff, "diff", theme="material", background_color="default")
        diff_panel = Panel(syntax, title="Diff", border_style="white", expand=True)
        console.print(diff_panel)

    # Fetch and display list of files changed in the commit
    files_changed = get_files_changed(commit)
    if files_changed:
        files_panel = Panel(Text(files_changed), title="Files Changed")
        console.print(files_panel)

    console.print("\n")


def get_commit_diff(commit: Commit, file_path: str) -> str:
    try:
        diff_output = commit.repo.git.diff('--unified=0', f'{commit.hexsha}^!', file_path)
        if not diff_output:
            return 'No diff available'
        return add_line_numbers_to_diff(diff_output)
    except GitCommandError as e:
        return f"Error obtaining diff: {str(e)}"


def add_line_numbers_to_diff(diff_output: str) -> str:
    lines = diff_output.split('\n')
    new_lines = []
    old_line_number = 0
    new_line_number = 0

    for line in lines:
        if line.startswith('@@'):
            # Extract line number info from the chunk header
            parts = line.split()
            if len(parts) > 2:
                old_line_info = parts[1]
                new_line_info = parts[2]
                try:
                    # Extract starting line numbers
                    old_line_number = abs(int(old_line_info.split(',')[0].lstrip('-')))
                    new_line_number = abs(int(new_line_info.split(',')[0].lstrip('+')))
                except ValueError:
                    pass
            new_lines.append(line)
        elif line.startswith('+'):
            new_lines.append(f"{new_line_number:5}: {line}")
            new_line_number += 1
        elif line.startswith('-'):
            new_lines.append(f"{old_line_number:5}: {line}")
            old_line_number += 1
        else:
            new_lines.append(line)
            if line != '\\ No newline at end of file':
                old_line_number += 1
                new_line_number += 1

    return '\n'.join(new_lines)


def get_files_changed(commit: Commit) -> str:
    try:
        # Convert each key to a string
        file_paths = [str(path) for path in commit.stats.files.keys()]
        return "\n".join(file_paths)
    except Exception as e:
        return f"Error obtaining file list: {str(e)}"


def get_user_input():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch
