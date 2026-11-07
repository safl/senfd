.. _sec-schema:

Schema
======

Senfd has the following documents:

* FigureDocument, the figures of a document as their tables are
* NormalizedFigureDocument, each figure by the shape of its table and the
  subject of its caption
* SpecDocument, the model of the specification

Their **JSON** representation is validated against a **JSON** schema. Links to
the schema files and the schemas themselves, in verbatim, are provided in the
sections below.

.. _sec-schema-figure-document:

Figure Document
---------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/plain.figure.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/plain.figure.document.schema.json
   :language: json

.. _sec-schema-normalized-figure-document:

Normalized Figure Document
--------------------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/normalized.figure.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/normalized.figure.document.schema.json
   :language: json

.. _sec-schema-spec-document:

Spec Document
-------------

* https://raw.githubusercontent.com/safl/senfd/main/src/senfd/schemas/spec.document.schema.json

.. literalinclude:: ../../../src/senfd/schemas/spec.document.schema.json
   :language: json
