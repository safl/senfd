#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Install senfd
=============

Installs senfd, with its 'ask' extra, from 'senfd.repo' at 'senfd.commit'
into a venv of the benchmark's own under 'bench.workdir', with uv; the
senfd on PATH is never used. Records the version and commit.

Config Arguments
----------------

senfd.repo, senfd.commit, senfd.python (default: 3.12)

Retargetable: False
-------------------
"""

import logging as log
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402


def main(args, cijoe):
    repo, commit = cijoe.getconf("senfd.repo"), cijoe.getconf("senfd.commit")
    venv = bench.workdir(cijoe) / "venv"
    spec = shlex.quote(f"senfd[sate,pdf] @ git+{repo}@{commit}")
    for cmd in (
        f"rm -rf {venv}",
        f"uv venv -q -p {cijoe.getconf('senfd.python', '3.12')} {venv}",
        f"VIRTUAL_ENV={venv} uv pip install -q {spec}",
    ):
        err, _ = cijoe.run_local(cmd)
        if err:
            log.error(f"installing senfd failed: {cmd}")
            return err
    err, state = cijoe.run_local(f"{venv}/bin/senfd --version")
    if err:
        return err
    bench.save(
        bench.records(cijoe) / "senfd.json",
        {"repo": repo, "commit": commit, "version": state.output().strip()},
    )
    return 0
