.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

senfd: the NVMe specifications, as data
=======================================

The NVMe specifications are published as documents, thousands of pages of
figures that every driver, tool, emulator, firmware and test suite transcribes
by hand. **senfd** reads the ratified documents, as ``.docx``, and makes a
data model of them: every command with its dwords and fields, every data
structure, register, feature, log page and table of values, each fact citing
the document, section, figure and page it is from.

It is a data model, not a language model. It is JSON, validated by a
:ref:`schema <sec-schema>`; nothing in it is trained, sampled or generated,
and the same documents give the same data model, every time. Language models
come in only where senfd hands its data model to one, and then as a reader of
it, never as the source of a fact.

From that one data model, today:

* **Precise answers, at once.** ``senfd-query`` and ``senfd-ask`` answer a
  question about a command, a field, a register, a feature or a log page in
  milliseconds, with the figure to check the answer against.
* **Language models that cannot make NVMe facts up.** ``senfd-mcp`` gives a
  coding agent the data model as tools, and ``senfd-ask --llm`` has a small
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

   $ pip install senfd[ask,mcp]
   $ senfd ~/specs/*.docx --output ~/.cache/senfd
   $ senfd-ask "Which bits of CDW12 of Write are PRINFO?"

The documents are NVM Express's and are not distributed with senfd, nor is
anything made from them: the data model is made locally, by whoever holds the
documents. senfd's tests and examples use synthetic documents of its own.

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   install/index.rst
   usage/index.rst
   ask/index.rst
   benchmark/index.rst
   linting/index.rst
   codegen/index.rst
   schema/index.rst
   contributors/index.rst
