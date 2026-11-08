# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
What the steps share: where the work and the records go

Not a task. The records of a run go under '<output>/bench/', beside cijoe's
own, so that the run tree holds them: the lanes' transcripts, the hashes of
the documents and of the data model, and the report. The venv, the
documents' data model and anything made from the documents go under 'bench.workdir',
outside the run, since the documents are NVM Express's and nothing made
from them is kept.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "questions.json"


def workdir(cijoe) -> Path:
    path = Path(cijoe.getconf("bench.workdir", "/tmp/senfd-bench"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def records(cijoe) -> Path:
    path = Path(cijoe.output_path) / "bench"
    (path / "lanes").mkdir(parents=True, exist_ok=True)
    return path


def data_model(cijoe) -> Path:
    return workdir(cijoe) / "model" / "merged.spec.document.json"


def python(cijoe) -> Path:
    return workdir(cijoe) / "venv" / "bin" / "python"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=1) + "\n")


def load(path: Path):
    return json.loads(Path(path).read_text())
