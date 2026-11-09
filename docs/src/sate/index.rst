.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-ask:

Ask the expert
==============

``sate`` answers questions about the specifications from senfd's data
model, at once. Alone on the command line it opens a session. Given a
question, it answers that and leaves. ``--raw`` prints the answer as
Markdown, unrendered, with the links as addresses. The same lookups answer
``senfd-query`` on the command line.

.. raw:: html

   <div id="cast-session"></div>

Straight to the specification
-----------------------------

An answer says where to read, and the specification has the last word.
Every answer cites the document, section, figure and page it is from, as
``[NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]``. Where NVM Express
publishes the document as PDF, the citation is a link to that page of it on
nvmexpress.org: a terminal that shows links opens it in the browser, at the
figure, to read what the specification says of the matter at hand. The
citation gives the page of the file too, ``PDF page 54``, for a PDF saved
rather than shown.

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

No language model is involved. A question is read by its words, as "opcode
of", "cdw12 of", "feature", "log page", "status code" or "section". It is
read by an identifier, as ``1Fh``. And it is read by the names and acronyms
of the data model it mentions, the longest first, so "the controller status
register" is ``CSTS`` and "dword 13 of Zone Append" is that dword of that
command. Each answer starts by saying what the question was understood as,
``command('Zone Append', dword=13)``, so a misreading shows at once.

An answer is shown only when it mentions every term of the question that
names something. Ask for the bit of Write that "enables the hyperdrive",
and the answer is that it is not known, not the fields of Write found for
the question's other words. An answer is also shown only when it is about
what the question names. Asked for the opcode of Read, the answer must be
Read, not Memory Read or Copy. Asked for the opcode of "Track", a word of
several commands' names, the answer is that it is not known.

The session
-----------

The session is made for someone who does not yet know how to ask. It opens
with a menu of the questions it answers, ``what is the opcode of
<command>?``, ``which bit of cdw<N> of <command> is <acronym>?`` and the
others. ``?`` on an empty line opens the menu again.

Tab completes each part of a question from what the data model holds, each
completion shown with its kind. After "opcode of" it offers the commands,
after "log page" the log pages, and after "which bit of cdw12 of Write is"
the acronyms of that dword's fields, in the order of its figure. A name
completes from where it starts, so "zone app" completes to Zone Append. A
word typed in capitals completes to acronyms.

The words it recognises are coloured as you type. The line at the bottom
says how the question is read so far, ``Read as command('Write',
dword=12)``, or what comes next. Under it are the keys that work at that
moment. Up and Down recall the questions asked before, kept between
sessions. F1 or ``help`` lists the forms above, and Ctrl-D leaves.

The answers
-----------

Each answer opens with a rule naming the question, so its start stands out
when scrolling back. An answer about a field marks the field's row and ends
by saying where it is, as "**FUA**, Force Unit Access, is bit 30 of cdw12
of Write [NVM 1.3, 3.3.6, Figure 71, page 54, PDF page 54]". A line under
each answer says what the question was read as, how many lookups it took,
how long, and how many figures it cites. An answer taller than the
terminal opens in a pager, and stays on the screen when the pager is quit.

A data structure's table is headed by bytes. Where a byte holds bits, as
the Reservation Capabilities of a namespace, the bits stand in a column of
their own, named by both acronyms, as ``RESCAP.PTPLS``. ``describe`` or
``explain`` before a question adds the first line of each field's
description.

.. _sec-usage-query:

On the command line: senfd-query
--------------------------------

``senfd-query`` gives the same answers to a lookup named on the command
line, for scripts and for the shell:

.. code-block:: console

   $ senfd-query command write 12
   $ senfd-query feature 07h
   $ senfd-query log-page 02h
   $ senfd-query structure "Controller Status"
   $ senfd-query search FUA
   $ senfd-query value "status code 82h"
   $ senfd-query section 5.2.6
   $ senfd-query errata Base
   $ senfd-query lint

``command`` takes a command's name and, after it, the number of one of its
dwords. ``feature`` and ``log-page`` take a name or an identifier, and
``structure`` a name or an acronym. ``search`` finds a word or an acronym
everywhere it is. ``value`` finds an entry of a table of values, as ``"CNS
05h"`` or ``"status code of zone boundary error"``. ``section`` takes a
section's number. ``errata`` and ``lint`` take a document to confine the
findings to; see :ref:`the linter <sec-linting>`.

``--verbose`` adds the descriptions. ``--markdown`` gives the fields as a
Markdown table and makes each citation a link to the page of the published
PDF. ``--spec``, or the environment variable ``SENFD_SPEC``, names another
data model than ``~/.cache/senfd/merged.spec.document.json``.

.. raw:: html

   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.css">
   <script src="https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player.min.js"></script>
   <script>
     AsciinemaPlayer.create("../_static/casts/session.cast", document.getElementById("cast-session"),
       {cols: 110, rows: 32, idleTimeLimit: 2, fit: "width", terminalFontSize: "small",
        poster: "npt:0:12"});
   </script>
