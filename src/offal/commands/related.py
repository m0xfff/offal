import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from git import Repo
from offal.pinned import get_pinned_item

app = typer.Typer()
console = Console()

@app.callback(invoke_without_command=True)
def related():
    pinned_file = get_pinned_item("file")

    if not pinned_file:
        console.print("No file is currently pinned. Use 'offal pin file' to pin a file first.")
        return

    repo = Repo(search_parent_directories=True)

    if "#" in pinned_file:
        file_path, line_number = pinned_file.split("#")
        line_number = int(line_number)
    else:
        file_path, line_number = pinned_file, None

    show_related_files(repo, file_path, line_number)

def show_related_files(repo, file_path, line_number=None):
    try:
        if line_number:
            commit = find_commit_for_line(repo, file_path, line_number)
        else:
            commit = next(repo.iter_commits(paths=file_path, max_count=1))

        if not commit:
            console.print(f"No commit found modifying line {line_number} in {file_path}")
            return

        console.print(f"Commit: {commit.hexsha}")
        console.print(f"Date: {commit.committed_datetime}")
        console.print(f"Message: {commit.message.strip()}")
        console.print()

        table = Table(title=f"Files changed in the same commit")
        table.add_column("File", style="cyan")
        table.add_column("Status", style="green")

        if not commit.parents:
            # This is the initial commit
            for file in commit.tree.traverse():
                if file.type == 'blob':  # It's a file
                    table.add_row(file.path, "Added")
        else:
            for file, stats in commit.stats.files.items():
                status = "Modified"
                if file not in repo.head.commit.tree:
                    status = "Deleted"
                elif file not in commit.parents[0].tree:
                    status = "Added"
                table.add_row(file, status)

        console.print(table)

    except StopIteration:
        console.print(f"No commit history found for {file_path}")

def find_commit_for_line(repo, file_path, line_number):
    for commit in repo.iter_commits(paths=file_path):
        if not commit.parents:
            # This is the initial commit
            return commit

        diffs = commit.parents[0].diff(commit, paths=file_path, create_patch=True)
        if not diffs:
            continue

        diff = diffs[0]
        if diff.a_path == file_path:
            for hunk in diff.diff.decode('utf-8').split('\n@@')[1:]:
                hunk_header = hunk.split('\n')[0]
                old_start = int(hunk_header.split('-')[1].split(',')[0])
                if old_start <= line_number < old_start + len(hunk.split('\n')) - 1:
                    return commit
    return None

def show_related_lines(repo, file_path, line_number, context=5):
    try:
        commit = next(repo.iter_commits(paths=file_path, max_count=1))
        console.print(f"Last commit for {file_path}: {commit.hexsha}")

        file_content = commit.tree[file_path].data_stream.read().decode('utf-8')
        lines = file_content.splitlines()

        start_line = max(1, line_number - context)
        end_line = min(len(lines), line_number + context)

        display_lines = lines[start_line-1:end_line]
        line_numbers = range(start_line, end_line + 1)

        numbered_lines = [f"{num}: {line}" for num, line in zip(line_numbers, display_lines)]

        highlighted_lines = [
            f"[bold cyan]{line}[/bold cyan]" if num == line_number else line
            for num, line in zip(line_numbers, numbered_lines)
        ]

        console.print(f"\n[bold]Context around line {line_number} in {file_path}:[/bold]")
        syntax = Syntax("\n".join(highlighted_lines), "python", line_numbers=False)
        console.print(syntax)

    except StopIteration:
        console.print(f"No commit history found for {file_path}")
    except KeyError:
        console.print(f"File {file_path} not found in the last commit")
