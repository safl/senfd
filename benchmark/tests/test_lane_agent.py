# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import bench  # noqa: E402
import lane_agent  # noqa: E402

QUESTIONS = [
    {"id": 3, "q": "Which bit is FUA?", "kind": "bits", "a": "30"},
    {"id": 4, "q": "Which bit is LR?", "kind": "bits", "a": "31"},
]

# Stands in for the claude CLI: answers each user turn read over stream-json
# with a result event, its cost and tokens summed over the session as the CLI
# gives them, and notes what its working directory held.
CLAUDE = """#!/usr/bin/env python3
import json, os, sys
turn = 0
for line in sys.stdin:
    turn += 1
    text = json.loads(line)["message"]["content"]
    with open(os.environ["SEEN"], "a") as seen:
        seen.write(json.dumps([text, sorted(os.listdir("."))]) + "\\n")
    print(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Looking it up."},
        {"type": "tool_use", "id": "t1", "name": "mcp__sate__structure",
         "input": {"name": "Write"}},
        {"type": "tool_use", "id": "t2", "name": "Bash",
         "input": {"command": "pdftotext a.pdf -", "description": "Read a"}},
    ]}}), flush=True)
    print(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "The figure text."},
        {"type": "tool_result", "tool_use_id": "t2", "content": "no", "is_error": True},
    ]}}), flush=True)
    print(json.dumps({
        "type": "result",
        "subtype": "success",
        "num_turns": 2,
        "result": 'The figure text.\\n```json\\n{"answer": "30", "confidence": "high"}\\n```',
        "total_cost_usd": 0.5 * turn,
        "modelUsage": {
            "m": {"inputTokens": 100 * turn, "cacheReadInputTokens": 0,
                  "cacheCreationInputTokens": 0, "outputTokens": 10 * turn},
        },
    }), flush=True)
"""


def words_of(condition):
    return lane_agent.command(condition, "m", "required", 25, Path("mcp.json"))


def test_no_condition_runs_in_safe_mode_as_that_leaves_out_sate_mcp():
    for condition in lane_agent.CONDITIONS:
        words = words_of(condition)
        assert "--safe-mode" not in words
        assert words[words.index("--setting-sources") + 1] == ""
        assert "--strict-mcp-config" in words and "--no-session-persistence" in words


def test_each_condition_has_only_its_own_tools():
    memory, mcp, pdf = (words_of(c) for c in ("memory", "mcp", "pdf"))
    assert memory[memory.index("--tools") + 1] == ""
    assert "--mcp-config" not in memory and "--allowedTools" not in memory

    assert mcp[mcp.index("--tools") + 1] == ""
    assert mcp[mcp.index("--mcp-config") + 1] == "mcp.json"
    assert mcp[mcp.index("--allowedTools") + 1 :] == ["mcp__sate"]

    assert pdf[pdf.index("--tools") + 1] == "Read,Grep,Glob,Bash"
    assert pdf[pdf.index("--allowedTools") + 1 :] == list(lane_agent.PDF_TOOLS)
    assert "Bash" not in lane_agent.PDF_TOOLS


def test_the_answer_is_the_last_json_object_giving_one():
    reply = 'Bit 30 {see figure}.\n```json\n{"answer": "30", "confidence": "high"}\n```'
    assert lane_agent.answer_of(reply) == {"answer": "30", "confidence": "high"}
    assert lane_agent.answer_of('{"note": 1}') == {
        "answer": "unknown",
        "confidence": "",
    }
    assert lane_agent.answer_of("") == {"answer": "unknown", "confidence": ""}


def test_sate_mcp_serves_the_runs_data_model(tmp_path):
    cijoe = Cijoe(tmp_path, {"bench.workdir": str(tmp_path / "work")})
    config = bench.load(lane_agent.mcp_config(cijoe))["mcpServers"]["sate"]
    assert config["command"] == str(tmp_path / "work" / "venv" / "bin" / "sate-mcp")
    assert config["env"]["SENFD_SPEC"] == str(bench.data_model(cijoe))


class Cijoe:
    def __init__(self, tmp_path, config):
        self.output_path = str(tmp_path / "out")
        self.config = config

    def getconf(self, key, default=None):
        return self.config.get(key, default)


@pytest.fixture
def claude(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "claude").write_text(CLAUDE)
    (bin_ / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:{Path(sys.executable).parent}:/usr/bin:/bin")
    monkeypatch.setenv("SEEN", str(tmp_path / "seen.jsonl"))
    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps(QUESTIONS))
    monkeypatch.setattr(bench, "QUESTIONS", questions)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("a.pdf", "b.pdf", "c.docx"):
        (docs / name).write_text(name)
    return Cijoe(
        tmp_path,
        {
            "spec.documents": str(docs / "*"),
            "bench.workdir": str(tmp_path / "work"),
            "bench.transcripts": str(tmp_path / "reports"),
            "frontier.models": ["m"],
            "frontier.modes": ["required"],
            "frontier.runs": 1,
        },
    )


def test_one_session_takes_the_opening_and_then_each_question_in_turn(claude, tmp_path):
    claude.config["frontier.conditions"] = ["pdf"]
    assert lane_agent.main(None, claude) == 0

    seen = [json.loads(line) for line in (tmp_path / "seen.jsonl").open()]
    assert [text for text, _ in seen] == [lane_agent.OPENING["pdf"]] + [
        q["q"] for q in QUESTIONS
    ]
    assert all(listed == ["a.pdf", "b.pdf"] for _, listed in seen)


def test_each_turn_keeps_what_it_spent_and_only_the_answer(claude, tmp_path):
    claude.config["frontier.conditions"] = ["memory"]
    assert lane_agent.main(None, claude) == 0
    lane = bench.load(
        tmp_path / "out" / "bench" / "lanes" / "agent-memory-m-required-1.json"
    )
    assert lane["opening"]["cost_usd"] == 0.5
    assert lane["calls"]["4"]["cost_usd"] == 0.5
    assert lane["calls"]["4"]["tokens_in"] == 100
    assert lane["calls"]["4"]["tokens_out"] == 10
    assert lane["cost_usd"] == pytest.approx(1.5)
    assert lane["answers"]["3"] == {"answer": "30", "confidence": "high"}
    assert lane["calls"]["3"]["tools"] == [
        {"tool": "mcp__sate__structure", "input": {"name": "Write"}, "error": False},
        {"tool": "Bash", "input": {"command": "pdftotext a.pdf -"}, "error": True},
    ]
    assert "The figure text" not in json.dumps(lane)
    assert lane["documents"] == []
    assert not (tmp_path / "work" / "agent" / "agent-memory-m-required-1").exists()


def test_the_full_transcript_goes_outside_the_run(claude, tmp_path):
    claude.config["frontier.conditions"] = ["mcp"]
    assert lane_agent.main(None, claude) == 0
    lane = bench.load(
        tmp_path / "out" / "bench" / "lanes" / "agent-mcp-m-required-1.json"
    )
    assert lane["transcript"] == "out/agent-mcp-m-required-1.jsonl"
    events = [
        json.loads(line) for line in (tmp_path / "reports" / lane["transcript"]).open()
    ]
    sent = [
        e["message"]["content"]
        for e in events
        if e.get("type") == "user" and isinstance(e["message"]["content"], str)
    ]
    assert sent == [lane_agent.OPENING["mcp"]] + [q["q"] for q in QUESTIONS]
    assert "The figure text" in json.dumps(events)
    assert sum(e.get("type") == "result" for e in events) == len(QUESTIONS) + 1
