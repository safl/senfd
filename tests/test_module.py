#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

from pathlib import Path
from argparse import Namespace

import senfd.pipeline


def test_the_errors_of_an_invalid_document_are_reported(tmp_path):
    """The example is a valid document but for what it writes oddly on purpose,
    as the documents do: a table wrapped in another, two figures in one table,
    a section numbered otherwise than its table of contents; the invalid one
    has captions and tables of figures not on the form senfd reads"""

    example = Path("example") / "example.docx"
    invalid = Path("example") / "invalid.docx"
    errors = senfd.pipeline.process(example, tmp_path, Namespace(skip_figures=None))
    assert [e.message for e in errors] == [
        "Table wrapped in a table of one cell; unwrapped",
        "Table of 2 figures, by the captions in its rows; split",
        "Section 'Data Structures' counted as 3, the table of contents has 4",
    ]
    errors = senfd.pipeline.process(invalid, tmp_path, Namespace(skip_figures=None))
    assert {type(e).__name__ for e in errors} >= {"TableError", "TableOfFiguresError"}


def test_the_package_version_is_that_of_the_module():
    """pyproject.toml takes the version from senfd.__version__, so a bump sets it
    in one place"""

    from importlib.metadata import version

    import senfd

    assert version("senfd") == senfd.__version__
