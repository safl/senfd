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
    toolbox/public_documents.py model OUTPUT
    toolbox/public_documents.py ask OUTPUT

The documents are NVM Express's: they are downloaded from nvmexpress.org into
the cache, $SENFD_PUBLIC_DOCUMENTS or ~/.cache/senfd/public, and neither they
nor the data model made of them is published: the data model is derived from
them, and so under the notice printed in each.
"""

import argparse
import hashlib
import json
import lzma
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

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "public" / "documents.toml"
BENCHMARK = ROOT / "benchmark"
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


def compressed(model: Path) -> Path:
    """'model', a data model, compressed with xz beside it: the same bytes in,
    the same bytes out, and read back to check that it is a data model"""

    from senfd.documents.spec import SpecDocument

    archive = model.with_name(model.name + ".xz")
    archive.write_bytes(
        lzma.compress(model.read_bytes(), preset=9 | lzma.PRESET_EXTREME)
    )
    SpecDocument.model_validate_json(lzma.decompress(archive.read_bytes()))
    return archive


def model(output: Path) -> int:
    """The data model of every public document, merged, and compressed, in
    'output'; it is not published, see the module's docstring"""

    paths = [fetched(document) for document in documents()]
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["senfd", *map(str, paths), "--output", str(output)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    merged = output / "merged.spec.document.json"
    archive = compressed(merged)
    found = counts(json.loads(merged.read_text()))
    print(", ".join(f"{k.replace('_', ' ')} {v}" for k, v in found.items()))
    print(f"{archive}: {archive.stat().st_size} bytes, of {merged.stat().st_size}")
    return 0


def graded(lane: Path) -> Dict[str, int]:
    """The answers of a lane of the benchmark, 'lane', graded, as a tally"""

    sys.path.insert(0, str(BENCHMARK / "scripts"))
    import grade

    questions = {
        q["id"]: q for q in json.loads((BENCHMARK / "questions.json").read_text())
    }
    answers = json.loads(lane.read_text())["answers"]
    verdicts = [grade.grade_text(questions[a["id"]], a["answer"]) for a in answers]
    for answer, verdict in zip(answers, verdicts):
        if verdict != grade.RIGHT:
            print(f"{answer['id']}: {verdict}: {answer['question']}")
    return grade.tally(verdicts)


def ask(output: Path) -> int:
    """The benchmark's questions answered by senfd-ask from the data model in
    'output', and every one of them right"""

    lane = output / "senfd-ask.json"
    subprocess.run(
        [
            sys.executable,
            str(BENCHMARK / "scripts" / "run_lane.py"),
            "--spec",
            str(output / "merged.spec.document.json"),
            "--out",
            str(lane),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    tally = graded(lane)
    print(", ".join(f"{verdict} {n}" for verdict, n in tally.items()))
    return 0 if tally["right"] == sum(tally.values()) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[1])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the PDFs into the cache, checked")
    checking = commands.add_parser("check", help="read each with senfd, and compare")
    checking.add_argument("names", nargs="*", help='as "Base 2.4"; all when none')
    modelling = commands.add_parser("model", help="make the merged data model, xz")
    modelling.add_argument("output", type=Path, help="the directory to make it in")
    asking = commands.add_parser("ask", help="answer the benchmark from it, all right")
    asking.add_argument("output", type=Path, help="the directory 'model' made it in")
    args = parser.parse_args()
    if args.command == "fetch":
        for document in documents():
            print(fetched(document))
        return 0
    if args.command == "model":
        return model(args.output)
    if args.command == "ask":
        return ask(args.output)
    return check(args.names)


if __name__ == "__main__":
    sys.exit(main())
