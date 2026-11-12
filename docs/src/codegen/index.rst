.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-codegen:

Code from the figures
=====================

NVMe drivers, tools, emulators and test suites carry a header of the
specification that someone transcribed by hand. The names in such a header
are the ones its transcriber chose, and the header lags each revision by as
long as the transcription takes. With the data model, a project can
generate the header from the figures instead. The generated header uses the
specification's own names, and each member cites the figure it is from.

senfd makes the data model and leaves the code generation to the project
that consumes the data model, because that project knows its own
conventions. For **xNVMe**, an early prototype of a generator is
``toolbox/xnvme_spec_headers.py``. `yace <https://github.com/safl/yace>`_
runs the generator, parses what the generator writes as it parses any C
header, and holds the result to a C subset that every binding target can
take. From the 2026 documents, the generator writes one header per
document, eleven in all. The headers hold:

* a struct of each command's dwords, with a mask of each field;
* an enum of the opcodes of each command set, and a constructor of each
  command;
* a packed struct of each data structure and log page, with its reserved
  gaps, arrays of numbered entries and unions of alternative layouts;
* the registers of each document as a packed struct, each register at its
  offset as a driver maps it, with the masks of the fields and an enum of
  the values of each field whose values the specification names;
* enums of the feature and log page identifiers, and of the status codes
  of each scope.

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

yace parses the 1871 entities of the eleven headers with no diagnostics,
and the generated sources compile without warnings. When NVM Express
revises a document, the project regenerates the header and reviews the
diff, in which each change cites its figure. The prototype comes with a
page of xNVMe's contributor documentation, "Producing the spec headers",
which gives the procedure.

The data model is JSON that a :ref:`schema <sec-schema>` validates. A
generator for another language or for another project's conventions reads
the same facts from the same file. So does another kind of tool, such as
the command decoder of an emulator or the expectations of a test suite.
