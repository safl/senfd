.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-ask:

Ask the expert
==============

``sate`` answers questions about the specifications from senfd's data
model, in milliseconds. You can ask sate in an interactive session, which
helps you phrase the question, or put the question on the command line, by
hand or from a script.

.. raw:: html

   <div id="cast-session"></div>

Citations
---------

Every answer cites the document, section, figure and page that the answer
is from, as ``[NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]``. The
specification is the authority, and the citation says where to read it.
Where NVM Express publishes the document as a PDF, the citation is a link to
the figure's page of the PDF on nvmexpress.org. A terminal that shows links
opens that page in the browser, at the figure. The citation also gives the
page number within the PDF file, ``PDF page 54``, for reading a downloaded
copy.

Interactive
-----------

.. code-block:: console

   $ sate

The interactive session is made for someone who does not yet know how to
phrase a question. The session opens with a menu of the questions that sate
answers. Each entry is an example with names from the data model, as ``what
is the opcode of Write?`` and ``which bit of cdw12 of Write is FUA?``, and
the names are marked as the parts to replace with your own. Choosing an
entry types its words, up to the first name, so that you can continue the
question. ``?`` on an empty line opens the menu again.

Tab completes each part of a question from what the data model holds, and
shows the kind of each completion. After "opcode of", Tab offers the
commands. After "log page", Tab offers the log pages. After "which bit of
cdw12 of Write is", Tab offers the acronyms of that dword's fields, in the
order of the dword's figure. A name completes from its beginning, so "zone
app" completes to Zone Append. A word typed in capitals completes to
acronyms.

The session colours the words it recognises as you type. The line at the
bottom shows how sate reads the question so far, as ``Read as
command('Write', dword=12)``, or what can come next. Under that line are
the keys that work at that moment. Up and Down recall earlier questions,
which sate keeps between sessions. F1 or ``help`` lists :ref:`the forms
<sec-ask-forms>`, and Ctrl-D ends the session.

.. _sec-ask-forms:

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
   * - a status code or a CNS value
     - ``status code 82h``, ``status code type 1h``, ``CNS 05h``, ``status
       code of zone boundary error``
   * - what a status of a completion means
     - ``what does status 0x4281 mean?``, ``what does SCT 1 SC 80h mean for
       Write?``, ``dw3 0x80050007``
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

How a question is read
----------------------

sate reads a question without a language model. sate reads the question's
words, such as "opcode of", "cdw12 of", "feature", "log page", "status
code" or "section". sate reads identifiers, such as ``1Fh``. sate also
reads the names and acronyms of the data model that the question mentions,
the longest first. "The controller status register" is therefore read as
``CSTS``, and "dword 13 of Zone Append" as dword 13 of the Zone Append
command. Each answer starts by saying what sate understood the question as,
such as ``command('Zone Append', dword=13)``, so that a misreading is
visible at once.

sate reads a status by its value, as ``status 0x4281``. The value is the
Status Field as nvme-cli and Linux print it, without the Phase Tag. sate
splits the value into its fields by the bits that the data model holds for
the figure of the Status Field; sate's code holds no such bits. sate then
looks up the Status Code Type and the Status Code in the tables of status
codes of that type. ``status code 82h`` asks for a status code of any type,
and ``SC 81h`` does the same.

sate shows an answer only when the answer mentions every term of the
question that names something. If you ask for the bit of Write that
"enables the hyperdrive", sate answers that the bit is not known. sate does
not show the fields of Write that match the question's other words. sate
also shows an answer only when the answer is about what the question names.
If you ask for the opcode of Read, the answer must be about Read, not
Memory Read or Copy. If you ask for the opcode of "Track", a word in the
names of several commands, sate answers that the opcode is not known.

The answers
-----------

Each answer opens with a horizontal rule that names the question, so that
the start of each answer is easy to find when scrolling back. An answer
about a field marks the field's row, and ends with a sentence that says
where the field is, as "**FUA**, Force Unit Access, is bit 30 of cdw12 of
Write [NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]". A line under each
answer says what sate read the question as, how many lookups sate made, how
long the lookups took, and how many figures the answer cites. An answer
taller than the terminal opens in a pager, and the answer stays on the
screen after you quit the pager.

The table of a data structure lists its fields by byte. Where a byte holds
bits, as the Reservation Capabilities of a namespace do, the bits are in a
column of their own, and each bit is named by both acronyms, as
``RESCAP.PTPLS``. ``describe`` or ``explain`` before a question adds the
full description of each field.

.. _sec-usage-query:

On the command line
-------------------

Given a question as an argument, ``sate`` answers the question and exits.
This suits a question asked once, or a question asked from a script:

.. code-block:: console

   $ sate "What is the opcode of the Sanitize Namespace command?"
   $ sate --raw "which bit of cdw12 of write is FUA"

``--raw`` prints the answer as unrendered Markdown, with the links as
addresses. A script can name the lookup instead of asking a question, and
sate then has no question to read:

.. code-block:: console

   $ sate command write 12
   $ sate feature 07h
   $ sate log-page 02h
   $ sate structure controller status
   $ sate search FUA
   $ sate value status code 82h
   $ sate status 4281h
   $ sate section 5.2.6

``command`` takes a command's name and, after the name, the number of one
of its dwords. ``feature`` and ``log-page`` take a name or an identifier.
``structure`` takes a name or an acronym. ``search`` finds every place where
a word or an acronym appears. ``value`` finds an entry in a table of
values, as ``"CNS 05h"`` or ``"status code of zone boundary error"``.
``status`` says what a status of a completion means. The status can be
given as nvme-cli and Linux print it, ``4281h``, as Dword 3 of the
completion, ``dw3 80050007h``, or by its type and code, ``sct 1h sc 80h of
write``. ``section`` takes a section's number. sate reads an argument in
quotes as a question, whatever its first word is. The problems that senfd
found while reading the documents are listed by ``senfd lint`` and ``senfd
errata``, not by sate; see :ref:`the linter <sec-linting>`.

``--verbose`` adds the descriptions. ``--markdown`` prints the fields as a
Markdown table and makes each citation a link to the page of the published
PDF. ``--spec``, or the environment variable ``SENFD_SPEC``, names a data
model other than ``~/.cache/senfd/merged.spec.document.json``.

A coding agent can use these lookups as tools, and a small language model
can choose the lookup for a question in your own words. The page :ref:`with
a language model <sec-llm>` describes both, and what each costs.

.. _sec-sate-web:

On the web
----------

``sate-web`` answers the same questions on a web page, for a browser
rather than a terminal:

.. code-block:: console

   $ sate-web
   $ sate-web --host 0.0.0.0 --port 8080

``sate-web`` listens on ``127.0.0.1:8000`` by default, and ``--spec`` names
the data model, as for ``sate``. The page completes a question as you type
it, and Enter or a click on a menu entry submits the question. The keys are
listed under the input field. Each answer cites its figures as links to the
PDF pages on nvmexpress.org. The count of documents above the input field
opens a table of the documents in the data model. The question is in the
URL, such as ``/?q=cdw12+of+write``, so an answer can be bookmarked. The
page has five colour themes, each with a light and a dark mode. The mode
follows the operating system's setting unless you choose one.

To try the page without installing senfd, run ``sate-preview-wizard``
with uvx:

.. code-block:: console

   $ uvx --from senfd@latest sate-preview-wizard

Or with pipx:

.. code-block:: console

   $ pipx run --no-cache --spec senfd sate-preview-wizard

``@latest`` and ``--no-cache`` fetch the latest release each time. Without
them, uvx and pipx run the version they ran before, which pipx keeps for 14
days.

When there is no data model, the wizard lists the specifications that it
will download from nvmexpress.org, and asks before it makes the data model,
because only members of NVM Express may make and use the data model.
``--yes`` makes the data model without asking. The wizard checks each PDF
against its SHA-256, makes the data model in ``~/.cache/senfd``, starts
``sate-web`` on the first free port from 8899, and opens the page in the
browser. On the next run, the wizard finds the data model and opens the
page at once. The wizard asks to make the data model again in two cases:
when the format of the data model is not the one that the installed senfd
reads, and when the data model was made from other documents than those
that NVM Express publishes now. The wizard tells the documents apart by
:ref:`their hashes <sec-schema-identity>`. The wizard uses a data model
made by another version of senfd as it is, and says so. ``--remake`` makes
the data model again with the installed senfd.

``sate-web`` also serves the tools of ``sate-mcp`` at ``/mcp``, to a coding
agent that sends a token. The page :ref:`with a language model <sec-llm>`
says how.

The page has no login. Anyone who reaches the page is served the data
model, which only members of NVM Express, Inc. may use. Where the page is
reachable over a network, put it behind a proxy that admits only members.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/session.cast", document.getElementById("cast-session"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
