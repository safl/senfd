#!/usr/bin/env python3
from pathlib import Path
from argparse import Namespace

import senfd.pipeline


def test_the_errors_of_an_invalid_document_are_reported(tmp_path):
    """The example is a valid document, the invalid one has captions and tables
    of figures that are not on the form senfd reads"""

    example = Path("example") / "example.docx"
    invalid = Path("example") / "invalid.docx"
    assert not senfd.pipeline.process(example, tmp_path, Namespace(skip_figures=None))
    errors = senfd.pipeline.process(invalid, tmp_path, Namespace(skip_figures=None))
    assert {type(e).__name__ for e in errors} >= {"TableError", "TableOfFiguresError"}


def test_the_package_version_is_that_of_the_module():
    """pyproject.toml takes the version from senfd.__version__, so a bump sets it
    in one place"""

    from importlib.metadata import version

    import senfd

    assert version("senfd") == senfd.__version__
