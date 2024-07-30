from senfd.documents.enriched import EnrichedFigureDocument
from senfd.documents.plain import FigureDocument


def test_check_schema_equivalence():
    for document_class in [FigureDocument, EnrichedFigureDocument]:
        dynamic_schema = document_class.schema()
        assert dynamic_schema

        static_schema = document_class.schema_static()
        assert static_schema

        assert dynamic_schema == static_schema
