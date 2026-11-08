.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-linting:

A linter of the documents
=========================

To read a figure as data is to check it. Every figure senfd normalises, and
every value it types, either takes the form its kind must have or is
reported, with the document, section, figure and page it is on, so the
author of a document goes straight to what to fix. senfd reports four kinds:

**Candidate errata**, listed by ``senfd-query errata`` and the MCP tool
``errata``: a value that is not of its column's kind, as a footnote marker
run into a flag; a field whose bits lie beyond the dwords that hold it; an
acronym that is not one; bits of a command's dwords that no figure gives a
field.

**Figures not modelled**: a figure of no shape senfd recognises, which is
either a figure not following the conventions of the others or a shape
senfd does not model yet.

**Unassigned dwords**: a figure of a command's dwords that no command,
feature or operation claims, often because its caption names the command
otherwise than the figure defining it.

**Document errors**, in each document's ``.error.log``: a caption not of the
form "Figure N: title", a table wrapped in a table of one cell, a table of
figures that does not match the figures it lists.

.. code-block:: console

   $ senfd-query errata
   $ senfd-query errata nvm

Each finding is a candidate: a person decides whether the figure or senfd
is wrong, and a figure of a shape senfd does not know is senfd's to learn.
On the eleven documents ratified in 2026 senfd reports 8 candidate errata,
39 figures it does not model, 19 unassigned dwords and 13 document errors.
The ratified documents are consistent by this measure; the value is in
running senfd on every draft, where it takes a minute and checks every
figure the same way, and in keeping each revision as consistent as the last.
