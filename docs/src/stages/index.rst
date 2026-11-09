.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-stages:

From the figure to the data model
=================================

What senfd makes of a document is easiest to see on one. This page follows
two figures of senfd's own example document, ``example/example.docx``, a
synthetic specification written to exercise the reader, through the three
forms it takes; nothing of NVM Express's is shown. Every file on this page
is written from ``example/output`` by ``toolbox/example_stages.py``, and a
test keeps it so.

.. raw:: html
   :file: style.html

As written
----------

The figure document holds the tables as the document has them, a row of
cells each, with what is merged marked. This is all a reader of a format
has to produce: the ``.docx`` reader and the PDF reader both give it, and
nothing after this stage knows which it came from. Figure 1 is an opcode
table, and Figure 19 a command dword:

.. raw:: html
   :file: figure-1.plain.html

.. raw:: html
   :file: figure-19.plain.html

Normalised
----------

Each figure is recognised, by its caption and the shape of its table, as
the kind it is, and read as that kind: Figure 1 as the opcodes of the
Foobar command set, an entry a row; Figure 19 as dword 11 of the Ring
command, a layout of fields, the range read as bits, the acronym taken from
the parentheses. Whatever had to be normalised to get there is a diagnostic
on the figure, as a dash in a caption or a range given in words:

.. raw:: html
   :file: figure-1.normalized.html

.. raw:: html
   :file: figure-19.normalized.html

In the data model
-----------------

The figures become what they define. The opcode table gives the command
Ring, opcode 04h, its footnote marker dropped from the name; three dword
figures give its submission queue entry, Figures 18, 19 and 20, each dword
citing the figure and page it is from. The command is one entry of the
data model, which the expert, the MCP server and the code generator all
read:

.. literalinclude:: ring.json
   :language: json

What the author sees
--------------------

Reading the figures as data is checking them, and what does not read as
data is a candidate erratum, with the document, section, figure and page.
No rule was written for any of these; each is a figure that did not fit
its kind. The opcode of Zing is not a value. The acronym of Ring Mode has
a space in it. Bits 0 to 15 of Ring's dword 11 belong to no field. Bit 64
of Ring Tail lies beyond the 64 bits of its two dwords. A support
requirement reads "Maybe", which is no level:

.. literalinclude:: errata.txt
   :language: text

``senfd lint`` lists these together with the document errors, the
figures of a shape senfd does not read, and the dwords no command claims;
see :ref:`the linter <sec-linting>`. On a draft, this is the check an
editor gets for nothing from making the data model.
