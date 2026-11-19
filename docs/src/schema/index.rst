.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-schema:

Schema
======

senfd writes three documents. Each is JSON, validated against a JSON
schema. The ``FigureDocument`` holds the figures of a document as their
tables are. The ``NormalizedFigureDocument`` holds each figure by the
shape of its table and the subject of its caption. The ``SpecDocument`` is
the data model of the specification. The schemas are in the repository,
under ``src/senfd/schemas``, and are shown in full below.

.. _sec-schema-data-model:

The data model
--------------

The ``SpecDocument`` is the data model. ``merged.spec.document.json`` merges
the data models of all the documents given. senfd makes a key of the data
model from a name or a column header: its words in lower case, joined by
underscores, with "I/O" as one word. The key of Create I/O Completion Queue
is ``create_io_completion_queue``. The ``SpecDocument`` has these parts:

* ``meta``: the format of the data model; the version of senfd that made
  the data model and the SHA-256 of that senfd's source; the name of the
  document, or ``merged`` for the merged data model; and the file the data
  model was made from, with that file's SHA-256, which identifies a
  published document. The merged data model has two more SHA-256 hashes:
  one of the documents it is made from, and one of those documents
  together with senfd's source. :ref:`sec-schema-identity` describes them.
* ``documents``: the documents the data model is made from, by name, each
  with its file and SHA-256, so the merged data model lists every document
  in it. Each also has the ``name`` of its specification, such as "NVM
  Command Set", the ``key`` of the specification without the revision, such
  as ``nvm``, and the ``revision``, such as ``1.3``.
* ``command_sets``: each command set by its ``key``, with its ``kind``, its
  ``title`` as the specifications write it, such as "NVM Command Set" or
  "I/O Commands", the key of the ``document`` whose opcode table lists it,
  and its commands. A command has the fields it ``uses``, as its section
  states them, such as ``DPTR`` and ``CDW10`` of "The Set Features command
  uses the Data Pointer and Command Dword 10", and the fields it
  ``delegated``, each with the ``fields`` whose use the ``selectors``
  select, such as ``CDW11`` to ``CDW15``, which are "Feature specific", by
  ``FID``. Where the section states no such sentence, ``uses_stated`` is
  false, and ``uses`` are the fields that the figures of the command lay
  out, other than reserved fields and fields that are not used: ``CDW3``,
  ``MPTR``, ``DPTR`` and ``CDW10`` to ``CDW15`` of Read. The commands of the
  Management Interface and the Fabrics command have no such ``uses``. A command has the opcode table's other columns of it,
  and ``typed`` holds those of a known kind as on an entry of a table of
  values: the bits of the opcode, as "0000 01b" of ``07_02``, and whether
  the command uses the namespace identifier. A command has its ``opcode``, its submission queue entry dwords
  ``sqe``, its completion queue entry dwords ``cqe``, its ``operations``,
  its ``status_values``, the tables of the status values specific to it, and
  its ``status_codes``, each status value whose "Commands Affected" names
  it, by the ``source`` of its table, the ``field`` and the ``value``. A
  name matches a command of the table's own document first, and otherwise
  the one command of that name in another document, as Read of the Zoned
  Namespace table, a command of the NVM Command Set.
* ``features`` and ``log_pages``: features and log pages by identifier. A
  feature has the dwords of the commands that set and get it, and its
  ``operations``. A log page has the ``structure`` that lays it out, and
  ``aliases``, the other names that tables give it.
* ``structures``: every layout that is not the dwords of a command: data
  structures, the layouts of log pages, and registers. The ``title`` of a
  structure is the name its caption gives, such as "CC - Controller
  Configuration". The title is split into the ``name``, "Controller
  Configuration", and the ``acronym``, "CC". Where the part before " - " is
  no acronym, it is the ``owner``, such as "Identify" of "Identify -
  Identify Controller". Text in parentheses is the acronym, as "CH" of "PDU
  Common Header (CH)", the flag ``optional``, or else the ``qualifier``, as
  "Set Features" of "Timestamp (Set Features)". The ``key`` of a structure
  is unique among the structures of its document. It is the key of the
  name without "Data Structure", the name of the document's command set,
  and words such as "I/O Command Set Specific". Where two keys would be the
  same, each takes those words back, then its owner, its qualifier, its
  kind and its figure number, as far as needed to tell them apart. A
  register has its ``offset`` in bytes, counted from ``offset_base`` for a
  register of a PCI capability, or an ``offset_formula`` for the doorbell
  registers. ``size`` is the size of the structure in bytes, where no range
  of its fields is a formula.
* ``values``: the tables of values, such as status codes or identifiers, by
  the ``kind`` of their caption, with the ``scope`` that the caption limits
  them to. Each entry has a ``name``, and can have an ``acronym``. Where the
  value of an entry is a code, a range or a list of codes, a number, or
  "All others", ``typed`` holds it as such under the key of its column. The
  ``role`` of an entry is ``field``, or the place the entry holds, such as
  ``reserved``. A table of status values has the ``status_code_type`` its
  caption names, as 1 of "Command Specific Status Values", and a
  ``status_scope`` of ``io_command_set`` or ``fabrics`` where the caption
  confines the codes to the I/O command sets or to Fabrics commands.
* ``dwords``: the dwords of every figure, by the name its caption gives, as
  read. ``unassigned`` holds the dwords that no command, feature or
  operation claims.
* ``diagnostics`` and ``errata``: what senfd normalised or could not read,
  and the candidate errata, each with its location.

.. _sec-schema-identity:

Format and instance
-------------------

The format of the data model is its shape, as the schemas define it. senfd
owns the format, and increments ``meta.format`` whenever the shape
changes. A test fails when the schemas change and the format does not.

A data model made from particular documents is an instance of the format.
The merged data model identifies its instance by three SHA-256 hashes.
``input_sha256`` is the hash of the documents the data model is made from,
in whatever order they were given. ``senfd_sha256`` is the hash of the
source of the senfd that read them. It leaves out sate, because sate only
answers from the data model. ``combined_sha256`` is the hash of the two
together. The same documents read by the same senfd give the same data
model, so two data models with the same combined hash are the same. When
two answers differ, the input hash shows whether the documents differ, and
the senfd hash shows whether the reading differs.

.. _sec-schema-parts:

Commands, structures and values
-------------------------------

The ``kind`` of a command set is ``io``, ``common_io``, ``admin``,
``fabrics`` or ``management_interface``. An I/O Command Set specification defines an I/O
command set, which has the Command Set Identifier that Base 2.4 Figure 337
gives it in ``identifier``, for example 00h for NVM. Base 2.4 defines some
I/O commands, such as Flush, for use in all I/O command sets. These commands
belong to no command set and have no Command Set Identifier. senfd lists
them as the command set "Common I/O", of the kind ``common_io``. The kind
``management_interface`` is for the command sets of the Management Interface
specification.

The Fabrics commands of Base 2.4 share the opcode 7Fh and differ in their
Fabrics Command Type, as Figure 29 lists them. senfd gives them as the
command set "Fabrics", of the kind ``fabrics``, with one command "Fabrics"
of the opcode 7Fh, whose ``sqe`` is Command Dword 0 of Figure 96. Each
Fabrics command is an operation of that command, selected by ``FCTYPE``.
The figure of its submission queue entry, as Figure 635 of Connect, is its
``sqe``, dwords 0 to 15 with the fields in bits. The figure of its response
is its ``cqe``, and the figure of the data it transfers, as Figure 636, is
in its ``structures``. These figures are structures of their own too.

An operation is what a command or a feature does for one value of a
selecting field, for example each directive operation. Dwords are an
operation of a command when they are in a section below the section of the
command, and the title of their section gives a code of a field of the
command, for example "SMBus/I2C Frequency (Configuration Identifier 01h)"
below Configuration Get. Dwords whose caption names a field of a command are
an operation of that command too, for example "Command Dword 11 - CNS
Specific Identifier" in "NVM Set List (CNS 04h)". The code is in
``selectors``. The Lockdown Persistence Personality is an operation of the
feature Configurable Device Personality, selected by PERID 02h.

Where every field of the dwords of an operation lies within one field of the
dwords of the command, the operation has ``refines``, the acronym of that
field: LSP of Get Log Page for the FDP Events log page, and CNSSID of
Identify for the CNS values that use it. An operation selected by a Command
Set Identifier has the command set in its name where the name does not
already say it, for example "I/O Command Set specific Identify Namespace
Data Structure (Key Value)". Dwords laid out under a condition of the form
"CETYPE is non-zero" have ``selected_when``: the acronym of the field, the
comparison and the value. The text of the condition stays in ``condition``.

A log page is one entry for each identifier. The first table of log page
identifiers that lists the identifier gives the name, and the names in other
tables go to ``aliases``. The ``structure`` of a log page is the figure in
the section that its row cites, for example Base 2.4 Figure 270 for 12h.

In every part of the data model, a ``Dwords`` is the dwords from ``lower``
to ``upper`` with their ``fields``, possibly under a ``condition``. A field,
``Bits``, is a ``range`` of bits or bytes, as given by ``unit``. A field
has a ``name``, an ``acronym`` and nested ``fields``. A row that has a
range and a nested table but no name is a field named after its range,
for example "Byte 00". Where fields share
bits, a field also names the ``union`` and ``alternative`` it belongs to.
A field lists the ``values`` it takes. Where the description of a field
refers to a table of values in another figure instead of listing the
values, for example "Refer to Figure 336" for CNS of the Identify command,
the field has ``values_in``. ``values_in`` is the ``source`` of that table,
and the table is the entry of ``values`` with the same ``source``.

A footnote marker is a number printed raised after a name, a value or a
cell, and is not part of the text. The readers of the PDF and of the
``.docx`` return a marker as superscript digits, and senfd moves the markers
out of the text. A field lists the numbers marked on its name, its
description and its other columns in ``footnotes``. An entry of a table of
values lists them in ``footnotes`` too, and by the key of the column in
``marked``. A command, a feature and a log page have ``footnotes``, the
numbers marked on the name and the other columns of its row, by the key of
the column. A raised number after another digit is an exponent and stays in
the text, for example the 16 of 2 to the power of 16, except after a lone 0
or 1, where it is a marker.

A figure lists the entries of an array as fields numbered by their index,
with a "..." row in place of the entries between them, for example LBAF0,
LBAF1, "..." and LBAF63 of the Identify Namespace data structure. Each
listed entry has ``array``, which holds the ``name`` and the ``acronym`` of
the entries without the index, the ``index`` of the entry, the index of the
``first`` entry, the ``count`` of entries, the ``stride``, which is the size
of one entry in bits or bytes, and ``lower``, the offset where the first
entry starts. A generator writes the array at the entry whose ``index`` is
``first``, and skips the other entries. Where the figure gives the range of
the last entry as a formula, ``count`` is null, and so is the ``index`` of
that entry.

senfd also makes an array of a run of two or more fields that the figure
lists in full, such as TSEN1 to TSEN8, or TMT1TC and TMT2TC. A run of two is
an array only where the figure leaves out no row that senfd cannot read. A
run numbered in hexadecimal, such as Performance Attribute C1h to FFh
Identifier, is an array too. An entry of another width at its place in a
run, such as Host Fabric Interface Descriptor 2 of Boot 1.4, is an entry of
the array and a candidate erratum.

Some figures give the ranges of the entries by the data, for example the ANA
Group Descriptors at "n:16" and "m:n+1", or by a text, for example the Media
Unit Status Descriptors at "NOTE 1". Such a run is an array without a count.
Its ``stride`` and ``lower`` are null where the widths or the offsets of the
entries depend on the data. One entry followed by a last entry numbered by a
name, such as Entry 0 and Entry N of the Discovery log page, is such an
array too. Where the entries of two runs alternate, such as Zone Descriptor
and Zone Descriptor Extension of ZNS 1.5 Figure 37, each pair is one entry
of an array without a stride, named "Zone Descriptor and Zone Descriptor
Extension 0", whose ``fields`` are the two at offsets from the start of the
entry. A range "n/a" is not a range that the data gives.

Where the formula of the last entry of a run gives a width, the array has
that stride, and the entries of another width are candidate errata. For
example, the formula of Exported NVM Subsystem Descriptor N of Base 2.4
Figure 384 gives 260 bytes, and Descriptors 1 and 2 are 520 and 22 bytes. An
array without a count takes its ``maximum`` from the field that counts its
entries, for example "up to 127 entries" of NUMENT. Where the last entry
names a field of the structure in place of its index, as "Zone Identifier
NZID-1", the array has ``counted_by``, the acronym of that field. The rows of a group
that a column names by an index, such as "Source Range 0" to "Source Range
127" of NVM 1.3 Figure 40, are one field, an entry of the array of those
groups, whose ``fields`` are the rows at offsets from the start of the
entry.

A field has ``structure`` where another figure lays out the field. Where
that figure lays out bits and the field is no entry of an array, the field
also has the fields of that figure as its own ``fields``, counted from bit
0 of the field: DW3 of the Completion Queue Entry of Base 2.4 Figure 97
holds STATUS, P and CID, and STATUS holds DNR to SC, which Figure 101
gives at bits 31:17. A data structure that a figure gives in bits, whose
fields all start and end at byte boundaries, is given in bytes, as the LBA
Format Extension of ZNS 1.5, unless a field other than an entry of an
array lays it out.
``structure`` is the ``source`` of that figure, and the structure is the
entry of ``structures`` with the same ``source``. senfd links a field that
has no subfields to a structure when the description of the field refers
to the figure of the structure, for example "defined in Figure 125", and
the structure is as wide as the field. senfd links an entry of an array
that refers to no figure to the structure whose name appears in its
description, for example "an I/O Command Set Vector". A field that refers
to no figure is linked to the one structure as wide as it in a section its
description cites, or, of several, to the one whose fields the others
divide further, as SGL1 to the Generic SGL Descriptor Format. A field
named with a number, as "PRP Entry 1", is linked to the structure captioned
with that name, as "PRP Entry - Page Base Address and Offset". The ``kind``
of a structure that lays out the entries of an array is
``data_structure``, whatever its caption says.

A field whose description cites a section is also linked to the structure in
that section whose fields cover exactly the bits of the field, for example
STATUS of Base 2.4 Figure 99 to the Status Field of Figure 101. senfd does
not link a field to a structure whose only field has the acronym and the
range of the field.

Two structures of a document have two names. Where a log page and a data
structure have the same name, as Base 2.4 Figures 216 and 217 do, the name
of the data structure ends in "Data Structure". An entry of a list, such as
"AVE Discovery Log Page Entry", is a data structure whose name ends in
"Entry". A figure whose caption repeats the caption of another figure takes
the name of the field it lays out, and the caption is a candidate erratum.
Two structures with the same name and different qualifiers have their
qualifiers in their names, for example "Timestamp (Set Features)". Base 2.4
Figure 97, the layout of a completion queue entry that all command sets
share, is named "Completion Queue Entry", with the qualifier "Admin and All
I/O Command Sets".

A table whose rows name the structure of each field, such as NVM 1.3 Figure
188, has the kind ``cited_fields``. A table that maps the bytes of one
message to another, such as MI 2.2 Figure 49, has the kind ``mapping``.
Neither kind lays out a structure of its own. A structure that lays out some
bytes of another structure has ``extends``, the ``source`` of the other
structure. For example, NVM 1.3 Figure 126 lays out AWUN, AWUPF and ACWU of
Identify Controller. Where the text names the field that the figure lays
out, ``extends_field`` is the acronym of that field.

A field has ``encoding``, which is "ascii", "utf-8" or "uuid", and
``byte_order``, where a document states them. The description of the field
can state them, for example "as an ASCII string" or "This field is big
endian". A paragraph that refers to the figure can state an encoding for a
term at the start of the name of the field, for example "The firmware
revision is indicated as an ASCII string" for the Firmware Slot Information
log page.

senfd also takes an encoding or a byte order from another field. A field
that has the value of another field, or holds bytes of it, takes the
encoding of that field, as NQNID of Base 2.4 Figure 698 takes the encoding
of SUBNQN. An NQN field takes the encoding of the NQN fields that state one.
A field takes the byte order or the encoding of the fields of the same name,
acronym and width in other documents, as NGUID of KV 1.4 takes the byte
order of NGUID in NVM 1.3. ``encoding_from`` and ``byte_order_from`` give
the ``source`` of the figure that a taken encoding or byte order comes from.
A field of one byte has no byte order.

The two fields of a value split over two fields, such as NUMDL and NUMDU,
"Number of Dwords Lower" and "Upper", have ``part``: the name and the
acronym of the value, and the bit of the value where each field starts.

An entry of a table of CNS values has ``selects``, the ``source`` of each
structure the value selects. For CNS 01h of the Base specification, these
are the Identify Controller data structure and the structures nested in it,
in the section that the entry's reference cites. An entry whose reference
cites another document selects what the same value selects there. An entry
that the Command Set Identifier selects, with "Y" in its CSI column, and
that selects nothing in its own document, selects what the same value
selects in the document of each command set: CNS 05h selects the I/O
Command Set specific Identify Namespace data structure of the NVM, Key
Value, Zoned Namespace, Subsystem Local Memory and Computational Programs
command sets. The command sets are those whose documents the entries of
the Command Set Identifiers name, and such an entry has ``document``, the
name of the document whose subject it names.

A value of a field also has ``selects`` where its name is the title of a
section one level below a section that the field's description cites. The
value selects the structures of that section, other than examples. PIF of
NVM 1.3 cites section 5.3.1, and its value 00b, "16b Guard Protection
Information", selects Figures 155 and 156 of section 5.3.1.1. Where a
caption lays a structure out under a condition, the structure has the
``condition``, and ``selected_when`` where the condition compares a field
with a value: Figure 155 holds where the STS field is cleared to 0h. A
condition can name the field by its name, as Base 2.4 Figure 201 names
Select; ``selected_when`` then has the acronym of the field of that name in
the section of the structure or the nearest section above it, SEL of Get
Features.

An entry of a table of values has the ``name`` that its row gives. Otherwise
senfd takes the name from a short definition, from a column that names the
value, such as the Management Operation column of SEL, from a first sentence
of at most three words, such as "Low" of AL in NVM 1.3, or from the title of
the section that the entry refers to. In a list where another value or a
range of reserved values has a name, a definition of one sentence of at most
six words is a name, for example "No action" of MO 00h. A name followed by
its initials is a name too, for example "Add or Replace Active ZoneGroup
(AAZ) operation" of ORI 2. The values of a case are named the same way.

senfd moves an aside in a name to the ``description``, for example "(refer
to RFC 6234)", or "(no shutdown has been requested)" of SHST 00b. senfd
moves the text after a colon there too. A qualifier, such as "(Controller
scope)", stays in the name. The ``acronym`` of an entry comes from an
acronym before a colon, such as CAP of "CAP: Controller Capabilities", from
the initials after the name, such as GAZ of "Get Active ZoneGroup (GAZ)
operation", or from the Acronym column, such as PUID of PIT 001b in CP 1.2.
A table of the minimum and maximum values of a field, such as STS of NVM
1.3, gives none of the values of the field.

The meaning of a field can depend on the value of another field of its
figure. Bits 15:08 of Command Dword 13 of Zone Management Receive, ZRAS, are
the Reporting Options when ZRA is Report Zones or Extended Report Zones,
and are reserved for all other values of ZRA. The figure gives this in a
table in the cell of ZRAS, whose first column is headed "Zone Receive
Action". Such a field has ``cases``. The ``selector`` of a case is the
acronym of the controlling field, and ``when`` lists the values of the
controlling field that the case applies to, each with its ``name`` as the
figure writes it and its ``value`` as a number. ``otherwise`` is true for
the case of all other values. A case also has the ``name``, ``acronym``,
``role`` and ``description`` of the field in that case, and the ``values``
and ``fields`` of the field in that case, with their ranges relative to the
field, as bytes 15:08 of DPTR for PRP2, which Base 2.4 Figure 93 gives as
bytes 39:32. The ``values`` of the field
itself apply whatever the value of the controlling field. Where the
controlling field is a field of another figure, the case has
``selector_in``, the ``source`` of that figure: DPTR of the Common Command
Format has cases by "CDW0.PSDT", and CDW0 of that figure is laid out by
Command Dword 0, which has PSDT. The DPTR of each command has the cases of
the DPTR of the Common Command Format, in the unit of its own figure, so
that DPTR of Read at bits 127:00 has PRP1 at bits 63:00, PRP2 at bits
127:64 and SGL1 at bits 127:00. A DPTR that its figure says is not used,
as of Memory Fill, has no cases.

A figure can draw a structure as a diagram instead of a table of ranges,
with the bits 7 to 0 as columns, one row for each byte, and each field
spanning the rows from the one marked "MSB" to the one marked "LSB". The
NVM Command Set specification draws the 16b, 32b and 64b Guard protection
information formats this way. senfd reads such a diagram as a structure of
bytes. The ``columns`` of each field hold ``msb_byte``, the byte with the
most significant bits of the field, and ``lsb_byte``, the byte with the
least significant bits. The Guard of the 16b format is bytes 1:0 with
``msb_byte`` 0, so the field is stored with its most significant byte
first.

A value in a table of a known kind
is ``typed`` as what it is: a requirement level, a flag, an identifier, a
range, a note, a reference, reserved or vendor specific. Every part has a
``source``: the document, the section and its title, the figure and the
page. Where the document was read from a PDF, the source also has the
page of the file, ``pdf_page``, at which a link to the PDF opens.

A field also states what it is. Its ``role`` is ``field``, or a role that
holds a place. The ``kind`` of its range is ``span``, with integer bounds
and a ``width``; ``formula``, written plainly as ``upper:lower``; or
``open``. The kinds of a caption, of a typed value and of an erratum are
also enumerated in the schema.

The format of a data model can be verified against the schema alone, with
a JSON Schema validator and no part of senfd. An example with the Python
package ``jsonschema``:

.. code-block:: python

   import json
   import jsonschema

   with open("schema/spec.document.schema.json") as schema:
       with open("merged.spec.document.json") as document:
           jsonschema.validate(json.load(document), json.load(schema))

``senfd --dump-schema --output schema`` writes the schema. The schema
states what each kind must hold. The schema cannot state rules that depend
on the values, such as that an upper bound is not below its lower bound.
senfd checks those rules when it reads the data model into its types, and
refuses a data model that breaks them.

The schema is versioned with senfd, and the changelog states the changes
of each release. The schema is a starting point for a data model of the
specifications, not a standard. These parts are likely to stay: the
commands with their dwords and fields, the features, the log pages, the
structures and their sources. These parts are likely to change: how
values are typed and how diagnostics are coded.

.. _sec-schema-figure-document:

FigureDocument
--------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/plain.figure.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/plain.figure.document.schema.json
   :language: json

.. _sec-schema-normalized-figure-document:

NormalizedFigureDocument
------------------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/normalized.figure.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/normalized.figure.document.schema.json
   :language: json

.. _sec-schema-spec-document:

SpecDocument
------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/spec.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/spec.document.schema.json
   :language: json
