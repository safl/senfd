.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-prior-art:

Prior art
=========

senfd is the third tool of its line, and its shape is an answer to the two
before it.

`nvme-lint <https://github.com/linux-nvme/nvme-lint>`_, from 2022 and
announced on nvmexpress.org, read the published PDFs and checked their
figures: a caption not in bold, column headings that differ from figure to
figure, holes and overlaps in the bit and byte ranges of a field. Its rules
were Python over tables that camelot found on the page by the lines drawn
around them, and what any reading of a PDF's tables meets, a merged cell, a
column lost, a header repeated past a page break, it met before a rule could
run. The rules were the goal; reading the tables was the price of reaching
them.

`Spex <https://github.com/SamsungDS/Spex>`_, from 2023, turned that around.
It read the ``.docx`` the authors hold, where a merged cell and a table in a
cell are stated rather than drawn, extracted every figure to JSON that a
schema checks, and made the lint a part of that extraction, for the authors
to run before a specification is published. It was deliberately not a code
generator, leaving that to the readers of its JSON.

senfd was a change of direction. Both tools before it wrote rules, a check
or an extractor for each kind of figure, against the tables as their reader
found them. senfd instead generalises: every figure, whatever its kind, is
reduced to the same plain markup, rows of cells with what is merged and
what is nested marked, and from that one form the figures are normalised
and the data behind them structured, each figure recognised as the kind it
is, its fields, values, dwords and bits read as data, and the lot resolved
across the documents and merged into one data model. The three forms are
the stages, each a JSON with a :ref:`schema <sec-schema>` of its own: the
figure document, the normalised figure document, and the data model.

Two things follow. Linting is a side effect rather than a goal: to read a
figure as data is to check it, and what does not read as data is reported
with its figure and page, as a :ref:`candidate erratum or a document error
<sec-linting>`, with no rule written for it. The lint is no less useful for
coming free; it is what an author gets from a tool whose goal is the data
model. And no format is forced: the plain markup is all a reader has to
produce, so the ``.docx`` reader and the PDF reader give the same figure
document and share everything after it, which is how the published PDFs
came to give the same data model as the ``.docx``.

The larger change is the goal itself. The tools before tossed checks at the
documents, and what they extracted served the checks. senfd's goal is the
NVMe data model, and the checks fall out of reaching it. A data model is
useful where a lint is not: it answers a question at once, as the
:ref:`expert <sec-ask>` does; it hands a coding agent the specification as
tools, through the MCP server; it writes a driver's headers, as the
:ref:`code generator <sec-codegen>` does; it compares two revisions by
their facts rather than their prose; and it can feed a test suite or an
emulator the same values the author wrote, each use from the one JSON,
each fact citing its figure. That is what this iteration added to the
line: a tool whose output is of general use, with the lint along for the
ride.
