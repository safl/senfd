.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-prior-art:

Prior art
=========

senfd is the third tool in a line of tools that read the NVMe
specifications. The design of senfd answers the problems of the two tools
before it.

`nvme-lint <https://github.com/linux-nvme/nvme-lint>`_ is from 2022 and was
announced on nvmexpress.org. nvme-lint read the published PDFs and checked
their figures for defects: a caption that is not in bold, column headings
that differ from figure to figure, and holes and overlaps in the bit and
byte ranges of a field. Its rules were written in Python, over tables that
camelot found on each page by the lines drawn around them. Before a rule
could run, nvme-lint met the problems that any reader of tables in a PDF
meets: merged cells, lost columns, and headers repeated after a page break.
The rules were the goal of nvme-lint, and reading the tables was the work
needed to reach them.

`Spex <https://github.com/SamsungDS/Spex>`_ is from 2023 and took the
opposite approach. Spex read the ``.docx`` that the authors hold, where a
merged cell or a table inside a cell is stated in the file rather than
drawn on a page. Spex extracted every figure to JSON that a schema checks,
and made the lint a part of that extraction, for the authors to run before
a specification is published. Spex was deliberately not a code generator;
it left code generation to the readers of its JSON.

senfd does what Spex does: it extracts every figure to JSON that a schema
checks. But senfd reads either the ``.docx`` that the authors hold or the
PDFs that NVM Express publishes, which anyone can download. Spex served the
authors before a specification is published. senfd serves the authors, and
also everyone who reads the specifications after publication: those who
implement, test, and write tools for NVMe. senfd is therefore a tool for a
larger audience than Spex.

The approach of senfd also differs from both earlier tools. nvme-lint and
Spex each had rules, a check or an extractor for each kind of figure,
written against the tables as their reader found them. senfd instead
reduces every figure, whatever its kind, to the same plain markup: rows of
cells, with merged and nested cells marked. From that one form, senfd
normalises the figures, recognises the kind of each figure, reads its
fields, values, dwords and bits as data, resolves references across the
documents, and merges the result into one data model. Each of the three
forms is a stage with a JSON :ref:`schema <sec-schema>` of its own: the
figure document, the normalised figure document, and the data model.

This design has two consequences. First, linting is a side effect rather
than a goal. To read a figure as data, senfd must check it, and senfd
reports a figure that does not read as data, with its figure number and
page, as a :ref:`candidate erratum or a document error <sec-linting>`. No
rule is written for these reports. Second, senfd does not require one input
format. A reader only has to produce the plain markup, so the ``.docx``
reader and the PDF reader produce the same kind of figure document and
share every stage after it. This is how senfd makes a data model from the
published PDFs as well as from the ``.docx``.

The larger difference is the goal. nvme-lint and Spex extracted data to
serve their checks. The goal of senfd is the NVMe data model, and senfd
performs the checks while it builds the data model. A data model has uses
that a lint does not. The :ref:`expert <sec-ask>` uses it to answer a
question at once. The MCP server gives it to a coding agent as tools. The
:ref:`code generator <sec-codegen>` uses it to write a driver's headers. A
data model of one revision can be compared with that of another, fact by
fact rather than by prose, and a data model can give a test suite or an
emulator the values that the authors wrote. Each of these uses reads the same JSON, and each fact in it
cites its figure. What senfd adds to this line of tools is an output of
general use, the data model. The lint is a by-product of building it.
