.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-tutorial:

Get started
===========

From nothing to a data model of the NVMe specifications, and an expert
answering from it, in a handful of commands. You need Python 3.11 or later
and `pipx <https://pipx.pypa.io/stable/>`_.

Install
-------

.. code-block:: console

   $ pipx install "senfd[sate,pdf]"

This installs four commands in a virtual environment of their own:
``senfd`` makes the data model, ``senfd-query`` and ``sate`` answer from
it, and ``sate-mcp`` serves it to a coding agent. :ref:`Install
<sec-install>` says what the extras bring.

Get the documents
-----------------

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

Make the data model
-------------------

.. code-block:: console

   $ senfd ~/specs/*.pdf --output ~/.cache/senfd

This takes a few minutes, two of them for the Base specification. The
data models of the documents are merged into
``~/.cache/senfd/merged.spec.document.json``, where ``senfd-query``,
``sate`` and ``sate-mcp`` look by default; :ref:`making the data model
<sec-usage>` names the other files. The run ends by saying what it made and
what to look at:

.. code-block:: text

   11 documents into ~/.cache/senfd/merged.spec.document.json: 100 commands, 51 features, 59 log pages and 613 structures.
   For the authors: 2 candidate errata and 6 document errors. For senfd, or the figures: 23 figures not modelled, 16 worked examples and 19 unassigned dwords.
   List them: senfd-query lint

Reading the figures as data checks them. The last line says how to list
what did not read as data, the authors' findings first:

.. code-block:: console

   $ senfd-query lint

Each finding cites the document, the figure and the page. :ref:`The
linter <sec-linting>` says what each category is.

.. raw:: html

   <div id="cast-lint"></div>

Ask the expert
--------------

.. code-block:: console

   $ sate

The session opens with a menu of the questions it answers, and ``?`` on an
empty line opens it again. Tab completes a name or an acronym from the data
model. The line at the bottom says how the question is read so far. Ask as
you would ask a colleague:

.. code-block:: text

   sate> opcode of sanitize
   sate> which bit of cdw12 of write is FUA
   sate> describe cdw12 of write
   sate> structure identify controller
   sate> CRIME

The first answers with the command's set, opcode and figure. The second
answers with the fields of the dword, the bit asked for marked, and says
"FUA, Force Unit Access, is bit 30 of cdw12 of Write". ``describe`` adds
the description of each field. An acronym alone finds the field everywhere
it is. Every citation, ``[NVM 1.3, 3.3.6, Figure 71, page 54, PDF page
54]``, is a link to that page of the published PDF. Ctrl-D leaves the
session. :ref:`The expert <sec-ask>` lists every form a question can take.

.. raw:: html

   <div id="cast-session"></div>

A question on the command line is answered and that is all:

.. code-block:: console

   $ sate "What is the opcode of the Sanitize Namespace command?"
   $ senfd-query command write 12
   $ senfd-query --markdown structure "Controller Status"

.. raw:: html

   <div id="cast-lookups"></div>

Give it to an agent
-------------------

The same answers are the tools of an MCP server, for a coding agent to ask
the specification rather than remember it:

.. code-block:: console

   $ claude mcp add sate -- sate-mcp

Each tool answers in Markdown with its citations linked, so the agent can
open the figure it was told of. The :ref:`benchmark <sec-benchmark>` shows
what answering from the data model is worth.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     for (const [id, cast] of [["cast-lint", "lint"], ["cast-session", "session"], ["cast-lookups", "lookups"]]) {
       AsciinemaPlayer.create(`../_static/casts/${cast}.cast`, document.getElementById(id),
         {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
          poster: "npt:0:12"});
     }
   </script>
