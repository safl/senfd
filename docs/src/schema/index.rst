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

* ``meta``: the version of senfd that made it, the name of the document it
  is of, ``merged`` for the merged one, and the file it was made from with
  that file's SHA-256, by which a published document is known.
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
