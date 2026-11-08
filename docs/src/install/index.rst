.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-install:

Install
=======

senfd is a Python package, on `PyPI <https://pypi.org/project/senfd/>`_, tested
on Python 3.10 to 3.12, on Linux and macOS; on Windows, use it in WSL or a
container. `pipx <https://pipx.pypa.io/stable/>`_ installs it with its commands
in a virtual environment of its own:

.. code-block:: console

   $ pipx install "senfd[ask,mcp]"

The extras are what the commands beyond ``senfd`` and ``senfd-query`` need:

* ``ask``, the prompt and rendering of ``senfd-ask``, by prompt_toolkit and
  rich; without it, ``senfd-ask`` reads a question a line and prints Markdown.
* ``mcp``, the MCP server ``senfd-mcp``.

Then make the data model, once, from the documents you have:

.. code-block:: console

   $ senfd ~/specs/*.docx --output ~/.cache/senfd

``senfd-query``, ``senfd-ask`` and ``senfd-mcp`` read it from there, or from
the file ``SENFD_SPEC`` names. The documents are the ratified specifications
as ``.docx``, from `NVM Express <https://nvmexpress.org/specifications/>`_.

.. note::
  senfd reads ``.docx`` with python-docx, which needs the system libraries
  ``libxml2`` and ``libxslt``; pipx does not install them.
