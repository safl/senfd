.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-llm:

With a language model
=====================

:ref:`The expert <sec-ask>` needs no language model. Two programs put one
beside the data model, each for a different user. In neither does the
language model state an NVMe fact: every field, bit and opcode in an answer
comes from the data model, with the figure it is in. The :ref:`benchmark
<sec-benchmark>` sets them beside frontier language models answering from
memory, with what each costs and gets wrong.

Questions in your own words: sate --llm
---------------------------------------

``sate --llm`` is the expert with a language model you run yourself reading
the question. ``sate`` alone reads a question by its words, the names,
acronyms and dwords of the specifications, so a question must name what it
asks about. With ``--llm``, a small language model reads the question
instead, and chooses which lookup to run and on what.

Use it when questions do not use the specifications' names: "hey, what
opcode does migration send use?", "which FID is the rate limiting feature",
"the shutdown type bit in CSTS, where is it?". Use it, too, where a question
must not leave the machine: the language model runs on your own CPU, with
no GPU, no account and no fee. Where a question names what it asks about,
``sate`` alone answers it as well, in milliseconds.

.. code-block:: console

   $ llama-server -m Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf --port 8088 --jinja
   $ sate --llm http://127.0.0.1:8088

A server holding several language models needs to be told which:
``--llm-model NAME`` asks it for that one.

The language model chooses the lookup and nothing else. Its output is
constrained, by a JSON schema the server turns into a grammar, to the name
of a query and its argument; the answer shown is what the query found, so
it can state no field, bit or opcode that is not in the figures. When a
lookup finds nothing, or nothing mentioning the question's terms, it is
told so and chooses again, three times at most, and then the answer is that
it is not known. A language model of 8 billion parameters on a CPU is
enough. One of 1 billion parameters chooses worse: it answers fewer of the
questions, and none of them wrongly.

.. raw:: html

   <div id="cast-llm"></div>

For a coding agent: sate-mcp
----------------------------

``sate-mcp`` is an MCP server whose tools are the expert's lookups,
``command``, ``feature``, ``log_page``, ``structure``, ``value``,
``search`` and ``section``, and the documents' ``lint`` and ``errata``. A
coding agent, such as Claude Code, calls them rather than answering from
memory or reading the documents.

Use it when an agent works on code that implements NVMe: writing a
command, decoding a log page, or checking an opcode, a bit or an offset in
a patch against its figure. An answer is a few lines, so it costs the agent
little of its context. Each cites its figure with a link to the page of
the published PDF, so the agent, or you, can open the figure it was told
of.

.. code-block:: console

   $ claude mcp add sate -- sate-mcp

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
