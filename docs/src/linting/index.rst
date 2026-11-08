.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-linting:

A linter of the documents
=========================

To read a figure as data is to check it. Every figure senfd normalises, and
every value it types, either takes the form its kind must have or is
reported, with the document, section, figure and page it is on, so the
author of a document goes straight to what to fix. A run of ``senfd`` ends
by saying how many of each it found, and ``senfd-query lint``, or the MCP
tool ``lint``, lists them, the authors' first, each citing the document and
the figure:

**Candidate errata**, the authors', also listed by ``senfd-query errata``: a
value that is not of its column's kind, as a footnote marker run into a
flag; a field whose bits lie beyond the dwords that hold it; an acronym that
is not one; bits of a command's dwords that no figure gives a field. The
same value in many rows of a figure is one erratum, said once with the
number of rows. A column of sentences is read as text whatever its name.

**Document errors**, the authors': a table with no caption of the form
"Figure N: title", a table wrapped in a table of one cell, a table holding
the rows of two figures, an entry of the table of figures not of its form,
and a section whose number in the headings differs from the table of
contents. Each says the document and the figure it follows; the errors are
also in each document's ``.error.log``.

**Figures of no shape senfd models**, senfd's or the figure's: a figure that
either does not follow the conventions of the others or is of a shape senfd
does not model yet. Worked examples are listed apart, since they are not
data. Figures known not to be data, by their captions, can be left out of a
run with ``--skip-figures`` and a skip list; ``skiplists/`` in the
repository holds those of the ratified documents.

**Unassigned dwords**, senfd's or the caption's: a figure of a command's
dwords that no command, feature or operation claims, by the name its
caption gives. Either senfd does not yet know what the caption names, or the
caption names it otherwise than the figure defining it.

.. code-block:: console

   $ senfd-query lint
   $ senfd-query lint nvm
   $ senfd-query errata base

Each finding is a candidate: a person decides whether the figure or senfd
is wrong, and a figure of a shape senfd does not know is senfd's to learn.
On the eleven documents ratified in 2026, as NVM Express publishes them as
PDF, senfd reports 2 candidate errata and 6 document errors for the authors,
and 23 figures it does not model, 16 worked examples and 19 unassigned
dwords.
The ratified documents are consistent by this measure; the value is in
running senfd on every draft, where it takes a minute and checks every
figure the same way, and in keeping each revision as consistent as the last.
