# offal test

[![Rye](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/rye/main/artwork/badge.json)](https://rye.astral.sh)

*offal* is a powerful command-line tool designed to help developers navigate and analyze their codebase efficiently. Inspired by Adam Tornhill's "Your Code as a Crime Scene", offal provides insights into your repository's history, file changes, and commit patterns, making it easier to isolate hard-to-reproduce bugs and understand code evolution.

> **Note**: offal is currently in the early stages of development. Please report any issues or feature requests on the [GitHub repository](https://github.com/m0xfff/offal).

## Features

- **Repository Summary**: Get an overview of your repository's revision history and lifespan.
- **File Change Analysis**: List files in the repository with their change frequency.
- **File Pinning**: Keep track of specific files or lines for focused analysis.
- **Commit History**: Explore the commit history of files with various filtering options.
- **Detailed Revision Traversal**: Dive deep into individual commits and their changes.

## Installation

To install offal, use the following command:

```bash
pipx install git+https://github.com/m0xfff/offal.git
```

## Usage

Here are the main commands and their functionalities:

### Summary

Get an overview of your repository:

```bash
offal summary
```

### Pin

Pin a file for focused analysis:

```bash
offal pin path/to/file.py
offal pin path/to/file.py#10  # Pin to a specific line
offal pin --clear  # Clear the current pin
```

### Status

Check the current status of offal:

```bash
offal status
```

### History

View commit history for the pinned file or a specified file:

```bash
offal history
offal history --file path/to/file.py
```

Options:
- `--limit` or `-l`: Control the number of commits returned
- `--reverse` or `-r`: List commits from oldest to latest
- `--author` or `-a`: Show commits by a specific author
- `--after`: Show revisions after a given date (YYYY-MM-DD)
- `--before`: Show revisions before a given date (YYYY-MM-DD)
- `--file` or `-f`: Provide a specific file for revision listing
- `--line` or `-L`: Provide a specific line number for revision listing
- `--ignore-line-number` or `-i`: Ignore the pinned line number
- `--summary` or `-s`: Show a summary of revisions
- `--traverse` or `-t`: Traverse each revision in detail
- `--files-changed`: List all changed files across commits

Note: `--summary`, `--traverse`, and `--files-changed` are mutually exclusive options.

## Examples

1. Pin a file and view its history:
   ```bash
   offal pin src/main.py
   offal history --limit 10
   ```

2. View history of a specific file with author filter:
   ```bash
   offal history --file path/to/file.py --author "John Doe" --after 2023-01-01
   ```

3. Traverse through detailed commit information:
   ```bash
   offal history --traverse
   ```

4. Get a summary of changes for the pinned file:
   ```bash
   offal history --summary
   ```

## Contributing

Contributions to offal are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
