<!--
SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>

SPDX-License-Identifier: LGPL-2.1-only
-->

# NVMe questions: frontier language models and senfd

86 questions with one exact answer each, an opcode, an identifier, a
status code, a bit or a byte offset, about the eleven NVMe documents
ratified in 2026, at least three from each: the commands, features, log
pages and fields that recent revisions added or moved, the bits of the
registers, the opcodes of every command set, the fields of the Identify
data structures, the PDUs and descriptors of the transports and the boot
table, with a few long-standing facts among them. `questions.json` holds
them, each with its `source`: the PDF and the figure that holds the
answer, against which the answer was checked. The latest run,
`results/2026-11-11-v0.17.0`, asked the first 71 of them. It made its data
model from the PDFs NVM Express publishes, at senfd 0.17.0. Kept beside it are the runs of
2026-11-10 at senfd 0.14.0 and of 2026-11-09 at senfd 0.13.0, with the
same language models, the run of
2026-11-09 at senfd 75c370d, on the way to 0.9.1, with Llama 3.1 8B and
3.2 1B in place of Qwen, and the run of 2026-11-08, which asked the first
30 from a data model made of the `.docx`, at 0.8.0.

| Lane, 2026-11-11, senfd 0.17.0 | Right | Wrong | Unknown | Cost and time |
|---|---|---|---|---|
| `sate`, no language model | 71 | 0 | 0 | free, 10 ms a question[^time] |
| `sate --llm`, Qwen 2.5 7B Q4_K_M, CPU only | 69 | 0 | 2 | free, 2.6 s a question |
| `sate --llm`, Qwen 2.5 1.5B Q4_K_M, CPU only | 50 | 0 | 21 | free, 1.3 s a question |
| Claude Opus 5.5, from memory, "unknown" allowed[^allowed] | 50 | 0.3 | 20.7 | USD 0.10 a run, 0.56 s a question |
| Claude Opus 5.5, from memory, answer required[^required] | 57.7 | 13.3 | 0 | USD 0.13 a run, 0.79 s a question |
| Claude Sonnet 5.5, from memory, "unknown" allowed[^allowed] | 30.7 | 6.7 | 33.7 | USD 0.02 a run, 0.14 s a question |
| Claude Sonnet 5.5, from memory, answer required[^required] | 39.7 | 31.3 | 0 | USD 0.02 a run, 0.15 s a question |

[^time]: Twice that of the run before. Timed again on the same machine,
    with the same virtual environment and data model, `sate` answered in
    5 ms a question, as before; the run's 10 ms is the load of that
    machine while the lane ran.

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
* Each frontier model is asked the way a person asks Claude Code. The
  benchmark runs `claude -p` with no settings, so the session has no
  CLAUDE.md, memory or MCP server of yours, and runs it in an empty
  directory. One run is one session. The session starts with an opening
  turn, and then each question is a turn of its own, in order. Each
  session has one of three conditions. From memory, the session has no
  tools. With sate-mcp, the session's only tools are those of the MCP
  server, which serves the run's data model. With the PDFs, the session's
  working directory holds the PDFs, and its tools are Read, Grep and
  Glob, and Bash for `pdftotext`, `pdfinfo`, `grep`, `ls` and `mkdir`.
  The opening turn tells the model that the PDFs are there and lets it
  prepare them as it sees fit. Each condition runs in two modes: in one,
  the model may answer "unknown", and a wrong answer counts against it;
  in the other, the model must answer every question. The benchmark
  records the time, model turns, tokens and cost of every turn, and
  records the opening turn separately, because with the PDFs the opening
  turn is where the model processes them. The benchmark also records each
  tool call: the tool, its input, and whether its result was an error. An
  answer given with no tool call shows as such in the report. Each
  condition and mode runs three times, so the report shows the spread
  between runs. The answers, the figures and the tool calls are committed
  with the run. The full transcript of each session, with the replies and
  the tools' output, holds text of the documents, so the benchmark writes it
  to `~/git/senfd-reports`, outside the repository.

Then `scripts/report.py` grades them, by `scripts/grade.py`, and writes
`summary.json` and `report.html`. The frontier sessions take most of a
run's time, and their cost is that of the models asked.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

The documents are not here and nothing made from them is, beyond the
transcripts' names, acronyms, bits and citations.
