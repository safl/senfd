#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
sate, by the words of the questions
========================================

Answers every question with sate understanding it by its words, names
and acronyms, with no language model, into '<output>/bench/lanes/sate.json'.

Retargetable: False
-------------------
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402


def main(args, cijoe):
    out = bench.records(cijoe) / "lanes" / "sate.json"
    err, _ = cijoe.run_local(
        f"{bench.python(cijoe)} {Path(__file__).parent / 'run_lane.py'} "
        f"--spec {bench.data_model(cijoe)} --out {out} --lane sate"
    )
    return err
