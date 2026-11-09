.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-ask:

Ask the expert
==============

``sate`` answers questions about the specifications as an expert would, at
once, and only from senfd's data model. Alone on the command line it opens
a session; given a question, it answers that and leaves, and with ``--raw``
it prints the answer as Markdown, unrendered, the links as addresses.
:ref:`Getting started <sec-tutorial>` walks through a session; this page is
the reference of what it answers and how.

The forms of a question
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Ask
     - As
   * - a command, with its dwords
     - ``write``, ``zone append``
   * - a command's opcode alone
     - ``opcode of sanitize``
   * - one dword of a command
     - ``cdw12 of write``, ``dword 10 of get log page``
   * - a bit or bits of a dword
     - ``which bit of cdw12 of write is FUA``, ``which bits of cdw12 of
       write are PRINFO``
   * - a feature or a log page
     - ``feature 07h``, ``feature number of queues``, ``log page 1Fh``
   * - what an identifier is
     - ``1Fh``
   * - a structure or a register
     - ``structure identify controller``, ``CC``, ``CSTS``
   * - a field, everywhere it is
     - ``FUA``, ``search storage tag``
   * - any of these with the descriptions
     - ``describe cdw12 of write``, ``explain CSTS``
   * - a section
     - ``section 5.2.6``
   * - what the documents may have wrong
     - ``errata``, ``errata nvm``

No language model is involved. A question is read by its words, as "opcode
of", "cdw12 of", "feature", "log page" or "section"; by an identifier, as
``1Fh``; and by the names and acronyms of the data model it names, the
longest first, so "the controller status register" is ``CSTS`` and "dword
13 of Zone Append" is that dword of that command. Each answer starts by
saying what the question was understood as, ``command('Zone Append',
dword=13)``, so a question understood otherwise than meant shows at once.

An answer is shown only when it mentions every term of the question that
names something. Ask for the bit of Write that "enables the hyperdrive" and
the answer is that it is not known, not the fields of Write that were found
for the question's other words. And an answer is shown only when it is
about what the question names: asked for the opcode of Read, the answer
must be Read, not Memory Read or Copy, whose names or fields mention it;
asked for the opcode of "Track", a word of several commands' names, the
answer is that it is not known.

The session
-----------

The session is made for someone who does not yet know how to ask. It opens
with the questions it can answer in a menu, ``what is the opcode of
<command>?``, ``which bit of cdw<N> of <command> is <acronym>?`` and the
others, and ``?`` on an empty line opens that menu again. Each part of a
question completes as you type, with Tab, from what the data model holds,
each completion shown with its kind: after "opcode of", the commands; after
"log page", the log pages; and after "which bit of cdw12 of Write is", the
acronyms of the fields of that dword, in the order of its figure. A name
completes from where it starts, so "zone app" completes to Zone Append, and
a word typed in capitals is completed by acronyms.

The words of the question it recognises, names and acronyms are coloured as
you type them. The line at the bottom says how the question is read so far,
``Read as command('Write', dword=12)``, or what comes next in it, as the
number of a dword after "cdw" or a field of cdw12 of Write after "is".
Under it are the keys that do something at that moment: in the menu, Tab
and the arrows to choose, Enter to take the choice, which does not yet ask,
and Esc to close it; on an empty line, ``?``, Up and Down for the questions
asked before, kept between sessions, F1 or ``help`` for the forms above
with their examples, and Ctrl-D to leave.

The answers
-----------

Each answer opens with a rule naming the question, so that where it starts
stands out when scrolling back. An answer asked of a field ends by saying
where that field is, citing its figure, as "**FUA**, Force Unit Access, is
bit 30 of cdw12 of Write [NVM 1.3, 3.3.6, Figure 71, page 54, PDF page
54]", with its row marked in the table above. Under each answer a line says
what the question was read as, by how many lookups, in how long, and how
many figures it cites, or that it is not known. An answer taller than the
terminal opens in a pager, from its top, and stays on the screen when the
pager is quit, with where the fields asked of are said again after it.

A table of a data structure is headed by bytes, and where a byte holds
bits, as the Reservation Capabilities of a namespace, the bits stand in a
column of their own beside it, named by both acronyms, as ``RESCAP.PTPLS``.
``describe`` or ``explain`` before any question answers it with the
descriptions of the fields, the first line of each. Every citation of a
document NVM Express publishes as PDF is a link to the page of that PDF,
which a terminal that shows links opens in the browser; the citation says
the page of the file too, ``page 54, PDF page 54``, for a PDF saved rather
than shown.

With a language model, for free, on your own hardware
-----------------------------------------------------

``--llm URL`` has a language model served at URL, as by llama.cpp's
``llama-server``, understand the questions instead, for questions phrased
in ways no rule foresees:

.. code-block:: console

   $ llama-server -m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --port 8088 --jinja
   $ sate --llm http://127.0.0.1:8088

The language model chooses the lookup and nothing else. Its output is
constrained, by a JSON schema the server turns into a grammar, to the name
of a query and its argument; the answer shown is what the query found. It
writes no part of the answer, so it can state no field, bit or opcode that
is not in the figures. When a lookup finds nothing, or nothing mentioning
the question's terms, it is told so and chooses again, three times at most,
and then the answer is that it is not known. A language model of 8 billion
parameters on a CPU is enough, as the :ref:`benchmark <sec-benchmark>`
shows; no GPU, no service and no fee. A smaller language model chooses
worse, and what it cannot find it says is not known: the language model of
1 billion parameters answers fewer of the questions, and none of them
wrongly.

.. raw:: html

   <div id="cast-llm"></div>

For an agent: the MCP server
----------------------------

The same lookups are the tools of an MCP server, ``sate-mcp``, for a coding
agent to answer a question about the specification with a tool call costing
a few lines rather than by reading the documents:

.. code-block:: console

   $ claude mcp add sate -- sate-mcp

Its answers are those of ``senfd-query --markdown``, each citation a link
to the page of the published PDF, so the agent can open the figure it was
told of.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/llm.cast", document.getElementById("cast-llm"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
