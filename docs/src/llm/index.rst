.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-llm:

With a language model
=====================

:ref:`The expert <sec-ask>` needs no language model, and answers in
milliseconds for free. A language model can still be of use in two ways,
neither of which lets it make an NVMe fact up. ``sate --llm`` has a small
language model on your own CPU read questions phrased in ways no rule
foresees. ``sate-mcp`` gives a coding agent the data model as tools. The
:ref:`benchmark <sec-benchmark>` sets the expert alone, the expert with a
language model choosing the lookup, and frontier language models answering
from memory side by side, with what each costs and gets wrong.

Choosing the lookup: sate --llm
-------------------------------

``--llm URL`` has a language model served at URL, as by llama.cpp's
``llama-server``, understand the questions instead:

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

``sate-mcp`` is an MCP server whose tools are the same lookups. A coding
agent answers a question about the specification with a tool call costing
a few lines, rather than by reading the documents:

.. code-block:: console

   $ claude mcp add sate -- sate-mcp

Its answers are those of ``senfd-query --markdown``, each citation a link to
the page of the published PDF, so the agent can open the figure it was told
of.

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
