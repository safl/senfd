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

   $ pipx install "senfd[ask,mcp,pdf]"

The extras are what the commands beyond ``senfd`` and ``senfd-query`` need:

* ``ask``, the prompt and rendering of ``senfd-ask``, by prompt_toolkit and
  rich; without it, ``senfd-ask`` reads a question a line and prints Markdown.
* ``mcp``, the MCP server ``senfd-mcp``.
* ``pdf``, reading the specifications as the PDFs NVM Express publishes, by
  pikepdf and pdfplumber; without it, senfd reads the ``.docx`` only.

Then make the data model, once, from the documents you have:

.. code-block:: console

   $ senfd ~/specs/*.pdf --output ~/.cache/senfd

``senfd-query``, ``senfd-ask`` and ``senfd-mcp`` read it from there, or from
the file ``SENFD_SPEC`` names. The documents are the ratified specifications,
as the PDFs `NVM Express <https://nvmexpress.org/specifications/>`_ publishes
for anyone to download, or as the ``.docx`` its members hold. A PDF must keep
the structure of its tables, as NVM Express's do, being exported from Word
with its document structure tags; one without is refused.

.. note::
  senfd reads ``.docx`` with python-docx, whose lxml installs as a prebuilt
  wheel on most systems; where pip has to build it, it needs the system
  libraries ``libxml2`` and ``libxslt``.
