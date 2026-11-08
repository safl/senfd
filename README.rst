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
    :target: https://safl.dk/senfd/ask/
    :alt: MCP server

**senfd** reads the ratified NVMe specification documents and makes a data
model of them: every command with its dwords and fields, every data
structure, register, feature, log page and table of values, each fact citing
the document, section, figure and page it is from. It is a data model, not a
language model: JSON validated by a schema, with nothing in it trained or
generated, and the same documents give the same data model every time. It
reads the specifications as NVM Express publishes them, as PDF, or as the
.docx its members hold. From that one data model:

* **Precise answers, at once**, with ``senfd-query`` and ``senfd-ask``, the
  expert to ask, which completes names as you type and answers in
  milliseconds, citing the figure.
* **Language models that cannot make NVMe facts up**: ``senfd-mcp`` gives a
  coding agent the data model as tools, and ``senfd-ask --llm`` has a small
  language model, free, on your own CPU, choose the lookup and write nothing
  of the answer.
* **Code generated from the figures**, as an early prototype for xNVMe writes
  its specification headers: structs, masks, opcodes, constructors and
  registers, citing their figures.
* **A linter of the documents**: what does not read as data is listed, with
  its figure and page, for the authors to fix.

.. code-block:: console

   $ pipx install "senfd[ask,mcp,pdf]"
   $ senfd ~/specs/*.pdf --output ~/.cache/senfd
   $ senfd-ask "Which bits of CDW12 of Write are PRINFO?"

with the specifications downloaded from `nvmexpress.org
<https://nvmexpress.org/specifications/>`_ into ``~/specs``, or, for a
member of NVM Express, their ``.docx``.

Asked 30 questions of the 2026 revisions, ``senfd-ask`` answered all 30
right, in 4 ms each, and with Llama 3.1 8B on a CPU choosing the lookups,
all 30 right in 2.7 s each, for free. Claude Opus 5.5 and Sonnet 5.5, asked
from memory and told to answer, got 4.7 and 7.7 of them wrong, on average
over three runs.

It runs on the eleven documents ratified in 2026, from Base 2.4 to the TCP
transport, in about a minute from the .docx and a few minutes from the PDFs.

Status and conditions
---------------------

**senfd is experimental, and independent of NVM Express.** It is not
endorsed by NVM Express, Inc., nor made by it, and its data model is not a
publication of NVM Express. Its answers cite the figure they are from so
that they can be checked against the specification, which is what counts.

**The specifications are NVM Express's,** under its copyright. NVM Express
publishes the ratified specifications as PDF, which anyone can download from
nvmexpress.org, and senfd reads those. The ``.docx`` of the specifications
are available to members of NVM Express only; senfd reads those too, for
those who hold them, and gives the same data model of either.

**Neither the documents nor anything made from them is distributed with
senfd.** Its examples and most of its tests use synthetic documents of its
own. The tests that read the specifications, and the CI job checking what
senfd makes of each, download the public PDFs from nvmexpress.org into a
cache, checked by their SHA-256, and keep them and the data model there,
uploading neither. Whoever runs senfd makes the data model locally, from the
documents they have.

See the `documentation <https://safl.dk/senfd/>`_ for the commands,
the benchmark against frontier language models, and the schema of the data
model.
