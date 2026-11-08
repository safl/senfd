<!--
SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>

SPDX-License-Identifier: LGPL-2.1-only
-->

# NVMe questions: frontier language models and senfd

30 questions with one exact answer each, an opcode, an identifier, a bit
or a byte offset, about the eleven NVMe documents ratified in 2026. Eight
are of long-standing facts, the rest of commands, features, log pages and
fields that recent revisions added or moved. Each right answer was checked
against the figure that gives it. `questions.json` holds them.

`sate` was named `senfd-ask` when these ran; their records say so.

| Lane, 2026-11-08 | Right | Wrong | Unknown | Cost and time |
|---|---|---|---|---|
| `sate`, no language model | 30 | 0 | 0 | free, 4 ms a question |
| `sate --llm`, Llama 3.1 8B Q4_K_M, CPU only | 30 | 0 | 0 | free, 2.7 s a question |
| `sate --llm`, Llama 3.2 1B Q4_K_M, CPU only | 18 | 0 | 12 | free, 1.1 s a question |
| Claude Opus 5.5, from memory, "unknown" allowed | 23 | 0.7 | 6.3 | USD 0.12 a run |
| Claude Opus 5.5, from memory, answer required | 25.3 | 4.7 | 0 | USD 0.17 a run |
| Claude Sonnet 5.5, from memory, "unknown" allowed | 20.7 | 2.3 | 7 | USD 0.07 a run |
| Claude Sonnet 5.5, from memory, answer required | 22.3 | 7.7 | 0 | USD 0.07 a run |

A frontier lane is the mean of three runs. `results/2026-11-08/bench/`
keeps every answer of every run: `report.html` shows them side by side,
right in green, wrong in red and unknown in grey, and `lanes/` holds the
transcripts, with what `sate` understood each question as and each
lookup it tried, and the llama-server logs.

## How it is run

The benchmark is a cijoe workflow, `workflows/benchmark.yaml`, with its steps
in `scripts/`. `configs/epyc-02.toml` names everything a run depends on: the
documents, by a glob; the senfd commit; the machine running llama-server,
its binary, threads and context; the language models, by path and SHA-256;
and the frontier language models; it is the lab's, so make one of your own
for your machine and documents. Claim the machine with dibs, then, in
`benchmark/`:

    cijoe workflows/benchmark.yaml -c configs/epyc-02.toml -o results/<date>

It records the machine, the documents' SHA-256 and the senfd commit; makes a
virtual environment of that senfd and its data model of the documents; and
runs the lanes:

* `sate` reads each question by its words and names.
* For each language model, llama-server is started on the machine, CPU only,
  and reached through an ssh tunnel; `sate --llm` has it choose the
  lookups. The server is stopped and the tunnel closed after each language
  model.
* Each frontier model answers from memory, by `claude -p --safe-mode --tools
  ''`, in a fresh context of about 570 tokens, three times in each of two
  modes: allowed to say "unknown", with a wrong answer counting against it,
  and told to answer every question.

Then `scripts/report.py` grades them, by `scripts/grade.py`, and writes
`summary.json` and `report.html`. A run takes about seven minutes.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

The documents are not here and nothing made from them is, beyond the
transcripts' names, acronyms, bits and citations.
