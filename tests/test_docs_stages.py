# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
from pathlib import Path

STAGES = Path("docs/src/stages")
TOOL = Path("toolbox/example_stages.py")


def test_the_stages_the_documentation_shows_are_those_of_the_example(tmp_path):
    """docs/src/stages holds what toolbox/example_stages.py writes from
    example/output; run the script rather than edit the files"""

    spec = importlib.util.spec_from_file_location("example_stages", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write(tmp_path)
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == sorted(p.name for p in STAGES.iterdir() if p.suffix != ".rst")
    for name in written:
        assert (tmp_path / name).read_text() == (STAGES / name).read_text(), name
