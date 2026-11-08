#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Frontier models, closed-book
============================

Asks each of 'frontier.models' all the questions in one prompt, from its
training alone, 'frontier.runs' times in each of the modes: "allowed", where
"unknown" may be answered and a wrong answer counts against it, and
"required", where every question must be answered, as in a chat. Runs the
claude CLI with no tools, no MCP servers, no session kept, in safe mode, so
that no CLAUDE.md, memory, skill or plugin is in its context, and with a
system prompt of the benchmark's own. Writes each run, its prompt and the
reply as given, to '<output>/bench/lanes/frontier-<model>-<mode>-<run>.json'.

Config Arguments
----------------

frontier.models: model ids, as "claude-opus-5-5"
frontier.modes: of "allowed" and "required" (default: both)
frontier.runs (default: 3)

Retargetable: False
-------------------
"""

import json
import logging as log
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402

SYSTEM = (
    "You answer a closed-book quiz about the NVMe specifications from memory "
    "only. You have no tools. Reply with only a JSON object."
)

FORM = (
    "Give each answer as the NVMe specification would write it: an opcode or "
    'identifier in hexadecimal (as "3Dh"), a bit as a number (as "30"), a range '
    'of bits as "upper:lower" (as "29:26"), a byte offset as a number. '
)
MODES = {
    "allowed": FORM
    + 'If you do not know, or are guessing, answer "unknown" rather than a '
    'guess; a wrong answer counts against you more than "unknown". ',
    "required": FORM + "Give your best answer to every question. ",
}
REPLY = (
    "Add a confidence of high, medium or low to each. Reply with only a JSON "
    "object, keys the question numbers as strings, each value an object "
    '{"answer": "...", "confidence": "..."}.'
)


def prompt(mode: str) -> str:
    questions = bench.load(bench.QUESTIONS)
    listed = "\n".join(f"{q['id']}. {q['q']}" for q in questions)
    return f"{MODES[mode]}{REPLY}\n\n{listed}"


def parse(result: str) -> dict:
    match = re.search(r"\{.*\}", result, re.DOTALL)
    return json.loads(match[0]) if match else {}


def main(args, cijoe):
    records = bench.records(cijoe)
    runs = int(cijoe.getconf("frontier.runs", 3))
    for model in cijoe.getconf("frontier.models", []) or []:
        for mode in cijoe.getconf("frontier.modes", list(MODES)):
            for run in range(1, runs + 1):
                text = prompt(mode)
                cmd = (
                    f"claude -p --safe-mode --model {shlex.quote(model)} --tools '' "
                    "--strict-mcp-config --no-session-persistence --output-format json "
                    f"--system-prompt {shlex.quote(SYSTEM)} {shlex.quote(text)}"
                )
                start = time.monotonic()
                err, state = cijoe.run_local(cmd, cwd=str(bench.workdir(cijoe)))
                seconds = round(time.monotonic() - start, 2)
                if err:
                    log.error(f"{model} {mode} {run} failed")
                    return err
                reply = json.loads(state.output().strip().splitlines()[-1])
                bench.save(
                    records / "lanes" / f"frontier-{model}-{mode}-{run}.json",
                    {
                        "lane": f"frontier {model} {mode}",
                        "kind": "value",
                        "model": model,
                        "mode": mode,
                        "run": run,
                        "system": SYSTEM,
                        "prompt": text,
                        "result": reply.get("result", ""),
                        "answers": parse(reply.get("result", "")),
                        "cost_usd": reply.get("total_cost_usd"),
                        "seconds": seconds,
                    },
                )
    return 0
