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

Place yourself in the root of the repository and run:

.. literalinclude:: usage_example.cmd
   :language: bash

This extracts the figures of the ``.docx`` file, their captions and tables,
into a ``FigureDocument``; normalises each into a ``NormalizedFigureDocument``,
by the shape of its table and the subject of its caption, with diagnostics
saying what was normalised; and makes the model of the specification of it, a
``SpecDocument``. The ``SpecDocument`` of every document given is merged into
``merged.spec.document.json``.

For all of the output files then they are stored in the directory pointed to
by ``--output``, in this case ``/tmp/foo``, each named by the input-document
it is made from.

In case you do not want to run it, then you can inspect the output files in the
`repository on GitHUB <https://github.com/safl/senfd/tree/main/example/output>`_
or locally in the folder ``example/output``.

For details on the structure of the **JSON** documents, then have a look at
the :ref:`schema <sec-schema>` section.

.. _sec-usage-query:

Query
~~~~~

The merged model answers questions about the specification. Make it once, from
the documents you have, into the cache:

.. code-block:: bash

   senfd path/to/specs/*.docx --output ~/.cache/senfd

Then ask, and each answer cites where it came from, the document, the
section, the figure and the page, as ``[Base 2.2, 5.1.10, Figure 190, page
195]``:

.. code-block:: bash

   senfd-query command write 12
   senfd-query feature 07h
   senfd-query log-page 02h
   senfd-query structure "Controller Status"
   senfd-query search FUA
   senfd-query section 5.1.25
   senfd-query errata Base

A value that is not what its kind must be, as a range beyond the dwords it is
of or an acronym that is not one, is left out of the model and is an erratum,
as are bits of a command's dwords that no figure gives a field; ``errata``
lists them, each with where it is, for the documents to be corrected.

``--spec`` or the environment variable ``SENFD_SPEC`` points at another
merged model, and ``--verbose`` gives the descriptions too.

The same queries are the tools of an MCP server, ``senfd-mcp``, installed with
``pip install senfd[mcp]``. Registered with an agent, it answers a question
about the specification with a tool call rather than by reading the documents:

.. code-block:: bash

   claude mcp add senfd -- senfd-mcp

.. _sec-usage-yace:

Spec headers, by yace
~~~~~~~~~~~~~~~~~~~~~

senfd is a generator for **yace**: it writes the spec header of the commands
of the model, a struct of each command's dwords with the masks of its fields,
named by the specification's acronyms and citing their figures, and the
function making a command, for **yace** to parse as any header, so its
pretty-printers, bindings and checks apply:

.. code-block:: bash

   yace --generate senfd --generator-option senfd.commands=nvm --emit capi python

The options are ``spec``, the merged model, by default the one in the cache,
``prefix``, by default ``spec``, and ``commands``, command sets or commands of
them, as ``nvm`` or ``nvm:write``. ``senfd-header <output> [key=value ...]``
writes the same without **yace**.

.. _sec-usage-auxiliary:

Auxiliary
~~~~~~~~~

The following tools are also convenient to have available when inspecting the
JSON files:

* bar - https://github.com/sharkdp/bat
* jless - https://jless.io/
* jq - https://jqlang.github.io/jq/

