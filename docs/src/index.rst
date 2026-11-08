.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

senfd: the NVMe specifications, as data
=======================================

**Not endorsed by NVM Express.** senfd is an independent project. It is not
endorsed by NVM Express, Inc., nor made by it, and its data model is not a
publication of NVM Express. NVM Express and NVMe are trademarks of NVM
Express, Inc.

**Experimental: use at your own risk.** senfd is young, what it says can be
wrong, and nothing it says replaces the specification. Every answer cites the
figure it is from: check it there before you rely on it.

**Derived from the specifications, and under their terms.** The data model
senfd makes is derived from the NVMe specifications, so the notice printed in
each specification governs it as it governs the specification. Members of NVM
Express, Inc. may use it subject to their Participation Agreement and the
Company's Intellectual Property Policy and Bylaws. To anyone else, the notice
grants only the right to review, refer to or cite the specification, and
not to make derivatives of it or implement it: **you must be a member of NVM
Express, Inc. to make the data model or make use of it.**

**And yet, see what it gets right.** Asked 30 questions with one exact
answer each, mostly about what the revisions ratified in 2026 added or moved,
``sate`` answered **all 30 right**, in 4 ms each, for free, and so did
Llama 3.1 8B on a CPU choosing its lookups, in 2.7 s each. Claude Opus 5.5
and Sonnet 5.5, from memory and told to answer, got **4.7 and 7.7 wrong** on
average, stated as surely as the right ones. The :ref:`benchmark
<sec-benchmark>` shows every answer.

The NVMe specifications are published as documents, thousands of pages of
figures that every driver, tool, emulator, firmware and test suite transcribes
by hand. **senfd** reads the **S**\ pecification documents, as the PDFs NVM
Express publishes or the ``.docx`` its members hold, **E**\ xtracts and
**N**\ ormalizes their **F**\ igures, and makes a structured **D**\ ata model
of them: every command with its dwords and fields, every data structure,
register, feature, log page and table of values, each fact citing the
document, section, figure and page it is from.

It is a data model, not a language model. It is JSON, validated by a
:ref:`schema <sec-schema>`; nothing in it is trained, sampled or generated,
and the same documents give the same data model, every time. Language models
come in only where senfd hands its data model to one, and then as a reader of
it, never as the source of a fact.

The package has two tools. ``senfd`` makes the data model. ``sate``, for
**S**\ enfd **A**\ sk **T**\ he **E**\ xpert, puts an expert on the
specifications at your fingertips: ask it as you would a colleague, and it
answers at once from the data model, citing the figure. *Senf* is Danish for
mustard, as the logo's documents drenched in it show, and a sate is what
comes of the marinade.

From that one data model, today:

* **Precise answers, at once.** ``senfd-query`` and ``sate`` answer a
  question about a command, a field, a register, a feature or a log page in
  milliseconds, with the figure to check the answer against.
* **Language models that cannot make NVMe facts up.** ``sate-mcp`` gives a
  coding agent the data model as tools, and ``sate --llm`` has a small
  language model, run for free on your own CPU, choose the lookup and write
  nothing of the answer. Frontier language models asked from memory invent
  opcodes and bits of recent revisions; senfd's answers are the figures'. In
  the :ref:`benchmark <sec-benchmark>`, Llama 3.1 8B on a CPU answered 30 of
  30 right, for free, where Claude Opus 5.5 told to answer got 4.7 wrong on
  average.
* **Code generated from the figures.** An early prototype for xNVMe writes
  its specification headers from the data model: structs, masks, opcodes,
  constructors and registers, one header per document, every member citing
  its figure. A revision of a document is then a regenerated header and a
  diff to review.
* **A linter of the documents.** Reading the figures as data checks them:
  values not of their column's kind, fields beyond their dwords, figures of no
  known shape and captions not of the form, each listed with its figure and
  page for the authors to fix.

It runs on the eleven documents ratified in 2026, Base 2.4, the NVM, Zoned
Namespace, Key Value, Subsystem Local Memory and Computational Programs
command sets, Management Interface 2.2, Boot 1.4 and the PCIe, RDMA and TCP
transports, in about a minute, into a data model of 4.9 MB. Nothing needs to
be built: ``pip install senfd`` and point it at the documents.

.. code-block:: console

   $ pip install senfd[sate,pdf]
   $ senfd ~/specs/*.pdf --output ~/.cache/senfd
   $ sate "Which bits of CDW12 of Write are PRINFO?"

The specifications are NVM Express's, under its copyright. NVM Express
publishes the ratified specifications as PDF, which anyone can download from
`nvmexpress.org <https://nvmexpress.org/specifications/>`_; their ``.docx``
are available to its members only. senfd reads either and gives the same data
model of both. The ``.docx`` is the simpler source, as it states what the PDF
only shows, and it is the one an editor has while a specification is under
revision: run on the draft, ``senfd-query lint`` lists what does not read as
data, for the figure to be corrected before it is ratified rather than
after. Neither the documents nor anything made from them is
distributed with senfd: the data model is made locally, by whoever has the
documents. senfd's examples and most of its tests use synthetic documents of
its own; the tests reading the specifications, and the CI job checking what
senfd makes of each, download the public PDFs into a cache and upload
nothing. The CI job also merges them into one data model and has ``sate``
answer the :ref:`benchmark's <sec-benchmark>` questions from it, failing
unless every one is right; that data model is not offered for download
either. **Make your own**: the commands above, on the PDFs downloaded from
nvmexpress.org, give the same data model the CI job checks.

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   install/index.rst
   usage/index.rst
   stages/index.rst
   sate/index.rst
   benchmark/index.rst
   linting/index.rst
   codegen/index.rst
   schema/index.rst
   prior-art/index.rst
   contributors/index.rst
