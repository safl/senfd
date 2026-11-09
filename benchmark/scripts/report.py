#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Report
======

Grades every lane of the run, '<output>/bench/lanes/*.json', and writes
'<output>/bench/summary.json' and '<output>/bench/report.html': a scoreboard,
then each question with the answer of every lane beside the right one, a
right answer green, a wrong one red, and "unknown" grey. A frontier model's
runs are shown one by one, so that the spread between them shows. Also
runnable on its own, over a run's output:

    report.py <output>

Retargetable: False
-------------------
"""

import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402
import grade  # noqa: E402

COLOURS = {grade.RIGHT: "#1a7f37", grade.WRONG: "#cf222e", grade.UNKNOWN: "#6e7781"}
STYLE = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #1f2328; }
table { border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #d0d7de; padding: 0.3rem 0.5rem; vertical-align: top; }
th { background: #f6f8fa; text-align: left; }
td.q { max-width: 28rem; }
span.v { font-family: ui-monospace, monospace; font-weight: 600; }
span.how { display: block; color: #6e7781; font-size: 0.8rem; }
details { font-size: 0.8rem; }
pre { white-space: pre-wrap; font-size: 0.8rem; }
"""


def lanes_of(output: Path):
    lanes = []
    for path in sorted((output / "bench" / "lanes").glob("*.json")):
        data = bench.load(path)
        if "answers" in data and "kind" in data:
            lanes.append(data)
    return lanes


def column_of(lane) -> str:
    if lane["kind"] == "value":
        return (
            f"{lane['model']}, unknown {lane['mode']}"
            if lane["mode"] == "allowed"
            else (f"{lane['model']}, answer required")
        )
    return lane["lane"]


def graded(questions, lane):
    """Each question's (verdict, shown, how) in 'lane'. A frontier model
    answers every question in one call, so the time under its answer is the
    call's, and what it shares of it by question."""

    out = {}
    for q in questions:
        if lane["kind"] == "value":
            given = (lane["answers"].get(str(q["id"])) or {}).get("answer", "unknown")
            confidence = (lane["answers"].get(str(q["id"])) or {}).get("confidence", "")
            seconds = lane.get("seconds")
            took = (
                f"{seconds}s for all {len(questions)}, "
                f"{seconds / len(questions):.3f}s each"
                if seconds
                else ""
            )
            how = ", ".join(part for part in (confidence, took) if part)
            out[q["id"]] = (grade.grade_value(q, given), given, how)
        else:
            entry = next(a for a in lane["answers"] if a["id"] == q["id"])
            verdict = grade.grade_text(q, entry["answer"])
            line = shown_line(q, entry["answer"])
            out[q["id"]] = (
                verdict,
                line,
                " / ".join(entry["tried"]) + f", {entry['seconds']}s",
            )
    return out


def shown_line(q, text: str) -> str:
    """The line of an answer that gives the question's value, else its first"""

    import re

    pattern = re.compile(grade.value_pattern(q), re.IGNORECASE)
    lines = [line for line in text.splitlines()[1:] if line.strip()]
    for line in lines:
        if q["about"].lower() in line.lower() and pattern.search(line):
            return line.strip("-*# ")
    return (lines[0] if lines else text).strip("-*# ")[:160]


def main(args, cijoe):
    return write(Path(cijoe.output_path))


def write(output: Path) -> int:
    questions = bench.load(bench.QUESTIONS)
    lanes = lanes_of(output)
    columns = defaultdict(list)
    for lane in lanes:
        columns[column_of(lane)].append((lane, graded(questions, lane)))

    summary = {}
    for column, runs in columns.items():
        tallies = [grade.tally([g[q["id"]][0] for q in questions]) for _, g in runs]
        lane = runs[0][0]
        seconds = (
            [a["seconds"] for a in lane["answers"]]
            if lane["kind"] == "text"
            else [r["seconds"] / len(questions) for r, _ in runs]
        )
        summary[column] = {
            "runs": tallies,
            "mean": {k: round(mean(t[k] for t in tallies), 1) for k in tallies[0]},
            "seconds_per_question": round(mean(seconds), 3),
            "cost_usd": sum((r.get("cost_usd") or 0) for r, _ in runs),
        }
    bench.save(output / "bench" / "summary.json", summary)

    rows = []
    for name, s in summary.items():
        m = s["mean"]
        rows.append(
            f"<tr><td>{html.escape(name)}</td><td>{len(s['runs'])}</td>"
            f"<td style='color:{COLOURS['right']}'>{m['right']}</td>"
            f"<td style='color:{COLOURS['wrong']}'>{m['wrong']}</td>"
            f"<td style='color:{COLOURS['unknown']}'>{m['unknown']}</td>"
            f"<td>{s['seconds_per_question']}</td><td>{s['cost_usd']:.2f}</td></tr>"
        )
    board = (
        "<table><tr><th>Lane</th><th>Runs</th><th>Right</th><th>Wrong</th>"
        "<th>Unknown</th><th>Seconds a question</th><th>USD</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = []
    for q in questions:
        cells = []
        for column, runs in columns.items():
            parts = []
            for _, g in runs:
                verdict, shown, how = g[q["id"]]
                parts.append(
                    f"<span class='v' style='color:{COLOURS[verdict]}'>"
                    f"{html.escape(str(shown))}</span>"
                    + (f"<span class='how'>{html.escape(how)}</span>" if how else "")
                )
            cells.append("<td>" + "".join(parts) + "</td>")
        expected = q["a"] + ("h" if q["kind"] == "hex" else "")
        body.append(
            f"<tr><td>{q['id']}</td><td class='q'>{html.escape(q['q'])}</td>"
            f"<td><span class='v'>{html.escape(expected)}</span></td>{''.join(cells)}</tr>"
        )
    facts = [
        f"<details><summary>{html.escape(p.name)}</summary><pre>"
        f"{html.escape(p.read_text())}</pre></details>"
        for p in sorted((output / "bench").glob("*.json"))
        if p.name != "summary.json"
    ]
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>NVMe questions: frontier models and senfd</title>"
        f"<style>{STYLE}</style></head><body>"
        "<h1>NVMe questions: frontier models and senfd</h1>"
        f"{board}<table><tr><th>#</th><th>Question</th><th>Right answer</th>{head}</tr>"
        + "".join(body)
        + "</table>"
        + "".join(facts)
        + "</body></html>"
    )
    (output / "bench" / "report.html").write_text(page)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(write(Path(sys.argv[1])))
