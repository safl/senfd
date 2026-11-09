.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-usage:

Usage
=====

``senfd`` reads the documents given and writes, into the directory
``--output`` names, three files of each, named by the document: its figures
as written, a ``FigureDocument``; each figure normalised by the shape of its
table and the subject of its caption, a ``NormalizedFigureDocument``, with
diagnostics saying what was normalised; and the data model of the
specification, a ``SpecDocument``. The ``SpecDocument`` of every document
given is merged into ``merged.spec.document.json``. :ref:`The stages
<sec-stages>` show what a figure becomes at each, and :ref:`the schema
<sec-schema>` what the JSON holds.

.. literalinclude:: usage.cmd
   :language: bash

.. literalinclude:: usage.out
   :language: bash

.. _sec-usage-example:

Example
-------

Run over the synthetic example document in senfd's repository,
``example/example.docx``:

.. literalinclude:: usage_example.cmd
   :language: bash

A run ends by saying what it made, what of the documents to look at, and
the command listing it:

.. literalinclude:: usage_example.out
   :language: text

The output of this run is kept in the repository, in `example/output
<https://github.com/safl/senfd/tree/main/example/output>`_. `bat
<https://github.com/sharkdp/bat>`_, `jless <https://jless.io/>`_ and `jq
<https://jqlang.github.io/jq/>`_ are handy for reading the JSON.

.. _sec-usage-query:

Query
-----

``senfd-query`` answers from the merged data model on the command line.
Each answer cites the document, the section, the figure and the page, as
``[NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]``, the page of the file
last where the data model was made from a PDF:

.. code-block:: console

   $ senfd-query command write 12
   $ senfd-query feature 07h
   $ senfd-query log-page 02h
   $ senfd-query structure "Controller Status"
   $ senfd-query search FUA
   $ senfd-query section 5.2.6
   $ senfd-query errata Base
   $ senfd-query lint

``command`` takes a command's name and, after it, the number of one of its
dwords; ``feature`` and ``log-page`` a name or an identifier; ``structure``
a name or an acronym; ``search`` a word or an acronym, found everywhere it
is; ``section`` a section's number; ``errata`` and ``lint`` a document to
confine the findings to, see :ref:`the linter <sec-linting>`. ``--verbose``
adds the descriptions. ``--markdown`` gives the fields as a Markdown table
and makes each citation of a document NVM Express publishes a link to the
page of its PDF, known by the SHA-256 of the file the data model was made
from. ``--spec``, or the environment variable ``SENFD_SPEC``, points at
another data model.

The same lookups answer ``sate`` and are the tools of ``sate-mcp``; see
:ref:`the expert <sec-ask>`.
