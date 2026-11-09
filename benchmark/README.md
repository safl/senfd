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
figure that gives it. `questions.json` holds them. The run of 2026-11-09
made its data model from the PDFs NVM Express publishes, at senfd 75c370d
on the way to 0.9.1; the run of 2026-11-08, kept beside it, asked the
first 30 from a data model made of the `.docx`, at 0.8.0.

| Lane, 2026-11-09 | Right | Wrong | Unknown | Cost and time |
|---|---|---|---|---|
| `sate`, no language model | 71 | 0 | 0 | free, 4 ms a question |
| `sate --llm`, Llama 3.1 8B Q4_K_M, CPU only | 70 | 0 | 1 | free, 2.7 s a question |
| `sate --llm`, Llama 3.2 1B Q4_K_M, CPU only | 37 | 0 | 34 | free, 1.3 s a question |
| Claude Opus 5.5, from memory, "unknown" allowed | 50.3 | 1.3 | 19.3 | USD 0.08 a run, 0.51 s a question |
| Claude Opus 5.5, from memory, answer required | 55.7 | 15.3 | 0 | USD 0.10 a run, 0.66 s a question |
| Claude Sonnet 5.5, from memory, "unknown" allowed | 38.7 | 4.3 | 28 | USD 0.03 a run, 0.30 s a question |
| Claude Sonnet 5.5, from memory, answer required | 38.7 | 32.3 | 0 | USD 0.02 a run, 0.13 s a question |

A frontier lane is the mean of three runs. `results/2026-11-09/bench/`
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
  modes: allowed to say "unknown", with a wrong answer counting against it,
  and told to answer every question. A run is one call answering them all,
  so its time a question is the call's time shared out.

Then `scripts/report.py` grades them, by `scripts/grade.py`, and writes
`summary.json` and `report.html`. A run takes about a quarter of an hour,
most of it the frontier lanes.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

The documents are not here and nothing made from them is, beyond the
transcripts' names, acronyms, bits and citations.
