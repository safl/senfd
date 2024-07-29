#!/usr/bin/env python3
from pathlib import Path

import senfd.pipeline


def test_module(tmp_path):

    path_example = Path("example")
    paths = list(path_example.glob("*"))
    assert len(paths) > 0, f"No documents available for testing in path({path_example})"

    for path in paths:
        errors = senfd.pipeline.process(path, tmp_path)
        assert not errors
