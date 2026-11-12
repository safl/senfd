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


def test_the_logo_and_the_favicon_the_configuration_names_exist():
    conf = runpy.run_path("docs/conf.py")

    assert conf["html_logo"] == "_static/logo.svg"
    assert conf["html_favicon"] == "_static/favicon.svg"
    for name in (conf["html_logo"], conf["html_favicon"]):
        assert (Path("docs") / name).is_file(), name


def contrast(foreground: str, background: str) -> float:
    """The WCAG contrast ratio of two colours written as "#RRGGBB" """

    def luminance(colour: str) -> float:
        channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_the_text_and_link_colours_are_readable_on_both_backgrounds():
    """WCAG asks 7:1 of body text and 4.5:1 of other text and of links, on
    the page's background and on the sidebar's"""

    gruvbox = runpy.run_path("docs/conf.py")["GRUVBOX"]
    needs = {
        "foreground-primary": 7.0,
        "foreground-secondary": 4.5,
        "foreground-muted": 4.5,
        "brand-primary": 4.5,
        "brand-content": 4.5,
    }
    for mode in ("light", "dark"):
        colours = gruvbox[mode]
        for name, need in needs.items():
            for background in ("background-primary", "background-secondary"):
                ratio = contrast(colours[name], colours[background])
                assert ratio >= need, (mode, name, background, round(ratio, 2))


def test_the_documentation_uses_the_palette_of_the_web_page():
    from senfd.sate import web

    gruvbox = runpy.run_path("docs/conf.py")["GRUVBOX"]
    _, light, dark = web.THEMES["gruvbox"]
    for mode, values in (("light", light), ("dark", dark)):
        page = dict(zip(web.TOKENS, values.split()))
        assert gruvbox[mode]["background-primary"] == page["bg"]
        assert gruvbox[mode]["foreground-primary"] == page["fg"]
        assert gruvbox[mode]["brand-content"] == page["accent"]
    options = runpy.run_path("docs/conf.py")["html_theme_options"]
    assert options["dark_css_variables"]["color-brand-content"] == "#fabd2f"


def test_the_pages_keep_straight_quotes_and_double_hyphens():
    assert runpy.run_path("docs/conf.py")["smartquotes"] is False


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
