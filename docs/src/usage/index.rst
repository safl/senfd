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

Place yourself in the root of the repository and run::

  senfd example/example.figure.document.json --output /tmp/foo

This will enrich the given figure(s) with semantic information, by first
categorizing them, then parse the associated table data into a logical
form. The enriched figures are stored in the folder
pointed to by ``--output``, in this case ``/tmp/foo``.

In case you do not want to run it, then you can inspect the
`JSON <https://github.com/safl/senfd/blob/main/example/output/categorized.figure.document.json>`_
in the
`repository on GitHUB <https://github.com/safl/senfd/tree/main/example/output>`_
or locally in the folder ``example/output``.

For details on the structure of the **JSON** document, then have a look at
the :ref:`schema <sec-schema>` section.