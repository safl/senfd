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

.. list-table:: 2026-11-12, senfd 0.17.0, 86 questions; a Claude lane is the mean of three sessions
   :header-rows: 1
   :widths: 40 9 9 9 15 18

   * - Lane
     - Right
     - Wrong
     - Unknown
     - Seconds a question
     - USD a session
   * - ``sate``, no language model
     - 76
     - 2
     - 8
     - 0.006
     - none
   * - ``sate --llm``, Qwen 2.5 7B (Q4_K_M), CPU only
     - 71
     - 0
     - 15
     - 2.6
     - none
   * - ``sate --llm``, Qwen 2.5 1.5B (Q4_K_M), CPU only
     - 54
     - 0
     - 32
     - 1.3
     - none
   * - Opus, from memory, "unknown" allowed [#allowed]_
     - 58.7
     - 1
     - 26.3
     - 1.8
     - 0.46
   * - Opus, from memory, answer required [#required]_
     - 70.3
     - 15.3
     - 0.3
     - 2.5
     - 0.59
   * - Opus, with sate-mcp, "unknown" allowed
     - 86
     - 0
     - 0
     - 3.0
     - 2.07
   * - Opus, with sate-mcp, answer required
     - 86
     - 0
     - 0
     - 3.0
     - 2.27
   * - Opus, with the PDFs, "unknown" allowed
     - 86
     - 0
     - 0
     - 3.8
     - 3.17
   * - Opus, with the PDFs, answer required
     - 86
     - 0
     - 0
     - 3.7
     - 2.83
   * - Haiku, from memory, "unknown" allowed
     - 35
     - 2.7
     - 48.3
     - 1.3
     - 0.02
   * - Haiku, from memory, answer required
     - 41
     - 26.7
     - 18.3
     - 1.4
     - 0.02
   * - Haiku, with sate-mcp, "unknown" allowed
     - 84.3
     - 1
     - 0.7
     - 1.9
     - 0.12
   * - Haiku, with sate-mcp, answer required
     - 84
     - 2
     - 0
     - 2.0
     - 0.10
   * - Haiku, with the PDFs, "unknown" allowed
     - 84
     - 2
     - 0
     - 4.3
     - 0.49
   * - Haiku, with the PDFs, answer required
     - 84.3
     - 1.7
     - 0
     - 4.6
     - 0.35

.. [#allowed] Claude is told: "If you do not know, or are guessing, answer
   "unknown" rather than a guess; a wrong answer counts against you more
   than "unknown"."

.. [#required] Claude is told: "Give your best answer to every question."
   Each answer also carries a confidence of high, medium or low.

The seconds of a Claude lane are those of the question turns. The USD of a
session include the opening turn. The sessions with tools also record the
opening turn and the tool calls:

.. list-table:: The sessions with tools, as the means of three sessions
   :header-rows: 1
   :widths: 40 14 16 16 14

   * - Session
     - Model turns a question
     - Tokens in a question
     - Opening turn
     - Answers with no tool call (right)
   * - Opus, with sate-mcp, "unknown" allowed
     - 2.1
     - 73,499
     - 2.8 s, USD 0.004
     - 8.7 (8.7)
   * - Opus, with sate-mcp, answer required
     - 2.1
     - 82,116
     - 4.6 s, USD 0.004
     - 9 (9)
   * - Opus, with the PDFs, "unknown" allowed
     - 2.1
     - 107,923
     - 34.8 s, USD 0.13
     - 10 (10)
   * - Opus, with the PDFs, answer required
     - 2.1
     - 93,782
     - 26.3 s, USD 0.10
     - 8 (8)
   * - Haiku, with sate-mcp, "unknown" allowed
     - 2.0
     - 108,068
     - 3.0 s, USD 0.0004
     - 14.7 (14)
   * - Haiku, with sate-mcp, answer required
     - 2.1
     - 92,944
     - 2.2 s, USD 0.0001
     - 13.7 (13.3)
   * - Haiku, with the PDFs, "unknown" allowed
     - 2.6
     - 180,600
     - 18.1 s, USD 0.004
     - 7 (7)
   * - Haiku, with the PDFs, answer required
     - 2.4
     - 153,844
     - 17.7 s, USD 0.003
     - 8 (8)

Tokens in count the input tokens, the cache reads and the cache writes.

`The report <../_static/benchmark/report-2026-11-12-v0.17.0.html>`_ has
every question, the right answer with the PDF and figure that holds it, and
the answer of every lane and session. For ``sate``, the report shows what
``sate`` understood each question as. For Claude, the report shows the tool
calls behind each answer.

What the run recorded
---------------------

Opus answered all 86 questions right in each of its six sessions with
sate-mcp and in each of its six sessions with the PDFs. A session with
sate-mcp cost USD 2.07 to 2.27, and a session with the PDFs cost USD 2.83 to
3.17. The opening turn of a session with the PDFs took Opus 26.3 to 34.8
seconds and USD 0.10 to 0.13. In that turn, every session with the PDFs ran
``pdftotext`` on the PDFs.

Haiku answered 84 to 84.3 questions right with sate-mcp and 84 to 84.3 with
the PDFs. A Haiku session cost USD 0.10 to 0.12 with sate-mcp and USD 0.35 to
0.49 with the PDFs. With sate-mcp, Haiku gave the Sanitize Namespace command
the opcode 84h in three of its six sessions; the figure gives 8Ch. Haiku
gave Purge Required (PREQ) bit 4 of Command Dword 10 of Sanitize in three
sessions; the figure gives bit 11. With the PDFs, Haiku gave Namespace
Multi-path I/O and Namespace Sharing Capabilities (NMIC) byte 30 in four of
its six sessions; the figure gives byte 1.

Over the twelve sessions with the PDFs, Claude Code refused 53 tool calls,
33 of Haiku's and 20 of Opus's, because the command combined several
operations, held a variable, or wrote outside the working directory. Six
other tool calls ran and failed.

From memory, with an answer required, Opus answered 15.3 questions wrongly.
Opus gave the Sanitize Namespace command the opcode 85h in two sessions and
87h in the third. Haiku from memory, with an answer required, answered 26.7
questions wrongly, and still answered "unknown" to 18.3.

``sate`` answered 76 questions right in 6 milliseconds a question.
``sate`` answered questions 72 and 73, the PDU types of the TCP transport,
with the data structure of the PDU, in which the grader found no line that
gives the PDU type.
``sate`` answered "not known" to eight questions, from the Boot, PCIe, RDMA,
Computational Programs and Subsystem Local Memory documents.

``sate --llm`` answered no question wrongly. With Qwen 2.5 7B, ``sate --llm``
answered 71 questions right and 15 "not known". With Qwen 2.5 1.5B, ``sate
--llm`` answered 54 right and 32 "not known".

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
and that Claude may prepare them. Each condition runs in both modes, three
times. The full transcript of each session holds text of the documents, so
the benchmark writes the transcripts outside the repository and commits
only the answers, the figures of each turn and the tool calls.

The ``sate --llm`` lanes ran ``llama-server``, llama.cpp version 9905
(6fed91c10), on an AMD EPYC 7532 with 16 threads, a context of 8,192
tokens and no GPU offload. The language models are the published Q4_K_M
files, checked by their SHA-256. ``sate`` ran from a virtual environment of
senfd 0.17.0, against the data model that senfd 0.17.0 made of the eleven
PDFs, which were checked by their SHA-256 too.

An answer of ``sate`` is right when a line about the field, command,
feature or log page asked of gives the right value. An answer of Claude is
right when the value it writes is the right value and no other, so "1Fh
(Namespace Admin Label)" is right and "82h or 83h" is wrong. The grader
has its tests in ``benchmark/tests``.

The run of 2026-11-11 at senfd
0.17.0, the run of 2026-11-10 at senfd 0.14.0 and the run of 2026-11-09 at
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
and writes the report. The run of 2026-11-12 took 50 minutes, 41 of them in
the Claude sessions.
