.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-usage:

Usage
-----


.. literalinclude:: usage.cmd
   :language: bash


.. literalinclude:: usage.out
   :language: bash


.. _sec-usage-example:

Example
~~~~~~~

Run it over the documents you hold; here over the synthetic example
document in senfd's repository, ``example/example.docx``:

.. literalinclude:: usage_example.cmd
   :language: bash

A run ends by saying what it made, what of the documents to look at, and the
command listing it:

.. literalinclude:: usage_example.out
   :language: text

This extracts the figures of the ``.docx`` file, their captions and tables,
into a ``FigureDocument``; normalises each into a
``NormalizedFigureDocument``, by the shape of its table and the subject of its
caption, with diagnostics saying what was normalised; and makes the data model
of the specification of it, a ``SpecDocument``. The ``SpecDocument`` of every
document given is merged into ``merged.spec.document.json``.

Every output goes into the directory ``--output`` names, each file named by
the document it is made from.

In case you do not want to run it, then you can inspect the output files in the
`repository on GitHUB <https://github.com/safl/senfd/tree/main/example/output>`_
or locally in the folder ``example/output``.

For details on the structure of the **JSON** documents, then have a look at
the :ref:`schema <sec-schema>` section.

.. _sec-usage-query:

Query
~~~~~

The merged data model answers questions about the specification. Make it once,
from the documents you have, into the cache:

.. code-block:: bash

   senfd path/to/specs/*.docx --output ~/.cache/senfd

Then ask, and each answer cites where it came from, the document, the
section, the figure and the page, as ``[Base 2.4, 5.2.13, Figure 203, page
213]``, and, where the data model was made from a PDF, the page of the file,
``page 213, PDF page 238``:

.. code-block:: bash

   senfd-query command write 12
   senfd-query feature 07h
   senfd-query log-page 02h
   senfd-query structure "Controller Status"
   senfd-query search FUA
   senfd-query section 5.2.6
   senfd-query errata Base
   senfd-query lint

A value that is not what its kind must be, as a range beyond the dwords it is
of or an acronym that is not one, is left out of the data model and is an
erratum, as are bits of a command's dwords that no figure gives a field;
``errata`` lists them, each with where it is, for the documents to be
corrected, and ``lint`` lists them with what senfd could not read as data;
see :ref:`the linter <sec-linting>`.

``--spec`` or the environment variable ``SENFD_SPEC`` points at another merged
data model, and ``--verbose`` gives the descriptions too. ``--markdown`` gives
the fields of a command, feature, log page or structure as a Markdown table,
for an answer shown to a reader, and makes each citation of a document NVM
Express publishes a link to the page of its PDF, known by the SHA-256 of
the file the data model was made from.

The same queries are the tools of an MCP server, ``sate-mcp``, installed with
``pip install senfd[sate]``. Registered with an agent, it answers a question
about the specification with a tool call rather than by reading the documents:

.. code-block:: bash

   claude mcp add sate -- sate-mcp

.. _sec-usage-auxiliary:

Auxiliary
~~~~~~~~~

The following tools are also convenient to have available when inspecting the
JSON files:

* bar - https://github.com/sharkdp/bat
* jless - https://jless.io/
* jq - https://jqlang.github.io/jq/

