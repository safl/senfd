# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from senfd import __version__  # noqa: E402

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
project = "senfd"
copyright = f"2024-{datetime.date.today().year}, Simon A. F. Lund"
author = "Simon A. F. Lund"
release = __version__


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx_copybutton"]

# The copy button of a console block copies its commands without the prompt
# and without their output, ready to paste into a shell
copybutton_prompt_text = "$ "

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
# The Gruvbox palette of sate's web page, with mustard links. Where a
# colour fell short of WCAG on either background, its lightness is changed
# and its hue kept; tests/test_docs_static.py checks the contrast.
GRUVBOX = {
    "light": {
        "background-primary": "#fbf1c7",
        "background-secondary": "#f2e5bc",
        "background-hover": "#ebdbb2",
        "background-border": "#d5c4a1",
        "foreground-primary": "#3c3836",
        "foreground-secondary": "#504945",
        "foreground-muted": "#70635a",
        "foreground-border": "#a5874a",
        "brand-primary": "#8c5b0f",
        "brand-content": "#8c5b0f",
        "brand-visited": "#8c5b0f",
        "highlighted-background": "#ebdbb2",
    },
    "dark": {
        "background-primary": "#282828",
        "background-secondary": "#3c3836",
        "background-hover": "#504945",
        "background-border": "#504945",
        "foreground-primary": "#ebdbb2",
        "foreground-secondary": "#d5c4a1",
        "foreground-muted": "#aca095",
        "foreground-border": "#7a706a",
        "brand-primary": "#fabd2f",
        "brand-content": "#fabd2f",
        "brand-visited": "#fabd2f",
        "highlighted-background": "#504945",
    },
}
html_theme_options = {
    "sidebar_hide_name": True,
    "light_css_variables": {f"color-{k}": v for k, v in GRUVBOX["light"].items()},
    "dark_css_variables": {f"color-{k}": v for k, v in GRUVBOX["dark"].items()},
}
html_static_path = ["_static"]
# Keep straight quotes and "--" as written; smartquotes would turn them into
# curly quotes and dashes, which the writing style leaves out
smartquotes = False
html_logo = "_static/logo.svg"
html_favicon = "_static/favicon.svg"

linkcheck_report_timeouts_as_broken = False
