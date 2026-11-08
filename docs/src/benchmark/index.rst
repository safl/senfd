.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-benchmark:

Benchmark: frontier language models and senfd
=============================================

**Fast, accurate answers, for free, on your own hardware, free of frontier
fees and frontier hallucinations.** That is a claim, so here is the
experiment behind it: 30 questions about the NVMe specifications, each with
one exact answer, an opcode, an identifier, a bit or a byte offset. Eight are
long-standing facts; the rest are commands, features, log pages and fields
that the revisions ratified in 2026 added or moved.

.. list-table:: 2026-11-08, 30 questions; a frontier lane is the mean of three runs
   :header-rows: 1
   :widths: 46 10 10 10 24

   * - Lane
     - Right
     - Wrong
     - Unknown
     - Cost and time
   * - ``senfd-ask``, no language model
     - **30**
     - **0**
     - 0
     - free, 3 ms a question
   * - ``senfd-ask --llm``, Llama 3.1 8B (Q4_K_M), CPU only
     - **30**
     - **0**
     - 0
     - free, 2.8 s a question
   * - ``senfd-ask --llm``, Llama 3.2 1B (Q4_K_M), CPU only
     - 20
     - **0**
     - 10
     - free, 1.0 s a question
   * - Claude Opus 5.5, from memory, "unknown" allowed
     - 23
     - 0.3
     - 6.7
     - USD 0.13 a run
   * - Claude Opus 5.5, from memory, answer required
     - 25
     - 5
     - 0
     - USD 0.15 a run
   * - Claude Sonnet 5.5, from memory, "unknown" allowed
     - 20.3
     - 2
     - 7.7
     - USD 0.07 a run
   * - Claude Sonnet 5.5, from memory, answer required
     - 19.3
     - 10.7
     - 0
     - USD 0.03 a run

Asked to answer, as a chat does, a frontier model states wrong opcodes,
identifiers and bits as confidently as right ones: Opus gave Sanitize
Namespace the opcode 85h in all three runs, where the figure says 8Ch, and
Sonnet put Purge Required at bit 13 of CDW10, where it is bit 11. Allowed to
say "unknown", they say it of what they do not know and still miss. Their
training predates the documents, which is the point: what a language model
knows is the revisions it was trained on, and the specifications move on.

A small language model on a CPU, used as ``senfd-ask --llm`` uses it, cannot
make the same mistake. It chooses the lookup, constrained to a query and its
argument, and the answer is what the lookup found in senfd's data model of the
documents, with the figure it cites. The 8 billion parameter language model
chose well for every question. The 1 billion parameter language model chose
badly for ten, the questions of a dword's bits, and said of those that they
are not known: a weaker language model costs answers, never correctness.

.. raw:: html

   <div class="bench-tabs">
     <input type="radio" name="bench-tab" id="bench-tab-transcript" checked>
     <label for="bench-tab-transcript">Transcript</label>
     <input type="radio" name="bench-tab" id="bench-tab-method">
     <label for="bench-tab-method">Method</label>
     <input type="radio" name="bench-tab" id="bench-tab-repeat">
     <label for="bench-tab-repeat">Run it yourself</label>
     <div class="bench-panel" id="bench-panel-transcript">
       <p>Every question, the right answer, and the answer of every lane and
       run: <span style="color:#1a7f37">right in green</span>,
       <span style="color:#cf222e">wrong in red</span>,
       <span style="color:#6e7781">unknown in grey</span>. Under each answer
       of <code>senfd-ask</code>, what the question was understood as and the
       time it took. <a href="../_static/benchmark/report-2026-11-08.html">Open
       it on its own page.</a></p>
       <iframe src="../_static/benchmark/report-2026-11-08.html"
               style="width:100%; height:42rem; border:1px solid #d0d7de"></iframe>
     </div>
     <div class="bench-panel" id="bench-panel-method">
       <p>Each frontier model answered from memory, with no tools and a
       system prompt of its own, in a fresh context of about 570 tokens, by
       <code>claude -p --safe-mode --tools ''</code>, three times in each of
       two modes: allowed to say "unknown", with a wrong answer counting
       against it, and told to answer every question, as a chat does.</p>
       <p>The local lanes ran <code>llama-server</code> of llama.cpp on an AMD
       EPYC 7532, 16 threads and no GPU offload, with the language models as
       published, Q4_K_M, checked by their SHA-256. <code>senfd-ask</code> ran
       from a pinned commit of senfd, against the data model it made of the
       eleven documents ratified in 2026, the documents checked by their
       SHA-256 too.</p>
       <p>An answer of <code>senfd-ask</code> is right when a line of it
       names the field, command, feature or log page asked about and gives
       the right value; a frontier model's, when its value is the right
       one. Each right answer was checked against the figure that gives it.</p>
     </div>
     <div class="bench-panel" id="bench-panel-repeat">
       <p>The benchmark is a <a href="https://cijoe.readthedocs.io/">cijoe</a>
       workflow, kept with the transcripts of every run in the
       <code>nvme-spec-model</code> repository: the questions and their
       answers, the steps, and a configuration naming the documents, the senfd
       commit, the machine and the language models. The documents are not in
       it; bring your own.</p>
       <pre>cijoe workflows/benchmark.yaml -c configs/epyc-02.toml -o results/$(date +%F)</pre>
       <p>It records what it ran on and with, makes a virtual environment of
       the pinned senfd, makes the data model of the documents, runs every
       lane, and writes the report above. A run takes about seven minutes.</p>
     </div>
   </div>
   <style>
     .bench-tabs { display: flex; flex-wrap: wrap; margin: 1rem 0; }
     .bench-tabs > input { display: none; }
     .bench-tabs > label { padding: 0.4rem 1rem; cursor: pointer;
       border-bottom: 2px solid transparent; font-weight: 600; }
     .bench-tabs > input:checked + label { border-bottom-color: var(--color-brand-primary); }
     .bench-panel { display: none; width: 100%; padding-top: 0.5rem; }
     #bench-tab-transcript:checked ~ #bench-panel-transcript,
     #bench-tab-method:checked ~ #bench-panel-method,
     #bench-tab-repeat:checked ~ #bench-panel-repeat { display: block; }
   </style>

What it does not show
---------------------

The questions are of facts with one answer, which a lookup answers and a
language model's memory may not. They are not questions of how to use a
feature, or why, where a frontier model's reasoning is worth its fee; given
``senfd-mcp`` as tools, it has the facts as well. Nor are 30 questions every
question: what ``senfd-ask`` does not understand, it says it does not know, so
the cost of a question it cannot read is an answer, not a wrong one.