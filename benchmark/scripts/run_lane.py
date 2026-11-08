#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Answer every question of questions.json with sate, and write the
transcript: each question, what it was understood as, each try, the answer
as shown, and how long it took

    run_lane.py --spec merged.spec.document.json --out lane.json [--llm URL]

Without --llm, sate understands the questions by their words; with it,
the language model served at URL does. Run with the Python of a venv that
has senfd; it does not grade, as the report does that from the transcript.
"""

import argparse
import json
import time
from pathlib import Path

import senfd
import senfd.sate
import senfd.query

QUESTIONS = Path(__file__).parent.parent / "questions.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--llm", default=None)
    parser.add_argument("--lane", default="sate")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    args = parser.parse_args()

    spec = senfd.query.load(args.spec)
    vocabulary = senfd.sate.Vocabulary.of(spec)
    answers = []
    for item in json.loads(args.questions.read_text()):
        start = time.monotonic()
        text, tried = senfd.sate.respond(spec, item["q"], vocabulary, args.llm)
        answers.append(
            {
                "id": item["id"],
                "question": item["q"],
                "tried": tried,
                "answer": text,
                "seconds": round(time.monotonic() - start, 3),
            }
        )
        print(f"{item['id']:3} {answers[-1]['seconds']:7.2f}s {tried}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "lane": args.lane,
                "kind": "text",
                "senfd": senfd.__version__,
                "llm": args.llm,
                "answers": answers,
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
