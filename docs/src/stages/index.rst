.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-stages:

From the figure to the data model
=================================

This page follows two figures of senfd's example document,
``example/example.docx``, through the three forms that senfd makes of them.
The example document is a synthetic specification written to exercise the
reader, so the page shows no text of NVM Express's.
``toolbox/example_stages.py`` writes every file on this page from
``example/output``, and a test checks that the files match what the script
writes.

.. raw:: html
   :file: style.html

As written
----------

The figure document holds each table as the document has it: rows of
cells, with the merged cells marked. A reader of a document format has to
produce only this form. The ``.docx`` reader and the PDF reader both
produce it, and no stage after this one knows which reader produced it.
Figure 1 is an opcode table, and Figure 19 is a command dword:

.. raw:: html
   :file: figure-1.plain.html

.. raw:: html
   :file: figure-19.plain.html

Normalised
----------

senfd recognises the kind of each figure by its caption and the shape of
its table, and reads the figure as that kind. senfd reads Figure 1 as the
opcodes of the Foobar command set, one entry per row. senfd reads Figure 19
as dword 11 of the Ring command: a layout of fields, with each range read
as bits and each acronym taken from the parentheses. Each thing that senfd
had to normalise on the way is a diagnostic on the figure, such as a dash
in a caption or a range given in words:

.. raw:: html
   :file: figure-1.normalized.html

.. raw:: html
   :file: figure-19.normalized.html

In the data model
-----------------

In the data model, the figures become the things they define. The opcode
table gives the command Ring, opcode 04h, with the footnote marker dropped
from its name. Three dword figures, Figures 18, 19 and 20, give the
submission queue entry of Ring, and each dword cites the figure and page it
is from. The command is one entry of the data model. The expert, the MCP
server and the code generator all read this entry:

.. literalinclude:: ring.json
   :language: json

What the author sees
--------------------

Reading the figures as data also checks them. A figure that does not read
as data becomes a candidate erratum, reported with the document, section,
figure and page. No rule was written for any of the candidate errata below;
each one is a figure that did not fit its kind. The opcode of Zing is not a value. The acronym of Ring Mode has
a space in it. Bits 0 to 15 of Ring's dword 11 belong to no field. Bit 64
of Ring Tail lies beyond the 64 bits of its two dwords. A support
requirement reads "Maybe", which is not a support level:

.. literalinclude:: errata.txt
   :language: text

``senfd lint`` lists the candidate errata together with the document
errors, the figures of a shape senfd does not read, and the dwords that no
command claims; see :ref:`the linter <sec-linting>`. An editor who makes
the data model of a draft gets this check with no further work.
