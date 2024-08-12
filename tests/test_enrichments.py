import re

from senfd.documents.enriched import FromFigureDocument


def test_enriching_classes_has_regex_grid():
    for cls in FromFigureDocument.get_figure_enriching_classes():
        assert hasattr(cls, "REGEX_GRID"), "Enrichment figure must have REGEX_GRID"


def test_enriching_classes_regex_grid_overlap():
    for cls in FromFigureDocument.get_figure_enriching_classes():
        try:
            list_of_sets = [
                set(re.compile(val_regex).groupindex.keys())
                for _, val_regex in cls.REGEX_GRID
            ]
        except ValueError:
            assert False, f"{cls.__name__} has invalid REGEX_GRID: {cls.REGEX_GRID}"

        for i in range(len(list_of_sets)):
            for j in range(i + 1, len(list_of_sets)):
                assert not list_of_sets[i].intersection(
                    list_of_sets[j]
                ), f"cls({cls.__name__}) has overlapping REGEX_GRID values"
