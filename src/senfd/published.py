# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The specifications NVM Express publishes as PDF, by the SHA-256 of each
file, from published.toml beside this module: a data model made from one of
them knows the file it was read from by its hash, and so can cite it by a
link to the page.
"""

import hashlib
import shutil
import subprocess
import sys
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional

import tomllib

TABLE = Path(__file__).with_name("published.toml")
AGENT = "senfd (https://github.com/safl/senfd)"
MERGED = "merged.spec.document.json"


@lru_cache(maxsize=1)
def documents() -> List[Dict[str, str]]:
    """The published documents: name, file, url and sha256 of each"""

    return list(tomllib.loads(TABLE.read_text(encoding="utf-8"))["document"])


def name_of(sha256: Optional[str]) -> Optional[str]:
    """The short name, such as "Base 2.4", of the published PDF with the
    SHA-256 'sha256', or None where no published PDF has it"""

    if not sha256:
        return None
    return next((d["name"] for d in documents() if d["sha256"] == sha256), None)


def url_of(sha256: Optional[str]) -> Optional[str]:
    """The URL of the published PDF whose SHA-256 is 'sha256'; None where
    none is"""

    if not sha256:
        return None
    return next((d["url"] for d in documents() if d["sha256"] == sha256), None)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetched(directory: Path, say: Callable[[str], None] = print) -> List[Path]:
    """The PDFs of the published documents in 'directory'. A PDF that is
    missing, or whose SHA-256 differs from the table's, is downloaded from
    its URL. Raises ValueError when a downloaded PDF has another SHA-256
    than the table gives, and then keeps no file of it."""

    paths = []
    for document in documents():
        path = directory / document["file"]
        if not path.exists() or sha256_of(path) != document["sha256"]:
            directory.mkdir(parents=True, exist_ok=True)
            say(f"Downloading {document['url']}")
            request = urllib.request.Request(
                document["url"], headers={"User-Agent": AGENT}
            )
            partial = path.with_suffix(".part")
            with urllib.request.urlopen(request, timeout=300) as response:
                with partial.open("wb") as file:
                    shutil.copyfileobj(response, file)
            found = sha256_of(partial)
            if found != document["sha256"]:
                partial.unlink()
                raise ValueError(
                    f"{document['file']} has the SHA-256 {found}, not the "
                    f"{document['sha256']} that senfd's table gives; NVM Express "
                    "may have replaced it"
                )
            partial.rename(path)
        paths.append(path)
    return paths


def make_data_model(
    documents: List[Path], spec: Path, say: Callable[[str], None] = print
) -> Path:
    """Make the merged data model of 'documents' and write it to 'spec'.
    senfd runs in a subprocess, so the memory it uses is freed when it ends.
    senfd writes into a directory beside 'spec', and only the merged data
    model is moved to 'spec', so an interrupted run leaves no 'spec'."""

    making = spec.parent / f"{spec.name}.making"
    shutil.rmtree(making, ignore_errors=True)
    making.mkdir(parents=True)
    say(f"Making the data model of {len(documents)} documents")
    subprocess.run(
        [sys.executable, "-m", "senfd.cli", *map(str, documents)]
        + ["--output", str(making)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    merged = making / MERGED
    if not merged.exists():
        raise ValueError(f"senfd made no data model of {len(documents)} documents")
    merged.replace(spec)
    shutil.rmtree(making)
    return spec
