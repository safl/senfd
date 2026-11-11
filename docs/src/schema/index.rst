.. SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
..
.. SPDX-License-Identifier: LGPL-2.1-only

.. _sec-schema:

Schema
======

senfd writes three documents, each JSON validated against a JSON schema:
the ``FigureDocument``, the figures of a document as their tables are; the
``NormalizedFigureDocument``, each figure by the shape of its table and the
subject of its caption; and the ``SpecDocument``, the data model of the
specification. The schemas are in the repository, under
``src/senfd/schemas``, and in full below.

.. _sec-schema-data-model:

The data model
--------------

The ``SpecDocument`` is the data model; ``merged.spec.document.json``
merges those of every document given. Its parts:

* ``meta``: the format of the data model, the version of senfd that made
  it and the SHA-256 of that senfd's source, the name of the document it is
  of, ``merged`` for the merged one, and the file it was made from with that
  file's SHA-256, by which a published document is known. The merged one
  has two more SHA-256 hashes, of the documents it is made from and of
  those together with senfd's; see :ref:`sec-schema-identity`.
* ``documents``: the documents the data model is of, by name, each with its
  file and SHA-256, so the merged one knows every document in it.
* ``command_sets``: each command set by its name, with its commands. A
  command has its ``opcode``, its submission queue entry dwords ``sqe`` and
  completion queue entry dwords ``cqe``, and its ``operations``, what it
  does for the values of a selecting field, as each directive operation.
* ``features`` and ``log_pages``: by identifier. A feature has the dwords
  of the commands setting and getting it; a log page the ``structure``
  laying it out.
* ``structures``: every layout that is no command's dwords: data
  structures, log pages' layouts, registers.
* ``values``: the tables of values, as status codes or identifiers, by the
  ``kind`` of their caption, with the ``scope`` a caption confines them to.
* ``dwords``: the dwords of every figure by the name its caption gives, as
  read; ``unassigned``: those no command, feature or operation claims.
* ``diagnostics`` and ``errata``: what senfd normalised or could not read,
  and the candidate errata, each with where it is.

.. _sec-schema-identity:

Format and instance
-------------------

The format of the data model is its shape, as the schemas give it. senfd
owns the format, and bumps ``meta.format`` whenever the shape changes; a
test fails when the schemas change and the format does not.

A data model made from particular documents is an instance of the format.
The merged data model tells its instance by three SHA-256 hashes.
``input_sha256`` is of the documents it is made from, in whatever order
they were given. ``senfd_sha256`` is of the source of the senfd that read
them, leaving out sate, which only answers from the data model.
``combined_sha256`` is of the two together. The same documents read by the
same senfd give the same data model, so two data models with the same
combined hash are the same. Where two answers differ, the input hash says
whether the documents differ, and the senfd hash whether the reading does.

Throughout, a ``Dwords`` is dwords ``lower`` to ``upper`` with their
``fields``, possibly under a ``condition``; a field, ``Bits``, is a
``range`` of bits or bytes, by ``unit``, with its ``name``, ``acronym``,
nested ``fields``, the ``union`` and ``alternative`` it is of where fields
share bits, and the ``values`` it takes. A value of a table of a known kind
is ``typed`` as what it is: a requirement level, a flag, an identifier or a
range, a note, a reference, reserved or vendor specific. Every part has a
``source``: the document, the section and its title, the figure and the
page, and, where the document was read from a PDF, the page of the file,
``pdf_page``, where a link to the PDF opens.

A field also says what it is: its ``role``, a ``field`` or what holds a
place, and the ``kind`` of its range, a ``span`` with integer bounds and a
``width``, a ``formula`` written plainly as ``upper:lower``, or ``open``.
The kinds of a caption, a typed value and an erratum are enumerated too.

A data model can be verified for its format against the schema alone, by
a JSON Schema validator and with no part of senfd, as with the Python
package ``jsonschema``:

.. code-block:: python

   import json
   import jsonschema

   with open("schema/spec.document.schema.json") as schema:
       with open("merged.spec.document.json") as document:
           jsonschema.validate(json.load(document), json.load(schema))

``senfd --dump-schema --output schema`` writes the schema. It says what each
kind must hold. It cannot say what depends on the values, as that an upper
bound is not below its lower; reading the data model into senfd's types
does, and refuses one that is not.

The schema is versioned with senfd, and changes in a release are said in
its changelog. It is a starting point for a data model of the
specifications, not a standard: what is likely to stay is the commands with
their dwords and fields, features, log pages, structures and their sources;
what is likely to move is how values are typed and how diagnostics are
coded.

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
