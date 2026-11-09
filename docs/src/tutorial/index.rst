.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-tutorial:

Get started
===========

From nothing to a data model of the NVMe specifications, and an expert
answering from it, in a handful of commands. You need Python 3.11 or later
and `pipx <https://pipx.pypa.io/stable/>`_; everything else comes with
senfd.

Install
-------

.. code-block:: console

   $ pipx install "senfd[sate,pdf]"

This installs four commands in a virtual environment of their own: ``senfd``,
which makes the data model; ``senfd-query``, which answers from it on the
command line; ``sate``, the expert to ask; and ``sate-mcp``, the same
answers as tools for a coding agent. The extra ``pdf`` reads the PDFs, the
extra ``sate`` gives the expert its prompt and its rendering; see
:ref:`install <sec-install>` for what each brings.

Get the documents
-----------------

NVM Express publishes the ratified specifications as PDF, for anyone to
download, at `nvmexpress.org/specifications
<https://nvmexpress.org/specifications/>`_. Download the eleven documents
ratified in 2026, the Base specification, the command sets, the Management
Interface, Boot and the transports, into one directory, ``~/specs`` here.
senfd knows these files by their SHA-256, listed in
``src/senfd/published.toml`` of its repository, so a data model made from
them cites each figure with a link to its page of the PDF. A member of NVM
Express may use the ``.docx`` of the same documents instead, and gets the
same data model.

The documents are NVM Express's, and the data model made from them is
under the notice printed in each specification, which lets members use it
and lets anyone else review, refer to and cite the specification; see
:ref:`the terms <sec-terms>`.

Make the data model
-------------------

.. code-block:: console

   $ senfd ~/specs/*.pdf --output ~/.cache/senfd

A few minutes; the Base specification alone takes about two. Each document
becomes three JSON files in ``~/.cache/senfd``, its figures as read, as
normalised and as the data model of that one document, each with an HTML
rendering beside it, and all of them merged into
``merged.spec.document.json``, which ``senfd-query``, ``sate`` and
``sate-mcp`` read from there by default. The run ends by saying what it
made and what to look at:

.. code-block:: text

   11 documents into ~/.cache/senfd/merged.spec.document.json: 100 commands, 51 features, 59 log pages and 613 structures.
   For the authors: 2 candidate errata and 6 document errors. For senfd, or the figures: 23 figures not modelled, 16 worked examples and 19 unassigned dwords.
   List them: senfd-query lint

Reading the figures as data checks them, and the last line says how to
list what did not read as data, the authors' findings first:

.. code-block:: console

   $ senfd-query lint

The candidate errata are values that are not what their column's kind must
be, as a footnote marker run into a flag, or a field whose bits lie beyond
its dwords; the document errors are what the documents get wrong as
documents, as a caption not of its form, or a heading that the PDF's
tagging puts inside a table; the rest is senfd's to learn, figures of a
shape it does not model yet, and the worked examples, which are figures
of no shape to model. Each finding cites the document, the figure and the
page. :ref:`The linter <sec-linting>` says what each category is.

.. raw:: html

   <div id="cast-lint"></div>

Ask the expert
--------------

.. code-block:: console

   $ sate

The session opens with a menu of the questions it answers; ``?`` on an empty
line opens it again, Tab completes a name or an acronym from the data model
as you type, and the line at the bottom says how the question is read so
far. Ask as you would ask a colleague:

.. code-block:: text

   sate> opcode of sanitize
   sate> which bit of cdw12 of write is FUA
   sate> describe cdw12 of write
   sate> structure identify controller
   sate> CRIME

The first answers with the one line asked for, the command's set, opcode and
figure. The second answers with the fields of the dword, the bit asked for
marked, and says where it is: "FUA, Force Unit Access, is bit 30 of cdw12
of Write". ``describe`` before a question adds the description of each
field. A data structure's table is headed by bytes, and where a byte holds
bits the bits stand in a column of their own beside it. An acronym alone
finds the field everywhere it is.

Each answer opens with a rule naming the question, so its start stands out
when scrolling back. An answer taller than the terminal opens in a pager,
from its top; ``q`` leaves it and the answer stays on the screen. Every
citation, ``[NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]``, is a link
to that page of the published PDF: Ctrl+Click it in a terminal that shows
links, or ask with ``sate --raw "..."`` to see the address. Ctrl-D leaves
the session.

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
open the figure it was told of. :ref:`The expert <sec-ask>` lists every
form a question can take; the :ref:`benchmark <sec-benchmark>` shows what
answering from the data model is worth.

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
