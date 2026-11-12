.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-llm:

With a language model
=====================

:ref:`The expert <sec-ask>` needs no language model. Two programs combine
a language model with the data model, each for a different user. In
neither program does the language model state an NVMe fact. Every field,
bit and opcode in an answer comes from the data model, with the figure it
is in. The :ref:`benchmark <sec-benchmark>` compares the two programs with
frontier language models, and gives what each costs and how many of its
answers are wrong.

Questions in your own words: sate --llm
---------------------------------------

``sate --llm`` is the expert with a language model, which you run
yourself, reading the question. Without ``--llm``, ``sate`` reads a
question by its words: the names, acronyms and dwords of the
specifications. A question to ``sate`` alone must therefore name what it
asks about. With ``--llm``, a small language model reads the question
instead, and chooses which lookup to run and on what.

Use ``sate --llm`` when your questions do not use the specifications'
names, as in "hey, what opcode does migration send use?", "which FID is the
rate limiting feature" or "the shutdown type bit in CSTS, where is it?".
Use ``sate --llm`` also when a question must not leave the machine. The
language model runs on your own CPU, with no GPU, no account and no fee.
When a question names what it asks about, ``sate`` alone answers the
question as well, in milliseconds.

.. code-block:: console

   $ llama-server -m Qwen2.5-7B-Instruct-Q4_K_M.gguf --port 8088 --jinja
   $ sate --llm http://127.0.0.1:8088

When the server holds several language models, ``--llm-model NAME`` tells
the server which one to use.

The language model chooses the lookup and nothing else. ``sate`` sends the
server a JSON schema, which the server turns into a grammar, and the
grammar constrains the language model's output to the name of a query and
its argument. The answer shown is what the query found, so the answer
cannot state a field, bit or opcode that is not in the figures. When a
lookup finds nothing, or finds nothing that mentions the question's terms,
``sate`` tells the language model so, and the language model chooses
again, at most three times. After the third try, the answer is that the
fact is not known. In the benchmark of 2026-11-12, with 86 questions, Qwen
2.5 7B on a CPU chose lookups that answered 71 questions right, and Qwen
2.5 1.5B chose lookups that answered 54 right. With either language model,
``sate --llm`` answered no question wrongly.

.. raw:: html

   <div id="cast-llm"></div>

For a coding agent: sate-mcp
----------------------------

``sate-mcp`` is an MCP server. Its tools are the expert's lookups,
``command``, ``feature``, ``log_page``, ``structure``, ``value``,
``status``, ``search`` and ``section``, and the documents' ``lint`` and
``errata``. A coding agent, such as Claude Code, calls these tools instead
of answering from memory or reading the documents.

Use ``sate-mcp`` when an agent works on code that implements NVMe: writing
a command, decoding a log page, or checking an opcode, a bit or an offset
in a patch against its figure. An answer from ``sate-mcp`` is a few lines,
so the answer takes up little of the agent's context. Each answer cites its
figure with a link to the page of the published PDF, so the agent, or you,
can open the figure that the answer came from.

.. code-block:: console

   $ claude mcp add sate -- sate-mcp

``sate-mcp`` runs on the same machine as the agent and talks to the agent
over stdio. When the agent runs on a different machine from the data
model, :ref:`sate-web <sec-sate-web>` serves the same tools over HTTP at
``/mcp``, provided the environment variable ``SATE_MCP_TOKEN`` holds a
token. A client must send that token in every request:

.. code-block:: console

   $ SATE_MCP_TOKEN=... sate-web --host 0.0.0.0
   $ claude mcp add --transport http sate http://host:8000/mcp \
       --header "Authorization: Bearer ..."

.. toctree::
   :hidden:

   ../benchmark/index.rst

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/llm.cast", document.getElementById("cast-llm"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
