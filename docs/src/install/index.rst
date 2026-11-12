.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-install:

Install
=======

senfd is a Python package on `PyPI <https://pypi.org/project/senfd/>`_,
tested on Python 3.13 to 3.15 on Linux and macOS. On Windows, use it in WSL
or :ref:`in a container <sec-install-container>`. `pipx
<https://pipx.pypa.io/stable/>`_ installs senfd and its commands in a
virtual environment of their own:

.. code-block:: console

   $ pipx install senfd

The package installs four commands. ``senfd`` makes the data model and
lints the documents. ``sate`` answers questions from the data model.
``sate-web`` answers questions on a web page. ``sate-mcp`` serves the data
model to a coding agent as an MCP server.

senfd reads a PDF only when the PDF keeps the structure of its tables. A
PDF exported from Word with its document structure tags keeps that
structure, and the PDFs NVM Express publishes are exported that way. senfd
refuses a PDF without the tags. When a PDF is published with its tracked
changes shown, senfd reads it as the document with the changes accepted:
senfd leaves out the struck-through deletions and keeps the insertions.

senfd reads the ``.docx`` with python-docx, which depends on lxml. lxml
installs as a prebuilt wheel on most systems. Where pip has to build lxml,
the build needs the system libraries ``libxml2`` and ``libxslt``.

.. _sec-install-container:

In a container
--------------

If the dependencies do not install on your system, use the container image
published with each release. The image holds senfd and all of its
dependencies:

.. code-block:: console

   $ docker pull ghcr.io/safl/senfd

The image of each release is also tagged with its version, as
``ghcr.io/safl/senfd:X.Y.Z``. The image holds no specification. Mount the
directory that holds the documents and a directory to keep the data model
in, and run the container as your own user, so that you own the files it
writes:

.. code-block:: console

   $ mkdir -p ~/.cache/senfd
   $ docker run --rm --user "$(id -u):$(id -g)" \
       -v ~/specs:/specs:ro -v ~/.cache/senfd:/home/senfd/.cache/senfd \
       ghcr.io/safl/senfd sh -c 'senfd /specs/*.pdf --output ~/.cache/senfd'
   $ docker run --rm -it --user "$(id -u):$(id -g)" \
       -v ~/.cache/senfd:/home/senfd/.cache/senfd ghcr.io/safl/senfd

The first command makes the data model, and the second command opens the
expert's session. Rootless Podman already runs the container as your own
user, so leave out ``--user`` there. The documents must be files in the
mounted directory. A symbolic link to a file outside that directory does
not resolve inside the container.
