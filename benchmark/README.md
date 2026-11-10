<!--
SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>

SPDX-License-Identifier: LGPL-2.1-only
-->

# NVMe questions: frontier language models and senfd

71 questions with one exact answer each, an opcode, an identifier, a
status code, a bit or a byte offset, about the eleven NVMe documents
ratified in 2026: the commands, features, log pages and fields that recent
revisions added or moved, the bits of the registers, the opcodes of every
command set and the fields of the Identify data structures, with a few
long-standing facts among them. Each right answer was checked against the
figure that gives it. `questions.json` holds them. The latest run,
`results/2026-11-10-v0.14.0`, made its data model from the PDFs NVM
Express publishes, at senfd 0.14.0. Kept beside it are the run of
2026-11-09 at senfd 0.13.0, with the same language models, the run of
2026-11-09 at senfd 75c370d, on the way to 0.9.1, with Llama 3.1 8B and
3.2 1B in place of Qwen, and the run of 2026-11-08, which asked the first
30 from a data model made of the `.docx`, at 0.8.0.

| Lane, 2026-11-10, senfd 0.14.0 | Right | Wrong | Unknown | Cost and time |
|---|---|---|---|---|
| `sate`, no language model | 71 | 0 | 0 | free, 5 ms a question |
| `sate --llm`, Qwen 2.5 7B Q4_K_M, CPU only | 69 | 0 | 2 | free, 2.3 s a question |
| `sate --llm`, Qwen 2.5 1.5B Q4_K_M, CPU only | 44 | 0 | 27 | free, 1.3 s a question |
| Claude Opus 5.5, from memory, "unknown" allowed[^allowed] | 50.7 | 1.3 | 19 | USD 0.11 a run, 0.59 s a question |
| Claude Opus 5.5, from memory, answer required[^required] | 54.3 | 16.7 | 0 | USD 0.13 a run, 0.74 s a question |
| Claude Sonnet 5.5, from memory, "unknown" allowed[^allowed] | 36.3 | 6.7 | 28 | USD 0.02 a run, 0.14 s a question |
| Claude Sonnet 5.5, from memory, answer required[^required] | 39 | 32 | 0 | USD 0.02 a run, 0.19 s a question |

[^allowed]: The frontier model is told: "If you do not know, or are
    guessing, answer "unknown" rather than a guess", and that a wrong
    answer counts against it. This measures whether it knows what it does
    not know.

[^required]: The frontier model is told to give its best answer to every
    question, with a confidence of high, medium or low, and may not answer
    "unknown". This is how a chat answers a question put to it.

A frontier lane is the mean of three runs. Each run's `bench/`
keeps every answer of every run: `report.html` shows them side by side,
right in green, wrong in red and unknown in grey, and `lanes/` holds the
transcripts, with what `sate` understood each question as and each
lookup it tried, and the llama-server logs.

## How it is run

The benchmark is a cijoe workflow, `workflows/benchmark.yaml`, with its steps
in `scripts/`. `configs/default.toml` names everything a run depends on: the
documents, by a glob; the senfd release; llama-server, its threads and
context; the language models, by path and SHA-256, with where to download
them; and the frontier language models. It runs everything on this
machine, or llama-server on another one named by ssh; copy it, and change
what differs on yours. Then, in `benchmark/`:

    cijoe workflows/benchmark.yaml -c configs/default.toml -o results/<date>

It records the machine, the documents' SHA-256 and the senfd commit; makes a
virtual environment of that senfd and its data model of the documents; and
runs the lanes:

* `sate` reads each question by its words and names.
* For each language model, llama-server is started on the machine, CPU only,
  and reached through an ssh tunnel; `sate --llm` has it choose the
  lookups. The server is stopped and the tunnel closed after each language
  model.
* Each frontier model answers from memory, by `claude -p --safe-mode --tools
  ''`, in a fresh context of about 1,300 tokens, three times in each of two
  modes: "unknown" allowed, with a wrong answer counting against it, and
  answer required, every question answered. A run is one call answering them all,
  so its time a question is the call's time shared out.

Then `scripts/report.py` grades them, by `scripts/grade.py`, and writes
`summary.json` and `report.html`. A run takes about a quarter of an hour,
most of it the frontier lanes.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

The documents are not here and nothing made from them is, beyond the
transcripts' names, acronyms, bits and citations.
