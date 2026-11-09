.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-linting:

Lint the documents
==================

To read a figure as data is to check it. Every figure senfd normalises, and
every value it types, either takes the form its kind must have or is
reported, with the document, section, figure and page it is on, so the
author of a document goes straight to what to fix. A run of ``senfd`` ends
by saying how many of each it found; ``senfd lint``, or the MCP tool
``lint``, lists them, the authors' first, and a document's name after
``lint`` or ``errata`` confines the list to it:

.. code-block:: console

   $ senfd lint
   $ senfd lint nvm
   $ senfd errata base

.. raw:: html

   <div id="cast-lint"></div>

**Candidate errata**, the authors', also listed by ``senfd errata``:
a value that is not of its column's kind; a range that is none, as a
formula whose parentheses do not match, bounds where the upper is below the
lower, or bits beyond the dwords or the bytes that hold them; an acronym
that is not one; bits of a command's dwords that no figure gives a field,
and bits or bytes of no field between two fields of a figure laying out the
whole of a data structure, a log page or a register, unless the figure
leaves rows out there with "..." or gives a formula between them.
A range is a span of numbers, a formula of values the figure names, as
"(N*16)+15:N*16", or left open, as "n/a"; text that is none of these is the
erratum, and a formula's bounds are compared whatever the values it names.
Such a value is left out of the data model. The same value in many rows of
a figure is one erratum, said once with the number of rows. A column of
sentences is read as text whatever its name.

**Document errors**, the authors': a table with no caption of the form
"Figure N: title", a table wrapped in a table of one cell, a table holding
the rows of two figures, an entry of the table of figures not of its form,
a section whose number in the headings differs from the table of contents,
and, in a PDF, text tagged inside a table's cell but printed outside its
borders, as a heading or a list that Word tagged into the table before it,
and text struck through, a PDF printed with its tracked changes shown,
said once a document with how much and where it starts. Each says the
document and the figure it follows; the errors are also in
each document's ``.error.log``.

**Rows that name no field**, senfd's or the figure's: a field is made with
a name, or as what holds a place, reserved, obsolete, vendor specific or
ignored; a row giving neither, as a sentence about bytes with no equivalent
here, makes no field and is listed.

**Figures of no shape senfd models**, senfd's or the figure's: a figure
that either does not follow the conventions of the others or is of a shape
senfd does not model yet. Worked examples are listed apart, since they are
not data. Figures known not to be data, by their captions, can be left out
of a run with ``--skip-figures`` and a skip list; ``skiplists/`` in the
repository holds those of the ratified documents.

**Unassigned dwords**, senfd's or the caption's: a figure of a command's
dwords that no command, feature or operation claims, by the name its
caption gives. Either senfd does not yet know what the caption names, or
the caption names it otherwise than the figure defining it.

Each finding is a candidate: a person decides whether the figure or senfd
is wrong, and a figure of a shape senfd does not know is senfd's to learn.
On the eleven documents ratified in 2026, as NVM Express publishes them as
PDF, senfd reports 13 candidate errata and 9 document errors for the
authors, and 15 rows that name no field, 23 figures it does not model, 16
worked examples and 19 unassigned dwords. Two of the candidate errata are senfd's: the "n/a9" of
Base 2.4, Figure 466, is "n/a" and the marker of the figure's note 9, and
the gap of Zoned Namespace 1.5, Figure 49, is a row senfd misreads.
Six are the formulas of Base 2.4, Figure 432, five of them a range
whose upper bound, "... + 59", is below its lower, "... + 60".
Three of the document errors are the tracked changes the PDFs of Base
2.4, Boot 1.4 and Management Interface 2.2 are printed with. On a draft,
the same run takes minutes and checks every figure the same way.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/lint.cast", document.getElementById("cast-lint"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
