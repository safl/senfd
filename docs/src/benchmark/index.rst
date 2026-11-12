.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-benchmark:

Benchmark: frontier language models and senfd
=============================================

The benchmark asks 86 questions about the NVMe specifications. Each
question has one exact answer: an opcode, an identifier, a status code, a
bit or a byte offset. The questions cover the eleven documents ratified in
2026, at least three from each document. The questions ask of commands,
features, log pages and fields that the 2026 revisions added or moved, the
bits of registers, the opcodes of every command set, the fields of the
Identify data structures, and the PDUs and descriptors of the transports and
the boot table.

The benchmark asks ``sate`` alone, ``sate --llm`` with two small language
models on a CPU, and Claude Opus 5.5 and Claude Haiku 5.5 through Claude
Code. Claude is asked in three conditions: from memory, with sate-mcp, and
with the PDFs.

.. list-table:: 2026-11-12, senfd 0.19.0, 86 questions; a Claude lane is the mean of three sessions
   :header-rows: 1
   :widths: 40 9 9 9 15 18

   * - Lane
     - Right
     - Wrong
     - Unknown
     - Seconds a question
     - USD a session
   * - ``sate``, no language model
     - 86
     - 0
     - 0
     - 0.007
     - none
   * - ``sate --llm``, Qwen 2.5 7B (Q4_K_M), CPU only
     - 72
     - 0
     - 14
     - 2.7
     - none
   * - ``sate --llm``, Qwen 2.5 1.5B (Q4_K_M), CPU only
     - 57
     - 0
     - 29
     - 1.5
     - none
   * - **Opus 5.5**
     -
     -
     -
     -
     -
   * - From memory
     - 57
     - 1
     - 28
     - 1.8
     - 0.50
   * - With sate-mcp
     - 86
     - 0
     - 0
     - 2.9
     - 1.91
   * - With the PDFs
     - 86
     - 0
     - 0
     - 3.8
     - 3.16
   * - **Haiku 5.5**
     -
     -
     -
     -
     -
   * - From memory
     - 35.7
     - 3.7
     - 46.7
     - 1.2
     - 0.02
   * - With sate-mcp
     - 84.3
     - 1.7
     - 0
     - 2.0
     - 0.10
   * - With the PDFs
     - 84.7
     - 1
     - 0.3
     - 3.2
     - 0.45

Each Claude session is told: "If you do not know, or are guessing, answer
"unknown" rather than a guess; a wrong answer counts against you more than
"unknown"." The seconds of a Claude lane are those of the question turns.
The USD of a session include the opening turn. The sessions with tools also
record the opening turn and the tool calls:

.. list-table:: The sessions with tools, as the means of three sessions
   :header-rows: 1
   :widths: 40 14 16 16 14

   * - Session
     - Model turns a question
     - Tokens in a question
     - Opening turn
     - Answers with no tool call (right)
   * - **Opus 5.5**
     -
     -
     -
     -
   * - With sate-mcp
     - 2.0
     - 66,526
     - 2.6 s, USD 0.011
     - 7 (7)
   * - With the PDFs
     - 2.1
     - 106,429
     - 53.0 s, USD 0.15
     - 7 (7)
   * - **Haiku 5.5**
     -
     -
     -
     -
   * - With sate-mcp
     - 2.0
     - 87,944
     - 2.1 s, USD 0.0003
     - 14.3 (13.7)
   * - With the PDFs
     - 2.6
     - 175,012
     - 20.0 s, USD 0.004
     - 7 (7)

Tokens in count the input tokens, the cache reads and the cache writes.

`The report <../_static/benchmark/report-2026-11-12-v0.19.0.html>`_ has
every question, the right answer with the PDF and figure that holds it, and
the answer of every lane and session. For ``sate``, the report shows what
``sate`` understood each question as. For Claude, the report shows the tool
calls behind each answer.

What the run recorded
---------------------

With a source, Opus and Haiku answered almost every question right. Opus
answered all 86 questions right in each of its three sessions with
sate-mcp and in each of its three sessions with the PDFs. From memory, Opus
answered 57 right and 28 "unknown". Haiku answered 84.3 questions right
with sate-mcp, 84.7 with the PDFs, and 35.7 from memory.

A source costs more than memory. An Opus session cost USD 0.50 from
memory, USD 1.91 with sate-mcp and USD 3.16 with the PDFs. A Haiku session
cost USD 0.02, USD 0.10 and USD 0.45. With sate-mcp, an Opus session cost
39% less than with the PDFs, and a Haiku session 78% less. Haiku with
sate-mcp answered 84.3 questions right at USD 0.10 a session. Opus with the
PDFs answered 86 right at USD 3.16 a session, 32 times as much.

The opening turn of a session with the PDFs took Opus 53.0 seconds and USD
0.15, and Haiku 20.0 seconds. In that turn, each of the six sessions with
the PDFs ran ``pdftotext`` on the PDFs. 29 of the 57 ``pdftotext`` calls of
the six opening turns returned errors, and each session had at least one
call that ran without an error. The cost with the PDFs is that of the PDFs as
NVM Express publishes them, prepared by Claude Code in the way it chose;
the benchmark measured no other preparation.

``sate`` with no language model answered all 86 questions right, in 7
milliseconds a question, at no cost a question. ``sate --llm`` answered no
question wrongly: 72 right with Qwen 2.5 7B and 57 with Qwen 2.5 1.5B.

Haiku with sate-mcp gave Purge Required (PREQ) bit 4 of Command Dword 10
of Sanitize in two sessions; the figure gives bit 11. Haiku with sate-mcp
answered "08h and 1Fh" and "08h, 1Fh" for the CNS value that returns the
I/O Command Set Independent Identify Namespace data structure in two
sessions; the figure gives 08h alone. Haiku with sate-mcp gave the Sanitize
Namespace command the opcode 84h in one session; the figure gives 8Ch. With
the PDFs, Haiku gave the Memory Copy command of the Subsystem Local Memory
Command Set the opcode 05h in two sessions, and answered "unknown" in the
third; the figure gives 01h. With the PDFs, Haiku gave Controller Ready
Independent of Media Enable (CRIME) bit 31 of the CC register in one
session; the figure gives bit 24. From memory, Haiku answered 11 questions
wrongly over its three sessions, among them CNS 05h for the I/O Command Set
Independent Identify Namespace data structure in all three, where the
figure gives 08h, and the Sanitize Namespace opcode 84h in two. Opus from
memory answered three questions wrongly in its third session: 1Bh for the
Log Page Identifier of Rotational Media Information, where the figure gives
16h; 03h for the RDMA transport error RDMA Invalid HSQSIZE, where the
figure gives 04h; and 04h for the descriptor type of the HFI Descriptor of
the NBFT, where the figure gives 03h.

Over the six sessions with the PDFs, Claude Code refused 22 tool calls, 13
of Haiku's and 9 of Opus's. 13 other tool calls ran and failed.

Method
------

Claude is asked through ``claude -p`` with no settings, so a session has no
``CLAUDE.md``, memory or MCP server of the person running the benchmark. One
run is one session. The session starts with an opening turn, and then each
question is a turn of its own, in order. From memory, the session has no
tools. With sate-mcp, the session's only tools are those of the MCP server,
which serves the run's data model. With the PDFs, the session's working
directory holds the PDFs, and its tools are Read, Grep and Glob, and Bash
for ``pdftotext``, ``pdfinfo``, ``grep``, ``ls`` and ``mkdir``. The opening
turn with the PDFs tells Claude that the PDFs are in the working directory
and that Claude may prepare them. Each condition runs three times.
``frontier.modes = ["required"]`` in the configuration tells Claude to give
its best answer to every question instead of "unknown". The full transcript of each session holds text of the documents, so
the benchmark writes the transcripts outside the repository and commits
only the answers, the figures of each turn and the tool calls.

The ``sate --llm`` lanes ran ``llama-server``, llama.cpp version 9905
(6fed91c10), on an AMD EPYC 7532 with 16 threads, a context of 8,192
tokens, ``--device none`` and no GPU visible. The language models are the
published Q4_K_M files, checked by their SHA-256. ``sate`` ran from a
virtual environment of senfd 0.19.0, against the data model that senfd
0.19.0 made of the eleven PDFs, which were checked by their SHA-256 too.

An answer of ``sate`` is right when a line about the field, command,
feature or log page asked of gives the right value. An answer of Claude is
right when the value it writes is the right value and no other, so "1Fh
(Namespace Admin Label)" is right and "82h or 83h" is wrong. The grader
has its tests in ``benchmark/tests``.

The run of 2026-11-12 at senfd 0.18.0 asked the same questions in the same
way; its `report <../_static/benchmark/report-2026-11-12-v0.18.0.html>`__ is
kept. The run of 2026-11-12 at senfd 0.17.0 asked the 86 questions, and asked
Claude both with "unknown" allowed and with an answer required; its
`report <../_static/benchmark/report-2026-11-12-v0.17.0.html>`_ is kept.
The run of 2026-11-11 at senfd 0.17.0, the run of 2026-11-10 at senfd 0.14.0 and the run of 2026-11-09 at
senfd 0.13.0 asked the first 71 questions, and asked Claude Opus and Sonnet
from memory only. The run of 2026-11-09 at the commit before senfd 0.9.1
had Llama 3.1 8B and Llama 3.2 1B choose the lookups. The run of 2026-11-08
asked the first 30 questions from a data model made of the ``.docx`` of the
same documents.

The CI job of every change makes the data model from the public PDFs, has
``sate`` answer the benchmark's questions from it, and fails unless every
answer is right.

Run it yourself
---------------

The benchmark is a `cijoe <https://cijoe.readthedocs.io/>`_ workflow, kept
in senfd's `benchmark/ <https://github.com/safl/senfd/tree/main/benchmark>`_
directory: the questions and their answers, the steps, and
``configs/default.toml``, which
names the documents, the senfd release and the language models. Download
the PDFs as :ref:`making the data model <sec-usage>` describes, and the two
language models from Hugging Face, by the names that the configuration
gives. Have llama.cpp's ``llama-server`` on PATH, and Claude Code logged in
for the Claude lanes. Copy the configuration where your machine differs.

.. code-block:: console

   $ make benchmark BENCHMARK_CONFIG=configs/default.toml

``make benchmark`` runs the workflow in ``benchmark/``, with the output in
``~/git/senfd-results/<date>-v<version>``, and ``RESULTS=<dir>`` names
another directory. ``make benchmark`` refuses to run unless the
configuration pins the senfd release that the checkout is, and unless the
directory exists. The records of a run are kept outside senfd's
repository, and the documentation publishes the report of each run.

The workflow records what it ran on and with, makes a virtual environment of
the pinned senfd, makes the data model of the documents, runs every lane,
and writes the report. The run of 2026-11-12 with senfd 0.19.0 took 28
minutes, 19 of them in the Claude sessions.
