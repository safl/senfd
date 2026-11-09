# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import importlib.util
import re
from pathlib import Path

TOOL = Path(__file__).parents[1] / "toolbox" / "project_version_update.py"


def test_a_version_of_parts_above_nine_is_found():
    spec = importlib.util.spec_from_file_location("project_version_update", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for line, version in [
        ('__version__ = "0.9.2"', "0.9.2"),
        ('__version__ = "0.10.0"', "0.10.0"),
        ('version = "12.34.56"', "12.34.56"),
    ]:
        match = re.match(module.REGEX, line)
        assert match and match["version"] == version, line
