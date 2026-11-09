# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).parents[1] / "toolbox" / "cast_svg.py"


def test_the_links_are_taken_out_and_the_rest_kept():
    spec = importlib.util.spec_from_file_location("cast_svg", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    linked = (
        "\x1b]8;id=1;https://example.org/a.pdf#page=2\x1b\\\x1b[4mFigure 2\x1b[0m"
        "\x1b]8;;\x1b\\ and \x1b]8;;https://example.org\x07here\x1b]8;;\x07"
    )
    header = json.dumps({"version": 2, "width": 80, "height": 24})
    cast = header + "\n" + json.dumps([0.5, "o", linked]) + "\n"
    plain = module.without_links(cast).splitlines()
    assert plain[0] == header
    assert json.loads(plain[1]) == [0.5, "o", "\x1b[4mFigure 2\x1b[0m and here"]
