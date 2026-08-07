#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


IGNORED_DIRECTORY_NAMES = {
    "__pycache__",
    ".git",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
}

IGNORED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def calculate_file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""

    digest = hashlib.sha256()

    try:
        with path.open("rb") as file:
            while True:
                chunk = file.read(1024 * 1024)

                if not chunk:
                    break

                digest.update(chunk)
    except OSError:
        return ""

    return digest.hexdigest()


def should_ignore_tree_path(path: Path, root: Path) -> bool:
    try:
        relative_path = path.relative_to(root)
    except ValueError:
        return True

    if any(
        part in IGNORED_DIRECTORY_NAMES
        for part in relative_path.parts
    ):
        return True

    if path.name in IGNORED_FILE_NAMES:
        return True

    if path.suffix.lower() in IGNORED_FILE_SUFFIXES:
        return True

    return False


def calculate_tree_sha256(root: Path) -> str:
    if not root.is_dir():
        return ""

    digest = hashlib.sha256()

    try:
        entries = sorted(
            (
                path
                for path in root.rglob("*")
                if not should_ignore_tree_path(path, root)
                and (path.is_file() or path.is_symlink())
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    except OSError:
        return ""

    try:
        for path in entries:
            relative_path = path.relative_to(root).as_posix()

            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")

            if path.is_symlink():
                digest.update(b"SYMLINK\0")
                digest.update(os.readlink(path).encode("utf-8"))
                digest.update(b"\0")
                continue

            digest.update(b"FILE\0")

            with path.open("rb") as file:
                while True:
                    chunk = file.read(1024 * 1024)

                    if not chunk:
                        break

                    digest.update(chunk)

            digest.update(b"\0")

    except OSError:
        return ""

    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Uso: checksum_utils.py <file|tree> <ruta>",
            file=sys.stderr,
        )
        return 2

    checksum_type = sys.argv[1]
    path = Path(sys.argv[2])

    if checksum_type == "file":
        checksum = calculate_file_sha256(path)
    elif checksum_type == "tree":
        checksum = calculate_tree_sha256(path)
    else:
        print(
            f"Tipo de huella no válido: {checksum_type}",
            file=sys.stderr,
        )
        return 2

    if not checksum:
        return 1

    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
