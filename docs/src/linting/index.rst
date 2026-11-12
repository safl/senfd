.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-linting:

Lint the documents
==================

To read a figure as data, senfd must check it. senfd normalises every
figure and types every value. A figure or value that does not take the
form its kind requires is reported with the document, section, figure and
page where it occurs, so the author of the document can go directly to
what needs fixing. At the end of a run, ``senfd`` prints how many findings
of each kind it found. ``senfd lint``, or the MCP tool ``lint``, lists the
findings, with those for the authors first. A document's name after
``lint`` or ``errata`` limits the list to that document:

.. code-block:: console

   $ senfd lint
   $ senfd lint nvm
   $ senfd errata base

.. raw:: html

   <div id="cast-lint"></div>

senfd reports five kinds of findings. The first two kinds are for the
authors of the documents. The other three kinds are either a gap in senfd
or a figure that does not follow the conventions of the others.

Candidate errata
----------------

Candidate errata are for the authors, and ``senfd errata`` also lists
them. senfd reports these as candidate errata:

* A value that is not of the kind its column holds.
* A range that is not a valid range. Examples are a formula whose
  parentheses do not match, bounds where the upper bound is below the
  lower bound, and bits beyond the dwords or bytes that hold them.
* An acronym that is not an acronym.
* Bits of a command's dwords that no figure assigns to a field.
* Bits or bytes that belong to no field, between two fields of a figure
  that lays out a whole data structure, log page or register. senfd does
  not report these when the figure leaves out rows there with "..." or
  gives a formula between the two fields.

A valid range is a span of numbers, a formula over values that the figure
names, as "(N*16)+15:N*16", or a value left open, as "n/a". Text that is
none of these is the erratum. senfd compares the bounds of a formula
whatever values the formula names. senfd leaves such a value out of the
data model. When the same value occurs in many rows of a figure, senfd
reports one erratum and gives the number of rows. senfd reads a column of
sentences as text, whatever the column's name.

Document errors
---------------

Document errors are for the authors. senfd reports these as document
errors:

* A table with no caption of the form "Figure N: title".
* A table wrapped in a table of one cell.
* A table that holds the rows of two figures.
* An entry in the table of figures that does not have the form of the
  others.
* A section whose number in the headings differs from its number in the
  table of contents.
* In a PDF, text that is tagged inside a table's cell but printed outside
  the table's borders. An example is a heading or a list that Word tagged
  into the table before it.
* In a PDF, struck-through text, which occurs when the PDF is printed with
  its tracked changes shown. senfd reports this once per document, with
  how much text is struck through and where it starts.

Each document error names the document and the figure it follows. senfd
also writes the document errors to each document's ``.error.log``.

Rows that name no field
-----------------------

A row that names no field is either a gap in senfd or a defect of the
figure. senfd makes a field from a row that gives a name, or that marks a
place as reserved, obsolete, vendor specific or ignored. A row that gives
neither, such as a sentence about bytes with no equivalent in senfd,
makes no field, and senfd lists the row.

Figures of no shape senfd models
--------------------------------

A figure of no shape that senfd models is either a gap in senfd or a
defect of the figure. Such a figure either does not follow the conventions
of the other figures, or has a shape that senfd does not model yet. senfd
lists worked examples separately, because they are not data. Figures that
are known not to be data, by their captions, can be left out of a run with
``--skip-figures`` and a skip list. The directory ``skiplists/`` in the
repository holds the skip lists of the ratified documents.

Unassigned dwords
-----------------

An unassigned dword is either a gap in senfd or a defect of the caption.
It is a figure of a command's dwords that no command, feature or operation
claims by the name that the caption gives. Either senfd does not yet know
what the caption names, or the caption names it differently from the
figure that defines it.

What senfd finds
----------------

Each finding is a candidate. A person decides whether the figure or senfd
is wrong. A figure of a shape that senfd does not know is a gap for senfd
to close. The eleven documents ratified in 2026, as NVM Express publishes
them as PDF, give these findings: 12 candidate errata and 9 document
errors for the authors, and 14 rows that name no field, 23 figures that
senfd does not model, 16 worked examples and 19 unassigned dwords. Six of
the candidate errata are formulas in Base 2.4, Figure 432. In five of
them, the upper bound of a range, "... + 59", is below its lower bound,
"... + 60". Three of the document errors are the tracked changes with
which the PDFs of Base 2.4, Boot 1.4 and Management Interface 2.2 are
printed. On a draft, the same run takes minutes and checks every figure
in the same way.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/lint.cast", document.getElementById("cast-lint"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
