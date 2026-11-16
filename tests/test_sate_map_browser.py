# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The map of sate-web in a headless browser: what the page does when a reader
clicks, searches, goes back, asks sate and changes the theme. The tests need
the browser of playwright, from 'playwright install chromium-headless-shell',
and are skipped without it.
"""

import threading
import time
from pathlib import Path

import pytest
import uvicorn

import senfd.query
from senfd.sate import web
from senfd.sate.wizard import free_port

playwright = pytest.importorskip("playwright.sync_api")

SPEC = Path("example") / "output" / "merged.spec.document.json"


@pytest.fixture(scope="module")
def url():
    host = "127.0.0.1"
    port = free_port(host, 18899)
    server = uvicorn.Server(
        uvicorn.Config(
            web.app(senfd.query.load(SPEC)), host=host, port=port, log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://{host}:{port}/"
    server.should_exit = True
    thread.join()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as driver:
        try:
            launched = driver.chromium.launch()
        except playwright.Error as exc:
            pytest.skip(f"the browser of playwright is not installed: {exc}")
        yield launched
        launched.close()


@pytest.fixture
def page(browser, url):
    """The map, drawn, with the errors the page raises in 'page.errors'"""

    page = browser.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(error))
    # ?static draws at once, so no test reads a node that is still in flight
    page.goto(f"{url}map?static")
    page.wait_for_selector("#loading", state="detached")
    yield page
    assert page.errors == []
    page.close()


def focused(page) -> str:
    return page.inner_text("#panel h2")


def test_a_click_on_a_neighbour_moves_the_focus_and_back_returns(page):
    assert focused(page) == "NVMe specifications"

    page.click('.node[data-id="cs:admin"] .dot')
    assert focused(page) == "Admin"
    assert page.evaluate("location.hash") == "#cs%3Aadmin"

    page.click("#back")
    assert focused(page) == "NVMe specifications"
    page.click("#fwd")
    assert focused(page) == "Admin"


def test_search_finds_a_structure_by_its_name(page):
    page.fill("#search", "foo entry")
    page.wait_for_selector("#results div.sel")
    page.press("#search", "Enter")
    assert focused(page) == "Foo Entry"


def test_a_link_of_the_panel_moves_the_focus(page):
    page.click('#panel a.go[data-id="cs:admin"]')
    assert focused(page) == "Admin"


def test_the_answer_of_sate_beside_the_map_leads_into_the_map(page):
    page.fill("#askq", "structure foo entry")
    page.click("#askform button")
    page.wait_for_selector('#answer a[href^="map#"]')
    page.click('#answer a[href^="map#"]')
    assert focused(page) == "Foo Entry"


def test_a_node_takes_the_colour_of_its_entity_in_the_chosen_theme(page):
    """A command is drawn in the red of the theme, and the colour follows
    the theme the reader chooses"""

    command = '.node[data-id="cmd:admin:foo_get"] .dot'
    page.click('.node[data-id="cs:admin"] .dot')
    page.wait_for_selector(command)

    page.emulate_media(color_scheme="light")
    for theme in ("one", "gruvbox"):
        page.select_option("#theme select", theme)
        light = web.ENTITY_COLOURS[theme][0].split()[web.ENTITIES.index("command")]
        red, green, blue = (int(light[i : i + 2], 16) for i in (1, 3, 5))
        page.wait_for_function(
            "([selector, want]) => {"
            " const e = document.querySelector(selector);"
            " return e && getComputedStyle(e).stroke === want; }",
            arg=[command, f"rgb({red}, {green}, {blue})"],
            timeout=5000,
        )
