#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Take the screenshots of sate-web that the front page of the documentation
shows, one in the light mode and one in the dark, of the theme Gruvbox:
of the question page answering a question, and of the map with the CNS
values of Identify in focus

sate-web answers a question from the data model, and a headless browser
takes each screenshot. It needs playwright, of the extra 'dev', and its
browser, from 'playwright install chromium-headless-shell':

    toolbox/web_screenshots.py --spec ~/.cache/senfd/merged.spec.document.json \\
        docs/_static/web
"""

import argparse
import threading
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote, quote_plus

import uvicorn
from playwright.sync_api import sync_playwright

import senfd.query
from senfd.documents.spec import SpecDocument
from senfd.graph import graph_of
from senfd.sate import web
from senfd.sate.wizard import PORT, free_port

QUESTION = "cdw12 of write"
THEME = "gruvbox"
MODES = ("light", "dark")
WIDTH, HEIGHT = 1100, 720
# The map needs the width of the graph beside the panel
MAP_WIDTH, MAP_HEIGHT = 1500, 820


def names(out: Path, view: str = "") -> List[Path]:
    """The screenshots of 'out', a path without suffix, one for each mode,
    of the question page, or of 'view' as "map" """

    named = f"{out.name}-{view}" if view else out.name
    return [out.with_name(f"{named}-{mode}.png") for mode in MODES]


def focus(spec: SpecDocument) -> str:
    """The node of the map that the screenshot shows: the CNS values of
    Identify, which select structures of each command set"""

    cns = [
        node
        for node in graph_of(spec)["nodes"]
        if node.get("sub") == "cns_values" and node["label"] == "Identify"
    ]
    return cns[0]["id"] if cns else "home"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--spec", type=Path, default=None, help="The data model")
    parser.add_argument("out", type=Path, help="Where to write, without suffix")
    args = parser.parse_args(argv)
    spec = senfd.query.load(args.spec)

    host = "127.0.0.1"
    port = free_port(host, PORT)
    server = uvicorn.Server(
        uvicorn.Config(
            web.app(spec),
            host=host,
            port=port,
            log_level="warning",
        )
    )
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://{host}:{port}/"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        for mode, path in zip(MODES, names(args.out)):
            page.goto(url)
            page.evaluate(
                "([theme, mode]) => { localStorage.setItem('theme', theme);"
                " localStorage.setItem('mode', mode); }",
                [THEME, mode],
            )
            page.goto(f"{url}?q={quote_plus(QUESTION)}")
            page.screenshot(path=str(path))
            print(path)
        page.set_viewport_size({"width": MAP_WIDTH, "height": MAP_HEIGHT})
        for mode, path in zip(MODES, names(args.out, "map")):
            page.goto(url)
            page.evaluate(
                "([theme, mode]) => { localStorage.setItem('theme', theme);"
                " localStorage.setItem('mode', mode); }",
                [THEME, mode],
            )
            # ?static draws the map at once, without the flight to the focus
            page.goto(f"{url}map?static#{quote(focus(spec))}")
            page.wait_for_selector("#loading", state="detached")
            page.screenshot(path=str(path))
            print(path)
        browser.close()
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
