def get_document_classes():
    """The classes of the documents senfd makes; imported here rather than at
    the top, as the modules of the documents import senfd.normalize, which
    imports senfd.documents.base, and so this package"""

    from senfd.documents.normalized import NormalizedFigureDocument
    from senfd.documents.plain import FigureDocument
    from senfd.documents.spec import SpecDocument

    return [FigureDocument, NormalizedFigureDocument, SpecDocument]
