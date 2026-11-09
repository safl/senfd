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
a value that is not of its column's kind; a field whose bits lie beyond
the dwords or the bytes that hold it; an acronym
that is not one; bits of a command's dwords that no figure gives a field.
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
PDF, senfd reports 3 candidate errata and 9 document errors for the
authors, and 23 figures it does not model, 16 worked examples and 19
unassigned dwords. One of the candidate errata is senfd's: the "n/a9" of
Base 2.4, Figure 466, is "n/a" and the marker of the figure's note 9.
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
