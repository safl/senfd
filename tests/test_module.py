#!/usr/bin/env python3
from pathlib import Path

from senfd.documents.categorized import CategorizedFigureDocument


def test_module(tmp_path):

    path_example = Path("example")
    paths = list(path_example.glob("*.json"))
    assert len(paths) > 0, f"No json available for testing in path({path_example})"

    for path in paths:
        document = CategorizedFigureDocument.from_figure_document_file(path)
        assert document.is_valid()

        json_str = document.to_json()
        assert json_str, "Failed producing a string of JSON"

        document.to_json_file(tmp_path / "test.json")

        from_disk = CategorizedFigureDocument.parse_file(tmp_path / "test.json")
        assert document == from_disk
