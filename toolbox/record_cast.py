#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Record a script of shell commands as an asciinema recording, asciicast v2

Each line of the script is typed at a prompt, a key at a time, run, and its
output shown as it was printed; a line starting with '#' is typed as a
comment and not run. The timing is made up, a fixed pace of typing and a
pause after each output, so a recording is the same each time it is made
from the same data model, and needs no terminal to make:

    toolbox/record_cast.py docs/casts/lookups.sh docs/_static/casts/lookups.cast
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List, Tuple

PROMPT = "\x1b[1;32m$\x1b[0m "
TYPING = 0.035  # Seconds a key
PAUSE = 1.6  # Seconds after an output, for reading it
WIDTH, HEIGHT = 110, 32


def events_of(script: List[str], env: dict) -> List[Tuple[float, str]]:
    events: List[Tuple[float, str]] = []
    at = 0.5
    for line in script:
        events.append((at, PROMPT))
        for key in line:
            at += TYPING
            events.append((at, key))
        at += 0.4
        events.append((at, "\r\n"))
        if not line.startswith("#"):
            done = subprocess.run(
                line, shell=True, capture_output=True, text=True, env=env
            )
            out = (done.stdout + done.stderr).replace("\n", "\r\n")
            at += 0.2
            events.append((at, out))
            at += PAUSE + min(out.count("\n"), 30) * 0.08
        else:
            at += 0.3
    events.append((at, PROMPT))
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("script", type=Path)
    parser.add_argument("cast", type=Path)
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    script = [
        line.rstrip() for line in args.script.read_text().splitlines() if line.strip()
    ]
    env = dict(os.environ, COLUMNS=str(WIDTH), TERM="xterm-256color")
    header = {"version": 2, "width": WIDTH, "height": HEIGHT, "title": args.title}
    args.cast.parent.mkdir(parents=True, exist_ok=True)
    with args.cast.open("w") as cast:
        cast.write(json.dumps(header) + "\n")
        for at, text in events_of(script, env):
            cast.write(json.dumps([round(at, 3), "o", text]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
