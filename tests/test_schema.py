from senfd.documents import FigureDocument, CategorizedFigureDocument


def test_check_schema_equivalence():
    for document_class in [FigureDocument, CategorizedFigureDocument]:
        dynamic_schema = document_class.schema()
        assert dynamic_schema

        static_schema = document_class.schema_static()
        assert static_schema

        assert dynamic_schema == static_schema
