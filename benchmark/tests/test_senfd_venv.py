# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import sys
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import senfd_venv  # noqa: E402

ROOT = Path(__file__).parents[2]


def requires_python() -> SpecifierSet:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return SpecifierSet(project["requires-python"])


def test_the_default_python_is_one_senfd_installs_on():
    assert senfd_venv.PYTHON in requires_python()


def test_the_configured_python_is_one_senfd_installs_on():
    config = tomllib.loads((ROOT / "benchmark/configs/default.toml").read_text())
    assert config["senfd"]["python"] in requires_python()
