#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The specifications NVM Express publishes as PDF: downloaded into a cache,
checked by their SHA-256, and read by senfd, its data model compared with
what tests/public/documents.toml says senfd makes of each

    toolbox/public_documents.py fetch
    toolbox/public_documents.py check [NAME ...]

The documents are NVM Express's: they are downloaded from nvmexpress.org into
the cache, $SENFD_PUBLIC_DOCUMENTS or ~/.cache/senfd/public, and neither they
nor the data model made of them is copied anywhere else.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, where it is tomli
    import tomli as tomllib  # type: ignore[no-redef]
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "public" / "documents.toml"
AGENT = "senfd (https://github.com/safl/senfd), testing with the public specifications"
COUNTED = ("commands", "features", "log_pages", "structures", "errata", "not_modelled")


def documents() -> List[Dict]:
    return tomllib.loads(MANIFEST.read_text())["document"]


def cache() -> Path:
    default = Path.home() / ".cache" / "senfd" / "public"
    return Path(os.environ.get("SENFD_PUBLIC_DOCUMENTS") or default)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetched(document: Dict) -> Path:
    """The PDF of 'document' in the cache, downloaded where it is not there,
    and the very one the manifest names; a ValueError where it is not"""

    path = cache() / document["file"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(document["url"], headers={"User-Agent": AGENT})
        with urllib.request.urlopen(request, timeout=300) as response:
            partial = path.with_suffix(".part")
            partial.write_bytes(response.read())
            partial.rename(path)
    found = sha256(path)
    if found != document["sha256"]:
        raise ValueError(
            f"{document['file']} is not the document the manifest names: its SHA-256 "
            f"is {found}; NVM Express may have replaced it"
        )
    return path


def counts(model: Dict) -> Dict[str, int]:
    """What the manifest counts of a data model"""

    return {
        "commands": sum(len(s["commands"]) for s in model["command_sets"].values()),
        "features": len(model["features"]),
        "log_pages": len(model["log_pages"]),
        "structures": len(model["structures"]),
        "errata": len(model["errata"]),
        "not_modelled": sum(
            d["code"] == "figure-not-modelled" for d in model["diagnostics"]
        ),
    }


def made(path: Path, output: Path) -> Dict:
    """The data model senfd makes of the document at 'path', in 'output'"""

    subprocess.run(
        ["senfd", str(path), "--output", str(output)], check=True, capture_output=True
    )
    return json.loads((output / "merged.spec.document.json").read_text())


def check(names: Optional[List[str]] = None) -> int:
    """Each document, or those of 'names', read by senfd and its counts
    compared with the manifest's"""

    failed = 0
    for document in documents():
        if names and document["name"] not in names:
            continue
        with tempfile.TemporaryDirectory() as output:
            found = counts(made(fetched(document), Path(output)))
        expected = {key: document[key] for key in COUNTED}
        differ = {
            k: (expected[k], found[k]) for k in COUNTED if expected[k] != found[k]
        }
        if differ:
            failed += 1
            said = ", ".join(f"{k} {was} -> {now}" for k, (was, now) in differ.items())
            print(f"{document['name']}: {said}")
        else:
            print(f"{document['name']}: as expected")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[1])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the PDFs into the cache, checked")
    checking = commands.add_parser("check", help="read each with senfd, and compare")
    checking.add_argument("names", nargs="*", help='as "Base 2.4"; all when none')
    args = parser.parse_args()
    if args.command == "fetch":
        for document in documents():
            print(fetched(document))
        return 0
    return check(args.names)


if __name__ == "__main__":
    sys.exit(main())
