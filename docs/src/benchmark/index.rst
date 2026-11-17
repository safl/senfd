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

.. list-table:: 2026-11-17, senfd 0.23.0, 86 questions; a Claude lane is the mean of three sessions
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
     - 0.009
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
     - 1.2
     - none
   * - **Opus 5.5**
     -
     -
     -
     -
     -
   * - From memory
     - 58.7
     - 0
     - 27.3
     - 2.0
     - 0.52
   * - With sate-mcp
     - 86
     - 0
     - 0
     - 2.7
     - 1.59
   * - With the PDFs
     - 86
     - 0
     - 0
     - 4.3
     - 3.20
   * - **Haiku 5.5**
     -
     -
     -
     -
     -
   * - From memory
     - 37.7
     - 4
     - 44.3
     - 1.6
     - 0.02
   * - With sate-mcp
     - 84.7
     - 1
     - 0.3
     - 2.3
     - 0.10
   * - With the PDFs
     - 84
     - 2
     - 0
     - 5.5
     - 0.37

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
     - 1.8
     - 52,603
     - 2.7 s, USD 0.012
     - 25 (25)
   * - With the PDFs
     - 2.2
     - 106,539
     - 30.2 s, USD 0.13
     - 7 (7)
   * - **Haiku 5.5**
     -
     -
     -
     -
   * - With sate-mcp
     - 1.9
     - 92,069
     - 4.1 s, USD 0.0003
     - 15.7 (15.3)
   * - With the PDFs
     - 2.7
     - 172,630
     - 19.7 s, USD 0.003
     - 7.7 (7.7)

Tokens in count the input tokens, the cache reads and the cache writes.

`The report <../_static/benchmark/report-2026-11-17-v0.23.0.html>`_ has
every question, the right answer with the PDF and figure that holds it, and
the answer of every lane and session. For ``sate``, the report shows what
``sate`` understood each question as. For Claude, the report shows the tool
calls behind each answer.

What the run recorded
---------------------

With a source, Opus and Haiku answered almost every question right. Opus
answered all 86 questions right in each of its three sessions with
sate-mcp and in each of its three sessions with the PDFs. From memory, Opus
answered 58.7 right and 27.3 "unknown". Haiku answered 84.7 questions right
with sate-mcp, 84 with the PDFs, and 37.7 from memory.

A source costs more than memory. An Opus session cost USD 0.52 from
memory, USD 1.59 with sate-mcp and USD 3.20 with the PDFs. A Haiku session
cost USD 0.02, USD 0.10 and USD 0.37. With sate-mcp, an Opus session cost
50% less than with the PDFs, and a Haiku session 73% less. Haiku with
sate-mcp answered 84.7 questions right at USD 0.10 a session. Opus with the
PDFs answered 86 right at USD 3.20 a session, 32 times as much.

The opening turn of a session with the PDFs took Opus 30.2 seconds and USD
0.13, and Haiku 19.7 seconds. In that turn, each of the six sessions with
the PDFs ran ``pdftotext`` on the PDFs. 19 of the 33 ``pdftotext`` calls of
the six opening turns returned errors. In two of Haiku's three sessions,
every ``pdftotext`` call of the opening turn returned an error. The cost
with the PDFs is that of the PDFs as NVM Express publishes them, prepared
by Claude Code in the way it chose; the benchmark measured no other
preparation.

``sate`` with no language model answered all 86 questions right, in 9
milliseconds a question, at no cost a question. ``sate --llm`` answered no
question wrongly: 72 right with Qwen 2.5 7B and 57 with Qwen 2.5 1.5B.

Haiku with sate-mcp gave the Sanitize Namespace command the opcode 84h in
two sessions; the figure gives 8Ch. In its third session with sate-mcp,
Haiku gave bit 4 of Command Dword 10 of Sanitize for Purge Required (PREQ);
the figure gives bit 11. In one session with sate-mcp, Haiku answered
"unknown" for the descriptor type designator of the HFI Descriptor of the
NVMe Boot Firmware Table (NBFT).

With the PDFs, Haiku gave byte 30 for Namespace Multi-path I/O and
Namespace Sharing Capabilities (NMIC) of the I/O Command Set Independent
Identify Namespace data structure in all three sessions; the figure gives
byte 1. Haiku with the PDFs also gave the Memory Copy command of the
Subsystem Local Memory Command Set the opcode 05h in two sessions, where the
figure gives 01h, and the Sanitize Namespace opcode 84h in one session.

From memory, Haiku answered 12 questions wrongly over its three sessions.
Haiku gave byte 30 for NMIC and CNS 05h for the I/O Command Set Independent
Identify Namespace data structure in all three sessions, and the Sanitize
Namespace opcode 84h in two. Opus answered no question wrongly in any of
its nine sessions.

Over the six sessions with the PDFs, Claude Code refused 29 tool calls, 19
of Haiku's and 10 of Opus's. One other tool call ran and failed.

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
virtual environment of senfd 0.23.0, against the data model that senfd
0.23.0 made of the eleven PDFs, which were checked by their SHA-256 too.

An answer of ``sate`` is right when a line about the field, command,
feature or log page asked of gives the right value. An answer of Claude is
right when the value it writes is the right value and no other, so "1Fh
(Namespace Admin Label)" is right and "82h or 83h" is wrong. The grader
has its tests in ``benchmark/tests``.

The run of 2026-11-16 at senfd 0.22.0 and the runs of 2026-11-12 at senfd
0.19.0 and 0.18.0 asked the same questions in the same way; their reports,
of `0.22.0 <../_static/benchmark/report-2026-11-16-v0.22.0.html>`__,
`0.19.0 <../_static/benchmark/report-2026-11-12-v0.19.0.html>`__ and
`0.18.0 <../_static/benchmark/report-2026-11-12-v0.18.0.html>`__, are kept.
The run of 2026-11-12 at senfd 0.17.0 asked the 86 questions, and asked
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
and writes the report. The run of 2026-11-17 with senfd 0.23.0 took 34
minutes, 24 of them in the Claude sessions.
