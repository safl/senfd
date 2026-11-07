import re

from senfd.documents.enriched import FromFigureDocument
from senfd.utils import pascal_to_snake


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
                assert not list_of_sets[i].intersection(list_of_sets[j]), (
                    f"cls({cls.__name__}) has overlapping REGEX_GRID values"
                )


def enriched_example(tmp_path):
    """The enriched figure document of the example, and the errors of making it"""

    import json
    from argparse import Namespace
    from pathlib import Path

    import senfd.pipeline

    path = Path("example") / "example.docx"
    errors = senfd.pipeline.process(path, tmp_path, Namespace(skip_figures=None))
    (enriched,) = tmp_path.glob("*.enriched.figure.document.json")
    return json.loads(enriched.read_text(encoding="utf-8")), errors


def test_the_admin_opcodes_are_not_an_io_command_set():
    from senfd.documents.enriched import CommandIoOpcodeFigure

    regex = CommandIoOpcodeFigure.REGEX_FIGURE_DESCRIPTION
    assert not re.match(regex, "Opcodes for Admin Commands", flags=re.IGNORECASE)
    assert re.match(regex, "Opcodes for NVM Commands", flags=re.IGNORECASE)


def test_an_example_of_a_log_page_is_an_example():
    """A figure showing what a log page returns is an example, not the
    definition of a log page"""

    from senfd.documents.enriched import ExampleFigure, LogPageFigure

    caption = "Example Foo Element returned by Foo Information Log Page"
    assert not re.match(LogPageFigure.REGEX_FIGURE_DESCRIPTION, caption, re.I)
    assert re.match(ExampleFigure.REGEX_FIGURE_DESCRIPTION, caption, re.I)
    assert re.match(LogPageFigure.REGEX_FIGURE_DESCRIPTION, "Foo Log Page", re.I)


def test_a_data_structure_of_a_format_is_a_data_structure():
    """A data structure named after a format, or one ending in the specific
    fields of a command set, is a data structure"""

    from senfd.documents.enriched import (
        DataStructureFigure,
        FormatFigure,
        ParameterFieldFigure,
    )

    for caption, other in [
        ("FB Format Data Structure", FormatFigure),
        ("Foo Format Data Structure, Foo Command Set Specific", FormatFigure),
        (
            "Identify - Identify Foo data structure, Foo Command Set Specific Fields",
            ParameterFieldFigure,
        ),
    ]:
        assert re.match(DataStructureFigure.REGEX_FIGURE_DESCRIPTION, caption, re.I)
        assert not re.match(other.REGEX_FIGURE_DESCRIPTION, caption, re.I), caption
    assert re.match(
        FormatFigure.REGEX_FIGURE_DESCRIPTION,
        "Foo Event Data Format (Event Type 02h)",
        re.I,
    )


def test_a_figure_matching_several_categories_is_left_uncategorized(
    tmp_path, monkeypatch
):
    """Neither category is chosen, and the error names both"""

    from senfd.documents.enriched import ExampleFigure

    # The example figure takes the data pointers too, which their own figure has
    monkeypatch.setattr(ExampleFigure, "REGEX_FIGURE_DESCRIPTION", r".*\bData Pointer$")
    document, errors = enriched_example(tmp_path)

    multiple = [str(e) for e in errors if "Matched on multiple" in str(e)]
    assert len(multiple) == 2
    assert all("CommandSqeDataPointerFigure, ExampleFigure" in e for e in multiple)
    assert not document["command_sqe_data_pointer"]


def test_every_category_has_a_figure_of_its_own_in_the_example(tmp_path):
    """senfd is tested on the example alone, so a category it has no figure
    of is a category nothing tests"""

    document, errors = enriched_example(tmp_path)

    assert not [e for e in errors if "Matched on multiple" in str(e)]
    for cls in FromFigureDocument.get_figure_enriching_classes():
        key = pascal_to_snake(cls.__name__).replace("_figure", "")
        assert document[key], f"example/example.docx has no {cls.__name__}"
