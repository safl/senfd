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

The latest run, `results/2026-11-12-v0.17.0`, asked all 86 questions. The
run made its data model from the PDFs that NVM Express publishes, with
senfd 0.17.0. The runs of 2026-11-11, 2026-11-10, 2026-11-09 and 2026-11-08
are kept beside it. Those runs asked 71 or fewer of the questions, and
asked Claude Opus and Sonnet from memory only.

| Lane, 2026-11-12, senfd 0.17.0 | Right | Wrong | Unknown | Seconds a question | USD a session |
|---|---|---|---|---|---|
| `sate`, no language model | 76 | 2 | 8 | 0.006 | none |
| `sate --llm`, Qwen 2.5 7B Q4_K_M, CPU only | 71 | 0 | 15 | 2.6 | none |
| `sate --llm`, Qwen 2.5 1.5B Q4_K_M, CPU only | 54 | 0 | 32 | 1.3 | none |
| Opus 5.5, from memory, "unknown" allowed | 58.7 | 1 | 26.3 | 1.8 | 0.46 |
| Opus 5.5, from memory, answer required | 70.3 | 15.3 | 0.3 | 2.5 | 0.59 |
| Opus 5.5, with sate-mcp, "unknown" allowed | 86 | 0 | 0 | 3.0 | 2.07 |
| Opus 5.5, with sate-mcp, answer required | 86 | 0 | 0 | 3.0 | 2.27 |
| Opus 5.5, with the PDFs, "unknown" allowed | 86 | 0 | 0 | 3.8 | 3.17 |
| Opus 5.5, with the PDFs, answer required | 86 | 0 | 0 | 3.7 | 2.83 |
| Haiku 5.5, from memory, "unknown" allowed | 35 | 2.7 | 48.3 | 1.3 | 0.02 |
| Haiku 5.5, from memory, answer required | 41 | 26.7 | 18.3 | 1.4 | 0.02 |
| Haiku 5.5, with sate-mcp, "unknown" allowed | 84.3 | 1 | 0.7 | 1.9 | 0.12 |
| Haiku 5.5, with sate-mcp, answer required | 84 | 2 | 0 | 2.0 | 0.10 |
| Haiku 5.5, with the PDFs, "unknown" allowed | 84 | 2 | 0 | 4.3 | 0.49 |
| Haiku 5.5, with the PDFs, answer required | 84.3 | 1.7 | 0 | 4.6 | 0.35 |

A Claude lane is the mean of three sessions. The seconds of a Claude lane
are those of the question turns. The USD of a session include the opening
turn. In the answer-required mode, Haiku from memory still answered
"unknown" to 18.3 questions.

The opening turn and the tool calls of the sessions with tools, as the
means of three sessions:

| Session | Model turns a question | Tokens in a question | Opening turn | Answers with no tool call (right) |
|---|---|---|---|---|
| Opus, with sate-mcp, "unknown" allowed | 2.1 | 73,499 | 2.8 s, USD 0.004 | 8.7 (8.7) |
| Opus, with sate-mcp, answer required | 2.1 | 82,116 | 4.6 s, USD 0.004 | 9 (9) |
| Opus, with the PDFs, "unknown" allowed | 2.1 | 107,923 | 34.8 s, USD 0.13 | 10 (10) |
| Opus, with the PDFs, answer required | 2.1 | 93,782 | 26.3 s, USD 0.10 | 8 (8) |
| Haiku, with sate-mcp, "unknown" allowed | 2.0 | 108,068 | 3.0 s, USD 0.0004 | 14.7 (14) |
| Haiku, with sate-mcp, answer required | 2.1 | 92,944 | 2.2 s, USD 0.0001 | 13.7 (13.3) |
| Haiku, with the PDFs, "unknown" allowed | 2.6 | 180,600 | 18.1 s, USD 0.004 | 7 (7) |
| Haiku, with the PDFs, answer required | 2.4 | 153,844 | 17.7 s, USD 0.003 | 8 (8) |

Tokens in count the input tokens, the cache reads and the cache writes. In
the opening turn with the PDFs, every session ran `pdftotext` on the PDFs.
Over the twelve sessions with the PDFs, Claude Code refused 53 tool calls,
33 of Haiku's and 20 of Opus's, because a command combined several
operations, held a variable, or wrote outside the working directory. Six
other tool calls ran and failed.

`sate` answered questions 72 and 73, the PDU types of the TCP transport,
with the PDU's data structure, in which the grader found no line that gives
the PDU type. `sate` answered "not known" to eight questions of the Boot,
PCIe, RDMA, Computational Programs and Subsystem Local Memory documents.

Each run's `bench/` keeps every answer: `report.html` shows them side by
side, right in green, wrong in red and unknown in grey, and `lanes/` holds
the lanes' records, with what `sate` understood each question as and each
lookup it tried, the tool calls of the Claude sessions, and the
llama-server logs.

## How it is run

The benchmark is a cijoe workflow, `workflows/benchmark.yaml`, with its steps
in `scripts/`. `configs/default.toml` names everything a run depends on: the
documents, by a glob; the senfd release; llama-server, its threads and
context; the language models, by path and SHA-256, with where to download
them; and the frontier language models. The workflow runs everything on
this machine, or runs llama-server on another machine named by ssh. Copy
the configuration, and change what differs on your machine. Then, in
`benchmark/`:

    cijoe workflows/benchmark.yaml -c configs/default.toml -o results/<date>

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

Then `scripts/report.py` grades the answers with `scripts/grade.py`, and
writes `summary.json` and `report.html`. The run of 2026-11-12 took 50
minutes. The frontier step took 41 minutes of that, and the llm step 6.
`tests/` holds the tests of the scripts, which senfd's `make test` runs.

The repository holds neither the documents nor anything made from them,
apart from the names, acronyms, bits and citations in the lanes' records.
