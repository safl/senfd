# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import report  # noqa: E402

SOURCE = {
    "pdf": "NVM-Express-Base-Specification-Revision-2.4-Ratified-2026.07.31.pdf",
    "figure": 143,
}
QUESTIONS = [
    {
        "id": 1,
        "q": "Opcode of Write?",
        "kind": "hex",
        "a": "01",
        "about": "Write",
        "source": SOURCE,
    },
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


def test_an_agents_answer_says_what_its_turn_spent():
    lane = {
        "kind": "agent",
        "condition": "pdf",
        "model": "m",
        "mode": "required",
        "answers": {"1": {"answer": "01h", "confidence": "high"}},
        "calls": {
            "1": {
                "seconds": 15.2,
                "turns": 4,
                "tokens_in": 27546,
                "tokens_out": 809,
                "cost_usd": 0.0658,
                "tools": [
                    {
                        "tool": "mcp__sate__command",
                        "input": {"name": "Write"},
                        "error": False,
                    }
                ],
            }
        },
    }
    assert report.column_of(lane) == "m, with the PDFs, answer required"
    assert report.graded(QUESTIONS, lane)[1] == (
        "right",
        "01h",
        "high, 15.2s, 4 turns, 27546 tokens in, 809 out, USD 0.0658, "
        "command(name='Write')",
    )


def test_an_agent_lane_sums_up_its_turns_and_tokens_and_its_opening(
    tmp_path, monkeypatch
):
    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps(QUESTIONS))
    monkeypatch.setattr(report.bench, "QUESTIONS", questions)
    lanes = tmp_path / "bench" / "lanes"
    lanes.mkdir(parents=True)
    call = {"seconds": 10, "turns": 4, "tokens_in": 1000, "tokens_out": 100}
    report.bench.save(
        lanes / "agent-pdf-m-required-1.json",
        {
            "kind": "agent",
            "condition": "pdf",
            "model": "m",
            "mode": "required",
            "opening": {
                "seconds": 60.0,
                "cost_usd": 0.4,
                "tokens_in": 30000,
                "tokens_out": 900,
            },
            "answers": {"1": {"answer": "01h"}, "2": {"answer": "31"}},
            "calls": {
                "1": call | {"cost_usd": 0.5, "tools": []},
                "2": call
                | {
                    "seconds": 20,
                    "turns": 6,
                    "cost_usd": 0.25,
                    "tools": [
                        {"tool": "Read", "input": {"file_path": "a.pdf"}, "error": True}
                    ],
                },
            },
            "cost_usd": 0.75,
        },
    )
    assert report.write(tmp_path) == 0
    summary = report.bench.load(tmp_path / "bench" / "summary.json")
    assert summary["m, with the PDFs, answer required"] == {
        "runs": [{"right": 1, "wrong": 1, "unknown": 0}],
        "mean": {"right": 1, "wrong": 1, "unknown": 0},
        "seconds_per_question": 15,
        "cost_usd": 0.75,
        "turns": 5,
        "tokens_in": 1000,
        "tokens_out": 100,
        "without_tool": {"answers": 1, "right": 1},
        "opening": {
            "seconds": 60.0,
            "cost_usd": 0.4,
            "tokens_in": 30000,
            "tokens_out": 900,
        },
    }
    page = (tmp_path / "bench" / "report.html").read_text()
    assert "5 turns, 1,000 in, 100 out" in page
    assert "60.0s, USD 0.4000, 30,000 in, 900 out" in page
    assert "Base 2.4, Figure 143" in page
    assert "Read(file_path=&#x27;a.pdf&#x27;) error" in page
    assert "<td>1 (1)</td>" in page
