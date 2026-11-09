.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-benchmark:

Benchmark: frontier language models and senfd
=============================================

Fast, accurate answers, for free, on your own hardware, free of frontier
fees and frontier hallucinations: that is a claim, and this is the
experiment behind it. 71 questions about the NVMe specifications, each with
one exact answer, an opcode, an identifier, a status code, a bit or a byte
offset: the commands, features, log pages and fields that the revisions
ratified in 2026 added or moved, the bits of the registers, the opcodes of
every command set and the fields of the Identify data structures, with a
few long-standing facts among them.

.. list-table:: 2026-11-09, 71 questions; a frontier lane is the mean of three runs
   :header-rows: 1
   :widths: 46 10 10 10 24

   * - Lane
     - Right
     - Wrong
     - Unknown
     - Cost and time
   * - ``sate``, no language model
     - **71**
     - **0**
     - 0
     - free, 4 ms a question
   * - ``sate --llm``, Llama 3.1 8B (Q4_K_M), CPU only
     - **70**
     - **0**
     - 1
     - free, 2.7 s a question
   * - ``sate --llm``, Llama 3.2 1B (Q4_K_M), CPU only
     - 37
     - **0**
     - 34
     - free, 1.3 s a question
   * - Claude Opus 5.5, from memory, "unknown" allowed
     - 50.3
     - 1.3
     - 19.3
     - USD 0.08 a run
   * - Claude Opus 5.5, from memory, answer required
     - 55.7
     - 15.3
     - 0
     - USD 0.10 a run
   * - Claude Sonnet 5.5, from memory, "unknown" allowed
     - 38.7
     - 4.3
     - 28
     - USD 0.03 a run
   * - Claude Sonnet 5.5, from memory, answer required
     - 38.7
     - 32.3
     - 0
     - USD 0.02 a run

`The transcript <../_static/benchmark/report-2026-11-09.html>`_ has every
question, the right answer, and the answer of every lane and run, with what
``sate`` understood each question as and the time it took.

Told to answer, as a chat does, a frontier model states wrong opcodes,
identifiers and bits as confidently as right ones: Opus gave Sanitize
Namespace the opcode 85h in all three runs, where the figure says 8Ch, and
Sonnet 84h, the opcode of Sanitize, in all three. Twelve questions Opus got
wrong in every run and Sonnet twenty-six, nearly all of them the opcodes
and identifiers the 2026 revisions added. Allowed to say "unknown", they
say it of a quarter to a third of the questions and still miss some. The
means move a little between runs of the workflow. Their training predates
the documents, which is the point: what a language model knows is the
revisions it was trained on, and the specifications move on.

A small language model on a CPU, used as ``sate --llm`` uses it, cannot
make the same mistake. It chooses the lookup, constrained to a query and
its argument, and the answer is what the lookup found in senfd's data model
of the documents, with the figure it cites. The 8 billion parameter
language model chose well for 70 of the 71 questions, and said of the one
left, a byte of a data structure named by its command, that it is not
known. The 1 billion parameter language model chose badly for 34, most of
them questions of a dword's or a register's bits, and said of those that
they are not known: a weaker language model costs answers, never
correctness.

The questions are of facts with one answer, which a lookup answers and a
language model's memory may not. They are not questions of how to use a
feature, or why, where a frontier model's reasoning is worth its fee; given
``sate-mcp`` as tools, it has the facts as well. Nor are 71 questions every
question: what ``sate`` does not understand, it says it does not know, so
the cost of a question it cannot read is an answer, not a wrong one.

Method
------

Each frontier model answered from memory, with no tools and a system prompt
of its own, in a fresh context of about 570 tokens, by ``claude -p
--safe-mode --tools ''``, three times in each of two modes: allowed to say
"unknown", with a wrong answer counting against it, and told to answer
every question, as a chat does. The local lanes ran ``llama-server`` of
llama.cpp on an AMD EPYC 7532, 16 threads and no GPU offload, with the
language models as published, Q4_K_M, checked by their SHA-256. ``sate``
ran from a pinned commit of senfd, against the data model it made of the
eleven documents ratified in 2026, the documents checked by their SHA-256
too.

An answer of ``sate`` is right when a line about the field, command,
feature or log page asked of gives the right value; a frontier model's,
when the value it writes is the right one and no other, so "1Fh (Namespace
Admin Label)" is right and "82h or 83h" is wrong. The grader has its tests
in ``benchmark/tests``. Each right answer was checked against the figure
that gives it.

The run of 2026-11-09 made its data model from the PDFs NVM Express
publishes, at the commit before 0.9.1, so anyone can repeat it; the run of
2026-11-08, kept beside it, asked the first 30 of the questions from a data
model made of the ``.docx`` of the same documents, and ``sate`` answered
them the same. The CI job of every change makes the data model from the
public PDFs and has ``sate`` answer the same 71 questions from it, failing
unless every one is right.

Run it yourself
---------------

The benchmark is a `cijoe <https://cijoe.readthedocs.io/>`_ workflow, kept
with the transcripts of every run in senfd's `benchmark/
<https://github.com/safl/senfd/tree/main/benchmark>`_ directory: the
questions and their answers, the steps, and a configuration naming the
documents, the senfd commit, the machine and the language models. The
documents are not in it; bring your own.

.. code-block:: console

   $ cd benchmark && cijoe workflows/benchmark.yaml -c configs/epyc-02.toml -o results/$(date +%F)

It records what it ran on and with, makes a virtual environment of the
pinned senfd, makes the data model of the documents, runs every lane, and
writes the report. A run takes about a quarter of an hour, most of it the
frontier lanes.
