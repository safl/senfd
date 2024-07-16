#!/usr/bin/env python3
from pathlib import Path

from senfd.documents import CategorizedFigureDocument


def test_module(tmp_path):

    path_example = Path("example")
    paths = list(path_example.glob("*.json"))
    assert len(paths) > 0, f"No json available for testing in path({path_example})"

    for path in paths:
        document = CategorizedFigureDocument.from_figure_document_file(path)

        json_str = document.to_json()
        assert json_str, "Failed producing a string of JSON"

        json_path = tmp_path / document.get_json_filename()
        json_str = document.to_json_file(json_path)
        assert json_path.exists(), "Failed producing a string of JSON"

        assert document.is_valid()
