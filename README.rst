.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

senfd: the NVMe specifications, as data
=======================================

.. image:: https://github.com/safl/senfd/actions/workflows/bd.yaml/badge.svg
    :target: https://github.com/safl/senfd/actions/workflows/bd.yaml
    :alt: Build and test

.. image:: https://coveralls.io/repos/github/safl/senfd/badge.svg?branch=main
    :target: https://coveralls.io/github/safl/senfd?branch=main
    :alt: Coverage

.. image:: https://img.shields.io/pypi/v/senfd
    :target: https://pypi.org/project/senfd/
    :alt: PyPI

.. image:: https://img.shields.io/pypi/pyversions/senfd
    :target: https://pypi.org/project/senfd/
    :alt: Python versions

.. image:: https://img.shields.io/badge/docs-safl.dk%2Fsenfd-blue
    :target: https://safl.dk/senfd/
    :alt: Documentation

.. image:: https://img.shields.io/badge/license-LGPL--2.1--only-blue
    :target: https://spdx.org/licenses/LGPL-2.1-only.html
    :alt: License

.. image:: https://img.shields.io/badge/REUSE-compliant-green
    :target: https://reuse.software/
    :alt: REUSE compliant, checked by pre-commit in CI

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff

.. image:: https://img.shields.io/badge/types-mypy-blue
    :target: https://mypy-lang.org/
    :alt: Checked with mypy

.. image:: https://img.shields.io/badge/MCP-server-8A2BE2
    :target: https://safl.dk/senfd/sate/
    :alt: MCP server

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
answer each, an opcode, an identifier, a bit or a byte offset, mostly about
what the revisions ratified in 2026 added or moved:

* ``sate``, by the words of the question: **30 of 30 right**, in 4 ms
  each, for free.
* ``sate`` with Llama 3.1 8B on a CPU choosing the lookup: **30 of 30
  right**, in 2.7 s each, for free, on your own hardware.
* Claude Opus 5.5 and Sonnet 5.5, from memory and told to answer: **4.7 and
  7.7 wrong** on average, stated as surely as the right ones, at USD 0.17
  and 0.07 a run.

The `benchmark <https://safl.dk/senfd/benchmark/>`_ shows every answer, and
how to run it again.

What it is
----------

**senfd** reads **S**\ pecification documents, **E**\ xtracts and
**N**\ ormalizes their **F**\ igures, and makes a structured **D**\ ata model
of them: every command with its dwords and fields, every data structure,
register, feature, log page and table of values, each fact citing the
document, section, figure and page it is from. It is a data model, not a
language model: JSON validated by a schema, with nothing in it trained or
generated, and the same documents give the same data model every time. It
reads the specifications as NVM Express publishes them, as PDF, or as the
.docx its members hold.

The package has two tools. ``senfd`` makes the data model. ``sate``, for
**S**\ enfd **A**\ sk **T**\ he **E**\ xpert, puts an expert on the
specifications at your fingertips: ask it as you would a colleague, and it
answers at once from the data model, citing the figure. *Senf* is Danish for
mustard, as the logo's documents drenched in it show, and a sate is what
comes of the marinade.

From that one data model:

* **Precise answers, at once**, with ``senfd-query`` and ``sate``, the
  expert to ask, which completes names as you type and answers in
  milliseconds, citing the figure.
* **Language models that cannot make NVMe facts up**: ``sate-mcp`` gives a
  coding agent the data model as tools, and ``sate --llm`` has a small
  language model, free, on your own CPU, choose the lookup and write nothing
  of the answer.
* **Code generated from the figures**, as an early prototype for xNVMe writes
  its specification headers: structs, masks, opcodes, constructors and
  registers, citing their figures.
* **A linter of the documents**: what does not read as data is listed, with
  its figure and page, for the authors to fix.

.. code-block:: console

   $ pipx install "senfd[sate,pdf]"
   $ senfd ~/specs/*.pdf --output ~/.cache/senfd
   $ sate "Which bits of CDW12 of Write are PRINFO?"

with the specifications downloaded from `nvmexpress.org
<https://nvmexpress.org/specifications/>`_ into ``~/specs``, or, for a
member of NVM Express, their ``.docx``. It runs on the eleven documents
ratified in 2026, from Base 2.4 to the TCP transport, in about a minute from
the .docx and a few minutes from the PDFs.

Prior art
---------

senfd is the third tool of its line. `nvme-lint
<https://github.com/linux-nvme/nvme-lint>`_ (2022) checked the figures of
the published PDFs with rules over tables found on the page; `Spex
<https://github.com/SamsungDS/Spex>`_ (2023) read the ``.docx`` instead and
extracted the figures to JSON under a schema, with the lint as part of it.
senfd was a change of direction: no rule for each kind of figure, but one
plain markup for every figure, rows of cells, from which the figures are
normalised and the data behind them structured. Linting is then a side
effect, since to read a figure as data is to check it, and no format is
forced, since the markup is all a reader has to produce, which is how the
``.docx`` and the PDF come to the same data model. Above all the goal moved,
from checks tossed at the documents to an NVMe data model, which is useful
where a lint is not: an expert to ask, tools for a coding agent, a driver's
headers, two revisions compared by their facts. The `documentation
<https://safl.dk/senfd/prior-art/>`_ says more.

On what terms the documents are read
------------------------------------

**The specifications are NVM Express's,** under its copyright. NVM Express
publishes the ratified specifications as PDF, which anyone can download from
nvmexpress.org, and senfd reads those. The ``.docx`` of the specifications
are available to members of NVM Express only; senfd reads those too, for
those who hold them, and gives the same data model of either. The ``.docx``
is the simpler source, as it states what the PDF only shows, and it is the
one an editor has while a specification is under revision: run on the
draft, ``senfd-query lint`` lists what does not read as data, for the
figure to be corrected before it is ratified rather than after.

**Neither the documents nor anything made from them is distributed with
senfd.** Its examples and most of its tests use synthetic documents of its
own. The tests that read the specifications, and the CI job checking what
senfd makes of each, download the public PDFs from nvmexpress.org into a
cache, checked by their SHA-256, and keep them and the data model there,
uploading neither. The job also merges them into one data model and has
``sate`` answer the benchmark's questions from it, failing unless every one
is right; that data model is not offered for download either. **Make your
own**: the commands above, on the PDFs downloaded from nvmexpress.org, give
the same data model the CI job checks.

See the `documentation <https://safl.dk/senfd/>`_ for the commands,
the benchmark against frontier language models, and the schema of the data
model.
