#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Record an interactive program as an asciinema recording, asciicast v2

The program runs in a terminal of its own, a pseudo-terminal, and each line
of the script is typed into it a key at a time, then Enter; '\\t' in a line
is a press of Tab. What the program draws is recorded as it draws it, so its
completion menus show. The timing is made up, as by record_cast.py, a fixed
pace of typing and a pause after each answer; at the end of the script the
input ends, as by Ctrl-D:

    toolbox/record_session.py "senfd-ask" docs/casts/session.txt \\
        docs/_static/casts/session.cast
"""

import argparse
import fcntl
import json
import os
import pty
import select
import shlex
import struct
import termios
import time
from pathlib import Path
from typing import List, Tuple

TYPING = 0.08  # Seconds a key
PAUSE = 2.4  # Seconds after an answer, for reading it
WIDTH, HEIGHT = 110, 32


def drawn(fd: int, quiet: float, longest: float) -> str:
    """What the program draws, until it has drawn nothing for 'quiet' seconds
    or 'longest' seconds have gone"""

    out = b""
    end = time.monotonic() + longest
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], quiet)
        if not ready:
            break
        try:
            chunk = os.read(fd, 65536)
        except OSError:  # The program has ended
            break
        if not chunk:
            break
        out += chunk
    return out.decode("utf-8", "replace")


def events_of(command: List[str], script: List[str], env: dict):
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe(command[0], command, env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", HEIGHT, WIDTH, 0, 0))

    events: List[Tuple[float, str]] = []
    at = 0.5

    def show(text: str, after: float) -> None:
        nonlocal at
        if text:
            events.append((at, text))
        at += after

    show(drawn(fd, 1.5, 30), 1.5)  # Until it waits for a question
    for line in script:
        for key in line.replace("\\t", "\t"):
            os.write(fd, key.encode())
            show(drawn(fd, 0.15, 5), TYPING if key != "\t" else 1.4)
        os.write(fd, b"\r")
        text = drawn(fd, 0.5, 120)
        show(text, PAUSE + min(text.count("\n"), 30) * 0.08)
    os.write(fd, b"\x04")
    show(drawn(fd, 0.3, 5), 0.5)
    os.waitpid(pid, 0)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("command", help="The program to run, as a shell would split it")
    parser.add_argument("script", type=Path)
    parser.add_argument("cast", type=Path)
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    script = [
        line.rstrip("\n")
        for line in args.script.read_text().splitlines()
        if line.strip()
    ]
    env = dict(
        os.environ,
        COLUMNS=str(WIDTH),
        LINES=str(HEIGHT),
        TERM="xterm-256color",
        PROMPT_TOOLKIT_NO_CPR="1",  # Nothing answers its cursor position requests
    )
    header = {"version": 2, "width": WIDTH, "height": HEIGHT, "title": args.title}
    args.cast.parent.mkdir(parents=True, exist_ok=True)
    with args.cast.open("w") as cast:
        cast.write(json.dumps(header) + "\n")
        for at, text in events_of(shlex.split(args.command), script, env):
            cast.write(json.dumps([round(at, 3), "o", text]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
