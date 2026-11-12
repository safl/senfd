.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-usage:

Make the data model
===================

NVM Express publishes the ratified specifications as PDF, for anyone to
download, at `nvmexpress.org/specifications
<https://nvmexpress.org/specifications/>`_. Download the eleven documents
ratified in 2026 into one directory, ``~/specs`` here: Base 2.4, the NVM,
Zoned Namespace, Key Value, Subsystem Local Memory and Computational
Programs command sets, Management Interface 2.2, Boot 1.4, and the PCIe,
RDMA and TCP transports. senfd knows these files by their SHA-256, so a
data model made from them links each citation to its page of the PDF. A
member of NVM Express may give senfd the ``.docx`` of the same documents
instead, and senfd makes the same data model from them. Read :ref:`the notices <sec-notices>` on
what the data model may be used for.

.. code-block:: console

   $ senfd ~/specs/*.pdf --output ~/.cache/senfd

The command takes a few minutes, two of them for the Base specification.
At the end, senfd says what it made and how many figures to look at.
``senfd lint`` lists those figures; see :ref:`linting the documents
<sec-linting>`.

The files
---------

``senfd`` reads the documents it is given, ``.pdf`` or ``.docx``, and
writes three files for each document into the directory that ``--output``
names:

* ``<name>.plain.figure.document.json``, the ``FigureDocument``: the document's
  figures as written, each figure as rows of cells.
* ``<name>.normalized.figure.document.json``, the
  ``NormalizedFigureDocument``: each figure read as the kind it is, with
  diagnostics saying what was normalised.
* ``<name>.spec.document.json``, the ``SpecDocument``: the data model of
  that one document.

senfd merges the data models of all the documents into
``merged.spec.document.json``. Each of the three files of a document has an
HTML rendering beside it. :ref:`The stages <sec-stages>` show what a figure
becomes at each stage, and :ref:`the schema <sec-schema>` describes what
the JSON holds.

.. literalinclude:: usage.cmd
   :language: bash

.. literalinclude:: usage.out
   :language: text

.. _sec-usage-example:

Example
-------

senfd's repository holds a synthetic document, ``example/example.docx``,
written to exercise the reader. Run senfd over it:

.. literalinclude:: usage_example.cmd
   :language: bash

The run ends with:

.. literalinclude:: usage_example.out
   :language: text

The repository keeps the output of this run in `example/output
<https://github.com/safl/senfd/tree/main/example/output>`_. `jless
<https://jless.io/>`_ and `jq <https://jqlang.github.io/jq/>`_ are useful
for reading the JSON. ``sate`` answers questions from the merged data
model; see :ref:`the expert <sec-ask>`.
