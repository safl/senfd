# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import report  # noqa: E402

QUESTIONS = [
    {"id": 1, "q": "Opcode of Write?", "kind": "hex", "a": "01", "about": "Write"},
    {"id": 2, "q": "Bit of FUA?", "kind": "bits", "a": "30", "about": "FUA"},
]


def test_a_frontier_answer_says_the_time_of_the_call_that_gave_it():
    lane = {
        "kind": "value",
        "seconds": 4.0,
        "answers": {"1": {"answer": "01h", "confidence": "high"}},
    }
    graded = report.graded(QUESTIONS, lane)
    assert graded[1] == ("right", "01h", "high, 4.0s for all 2, 2.000s each")
    assert graded[2] == ("unknown", "unknown", "4.0s for all 2, 2.000s each")


def test_a_lookup_answer_says_its_own_time():
    lane = {
        "kind": "text",
        "answers": [
            {"id": q["id"], "answer": "", "tried": ["command('Write')"], "seconds": 0.5}
            for q in QUESTIONS
        ],
    }
    assert report.graded(QUESTIONS, lane)[1][2] == "command('Write'), 0.5s"
