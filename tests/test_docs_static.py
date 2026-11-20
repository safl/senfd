# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
import runpy
from pathlib import Path
from typing import List, get_args

from senfd.documents.spec import ErratumCode

STATIC = re.compile(r"_static/[\w./-]+\.(?:png|svg|cast)")


def test_each_static_file_the_documentation_shows_exists():
    pages = sorted(Path("docs/src").rglob("*.rst"))
    shown = {name for page in pages for name in STATIC.findall(page.read_text())}

    assert "_static/web-light.png" in shown
    assert "_static/web-map-light.png" in shown
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


def test_the_wizard_is_run_with_uvx_alone():
    """senfd is tried with uvx and installed with uv, so each page gives one
    command to copy, and none gives pipx"""

    command = "uvx --from senfd@latest sate-preview-wizard"
    for page in (Path("docs/src/index.rst"), Path("docs/src/sate/index.rst")):
        text = page.read_text()
        wizards = [
            block
            for block in console_blocks(text)
            if any("sate-preview-wizard" in line for line in block)
        ]
        assert wizards == [[command]], page
        assert "pipx" not in text, page
    readme = Path("README.md").read_text()
    fenced = re.findall(r"```\n(.*?)```", readme, re.S)
    wizards = [block for block in fenced if "sate-preview-wizard" in block]
    assert wizards == [f"{command}\n"]
    assert "pipx" not in readme

    install = Path("docs/src/install/index.rst").read_text()
    assert ["uv tool install senfd"] in console_blocks(install)
    assert "pipx" not in install


def test_the_linting_page_names_each_kind_of_candidate_erratum():
    page = Path("docs/src/linting/index.rst").read_text()
    section = page.split("Candidate errata\n")[1].split("Document errors\n")[0]

    assert [c for c in get_args(ErratumCode) if f"``{c}``" not in section] == []
