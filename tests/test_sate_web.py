# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import html
import re
from pathlib import Path

import pytest
import uvicorn
from starlette.testclient import TestClient

import senfd
import senfd.published
import senfd.query
from senfd.documents.spec import SpecDocument
from senfd.sate import web

SPEC = Path("example") / "output" / "merged.spec.document.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app(senfd.query.load(SPEC)))


def test_the_page_shows_the_answer_and_its_status(client):
    response = client.get("/", params={"q": "cdw10 of ding"})

    assert response.status_code == 200
    assert "<td>Foo Count</td>" in response.text
    assert "read as command(&#x27;Ding&#x27;, dword=10)" in response.text
    assert 'value="cdw10 of ding"' in response.text


def test_the_start_page_lists_the_keys_and_has_the_forms_dialog(client):
    response = client.get("/")
    forms = response.text.index('<dialog id="forms">')

    assert "<main></main>" in response.text
    # The counts appear once, above the input field
    assert response.text.count(" commands, ") == 1
    assert response.text.index("Ask about any of ") < response.text.index(
        '<input id="q"'
    )
    assert (
        "<kbd>Ctrl</kbd>+<kbd>I</kbd> goes to the field and <kbd>Esc</kbd>\nleaves it"
    ) in response.text
    assert "completes a name or an acronym" in response.text
    assert '<form class="ask" method="get"' in response.text
    assert response.text.index("sate answers these forms of question") > forms
    assert "Ctrl-D" not in response.text


def test_the_page_shows_the_document_count_as_a_link(client):
    response = client.get("/")

    assert (
        '3 log pages, 49 structures, across <a class="documents" '
        'href="#documents">2 documents</a>'
    ) in response.text
    assert '<dialog id="documents">' in response.text


def test_the_document_table_links_the_published_pdfs():
    from senfd.documents.base import DocumentMeta

    base = next(d for d in senfd.published.documents() if d["name"] == "Base 2.4")
    spec = SpecDocument()
    spec.documents["NVM Express Base Specification, Revision 2-4"] = DocumentMeta(
        stem="Base", file=base["file"], sha256=base["sha256"]
    )
    spec.documents["Own"] = DocumentMeta(stem="Own", file="own.docx", sha256="ab" * 32)

    rows = [
        line for line in web.manifest(spec).splitlines() if line.startswith("<tr><td>")
    ]
    assert rows == [
        f'<tr><td>Base 2.4</td><td><a href="{base["url"]}" target="_blank" '
        f'rel="noopener">{base["file"]}</a></td><td><code title="{base["sha256"]}">'
        f"{base['sha256'][:12]}</code></td></tr>",
        f'<tr><td>Own</td><td>own.docx</td><td><code title="{"ab" * 32}">'
        f"{'ab' * 6}</code></td></tr>",
    ]


def test_each_theme_has_light_and_dark_rules_and_an_option(client):
    response = client.get("/")

    assert next(iter(web.THEMES)) == "gruvbox"
    assert '<html lang="en" data-theme="gruvbox">' in response.text
    assert '<button id="mode" type="button" hidden>' in response.text
    for name, (title, *_) in web.THEMES.items():
        root = f':root[data-theme="{name}"]'
        assert f"{root} {{ color-scheme: light;" in response.text
        assert (
            "@media (prefers-color-scheme: dark) {\n"
            f'  {root}:not([data-mode="light"]) {{ color-scheme: dark;'
        ) in response.text
        assert f'{root}[data-mode="dark"] {{ color-scheme: dark;' in response.text
        assert f'<option value="{name}">{html.escape(title)}</option>' in response.text


@pytest.mark.parametrize("theme", list(web.THEMES))
@pytest.mark.parametrize("dark", [False, True])
def test_each_theme_sets_every_colour_variable(theme, dark):
    declared = web.colours(theme, dark)

    assert [f"--{token}: #" in declared for token in web.TOKENS] == [True] * 8
    assert declared.count("--") == len(web.TOKENS)


def test_an_unknown_question_gets_a_note_with_suggestions(client):
    response = client.get("/", params={"q": "opcode of dimg"})

    assert '<div class="note" role="note"><p><strong>NOTE</strong> ' in response.text
    assert '<a href="?q=opcode+of+Ding">opcode of Ding</a>' in response.text
    assert '<a href="?q=help">The forms of a question</a>' in response.text
    assert "sate help" not in response.text


def test_the_note_has_no_suggestions_for_an_unknown_identifier(client):
    response = client.get("/", params={"q": "feature FFh"})

    assert "<strong>NOTE</strong>" in response.text
    assert "Did you mean" not in response.text


def test_the_selected_completion_has_a_frame_in_the_link_colour(client):
    response = client.get("/")

    assert (
        "inset 4px 0 0 var(--accent), inset 0 0 0 1px var(--accent);" in response.text
    )


def test_choosing_a_completion_submits_except_a_question_form(client):
    response = client.get("/")

    assert (
        '  if (offer.kind === "question") update();\n  else input.form.requestSubmit();'
    ) in response.text
    # take() closes the menu, so a second Enter cannot insert the completion
    take = response.text.index("function take(offer)")
    assert (
        response.text.index("  close();\n}", take)
        < response.text.index("\n}", take + 1) + 2
    )
    assert client.get("/complete", params={"q": ""}).json()["offers"][0]["kind"] == (
        "question"
    )


def test_only_the_start_page_focuses_the_input_field(client):
    assert '<input id="q" name="q" value=""' in client.get("/").text
    assert "\n autofocus spellcheck" in client.get("/").text
    answered = client.get("/", params={"q": "cdw10 of ding"}).text
    assert "autofocus" not in answered


def test_the_header_links_the_documentation_and_the_source(client):
    response = client.get("/")

    assert 'href="https://safl.dk/senfd/"' in response.text
    assert 'href="https://github.com/safl/senfd"' in response.text


def test_the_title_is_a_button_with_the_logo_and_the_logo_is_the_favicon(client):
    page = client.get("/").text
    title = re.search(r'<h1><a class="home" href="\.">(.*?)</a>(.*?)</h1>', page, re.S)

    assert title is not None
    assert title.group(1) == web.LOGO + '<span class="name">sate</span>'
    assert title.group(2) == f'<span class="version">v{senfd.__version__}</span>'
    assert "header h1 a.home {" in page
    assert "header h1 .name {" in page
    assert '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' in page
    assert 'fill="#D79921" stroke="#282828"' in web.LOGO
    button = re.search(r"header h1 a\.home \{(.*?)\}", page, re.S).group(1)
    assert "background: #282828;" in button
    assert "var(--" not in button
    assert "light-dark" not in page
    assert "header h1 .logo g { stroke: none; }" in page


def test_an_unknown_question_is_reported_as_not_known(client):
    response = client.get("/", params={"q": "opcode of hyperdrive"})

    assert "not known" in response.text


def test_complete_returns_the_completions_of_the_text(client):
    found = client.get("/complete", params={"q": "opcode of di"}).json()

    assert found["offers"] == [
        {"text": "Ding", "start": -2, "kind": "command", "shown": "Ding", "parts": []}
    ]


def test_complete_returns_question_forms_for_empty_text(client):
    found = client.get("/complete", params={"q": ""}).json()

    assert found["offers"][0]["kind"] == "question"


def test_the_question_is_escaped_in_the_page(client):
    response = client.get("/", params={"q": '"><script>alert(1)</script>'})

    assert "<script>alert(1)" not in response.text
    assert "&lt;script&gt;alert(1)" in response.text


def test_html_in_an_answer_is_escaped():
    assert web.rendered("<b>Foo</b>") == "<p>&lt;b&gt;Foo&lt;/b&gt;</p>\n"


def test_a_citation_link_opens_in_a_new_tab():
    assert web.rendered("[Figure 1](https://example.org/a.pdf#page=1)") == (
        '<p><a target="_blank" rel="noopener" '
        'href="https://example.org/a.pdf#page=1">Figure 1</a></p>\n'
    )


def test_a_missing_data_model_is_reported_and_fails(tmp_path, capsys):
    assert web.main(["--spec", str(tmp_path / "missing.json")]) == 1
    assert "no data model to answer from" in capsys.readouterr().err


@pytest.fixture
def served():
    """A client of sate-web serving the tools of sate-mcp at /mcp to the
    token 'secret'"""

    import senfd.sate.mcp

    with TestClient(web.app(senfd.query.load(SPEC), "secret")) as client:
        yield client
    senfd.sate.mcp.given = None


CALL = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "command", "arguments": {"name": "ding", "dword": 10}},
}
ACCEPT = {"Accept": "application/json, text/event-stream"}


def test_mcp_answers_a_request_with_the_token(served):
    response = served.post(
        "/mcp", json=CALL, headers={**ACCEPT, "Authorization": "Bearer secret"}
    )

    assert response.status_code == 200
    (content,) = response.json()["result"]["content"]
    assert content["text"].splitlines()[1:] == [
        "cdw10 [example, 1.2, Figure 2, page 2]",
        "  31:16 Reserved",
        "  15:00 Foo Count (FCNT)",
    ]


@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "secret"])
def test_mcp_refuses_a_request_without_the_token(served, authorization):
    headers = {**ACCEPT, **({"Authorization": authorization} if authorization else {})}
    response = served.post("/mcp", json=CALL, headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_mcp_is_absent_without_a_token(client):
    assert client.post("/mcp", json=CALL, headers=ACCEPT).status_code == 404


def test_the_status_shows_the_icon_and_the_reading_of_the_question(client):
    response = client.get("/", params={"q": "cdw10 of ding"})

    assert (
        '<p class="status"><span class="tag" title="read as command(&#x27;Ding&#x27;, '
        "dword=10) | 1 lookup | " in response.text
    )
    assert (
        f'{web.mark("command")}command <span class="what">Ding</span>, cdw10</span>'
        in (response.text)
    )
    assert web.mark("command").startswith('<svg class="mark"')


@pytest.mark.parametrize(
    "typed", ["", "w", "log page ", "feature ", "structure ", "which bit of ", "F"]
)
def test_every_kind_of_completion_has_an_icon(client, typed):
    offered = client.get("/complete", params={"q": typed}).json()["offers"]

    assert {offer["kind"] for offer in offered} <= set(web.MARKS)


def luminance(colour):
    """The relative luminance of '#rrggbb', as WCAG defines it"""

    channels = [int(colour[at : at + 2], 16) / 255 for at in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# Each pair of colours that appear together, and the minimum contrast ratio
# of the pair: WCAG AAA for text, and WCAG AA for other text and for lines
NEEDS = [
    ("fg", "bg", 7.0),
    ("fg", "chosen", 7.0),
    ("fg", "note", 7.0),
    ("dim", "bg", 4.5),
    ("accent", "bg", 4.5),
    ("accent", "note", 4.5),
    ("warn", "note", 4.5),
    ("line", "bg", 3.0),
]


def test_the_default_theme_is_the_gruvbox_palette_of_senfd():
    """Background, text, mustard links and the secondary surface; the light
    mustard is #B57614 darkened in lightness to reach 4.5:1"""

    _, light, dark = web.THEMES["gruvbox"]
    tokens = ("bg", "fg", "accent", "chosen", "note")

    def pick(values):
        return [dict(zip(web.TOKENS, values.split()))[t] for t in tokens]

    assert pick(dark) == ["#282828", "#ebdbb2", "#fabd2f", "#3c3836", "#3c3836"]
    assert pick(light) == ["#fbf1c7", "#3c3836", "#8c5b0f", "#f2e5bc", "#f2e5bc"]


@pytest.mark.parametrize("theme", list(web.THEMES))
@pytest.mark.parametrize("dark", [False, True])
def test_each_theme_meets_the_wcag_contrast_ratios(theme, dark):
    _, light, darks = web.THEMES[theme]
    colours = dict(zip(web.TOKENS, (darks if dark else light).split()))

    weak = [
        f"{a} on {b} {contrast(colours[a], colours[b]):.2f}"
        for a, b, need in NEEDS
        if contrast(colours[a], colours[b]) < need
    ]
    assert weak == []


@pytest.mark.parametrize(
    "read, words",
    [
        (
            "command('Write', dword=12)",
            'command <span class="what">Write</span>, cdw12',
        ),
        (
            "command('Format NVM', opcode=True)",
            'command <span class="what">Format NVM</span>, opcode',
        ),
        (
            "log_page('SMART / Health')",
            'log page <span class="what">SMART / Health</span>',
        ),
        ("help('')", "help"),
        ("nothing", "nothing"),
        ("command('<b>')", 'command <span class="what">&lt;b&gt;</span>'),
    ],
)
def test_said_describes_the_reading_in_words(read, words):
    assert web.said(read) == words


@pytest.mark.parametrize(
    "lookups, shown",
    [
        ("1 lookup", []),
        (
            "3 lookups, chosen by the language model",
            ["3 lookups, chosen by the language model"],
        ),
        ("1 lookup, chosen by the language model", ["chosen by the language model"]),
    ],
)
def test_the_status_tags_leave_out_a_single_lookup(lookups, shown):
    status = f"read as command('Ding') | {lookups} | 5.2 ms | cites 1 figure"
    tags = re.findall(r'<span class="tag">([^<]*)</span>', web.marked(status))

    assert tags == shown + ["cites 1 figure", "5.2 ms"]


class Started:
    def __init__(self, started):
        self.started = started


def test_open_when_started_opens_the_page(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    assert web.open_when_started(Started(True), "http://127.0.0.1:8000/")
    assert opened == ["http://127.0.0.1:8000/"]


def test_open_when_started_opens_nothing_when_the_server_does_not_start(
    monkeypatch,
):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    assert not web.open_when_started(Started(False), "http://x/", timeout=0.2)
    assert opened == []


def test_serve_listens_where_told_and_opens_the_page(monkeypatch):
    ran = []
    opened = []
    monkeypatch.setattr(
        uvicorn.Server,
        "run",
        lambda server: ran.append((server.config.host, server.config.port)),
    )
    monkeypatch.setattr(
        web, "open_when_started", lambda server, url: opened.append(url)
    )

    web.serve(senfd.query.load(SPEC), "127.0.0.1", 8123, browse=True)

    assert ran == [("127.0.0.1", 8123)]
    assert opened == ["http://127.0.0.1:8123/"]
