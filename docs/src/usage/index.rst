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
member of NVM Express may use the ``.docx`` of the same documents instead,
and gets the same data model. Read :ref:`the notices <sec-notices>` on
what the data model may be used for.

.. code-block:: console

   $ senfd ~/specs/*.pdf --output ~/.cache/senfd

This takes a few minutes, two of them for the Base specification. The run
ends by saying what it made, and how many of the figures to look at, which
``senfd lint`` lists; see :ref:`linting the documents <sec-linting>`.

The files
---------

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
rendering beside them. :ref:`The stages <sec-stages>` show what a figure
becomes at each, and :ref:`the schema <sec-schema>` what the JSON holds.

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

It ends by saying:

.. literalinclude:: usage_example.out
   :language: text

The output of this run is kept in the repository, in `example/output
<https://github.com/safl/senfd/tree/main/example/output>`_. `jless
<https://jless.io/>`_ and `jq <https://jqlang.github.io/jq/>`_ are handy
for reading the JSON. ``sate`` reads the merged data model; see :ref:`the expert <sec-ask>`.
