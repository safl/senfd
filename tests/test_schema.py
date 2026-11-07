from senfd.documents import get_document_classes


def test_check_schema_equivalence():
    for document_class in get_document_classes():
        dynamic_schema = document_class.schema()
        assert dynamic_schema

        static_schema = document_class.schema_static()
        assert static_schema

        assert dynamic_schema == static_schema
