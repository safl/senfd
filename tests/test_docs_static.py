# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
import runpy
from pathlib import Path
from typing import List

STATIC = re.compile(r"_static/[\w./-]+\.(?:png|svg|cast)")


def test_each_static_file_the_documentation_shows_exists():
    pages = sorted(Path("docs/src").rglob("*.rst"))
    shown = {name for page in pages for name in STATIC.findall(page.read_text())}

    assert "_static/web-light.png" in shown
    assert [name for name in sorted(shown) if not (Path("docs") / name).is_file()] == []


def console_blocks(text: str) -> List[List[str]]:
    """The commands of each console block of 'text', without their prompt"""

    blocks = re.findall(r"\.\. code-block:: console\n\n((?:   .*\n|\n)+)", text)
    return [
        [line[5:] for line in block.splitlines() if line.startswith("   $ ")]
        for block in blocks
    ]


def test_the_copy_button_copies_the_commands_without_the_prompt():
    conf = runpy.run_path("docs/conf.py")

    assert "sphinx_copybutton" in conf["extensions"]
    assert conf["copybutton_prompt_text"] == "$ "


def test_each_way_of_running_the_wizard_is_a_block_of_its_own():
    """So that its copy button copies one command, not the alternatives"""

    pages = [Path("docs/src/index.rst"), Path("docs/src/sate/index.rst")]
    for page in pages:
        wizards = [
            block
            for block in console_blocks(page.read_text())
            if any("sate-preview-wizard" in command for command in block)
        ]
        assert len(wizards) == 2, page
        assert all(len(block) == 1 for block in wizards), page
    readme = Path("README.md").read_text()
    fenced = re.findall(r"```\n(.*?)```", readme, re.S)
    wizards = [block for block in fenced if "sate-preview-wizard" in block]
    assert [block.count("\n") for block in wizards] == [1, 1]
