.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

senfd and sate
==============

.. warning::

   senfd is not endorsed by NVM Express, it is experimental, and you must be
   a member of NVM Express, Inc. to make its data model or make use of it.
   Read the :ref:`notices <sec-notices>` at the end of this page first.

**senfd** makes a data model of the NVMe specifications. It reads the PDFs
NVM Express publishes, or the ``.docx`` its members hold, and turns the
figures into data: every command with its dwords and fields, every data
structure, register, feature, log page and table of values. Each fact cites
the document, section, figure and page it is from. It is a data model, not
a language model: JSON validated by a :ref:`schema <sec-schema>`, nothing
in it trained or generated, and the same documents give the same data
model every time.

**sate** answers questions from that data model, as an expert would. Ask it
as you would ask a colleague, and it answers at once, citing the figure to
check the answer against. It is a session with completion, a question on
the command line, or an MCP server for a coding agent.

.. code-block:: console

   $ pipx install "senfd[sate,pdf]"
   $ senfd ~/specs/*.pdf --output ~/.cache/senfd
   $ sate "Which bits of CDW12 of Write are PRINFO?"

:ref:`Get started <sec-tutorial>` walks through these, from downloading the
documents to the first answer.

What it gets right
------------------

Asked 71 questions with one exact answer each, mostly about what the
revisions ratified in 2026 added or moved, ``sate`` answered all 71 right,
in 4 ms each. With Llama 3.1 8B on a CPU choosing the lookup, it answered
70 and said of one that it is not known. Claude Opus 5.5 and Sonnet 5.5,
from memory and told to answer, got 15.3 and 32.3 wrong on average, stated
as surely as the right ones. The :ref:`benchmark <sec-benchmark>` shows
every answer.

What the data model is for
--------------------------

* **Precise answers, at once.** ``sate`` and ``senfd-query`` answer a
  question about a command, a field, a register, a feature or a log page in
  milliseconds; see :ref:`the expert <sec-ask>`.
* **Language models that cannot make NVMe facts up.** ``sate-mcp`` gives a
  coding agent the data model as tools, and ``sate --llm`` has a small
  language model on your own CPU choose the lookup and write nothing of the
  answer.
* **Code generated from the figures.** An early prototype writes xNVMe's
  specification headers from the data model, every member citing its
  figure; see :ref:`code from the figures <sec-codegen>`.
* **A linter of the documents.** What does not read as data is listed with
  its figure and page, for the authors to fix; see :ref:`the linter
  <sec-linting>`.

The names
---------

senfd reads the **S**\ pecification documents, **E**\ xtracts and
**N**\ ormalises their **F**\ igures, and makes a **D**\ ata model.
``sate`` is **S**\ enfd **A**\ sk **T**\ he **E**\ xpert. *Senf* is
Danish for mustard, as the logo's documents drenched in it show, and a sate
is what comes of the marinade.

.. _sec-notices:

Notices
-------

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

On what terms the documents are read
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The specifications are NVM Express's, under its copyright. NVM Express
publishes the ratified specifications as PDF, which anyone can download from
`nvmexpress.org <https://nvmexpress.org/specifications/>`_; their ``.docx``
are available to its members only. senfd reads either and gives the same
data model of both. The ``.docx`` is the simpler source, as it states what
the PDF only shows, and it is the one an editor has while a specification
is under revision: run on the draft, ``senfd-query lint`` lists what does
not read as data, for the figure to be corrected before it is ratified
rather than after.

Neither the documents nor anything made from them is distributed with
senfd: the data model is made locally, by whoever has the documents.
senfd's examples and most of its tests use synthetic documents of its own;
the tests reading the specifications, and the CI job checking what senfd
makes of each, download the public PDFs into a cache, checked by their
SHA-256, and upload nothing. The CI job also merges them into one data
model and has ``sate`` answer the :ref:`benchmark's <sec-benchmark>`
questions from it, failing unless every one is right; that data model is
not offered for download either. Make your own: the commands of :ref:`Get started
<sec-tutorial>`, on the PDFs downloaded from nvmexpress.org, give the same
data model the CI job checks.

.. toctree::
   :caption: Use
   :hidden:

   tutorial/index.rst
   install/index.rst
   sate/index.rst
   usage/index.rst
   linting/index.rst

.. toctree::
   :caption: How it works
   :hidden:

   stages/index.rst
   schema/index.rst
   codegen/index.rst
   benchmark/index.rst
   prior-art/index.rst

.. toctree::
   :caption: Project
   :hidden:

   contributors/index.rst
