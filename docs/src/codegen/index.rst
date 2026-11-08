.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-codegen:

Code from the figures
=====================

Every NVMe driver, tool, emulator and test suite carries a header of the
specification, transcribed by hand, with names its transcriber chose, and
lagging each revision by as long as the transcription takes. The data model
makes that header a thing to generate: from the figures, with the
specification's own names, each member citing the figure it is from.

senfd makes the data model and leaves writing code from it to the project that
consumes it, which knows its conventions. For **xNVMe**, an early prototype
does so, ``toolbox/xnvme_spec_headers.py``, parked while senfd and yace were
made ready for it, run by `yace
<https://github.com/safl/yace>`_, which parses what the generator writes as
any C header and holds it to a C subset every binding target can take. From
the 2026 documents it writes one header per document, eleven in all:

* a struct of each command's dwords, with a mask of each field, an enum of the
  opcodes of each command set, and a constructor of each command;
* a packed struct of each data structure and log page, with its reserved
  gaps, arrays of numbered entries, and unions of alternative layouts;
* the registers of each document as a packed struct at their offsets, as a
  driver maps them, with the masks of their fields and an enum of the values
  of each field whose values the specification names;
* enums of the feature and log page identifiers, and of the status codes of
  each scope.

.. code-block:: c

   struct __attribute__((packed)) xnvme_spec_base_registers {
           uint64_t cap; ///< CAP - Controller Capabilities (Base 2.4, 3.1.4.1, Figure 36, page 55), at 0h
           uint32_t vs;  ///< VS - Version (Base 2.4, 3.1.4.2, Figure 37, page 58), at 8h
           ...
           uint32_t cc;  ///< CC - Controller Configuration (Base 2.4, 3.1.4.5, Figure 41, page 60), at 14h
           ...
   };

   /** Enable (Base 2.4, 3.1.4.5, Figure 41, page 60); bit 0 of 'cc' */
   #define XNVME_SPEC_BASE_REGISTERS_CC_EN 0x1

yace parses the 1871 entities of the eleven headers with no diagnostics, and
the generated sources compile warning-free. A revision of a document is then
a regenerated header and a diff to review, with the figure of every change
cited in it. The prototype comes with a page of xNVMe's contributor
documentation, "Producing the spec headers", giving the procedure.

The data model is JSON validated by a :ref:`schema <sec-schema>`, so a
generator for another language, another project's conventions or another tool,
an emulator's command decoder or a test suite's expectations, reads the same
facts from the same file.