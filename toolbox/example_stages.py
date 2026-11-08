#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Two figures of the example document, example/example.docx, at each stage of
senfd, as the documentation shows them: the tables as written, the figures
normalised, the command they define in the data model, and the candidate
errata of the document. Written from example/output, as HTML and JSON and
text the documentation includes:

    toolbox/example_stages.py docs/src/stages

The committed files are checked against what this writes.
"""

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "example" / "output"
FIGURES = (1, 19)
COMMAND = ("foobar", "ring")

STYLE = """<style>
.senfd-stage table { border-collapse: collapse; margin: 0.5em 0 1em 0; }
.senfd-stage th, .senfd-stage td { border: 1px solid #999; padding: 0.3em 0.6em; text-align: left; vertical-align: top; }
.senfd-stage th { background: #eee; }
.senfd-stage td.caption { font-weight: bold; }
.senfd-stage p.subject { margin: 0 0 0.3em 0; font-style: italic; }
</style>
"""


def escape(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def plain(figure: Dict) -> str:
    """The figure's table as the document has it, a cell merged with the one
    to its left spanning its columns"""

    out = ['<div class="senfd-stage">', "<table>"]
    for number, row in enumerate(figure["table"]["rows"]):
        out.append("<tr>")
        cells = row["cells"]
        at = 0
        while at < len(cells):
            span = 1
            while at + span < len(cells) and cells[at + span].get("merged") == "left":
                span += 1
            tag = "th" if number == 1 else "td"
            attrs = f' colspan="{span}"' if span > 1 else ""
            if number == 0:
                attrs += ' class="caption"'
            out.append(f"<{tag}{attrs}>{escape(cells[at]['text'])}</{tag}>")
            at += span
        out.append("</tr>")
    out += ["</table>", "</div>"]
    return "\n".join(out) + "\n"


def normalized(figure: Dict, diagnostics: List[Dict]) -> str:
    """The figure as normalised: its subject and shape, its layout or its
    entries as a table, and the diagnostics of normalising it"""

    subject = figure["subject"]
    said = [f"kind {subject['kind']}"]
    for key in ("name", "lower", "upper", "condition"):
        if subject.get(key) is not None:
            said.append(f"{key} {subject[key]}")
    out = [
        '<div class="senfd-stage">',
        f'<p class="subject">Subject: {escape(", ".join(said))}. Shape: {figure["shape"]}.</p>',
    ]
    if figure.get("layout"):
        out.append("<table>")
        out.append(
            "<tr><th>range</th><th>name</th><th>acronym</th><th>description</th></tr>"
        )
        for field in figure["layout"]["fields"]:
            out.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(value))}</td>"
                    for value in (
                        field["range"]["text"],
                        field["name"],
                        field.get("acronym") or "",
                        field.get("description") or "",
                    )
                )
                + "</tr>"
            )
        out.append("</table>")
    if figure.get("entries"):
        out.append("<table>")
        out.append(
            "<tr>"
            + "".join(f"<th>{escape(c)}</th>" for c in figure["columns"])
            + "</tr>"
        )
        for entry in figure["entries"]:
            out.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(entry.get(c) or ''))}</td>"
                    for c in figure["columns"]
                )
                + "</tr>"
            )
        out.append("</table>")
    own = [d for d in diagnostics if d.get("figure_nr") == figure["figure_nr"]]
    if own:
        out.append("<p>Diagnostics:</p><ul>")
        out += [
            f"<li>{escape(d['severity'])} {escape(d['code'])}: {escape(d['message'])}</li>"
            for d in own
        ]
        out.append("</ul>")
    else:
        out.append("<p>No diagnostics: the figure read as its kind must.</p>")
    out.append("</div>")
    return "\n".join(out) + "\n"


def write(into: Path) -> None:
    into.mkdir(parents=True, exist_ok=True)
    plain_document = json.loads(
        (OUTPUT / "example.plain.figure.document.json").read_text()
    )
    normalized_document = json.loads(
        (OUTPUT / "example.normalized.figure.document.json").read_text()
    )
    spec = json.loads((OUTPUT / "example.spec.document.json").read_text())
    by_number = {f["figure_nr"]: f for f in plain_document["figures"]}
    normalised = {f["figure_nr"]: f for f in normalized_document["figures"]}
    (into / "style.html").write_text(STYLE)
    for number in FIGURES:
        (into / f"figure-{number}.plain.html").write_text(plain(by_number[number]))
        (into / f"figure-{number}.normalized.html").write_text(
            normalized(normalised[number], normalized_document["diagnostics"])
        )
    command = spec["command_sets"][COMMAND[0]]["commands"][COMMAND[1]]
    (into / f"{COMMAND[1]}.json").write_text(json.dumps(command, indent=2) + "\n")
    errata = subprocess.run(
        ["senfd-query", "--spec", str(OUTPUT / "merged.spec.document.json"), "errata"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (into / "errata.txt").write_text(errata)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[1])
    parser.add_argument("into", type=Path, help="the directory to write into")
    write(parser.parse_args().into)
    return 0


if __name__ == "__main__":
    sys.exit(main())
