.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-install:

Install
=======

senfd is a Python package on `PyPI <https://pypi.org/project/senfd/>`_,
tested on Python 3.11 to 3.13 on Linux and macOS. On Windows, use it in WSL
or a container. `pipx <https://pipx.pypa.io/stable/>`_ installs it with its
commands in a virtual environment of their own:

.. code-block:: console

   $ pipx install senfd

This installs four commands: ``senfd`` makes the data model,
``senfd-query`` and ``sate`` answer from it, and ``sate-mcp`` serves it to
a coding agent.

A PDF must keep the structure of its tables, as NVM Express's do, being
exported from Word with its document structure tags; one without is
refused. A PDF published with its tracked changes shown reads as the
document with them accepted: the struck-through deletions are left out and
the insertions kept.

The ``.docx`` is read with python-docx. Its lxml installs as a prebuilt
wheel on most systems; where pip has to build it, it needs the system
libraries ``libxml2`` and ``libxslt``.
