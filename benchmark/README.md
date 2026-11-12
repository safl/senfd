<!--
SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>

SPDX-License-Identifier: LGPL-2.1-only
-->

# NVMe questions: frontier language models and senfd

`questions.json` holds 86 questions about the eleven NVMe documents ratified
in 2026, at least three from each document. Each question has one exact
answer: an opcode, an identifier, a status code, a bit or a byte offset.
Each question names its `source`, the PDF and the figure that holds the
answer, and each answer was checked against that figure.

The latest run, of 2026-11-12, asked all 86 questions with senfd 0.18.0.
The run made its data model from the PDFs that NVM Express publishes. The
run of 2026-11-12 with senfd 0.17.0 asked the 86 questions too, and asked
Claude both with "unknown" allowed and with an answer required. The runs
of 2026-11-11, 2026-11-10, 2026-11-09 and 2026-11-08 asked 71 or fewer of
the questions, and asked Claude Opus and Sonnet from memory only.

| Lane, 2026-11-12, senfd 0.18.0 | Right | Wrong | Unknown | Seconds a question | USD a session |
|---|---|---|---|---|---|
| `sate`, no language model | 86 | 0 | 0 | 0.007 | none |
| `sate --llm`, Qwen 2.5 7B Q4_K_M, CPU only | 72 | 0 | 14 | 2.7 | none |
| `sate --llm`, Qwen 2.5 1.5B Q4_K_M, CPU only | 57 | 0 | 29 | 1.2 | none |
| **Opus 5.5** | | | | | |
| From memory | 58 | 0.3 | 27.7 | 1.8 | 0.49 |
| With sate-mcp | 86 | 0 | 0 | 3.0 | 2.07 |
| With the PDFs | 86 | 0 | 0 | 3.9 | 3.22 |
| **Haiku 5.5** | | | | | |
| From memory | 35.7 | 4 | 46.3 | 1.4 | 0.02 |
| With sate-mcp | 85 | 0.7 | 0.3 | 2.0 | 0.16 |
| With the PDFs | 85 | 1 | 0 | 3.4 | 0.37 |

A Claude lane is the mean of three sessions. Each session was told that it
may answer "unknown", and that a wrong answer counts against it more than
"unknown". The seconds of a Claude lane are those of the question turns.
The USD of a session include the opening turn.

The opening turn and the tool calls of the sessions with tools, as the
means of three sessions:

| Session | Model turns a question | Tokens in a question | Opening turn | Answers with no tool call (right) |
|---|---|---|---|---|
| **Opus 5.5** | | | | |
| With sate-mcp | 2.0 | 74,735 | 6.6 s, USD 0.001 | 7.7 (7.7) |
| With the PDFs | 2.2 | 110,978 | 55.9 s, USD 0.14 | 8.7 (8.7) |
| **Haiku 5.5** | | | | |
| With sate-mcp | 1.9 | 100,551 | 2.2 s, under USD 0.0001 | 14.7 (14.3) |
| With the PDFs | 2.5 | 154,703 | 19.2 s, USD 0.003 | 8.3 (8.3) |

Tokens in count the input tokens, the cache reads and the cache writes. In
the opening turn with the PDFs, every session ran `pdftotext` on the PDFs.
Over the six sessions with the PDFs, Claude Code refused 28 tool calls, 15
of Haiku's and 13 of Opus's, because a command combined several operations,
held a variable, or wrote outside the working directory. Two other tool
calls ran and failed.

Each run's `bench/` keeps every answer: `report.html` shows them side by
side, right in green, wrong in red and unknown in grey, and `lanes/` holds
the lanes' records, with what `sate` understood each question as and each
lookup it tried, the tool calls of the Claude sessions, and the
llama-server logs. The records of a run take tens of thousands of lines, so
they are kept in a repository of their own, `~/git/senfd-results`, which is
not published. The documentation publishes the `report.html` of each run.

## How it is run

The benchmark is a cijoe workflow, `workflows/benchmark.yaml`, with its steps
in `scripts/`. `configs/default.toml` names everything a run depends on: the
documents, by a glob; the senfd release; llama-server, its threads and
context; the language models, by path and SHA-256, with where to download
them; and the frontier language models. The workflow runs everything on
this machine, or runs llama-server on another machine named by ssh. Copy
the configuration, and change what differs on your machine. Then, at the
top of the repository:

    make benchmark BENCHMARK_CONFIG=configs/default.toml

`make benchmark` runs `cijoe workflows/benchmark.yaml` in `benchmark/`, with
the output in `~/git/senfd-results/<date>-v<version>`; `RESULTS=<dir>`
names another directory. It refuses to run unless the configuration pins
the senfd release that the checkout is, and unless the directory exists.

The workflow records the machine, the documents' SHA-256 and the senfd
commit. The workflow then makes a virtual environment of that senfd, makes
the data model of the documents with it, and runs the lanes:

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
  Claude Code refuses a Bash command that combines several operations,
  holds a variable, or writes outside the working directory.
  The opening turn tells the model that the PDFs are there and lets it
  prepare them as it sees fit. The model may answer "unknown", and a wrong
  answer counts against it. `frontier.modes = ["required"]` in the
  configuration makes the model answer every question instead. The benchmark
  records the time, model turns, tokens and cost of every turn, and
  records the opening turn separately, because with the PDFs the opening
  turn is where the model processes them. The benchmark also records each
  tool call: the tool, its input, and whether its result was an error. An
  answer given with no tool call shows as such in the report. Each
  condition runs three times, so the report shows the spread
  between runs. The answers, the figures and the tool calls are kept with
  the run. The full transcript of each session, with the replies and
  the tools' output, holds text of the documents, so the benchmark writes it
  to `~/git/senfd-reports`, outside the repository.

Then `scripts/report.py` grades the answers with `scripts/grade.py`, and
writes `summary.json` and `report.html`. The run of 2026-11-12 with senfd
0.18.0 took 30 minutes. The frontier step took 21 minutes of that, and the
llm step 6.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

senfd's repository holds neither the documents nor anything made from
them, apart from the report of each run in the documentation.
