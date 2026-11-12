.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

senfd and sate
==============

**senfd** reads the NVMe specifications, the PDFs NVM Express publishes or
the ``.docx`` its members hold, and makes a data model of them: every command
with its dwords and fields, every data structure, register, feature, log page
and table of values, each fact citing the document, section, figure and page
it is from.

.. image:: ../_static/senfd.svg
   :alt: The .pdf and .docx documents go through senfd's stages, read,
         normalise, define and merge, into one data model

The data model is JSON validated by a :ref:`schema <sec-schema>`, and the
same documents give the same data model every time.

**sate** answers questions from a data model. Here the data model is the
one that senfd makes of the NVMe specifications. You can ask sate about a
command, a field, a register, a feature or a log page, in an interactive
session with completion or on the command line. sate answers in
milliseconds, and cites the figure with a link to the figure's page of the
specification on nvmexpress.org, so that you can check the answer:

.. raw:: html

   <div class="casts">
     <div class="cast-tabs" role="tablist">
       <button role="tab" aria-selected="true" data-cast="session">Interactive (TUI)</button>
       <button role="tab" aria-selected="false" data-cast="intro">Scripted (CLI)</button>
       <button role="tab" aria-selected="false" data-cast="web">Interactive (Web UI)</button>
     </div>
     <div class="cast-pane" id="cast-session"></div>
     <div class="cast-pane" id="cast-intro" hidden></div>
     <div class="cast-pane" id="cast-web" data-still hidden>
       <img class="only-light" src="_static/web-light.png" alt="sate's web page answering cdw12 of write, with the fields of the dword and the figures they are from">
       <img class="only-dark" src="_static/web-dark.png" alt="sate's web page answering cdw12 of write, with the fields of the dword and the figures they are from">
     </div>
   </div>

To try the web page on your own machine, without installing senfd, run the
wizard with uvx:

.. code-block:: console

   $ uvx --from senfd@latest sate-preview-wizard

Or with pipx:

.. code-block:: console

   $ pipx run --no-cache --spec senfd sate-preview-wizard

The wizard lists the specifications that it will download from
nvmexpress.org, and asks before it makes the data model. The section
:ref:`on the web <sec-sate-web>` describes the wizard.

.. caution::

   senfd is experimental and is not endorsed by NVM Express. senfd's data
   model is derived from the NVMe specifications, and you must be a member
   of NVM Express, Inc. to make the data model or use it. Read the
   :ref:`notices <sec-notices>` at the end of this page first.

The pages under Use take the steps in order: :ref:`install <sec-install>`,
:ref:`make the data model <sec-usage>`, :ref:`lint the documents
<sec-linting>`, :ref:`ask the expert <sec-ask>`, and, optionally, use sate
:ref:`with a language model <sec-llm>`.

What the data model is for
--------------------------

``sate`` answers a question about a command, a field, a register, a
feature or a log page in milliseconds, from the data model. The page
:ref:`ask the expert <sec-ask>` describes the questions that sate answers.

``sate --llm`` answers questions put in your own words. A small language
model on your own CPU chooses the lookup, and the answer is the result of
the lookup; the language model writes no part of the answer. ``sate-mcp``
gives a coding agent the lookups as tools, so that the agent checks an
opcode, a bit or an offset against its figure instead of recalling it. The
page :ref:`with a language model <sec-llm>` describes both.

An early prototype generates xNVMe's specification headers from the data
model, and every generated member cites its figure. The page :ref:`code
from the figures <sec-codegen>` describes the prototype.

senfd lists each part of a figure that does not read as data, with the
figure and the page, for the authors to fix. The page :ref:`the linter
<sec-linting>` describes the list.

.. _sec-notices:

Notices
-------

**Not endorsed by NVM Express.** senfd is independent of NVM Express, Inc.
NVM Express and NVMe are its trademarks.

**Experimental.** What senfd says can be wrong. Every answer cites the
figure it is from; check it there before you rely on it.

**The data model is under the specifications' terms.** The data model is
derived from the NVMe specifications, so the notice printed in each
specification governs the data model. Members of NVM Express, Inc. may use
the data model under their Participation Agreement and the Company's
Intellectual Property Policy and Bylaws. To anyone else, the notice grants
only the right to review, refer to or cite the specification. **You must be
a member of NVM Express, Inc. to make the data model or use it.**

**Nothing made from the specifications is distributed.** senfd ships no
specification and no data model, and its CI job, which reads the public
PDFs, uploads nothing made from them. You can make your own data model from
the public PDFs, as :ref:`making the data model <sec-usage>` shows.

.. toctree::
   :caption: Use
   :hidden:

   install/index.rst
   usage/index.rst
   linting/index.rst
   sate/index.rst
   llm/index.rst

.. toctree::
   :caption: How it works
   :hidden:

   stages/index.rst
   schema/index.rst
   codegen/index.rst
   prior-art/index.rst

.. toctree::
   :caption: Project
   :hidden:

   contributors/index.rst
   names/index.rst

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <style>
     .cast-tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid var(--color-background-border); margin-bottom: 0.5rem; }
     .cast-tabs button { background: none; border: none; border-bottom: 2px solid transparent; padding: 0.4rem 0.9rem; color: var(--color-foreground-secondary); cursor: pointer; font: inherit; }
     .cast-tabs button[aria-selected="true"] { border-bottom-color: var(--color-brand-primary); color: var(--color-foreground-primary); font-weight: 600; }
   </style>
   <script>
     // A player made in a hidden pane has no width to fit, so each is made
     // when its pane is first shown
     const made = {};
     function show(cast) {
       for (const button of document.querySelectorAll(".cast-tabs button")) {
         const on = button.dataset.cast === cast;
         button.setAttribute("aria-selected", on);
         document.getElementById(`cast-${button.dataset.cast}`).hidden = !on;
       }
       // A pane marked data-still holds a picture rather than a recording
       if (!made[cast] && !("still" in document.getElementById(`cast-${cast}`).dataset)) {
         made[cast] = AsciinemaPlayer.create(`_static/casts/${cast}.cast`, document.getElementById(`cast-${cast}`),
           {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
            poster: "npt:0:12"});
       }
     }
     for (const button of document.querySelectorAll(".cast-tabs button")) {
       button.addEventListener("click", () => show(button.dataset.cast));
     }
     show("session");
   </script>
