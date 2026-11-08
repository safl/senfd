# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from senfd.documents import get_document_classes
from senfd.documents.spec import SpecDocument


def test_check_schema_equivalence():
    for document_class in get_document_classes():
        dynamic_schema = document_class.schema()
        assert dynamic_schema

        static_schema = document_class.schema_static()
        assert static_schema

        assert dynamic_schema == static_schema


def test_every_part_of_the_data_model_is_described():
    schema = SpecDocument.model_json_schema()
    undescribed = [
        f"{name}.{field}"
        for name, definition in schema["$defs"].items()
        for field, value in definition.get("properties", {}).items()
        if not value.get("description")
    ] + [f for f, v in schema["properties"].items() if not v.get("description")]
    assert undescribed == []
    assert [n for n, d in schema["$defs"].items() if not d.get("description")] == []
