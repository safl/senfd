from senfd.documents.enriched import EnrichedFigureDocument
from senfd.documents.normalized import NormalizedFigureDocument
from senfd.documents.plain import FigureDocument
from senfd.documents.spec import SpecDocument


def get_document_classes():
    return [
        FigureDocument,
        EnrichedFigureDocument,
        NormalizedFigureDocument,
        SpecDocument,
    ]
