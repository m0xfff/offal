import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from git import Repo
from collections import Counter
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
        commits = list(repo.iter_commits(paths=file_path))

        if not commits:
            console.print(f"No commit history found for {file_path}")
            return

        file_changes = Counter()
        commit_info = []

        for commit in commits:
            changed_files = get_changed_files(commit)
            file_changes.update(changed_files)

            try:
                if line_number is not None:
                    is_modified = is_line_modified(commit, file_path, line_number)
                else:
                    is_modified = "N/A"
            except Exception:
                is_modified = "Error"

            commit_info.append({
                "hash": commit.hexsha[:7],
                "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "message": commit.message.strip().split('\n')[0],
                "files": changed_files,
                "modified_line": is_modified
            })

        # Display summary table
        summary_table = Table(title="Summary of Related File Changes")
        summary_table.add_column("File", style="cyan")
        summary_table.add_column("Times Modified", justify="right", style="magenta")

        for file, count in file_changes.most_common():
            summary_table.add_row(file, str(count))

        console.print(summary_table)
        console.print()

        # Display detailed commit information
        commit_table = Table(title="Detailed Commit Information")
        commit_table.add_column("Commit", style="yellow")
        commit_table.add_column("Date", style="green")
        commit_table.add_column("Message", style="cyan")
        commit_table.add_column("Files Changed", style="magenta")
        if line_number is not None:
            commit_table.add_column("Modified Line", style="red")

        for info in reversed(commit_info):  # Reverse to show oldest first
            row = [
                info["hash"],
                info["date"],
                info["message"],
                ", ".join(info["files"])
            ]
            if line_number is not None:
                row.append(str(info["modified_line"]))
            commit_table.add_row(*row)

        console.print(commit_table)

    except Exception as e:
        console.print(f"An error occurred: {str(e)}")
        console.print(f"Error details: {type(e).__name__} at line {e.__traceback__.tb_lineno}")

def is_line_modified(commit, file_path, target_line_number):
    if not commit.parents:
        return True  # Initial commit, consider it as modifying all lines

    diffs = commit.parents[0].diff(commit, paths=file_path, create_patch=True)
    if not diffs:
        return False

    diff = diffs[0]
    patch = diff.diff.decode('utf-8')

    current_line = 1
    for line in patch.split('\n'):
        if line.startswith('@@'):
            # Parse the hunk header
            hunk_info = line.split('@@')[1].strip()
            try:
                new_start = int(hunk_info.split('+')[1].split(',')[0])
                current_line = new_start
            except IndexError:
                continue
        elif not line.startswith('-'):
            if current_line == target_line_number:
                return not line.startswith(' ')  # Modified if it's a '+' line
            current_line += 1

    return False

def get_changed_files(commit):
    if not commit.parents:
        return [item.path for item in commit.tree.traverse() if item.type == 'blob']
    else:
        return list(commit.stats.files.keys())

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
