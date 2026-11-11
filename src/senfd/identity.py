# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
What tells one data model from another. The format is the shape of the data
model, which senfd owns and bumps whenever the schemas change. An instance
of the data model is told by three SHA-256 hashes: of the input documents,
of the senfd that read them, and of the two together. Two data models with
the same combined hash are the same, since the same documents read by the
same senfd give the same data model. Where answers differ, the input hash
says whether the documents differ, and the senfd hash whether the reading
does.
"""

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Iterable

FORMAT = 1

# The files of the package that the wheel ships, and so the files whose
# change can change what senfd makes of a document
SOURCES = ("*.py", "*.jinja2", "*.schema.json", "*.toml")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sources(package: Path) -> Iterable[Path]:
    """The source files of the package at 'package' that read documents:
    those the wheel ships, without sate, which only answers from the data
    model"""

    for pattern in SOURCES:
        for path in package.rglob(pattern):
            relative = path.relative_to(package)
            if relative.parts[0] not in ("sate", "__pycache__"):
                yield path


def tree_sha256(package: Path) -> str:
    """The SHA-256 of the source files of the package at 'package', each by
    its path within the package and the SHA-256 of its content"""

    lines = sorted(
        f"{path.relative_to(package).as_posix()} {sha256_of(path)}\n"
        for path in sources(package)
    )
    return hashlib.sha256("".join(lines).encode()).hexdigest()


@lru_cache(maxsize=None)
def senfd_sha256() -> str:
    """The SHA-256 of the source of this senfd"""

    return tree_sha256(Path(__file__).parent)


def input_sha256(hashes: Iterable[str]) -> str:
    """The SHA-256 of a set of input documents, given by their SHA-256s, in
    whatever order"""

    return hashlib.sha256(
        "".join(f"{h}\n" for h in sorted(hashes)).encode()
    ).hexdigest()


def combined_sha256(input: str, senfd: str) -> str:
    """The SHA-256 of an input hash and a senfd hash together"""

    return hashlib.sha256(f"{input}\n{senfd}\n".encode()).hexdigest()
