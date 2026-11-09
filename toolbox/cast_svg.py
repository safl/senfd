#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Render a recording as an animated SVG, for the README

GitHub and PyPI show the README's images but run no player, so the README
shows a recording as an animated SVG, rendered by svg-term-cli through npx.
svg-term does not know a terminal's links, and prints their escapes as
text, so they are taken out first; the underline of a link stays:

    toolbox/cast_svg.py docs/_static/casts/session.cast docs/_static/casts/session.svg
"""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

SVG_TERM = "svg-term-cli@2.1.1"

# A link, OSC 8, opened or closed, ended by BEL or by ST
LINK = re.compile(r"\x1b\]8;[^\x07\x1b]*(?:\x07|\x1b\\)")


def without_links(cast: str) -> str:
    """The asciicast v2 'cast' with the links taken out of its output"""

    header, *events = cast.splitlines()
    lines = [header]
    for event in events:
        at, kind, data = json.loads(event)
        lines.append(json.dumps([at, kind, LINK.sub("", data)]))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("cast", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / args.cast.name
        plain.write_text(without_links(args.cast.read_text()))
        command = ["npx", "-y", SVG_TERM, "--in", str(plain)]
        command += ["--out", str(args.svg.resolve()), "--window", "--no-cursor"]
        return subprocess.run(command, cwd=tmp).returncode


if __name__ == "__main__":
    raise SystemExit(main())
