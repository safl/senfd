.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-ask:

Ask the expert
==============

``senfd-ask`` answers questions about the specifications as an expert would,
at once, and only from senfd's data model. Ask it as you would ask a
colleague:

.. code-block:: console

   $ pip install senfd[ask]
   $ senfd-ask
   ask> opcode of zone append
   ask> Which bit of CDW12 of the Write command is FUA?
   ask> What are the fields of the controller status register?
   ask> log page 1Fh
   ask> FUA

The session is made for someone who does not yet know how to ask. It opens
with the questions it can answer in a menu, ``what is the opcode of
<command>?``, ``which bit of cdw<N> of <command> is <acronym>?`` and the
others, and ``?`` on an empty line opens that menu again. Each part of a
question then completes as you type, with Tab, from what the data model
holds, each completion shown with its kind: after "opcode of", the
commands; after "log page", the log pages; and after "which bit of cdw12 of
Write is", the acronyms of the fields of that dword, in the order of its
figure. A name completes from where it starts, so "zone app" completes to
Zone Append, and a word typed in capitals is completed by acronyms.

The words of the question it recognises, names and acronyms are coloured
as you type them, and the line at the bottom says how the question is read
so far, ``Read as command('Write', dword=12)``, or what kind of name comes
next in it, above the keys: Tab, ``?``, Up and Down for the questions asked
before, kept between sessions, F1 for the forms of a question with examples,
and Ctrl-D to leave. An answer asked of a field ends by saying where that
field is, citing its figure, as "**FUA**, Force Unit Access, is bit 30 of
cdw12 of Write [NVM 1.3, 3.3.6, Figure 71, page 54]", with its row marked in
the table above, and under each answer a line says what the question was
read as, by how many lookups, in how long, and how many figures it cites.

.. raw:: html

   <div id="cast-session"></div>

Given a question on the command line, it answers that and leaves:

.. code-block:: console

   $ senfd-ask "What is the opcode of the Sanitize Namespace command?"

.. raw:: html

   <div id="cast-lookups"></div>

How a question is understood
----------------------------

No language model is involved. A question is read by its words, as "opcode
of", "cdw12 of", "feature", "log page" or "section"; by an identifier, as
``1Fh``; and by the names and acronyms of the data model it names, the longest
first, so "the controller status register" is ``CSTS`` and "dword 13 of Zone
Append" is that dword of that command. Each answer starts by saying what the
question was understood as, ``command('Zone Append', dword=13)``, so a
question understood otherwise than meant shows at once.

Each answer is the answer of a query of the data model, rendered as a table,
with the figure it cites. An answer is shown only when it mentions every term
of the question that names something. Ask for the bit of Write that "enables
the hyperdrive" and the answer is that it is not known, not the fields of
Write that were found for the question's other words. And an answer is shown
only when it is about what the question names: asked for the opcode of Read,
the answer must be Read, not Memory Read or Copy, whose names or fields
mention it; asked for the opcode of "Track", a word of several commands'
names, the answer is that it is not known.

With a language model, for free, on your own hardware
-----------------------------------------------------

``--llm URL`` has a language model served at URL, as by llama.cpp's
``llama-server``, understand the questions instead, for questions phrased
in ways no rule foresees:

.. code-block:: console

   $ llama-server -m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --port 8088 --jinja
   $ senfd-ask --llm http://127.0.0.1:8088

The language model chooses the lookup and nothing else. Its output is
constrained, by a JSON schema the server turns into a grammar, to the name of
a query and its argument; the answer shown is what the query found. It writes
no part of the answer, so it can state no field, bit or opcode that is not in
the figures. When a lookup finds nothing, or nothing mentioning the question's
terms, it is told so and chooses again, three times at most, and then the
answer is that it is not known. A language model of 8 billion parameters on a
CPU is enough, as the :ref:`benchmark <sec-benchmark>` shows; no GPU, no
service and no fee. A smaller language model chooses worse, and what it cannot
find it says is not known: the language model of 1 billion parameters answers
fewer of the questions, and none of them wrongly.

.. raw:: html

   <div id="cast-llm"></div>

For an agent: the MCP server
----------------------------

The same queries are the tools of an MCP server, ``senfd-mcp``, for a coding
agent to answer a question about the specification with a tool call costing a
few lines rather than by reading the documents:

.. code-block:: console

   $ pip install senfd[mcp]
   $ claude mcp add senfd -- senfd-mcp

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     for (const [id, cast] of [["cast-session", "session"], ["cast-lookups", "lookups"], ["cast-llm", "llm"]]) {
       AsciinemaPlayer.create(`../_static/casts/${cast}.cast`, document.getElementById(id),
         {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
          poster: "npt:0:12"});
     }
   </script>
