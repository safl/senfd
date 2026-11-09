.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-usage:

Make the data model
===================

``senfd`` reads the documents given, ``.pdf`` or ``.docx``, and writes three
files of each into the directory ``--output`` names:

* ``<name>.plain.figure.document.json``, the ``FigureDocument``: its figures
  as written, a row of cells each.
* ``<name>.normalized.figure.document.json``, the
  ``NormalizedFigureDocument``: each figure read as the kind it is, with
  diagnostics saying what was normalised.
* ``<name>.spec.document.json``, the ``SpecDocument``: the data model of
  that one document.

The data models of every document given are merged into
``merged.spec.document.json``. The files of each document have an HTML
rendering beside them. :ref:`The stages <sec-stages>` show what a figure becomes at each, and
:ref:`the schema <sec-schema>` what the JSON holds.

.. literalinclude:: usage.cmd
   :language: bash

.. literalinclude:: usage.out
   :language: text

.. _sec-usage-example:

Example
-------

senfd's repository holds a synthetic document, ``example/example.docx``,
written to exercise the reader. Run over it:

.. literalinclude:: usage_example.cmd
   :language: bash

A run ends by saying what it made, what of the documents to look at, and
the command listing it:

.. literalinclude:: usage_example.out
   :language: text

The output of this run is kept in the repository, in `example/output
<https://github.com/safl/senfd/tree/main/example/output>`_. `jless
<https://jless.io/>`_ and `jq <https://jqlang.github.io/jq/>`_ are handy
for reading the JSON. ``senfd-query`` and ``sate`` read the merged data
model; see :ref:`the expert <sec-ask>`.
