#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The data model of the documents
===============================

Runs the installed senfd over the documents 'spec.documents' names, .docx or PDF,
a glob, into '<bench.workdir>/model'. The documents and the data model stay
there; the run records only their names and SHA-256, so a later run can be
checked to be of the same documents.

Config Arguments
----------------

spec.documents: a glob of the documents, .docx or PDF, outside any repository

Retargetable: False
-------------------
"""

import glob
import logging as log
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402


def main(args, cijoe):
    documents = sorted(
        glob.glob(str(Path(cijoe.getconf("spec.documents")).expanduser()))
    )
    if not documents:
        log.error("spec.documents names no documents")
        return 1
    out = bench.data_model(cijoe).parent
    senfd = bench.python(cijoe).parent / "senfd"
    quoted = " ".join(shlex.quote(d) for d in documents)
    for cmd in (f"rm -rf {out}", f"{senfd} {quoted} --output {out}"):
        err, _ = cijoe.run_local(cmd)
        if err:
            log.error(f"modelling failed: {cmd}")
            return err
    bench.save(
        bench.records(cijoe) / "documents.json",
        {
            "documents": {Path(d).name: bench.sha256(Path(d)) for d in documents},
            "model": bench.sha256(bench.data_model(cijoe)),
        },
    )
    return 0
