from functools import lru_cache
from pathlib import Path

import git

from offal.constants import PINNED_FILENAME


def get_pinned_path():
    repo = git.Repo(search_parent_directories=True)

    if not repo.working_tree_dir:
        raise Exception("Not a git repository")

    pinned_file = Path(repo.working_tree_dir) / ".offal" / PINNED_FILENAME

    if not pinned_file.is_file():
        pinned_file.parent.mkdir(exist_ok=True, parents=True)
        pinned_file.write_text("")

    return pinned_file


@lru_cache(maxsize=1)
def parse_pinned_file(file: Path):
    pinned_items = {}

    if file.is_file():
        with file.open("r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                pinned_items[key.strip()] = value.strip()
    return pinned_items


def get_pinned_item(key):
    pinned_items = parse_pinned_file(get_pinned_path())
    return pinned_items.get(key)


def set_pinned_item(key, value):
    file = get_pinned_path()
    pinned_items = parse_pinned_file(file)
    pinned_items[key] = value

    with file.open("w") as f:
        for key, value in pinned_items.items():
            f.write(f"{key}={value}\n")

    parse_pinned_file.cache_clear()


def remove_pinned_item(key):
    file = get_pinned_path()
    pinned_items = parse_pinned_file(file)
    pinned_items.pop(key, None)

    with file.open("w") as f:
        for key, value in pinned_items.items():
            f.write(f"{key}={value}\n")

    parse_pinned_file.cache_clear()


def clear_pinned_items():
    file = get_pinned_path()
    file.write_text("")
    parse_pinned_file.cache_clear()
