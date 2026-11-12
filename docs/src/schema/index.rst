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

The ``SpecDocument`` is the data model. ``merged.spec.document.json``
merges the data models of all the documents given. The ``SpecDocument``
has these parts:

* ``meta``: the format of the data model; the version of senfd that made
  the data model and the SHA-256 of that senfd's source; the name of the
  document, or ``merged`` for the merged data model; and the file the data
  model was made from, with that file's SHA-256, which identifies a
  published document. The merged data model has two more SHA-256 hashes:
  one of the documents it is made from, and one of those documents
  together with senfd's source. :ref:`sec-schema-identity` describes them.
* ``documents``: the documents the data model is made from, by name, each
  with its file and SHA-256, so the merged data model lists every document
  in it.
* ``command_sets``: each command set by its name, with its commands. A
  command has its ``opcode``, its submission queue entry dwords ``sqe``,
  its completion queue entry dwords ``cqe``, and its ``operations``. An
  operation is what the command does for one value of a selecting field,
  as for each directive operation.
* ``features`` and ``log_pages``: features and log pages by identifier. A
  feature has the dwords of the commands that set and get it. A log page
  has the ``structure`` that lays it out.
* ``structures``: every layout that is not the dwords of a command: data
  structures, the layouts of log pages, and registers.
* ``values``: the tables of values, such as status codes or identifiers,
  by the ``kind`` of their caption, with the ``scope`` that the caption
  limits them to.
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

In every part of the data model, a ``Dwords`` is the dwords from ``lower``
to ``upper`` with their ``fields``, possibly under a ``condition``. A field,
``Bits``, is a ``range`` of bits or bytes, as given by ``unit``. A field
has a ``name``, an ``acronym`` and nested ``fields``. Where fields share
bits, a field also names the ``union`` and ``alternative`` it belongs to.
A field lists the ``values`` it takes. Where the description of a field
names the figure of a table of values instead of giving the values, as CNS
of the Identify command says "Refer to Figure 336", the field has
``values_in``: the ``source`` of that table, which is the table of
``values`` with the same ``source``.

A figure writes the entries of an array as fields numbered by their index,
and leaves out the rows between two of them, as LBAF0, LBAF1, "..." and
LBAF63 of the Identify Namespace data structure. Each entry that the figure
writes has ``array``: the ``name`` and the ``acronym`` of the entries
without their index, the ``index`` of the entry, the index of the ``first``
entry, the ``count`` of the entries, the ``stride``, which is the bits or
bytes of one entry, and ``lower``, where the first entry starts. A
generator writes the array at the entry whose ``index`` is ``first``, and
skips the other entries. Where the figure gives the range of the last entry
by a formula, ``count`` is null, and so is the ``index`` of that entry.

A field has ``structure`` where another figure lays the field out: the
``source`` of that structure, which is the structure of ``structures`` with
the same ``source``. senfd links a field that has no fields of its own to
the structure whose figure the description of the field names, as "defined
in Figure 125", and which is as wide as the field. An entry of an array
that names no figure is linked to the structure whose name its description
has, as "an I/O Command Set Vector". The ``kind`` of a structure that lays
out the entries of an array is ``data_structure``, whatever its caption
says.

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
