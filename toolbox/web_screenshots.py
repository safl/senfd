#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
Take the screenshots of sate-web that the front page of the documentation
shows, one in the light mode and one in the dark, of the theme One

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
from urllib.parse import quote_plus

import uvicorn
from playwright.sync_api import sync_playwright

import senfd.query
from senfd.sate import web
from senfd.sate.wizard import PORT, free_port

QUESTION = "cdw12 of write"
THEME = "one"
MODES = ("light", "dark")
WIDTH, HEIGHT = 1100, 720


def names(out: Path) -> List[Path]:
    """The screenshots of 'out', a path without suffix, one for each mode"""

    return [out.with_name(f"{out.name}-{mode}.png") for mode in MODES]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--spec", type=Path, default=None, help="The data model")
    parser.add_argument("out", type=Path, help="Where to write, without suffix")
    args = parser.parse_args(argv)

    host = "127.0.0.1"
    port = free_port(host, PORT)
    server = uvicorn.Server(
        uvicorn.Config(
            web.app(senfd.query.load(args.spec)),
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
        browser.close()
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
