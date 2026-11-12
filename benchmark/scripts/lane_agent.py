#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Frontier models as a coding agent: from memory, with sate-mcp, with the PDFs
============================================================================

Asks each of 'frontier.models' the questions the way a person asks Claude
Code. One run is one session. The session starts with an opening turn, and
then each question is a turn of its own, in the order of questions.json.
Each session has one of three conditions:

memory: the session has no tools, so the model answers from its training.
mcp: the session's only tools are those of sate-mcp, which serves the
    run's data model.
pdf: the session's working directory holds the PDFs of 'spec.documents',
    and its tools are Read, Grep, Glob, and Bash for pdftotext, pdfinfo,
    grep, ls and mkdir. The opening turn tells the model that the PDFs are
    there and lets it prepare them as it sees fit.

The lane records the wall time, model turns, tokens and USD of every turn,
and every tool call of the turn: the tool's name, its input, and whether
its result was an error. The output of a tool is kept only in the full
transcript.
The figures of the opening turn are recorded separately from those of the
questions, because in the pdf condition the opening turn is where the model
processes the PDFs. The claude CLI runs with no settings, so the session
has no CLAUDE.md, memory, plugin or MCP server of the user's, and it runs
in an empty directory of its own. The CLI does not run in safe mode,
because safe mode also disables sate-mcp. The CLI keeps no session on
disk, and one process takes all the turns of a session over stream-json.
The lane writes the answers, the figures and the tool calls to
'<output>/bench/lanes/agent-<condition>-<model>-<mode>-<run>.json', which
is committed. The full transcript of each session, every event of the
claude CLI and every turn sent to it, goes to
'<bench.transcripts>/<output name>/<session>.jsonl', outside the
repository, because the replies and the tools' output hold text of the
documents.

Config Arguments
----------------

spec.documents: a glob of the PDFs
frontier.models: model ids, as "claude-opus-5-5"
frontier.conditions: of "memory", "mcp" and "pdf" (default: all)
frontier.modes: of "allowed" and "required" (default: both)
frontier.runs (default: 3)
frontier.jobs: sessions run at once (default: 4)
frontier.budget_usd: the most one session may cost (default: 25)
frontier.timeout: seconds one turn may take (default: 900)
bench.transcripts: where the full transcripts go, outside the repository
    (default: "~/git/senfd-reports")

Retargetable: False
-------------------
"""

import glob
import json
import logging as log
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402

CONDITIONS = ("memory", "mcp", "pdf")

FORM = (
    "Give each answer as the NVMe specification would write it: an opcode or "
    'identifier in hexadecimal (as "3Dh"), a bit as a number (as "30"), a range '
    'of bits or bytes as "upper:lower" (as "29:26"), a byte offset as a number. '
)
MODES = {
    "allowed": 'If you do not know, or are guessing, answer "unknown" rather than '
    'a guess; a wrong answer counts against you more than "unknown". ',
    "required": "Give your best answer to every question. ",
}
REPLY = (
    "End each reply with only a JSON object "
    '{"answer": "...", "confidence": "..."}, the confidence high, medium or low.'
)
HAVE = {
    "memory": "You have no tools; answer from memory. ",
    "mcp": "The sate tools answer from a data model of the specifications. ",
    "pdf": "The specifications are the PDF files in the working directory; "
    "pdftotext and pdfinfo are installed. ",
}
OPENING = {
    "memory": "I will ask you questions about the NVMe specifications, one at a "
    "time. Say when you are ready.",
    "mcp": "I will ask you questions about the NVMe specifications, one at a "
    "time. Say when you are ready.",
    "pdf": "The NVMe specifications are the PDF files in this directory. Prepare "
    "them as you see fit; I will then ask you questions about them, one at a "
    "time. Say when you are ready.",
}
PDF_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "Bash(pdftotext:*)",
    "Bash(pdfinfo:*)",
    "Bash(grep:*)",
    "Bash(ls:*)",
    "Bash(mkdir:*)",
)


def system(condition: str, mode: str) -> str:
    return (
        "You answer questions about the NVMe specifications. "
        + HAVE[condition]
        + FORM
        + MODES[mode]
        + REPLY
    )


def command(
    condition: str, model: str, mode: str, budget: float, mcp_config: Path
) -> list:
    cmd = [
        "claude",
        "-p",
        "--setting-sources",
        "",
        "--model",
        model,
        "--strict-mcp-config",
        "--no-session-persistence",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-budget-usd",
        str(budget),
        "--system-prompt",
        system(condition, mode),
    ]
    if condition == "memory":
        return cmd + ["--tools", ""]
    if condition == "mcp":
        return cmd + [
            "--tools",
            "",
            "--mcp-config",
            str(mcp_config),
            "--allowedTools",
            "mcp__sate",
        ]
    return cmd + ["--tools", "Read,Grep,Glob,Bash", "--allowedTools", *PDF_TOOLS]


def mcp_config(cijoe) -> Path:
    """sate-mcp of the run's venv, serving the run's data model"""

    path = bench.workdir(cijoe) / "mcp.json"
    sate = bench.python(cijoe).parent / "sate-mcp"
    bench.save(
        path,
        {
            "mcpServers": {
                "sate": {
                    "command": str(sate),
                    "env": {"SENFD_SPEC": str(bench.data_model(cijoe))},
                }
            }
        },
    )
    return path


def parse(result: str) -> dict:
    """The last JSON object of a reply that gives an answer, as a reply may
    put it in a code block or say more after it"""

    for found in reversed(re.findall(r"\{[^{}]*\}", result or "")):
        try:
            data = json.loads(found)
        except ValueError:
            continue
        if isinstance(data, dict) and "answer" in data:
            return data
    return {}


def answer_of(result: str) -> dict:
    found = parse(result)
    return {
        "answer": str(found.get("answer", "unknown")),
        "confidence": str(found.get("confidence", "")),
    }


def totals(event: dict) -> dict:
    """What the session has spent so far, by a result event, which the claude
    CLI gives cumulatively; a session may call other models than the one
    asked for, so the tokens are those of all"""

    used = (event.get("modelUsage") or {}).values()
    return {
        "cost_usd": event.get("total_cost_usd") or 0,
        "tokens_in": sum(
            u.get("inputTokens", 0)
            + u.get("cacheReadInputTokens", 0)
            + u.get("cacheCreationInputTokens", 0)
            for u in used
        ),
        "tokens_out": sum(u.get("outputTokens", 0) for u in used),
    }


def tools_of(event: dict) -> list:
    """The tool calls of an assistant event: each tool's name and input,
    without the description a Bash call carries, which is the model's own
    prose"""

    message = event.get("message")
    if event.get("type") != "assistant" or not isinstance(message, dict):
        return []
    return [
        {
            "id": block.get("id"),
            "tool": block.get("name"),
            "input": {
                k: v
                for k, v in (block.get("input") or {}).items()
                if k != "description"
            },
        }
        for block in message.get("content") or []
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]


def failed_of(event: dict) -> set:
    """The ids of the tool calls whose results an event reports as errors;
    the results themselves are not kept"""

    message = event.get("message")
    if event.get("type") != "user" or not isinstance(message, dict):
        return set()
    content = message.get("content") or []
    return {
        block.get("tool_use_id")
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "tool_result"
        and block.get("is_error")
    }


def spent(before: dict, after: dict) -> dict:
    return {k: round(after[k] - before[k], 6) for k in after}


def called(tools: list, failed: set) -> list:
    """The tool calls of a turn, in order, each marked by whether its result
    was an error"""

    return [
        {"tool": t["tool"], "input": t["input"], "error": t["id"] in failed}
        for t in tools
    ]


class Session:
    """A claude CLI process taking user turns over stream-json"""

    def __init__(self, cmd: list, cwd: Path, timeout: float, transcript: Path):
        self.timeout = timeout
        transcript.parent.mkdir(parents=True, exist_ok=True)
        self.transcript = transcript.open("w")
        self.lock = threading.Lock()
        self.process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert self.process.stdin and self.process.stdout
        self.stdin, self.stdout = self.process.stdin, self.process.stdout
        self.events: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.so_far = totals({})

    def _keep(self, line: str):
        with self.lock:
            self.transcript.write(line.rstrip("\n") + "\n")
            self.transcript.flush()

    def _read(self):
        for line in self.stdout:
            self._keep(line)
            try:
                self.events.put(json.loads(line))
            except ValueError:
                continue
        self.events.put(None)

    def ask(self, text: str) -> tuple:
        """The reply's text and what the turn spent; on a timeout or the
        process gone, an empty reply and the turn's time"""

        start = time.monotonic()
        turn = json.dumps(
            {"type": "user", "message": {"role": "user", "content": text}}
        )
        self._keep(turn)
        try:
            self.stdin.write(turn + "\n")
            self.stdin.flush()
        except (BrokenPipeError, OSError):
            return "", {"seconds": 0.0, "stopped": "gone", "tools": []}
        tools: list = []
        failed: set = set()
        while True:
            left = self.timeout - (time.monotonic() - start)
            try:
                event = self.events.get(timeout=max(left, 0.001))
            except queue.Empty:
                self.close()
                return "", {
                    "seconds": round(time.monotonic() - start, 2),
                    "stopped": "timeout",
                    "tools": called(tools, failed),
                }
            if event is None:
                return "", {
                    "seconds": round(time.monotonic() - start, 2),
                    "stopped": "gone",
                    "tools": called(tools, failed),
                }
            tools += tools_of(event)
            failed |= failed_of(event)
            if event.get("type") != "result":
                continue
            now = totals(event)
            figures = spent(self.so_far, now) | {
                "seconds": round(time.monotonic() - start, 2),
                "turns": event.get("num_turns"),
                "denied": len(event.get("permission_denials") or []),
                "stopped": event.get("subtype", ""),
                "tools": called(tools, failed),
            }
            self.so_far = now
            return event.get("result", "") or "", figures

    def close(self):
        if self.process.poll() is None:
            try:
                self.stdin.close()
                self.process.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
        with self.lock:
            self.transcript.close()


def place(cijoe, condition: str, documents: list, name: str) -> Path:
    """A fresh working directory: for 'pdf' holding only links to the
    documents, else empty, so that no project's files are at hand"""

    path = bench.workdir(cijoe) / "agent" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    if condition == "pdf":
        for document in documents:
            (path / Path(document).name).symlink_to(Path(document).resolve())
    return path


def session(cijoe, job: tuple, documents: list, settings: dict) -> dict:
    condition, model, mode, run = job
    name = f"agent-{condition}-{model}-{mode}-{run}"
    cwd = place(cijoe, condition, documents, name)
    transcript = f"{Path(cijoe.output_path).name}/{name}.jsonl"
    agent = Session(
        command(condition, model, mode, settings["budget"], settings["mcp"]),
        cwd,
        settings["timeout"],
        settings["transcripts"] / transcript,
    )
    try:
        _, opening = agent.ask(OPENING[condition])
        answers, calls = {}, {}
        for q in bench.load(bench.QUESTIONS):
            result, figures = agent.ask(q["q"])
            answers[str(q["id"])] = answer_of(result)
            calls[str(q["id"])] = figures
    finally:
        agent.close()
        shutil.rmtree(cwd, ignore_errors=True)
    lane = {
        "lane": f"{condition} {model} {mode}",
        "kind": "agent",
        "condition": condition,
        "model": model,
        "mode": mode,
        "run": run,
        "system": system(condition, mode),
        "opening_prompt": OPENING[condition],
        "tools": list(PDF_TOOLS) if condition == "pdf" else [],
        "documents": [Path(d).name for d in documents] if condition == "pdf" else [],
        "transcript": transcript,
        "opening": opening,
        "answers": answers,
        "calls": calls,
        "cost_usd": round(
            (opening.get("cost_usd") or 0)
            + sum(c.get("cost_usd") or 0 for c in calls.values()),
            6,
        ),
    }
    bench.save(bench.records(cijoe) / "lanes" / f"{name}.json", lane)
    log.info(f"{name}: done")
    return lane


def main(args, cijoe):
    documents = sorted(
        d
        for d in glob.glob(str(Path(cijoe.getconf("spec.documents")).expanduser()))
        if d.lower().endswith(".pdf")
    )
    conditions = cijoe.getconf("frontier.conditions", list(CONDITIONS))
    if "pdf" in conditions and not documents:
        log.error("spec.documents names no PDFs")
        return 1
    settings = {
        "budget": float(cijoe.getconf("frontier.budget_usd", 25)),
        "timeout": float(cijoe.getconf("frontier.timeout", 900)),
        "mcp": mcp_config(cijoe),
        "transcripts": Path(
            cijoe.getconf("bench.transcripts", "~/git/senfd-reports")
        ).expanduser(),
    }
    jobs = [
        (condition, model, mode, run)
        for condition in conditions
        for model in cijoe.getconf("frontier.models", []) or []
        for mode in cijoe.getconf("frontier.modes", list(MODES))
        for run in range(1, int(cijoe.getconf("frontier.runs", 3)) + 1)
    ]
    with ThreadPoolExecutor(int(cijoe.getconf("frontier.jobs", 4))) as pool:
        lanes = list(
            pool.map(lambda job: session(cijoe, job, documents, settings), jobs)
        )
    failed = [
        lane["lane"]
        for lane in lanes
        if any(c.get("stopped") in ("gone", "timeout") for c in lane["calls"].values())
    ]
    for name in failed:
        log.error(f"{name}: a turn timed out or the session ended early")
    return 0
