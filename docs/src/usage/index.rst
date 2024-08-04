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

This will extract table and figure information from the ``.docx`` file,
storing it as a ``FigureDocument`` with minimal semantic enrichment, then the
``FigureDocument`` is processed producing a ``CategorizedFigureDocument`` with
figures categorized by the content they are captioning.

For all of the output files then they are stored in the directory pointed to
by ``--output``, in this case ``/tmp/foo``. Each input-document gets a folder
dedicated to the output files related to it.

In case you do not want to run it, then you can inspect the output files in the
`repository on GitHUB <https://github.com/safl/senfd/tree/main/example/output/document1>`_
or locally in the folder ``example/output/document1``.

For details on the structure of the **JSON** documents, then have a look at
the :ref:`schema <sec-schema>` section.