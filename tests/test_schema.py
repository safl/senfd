# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import hashlib
import json
import typing
from pathlib import Path

import jsonschema
import pydantic
import pytest

from senfd.documents import get_document_classes
from senfd.identity import FORMAT
from senfd.documents.spec import TYPED_FORMS, Bits, SpecDocument, TypedKind
from senfd.normalize import CAPTIONS, CaptionKind


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


MERGED = Path("example") / "output" / "merged.spec.document.json"


def example():
    return json.loads(MERGED.read_text(encoding="utf-8"))


def format_errors(document):
    validator = jsonschema.Draft202012Validator(SpecDocument.schema_static())
    return list(validator.iter_errors(document))


def fields_of(document):
    """Every field of the 'structures' of 'document'"""

    return [field for s in document["structures"] for field in s["fields"]]


def of_kind(document, kind):
    return next(f for f in fields_of(document) if f["kind"] == kind)


def test_a_data_model_is_verified_for_format_by_its_schema_alone():
    assert format_errors(example()) == []


def banana(field):
    field["kind"] = "banana"


def nameless(field):
    field["name"] = None


def no_role(field):
    del field["role"]


def nibbles(field):
    field["unit"] = "nibbles"


def unbounded(field):
    field["upper"] = None


def with_formula(field):
    field["formula"] = "N + 3:N"


@pytest.mark.parametrize(
    "broken", [banana, nameless, no_role, nibbles, unbounded, with_formula]
)
def test_a_span_not_of_the_format_is_refused_by_the_schema(broken):
    document = example()
    broken(of_kind(document, "span"))
    assert format_errors(document)


def test_a_formula_or_an_open_range_with_bounds_is_refused_by_the_schema():
    document = example()
    good = copy.deepcopy(document)
    of_kind(document, "formula")["upper"] = 3
    assert format_errors(document)
    of_kind(good, "formula")["formula"] = "no colon"
    assert format_errors(good)


def test_a_kind_of_structure_or_erratum_outside_the_schema_is_refused():
    document = example()
    document["structures"][0]["kind"] = "banana"
    assert format_errors(document)
    document = example()
    document["errata"][0]["code"] = "banana"
    assert format_errors(document)


def test_a_typed_value_holds_what_its_kind_needs():
    document = example()
    typed = next(
        t
        for v in document["values"]
        for e in v["entries"]
        for t in e["typed"].values()
        if t["kind"] == "level"
    )
    typed["level"] = None
    assert format_errors(document)


def test_the_schema_enumerates_every_kind_senfd_makes():
    assert set(typing.get_args(CaptionKind)) == {k for k, _ in CAPTIONS} | {"other"}
    assert set(typing.get_args(TypedKind)) == {k for k, _ in TYPED_FORMS}


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "span", "upper": 1, "lower": 2, "width": 0},
        {"kind": "span", "upper": 3, "lower": 2, "width": 9},
        {"kind": "span", "upper": None, "lower": 2},
        {"kind": "formula", "upper": 3},
        {"kind": "formula"},
        {"kind": "open", "formula": "N:M"},
    ],
)
def test_what_a_schema_cannot_say_loading_the_data_model_refuses(values):
    with pytest.raises(pydantic.ValidationError):
        Bits(name="Foo", unit="bytes", range="x", role="field", **values)


# The format of the data model, and the SHA-256 of the shape its schemas give
FORMAT_SHAPE = (3, "78fae4f2f99eeff7c130b2877c9c861555f0fd9bb70caf5531757941eda7b78e")


def shape(node: typing.Any) -> typing.Any:
    """'node' of a schema without its descriptions and titles"""

    if isinstance(node, dict):
        return {
            k: shape(v) for k, v in node.items() if k not in ("description", "title")
        }
    if isinstance(node, list):
        return [shape(v) for v in node]
    return node


def shape_sha256(schemas: typing.List[typing.Dict]) -> str:
    """The SHA-256 of what 'schemas' say of the shape of the data model,
    leaving out the default version of senfd, which changes at each release"""

    shapes = []
    for schema in schemas:
        shaped = shape(copy.deepcopy(schema))
        shaped["$defs"]["DocumentMeta"]["properties"]["version"].pop("default")
        shapes.append(shaped)
    return hashlib.sha256(json.dumps(shapes, sort_keys=True).encode()).hexdigest()


def committed_schemas() -> typing.List[typing.Dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(Path("src/senfd/schemas").glob("*.schema.json"))
    ]


def test_the_format_is_bumped_when_the_shape_of_the_schemas_changes():
    """When this fails, the shape of the data model changed: bump FORMAT in
    src/senfd/identity.py, and set FORMAT_SHAPE to it and the hash given"""

    assert (FORMAT, shape_sha256(committed_schemas())) == FORMAT_SHAPE


def test_the_shape_leaves_out_descriptions_and_the_version_of_senfd():
    schemas = committed_schemas()
    reworded = copy.deepcopy(schemas)
    reworded[0]["description"] = "reworded"
    reworded[0]["$defs"]["DocumentMeta"]["properties"]["version"]["default"] = "9.9"
    retyped = copy.deepcopy(schemas)
    retyped[0]["$defs"]["DocumentMeta"]["properties"]["format"]["type"] = "string"

    assert shape_sha256(reworded) == shape_sha256(schemas)
    assert shape_sha256(retyped) != shape_sha256(schemas)
