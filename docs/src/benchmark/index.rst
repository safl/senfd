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

.. list-table:: 2026-11-09, senfd 0.13.0, 71 questions; a frontier lane is the mean of three runs
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
     - free, 11 ms a question
   * - ``sate --llm``, Qwen 2.5 7B (Q4_K_M), CPU only
     - **69**
     - **0**
     - 2
     - free, 2.4 s a question
   * - ``sate --llm``, Qwen 2.5 1.5B (Q4_K_M), CPU only
     - 44
     - **0**
     - 27
     - free, 1.5 s a question
   * - Claude Opus 5.5, from memory, "unknown" allowed [#allowed]_
     - 53
     - 0
     - 18
     - USD 0.14 a run, 0.82 s a question
   * - Claude Opus 5.5, from memory, answer required [#required]_
     - 60.3
     - 10.7
     - 0
     - USD 0.14 a run, 0.88 s a question
   * - Claude Sonnet 5.5, from memory, "unknown" allowed [#allowed]_
     - 30
     - 6
     - 35
     - USD 0.02 a run, 0.14 s a question
   * - Claude Sonnet 5.5, from memory, answer required [#required]_
     - 38.3
     - 32.7
     - 0
     - USD 0.02 a run, 0.16 s a question

.. [#allowed] The frontier model is told: "If you do not know, or are
   guessing, answer "unknown" rather than a guess", and that a wrong answer
   counts against it. This measures whether it knows what it does not know.

.. [#required] The frontier model is told to give its best answer to every
   question, with a confidence of high, medium or low, and may not answer
   "unknown". This is how a chat answers a question put to it.

`The transcript <../_static/benchmark/report-2026-11-09-v0.13.0.html>`_ has
every question, the right answer, and the answer of every lane and run, with
what ``sate`` understood each question as and the time it took.

With answers required, a frontier model states wrong opcodes, identifiers
and bits in the same form as right ones. Opus gave the Host Addressable
Namespaces log page the identifier 83h in all three runs, where the figure
says 85h, and Sonnet gave Sanitize Namespace the opcode 84h, that of
Sanitize, in all three. Eight questions Opus got wrong in every run and
Sonnet twenty-seven, nearly all of them opcodes and identifiers. Asked for a
confidence, Opus marked 31 of its 32 wrong answers low and Sonnet 78 of its
98, so the guesses are there to be seen when asked for; a chat asks for
none. With "unknown" allowed, Opus said it of a quarter of the questions and
got none wrong, and Sonnet said it of half and still got six wrong. The
means move a little between runs of the workflow. Their training predates
the documents, which is the point: what a language model knows is the
revisions it was trained on, and the specifications move on.

A small language model on a CPU, used as ``sate --llm`` uses it, cannot
make the same mistake. It chooses the lookup, constrained to a query and
its argument, and the answer is what the lookup found in senfd's data model
of the documents, with the figure it cites. The 7 billion parameter
language model chose well for 69 of the 71 questions, and said of the two
left, a byte of an Identify data structure and the bits of a register, that
they are not known. The 1.5 billion parameter language model chose badly
for 27, of every kind, and said of those that they are not known: a weaker
language model costs answers, never correctness.

The questions are of facts with one answer, which a lookup answers and a
language model's memory may not. They are not questions of how to use a
feature, or why, where a frontier model's reasoning is worth its fee; given
``sate-mcp`` as tools, it has the facts as well. Nor are 71 questions every
question: what ``sate`` does not understand, it says it does not know, so
the cost of a question it cannot read is an answer, not a wrong one.

Method
------

Each frontier model answered from memory, with no tools and a system prompt
of its own, in a fresh context of about 1,300 tokens, by ``claude -p
--safe-mode --tools ''``, three times in each of two modes: "unknown" allowed, with a wrong answer
counting against it, and answer required, every question answered as a
chat does. Each run is one call answering all the
questions, so its time a question is the call's time shared out. The local
lanes ran ``llama-server``, a build of llama.cpp reporting 0.6.0-dev, commit
1bb2b9f, on an AMD EPYC 7532, 16 threads and no GPU offload, with the
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

The run shown made its data model from the PDFs NVM Express publishes, at
senfd 0.13.0, so anyone can repeat it. Two earlier runs are kept beside it.
That of 2026-11-09 at the commit before 0.9.1 had Llama 3.1 8B and Llama
3.2 1B choose the lookups, the first answering 70 and the second 37, none
wrongly; that of 2026-11-08 asked the first 30 of the questions from a data
model made of the ``.docx`` of the same documents, and ``sate`` answered
them the same. The CI job of every change makes the data model from the
public PDFs and has ``sate`` answer the same 71 questions from it, failing
unless every one is right.

Run it yourself
---------------

The benchmark is a `cijoe <https://cijoe.readthedocs.io/>`_ workflow, kept
with the transcripts of every run in senfd's `benchmark/
<https://github.com/safl/senfd/tree/main/benchmark>`_ directory: the
questions and their answers, the steps, and ``configs/default.toml``,
naming the documents, the senfd release and the language models. It runs on
your own machine. Download the PDFs as :ref:`making the data model
<sec-usage>` says, and the two language models from Hugging Face, by the
names the configuration gives. Have llama.cpp's ``llama-server`` on PATH,
and Claude Code logged in for the frontier lanes. Copy the configuration
where your machine differs.

.. code-block:: console

   $ cd benchmark && cijoe workflows/benchmark.yaml -c configs/default.toml -o results/$(date +%F)

It records what it ran on and with, makes a virtual environment of the
pinned senfd, makes the data model of the documents, runs every lane, and
writes the report. A run takes about a quarter of an hour, most of it the
frontier lanes.
