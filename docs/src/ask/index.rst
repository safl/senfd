.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-ask:

Ask the expert
==============

``senfd-ask`` answers questions about the specifications as an expert would,
at once, and only from the model. Ask it as you would ask a colleague:

.. code-block:: console

   $ pip install senfd[ask]
   $ senfd-ask
   ask> opcode of zone append
   ask> Which bit of CDW12 of the Write command is FUA?
   ask> What are the fields of the controller status register?
   ask> log page 1Fh
   ask> FUA

Names, acronyms and the words of questions complete as you type, with Tab,
from what the model holds: every command, feature, log page, structure and
register, and every field's acronym. ``help`` lists the forms a question can
take. Given a question on the command line, it answers that and leaves:

.. code-block:: console

   $ senfd-ask "What is the opcode of the Sanitize Namespace command?"

.. raw:: html

   <div id="cast-lookups"></div>

How a question is understood
----------------------------

No language model is involved. A question is read by its words, as "opcode
of", "cdw12 of", "feature", "log page" or "section"; by an identifier, as
``1Fh``; and by the names and acronyms of the model it names, the longest
first, so "the controller status register" is ``CSTS`` and "dword 13 of Zone
Append" is that dword of that command. Each answer starts by saying what the
question was understood as, ``command('Zone Append', dword=13)``, so a
question understood otherwise than meant shows at once.

Each answer is the answer of a query of the model, rendered as a table, with
the figure it cites. An answer is shown only when it mentions every term of
the question that names something. Ask for the bit of Write that "enables the
hyperdrive" and the answer is that it is not known, not the fields of Write
that were found for the question's other words.

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
the figures. When a lookup finds nothing, or nothing mentioning the
question's terms, it is told so and chooses again, three times at most, and
then the answer is that it is not known. A model of 8 billion parameters on
a CPU is enough, as the :ref:`benchmark <sec-benchmark>` shows; no GPU, no
service and no fee. A smaller model chooses worse, and what it cannot find it
says is not known: the model of 1 billion parameters answers fewer of the
questions, and none of them wrongly.

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
     for (const [id, cast] of [["cast-lookups", "lookups"], ["cast-llm", "llm"]]) {
       AsciinemaPlayer.create(`../_static/casts/${cast}.cast`, document.getElementById(id),
         {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
          poster: "npt:0:12"});
     }
   </script>
