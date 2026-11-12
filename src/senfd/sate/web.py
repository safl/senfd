# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
sate-web: a web page that answers sate's questions

    sate-web
    sate-web --host 0.0.0.0 --port 8080

The page works without JavaScript. The question is a form field, and the
server renders the answer, so each question has its own URL. With
JavaScript, the page completes the question from /complete as it is typed,
and the line under the field lists the keys for the field, the completion
menu and the answer.

When the environment variable SATE_MCP_TOKEN is set, sate-web also serves
the tools of sate-mcp at /mcp, over MCP's streamable HTTP transport, to a
client that sends "Authorization: Bearer <token>".
"""

import argparse
import ast
import hmac
import html
import json
import os
import re
import sys
from urllib.parse import quote, quote_plus
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from markdown_it import MarkdownIt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

import senfd
import senfd.published
import senfd.query
from senfd.sate.answering import exchange
from senfd.sate.completion import completions
from senfd.sate.phrasing import FORMS
from senfd.sate.reading import understand
from senfd.sate.session import holds
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument

if TYPE_CHECKING:
    import uvicorn

# Each theme maps its name to its title and two strings of colours, the
# first for light mode and the second for dark mode. The colours are in the
# order of TOKENS: the page background, text, secondary text, lines, links,
# the background of the selected completion, the background of a note, and
# the label of a note. The page uses the first theme until the reader
# chooses another; the first is Gruvbox with mustard links, the palette of
# senfd. The colours start from each theme's published palette. Where a
# colour failed the WCAG contrast ratio for its use, its lightness
# was changed and its hue kept: 7:1 for text, 4.5:1 for secondary text,
# links and the note's label, and 3:1 for lines.
THEMES = {
    "gruvbox": (
        "Gruvbox",
        "#fbf1c7 #3c3836 #786b61 #a5874a #8c5b0f #f2e5bc #f2e5bc #af3a03",
        "#282828 #ebdbb2 #9a8c7e #7a706a #fabd2f #3c3836 #3c3836 #fe8019",
    ),
    "one": (
        "One",
        "#fafafa #383a42 #696c77 #909095 #2162f0 #f0f0f1 #f0f0f1 #916301",
        "#282c34 #b9bfca #8f949c #6a758b #61afef #2c313a #2c313a #e5c07b",
    ),
    "solarized": (
        "Solarized",
        "#fdf6e3 #3e4d52 #647476 #9d8d5c #1e6da5 #eee8d5 #eee8d5 #826200",
        "#002b36 #b8c1c1 #7b9199 #5d757c #2ca9a0 #073642 #073642 #c29300",
    ),
    "catppuccin": (
        "Catppuccin",
        "#eff1f5 #3a3c50 #6a6d82 #848ba1 #0d5af4 #ccd0da #e6e9ef #925d13",
        "#1e1e2e #cdd6f4 #82879e #656884 #89b4fa #313244 #313244 #f9e2af",
    ),
    "rose-pine": (
        "Ros\u00e9 Pine",
        "#faf4ed #4d496b #716d8c #9a8a87 #286983 #f2e9e1 #fffaf3 #a46611",
        "#191724 #e0def4 #908caa #666182 #9ccfd8 #26233a #1f1d2e #f6c177",
    ),
}
TOKENS = ("bg", "fg", "dim", "line", "accent", "chosen", "note", "warn")
MODES = ("light", "dark")


def colours(theme: str, dark: bool) -> str:
    """The CSS declarations that set the colour variables of 'theme', for
    dark mode where 'dark' is true"""

    _, light_values, dark_values = THEMES[theme]
    values = dark_values if dark else light_values
    declared = " ".join(
        f"--{token}: {value};" for token, value in zip(TOKENS, values.split())
    )
    return f"color-scheme: {'dark' if dark else 'light'}; {declared}"


def themed() -> str:
    """The CSS rules of every theme. The data-theme attribute of the html
    element selects the theme, and its data-mode attribute, light or dark,
    selects the mode. Without data-mode, the system's colour scheme decides
    the mode."""

    rules = []
    for name in THEMES:
        root = f':root[data-theme="{name}"]'
        rules += [
            f"{root} {{ {colours(name, False)} }}",
            "@media (prefers-color-scheme: dark) {",
            f'  {root}:not([data-mode="light"]) {{ {colours(name, True)} }}',
            "}",
            f'{root}[data-mode="dark"] {{ {colours(name, True)} }}',
        ]
    return "\n".join(rules)


def chooser() -> str:
    """The <option> elements of the theme selector"""

    return "\n".join(
        f'<option value="{name}">{html.escape(title)}</option>'
        for name, (title, *_) in THEMES.items()
    )


# The icon of each kind of completion and of each query that a question is
# read as, as the SVG path of a 24 by 24 drawing. The icons are SVG rather
# than emoji, because a system without an emoji font shows an emoji as a
# box.
QUESTION = (
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.4M12 17h.01"/>'
)
STRUCTURE = '<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M3 15h18M10 4v16"/>'
NUMBER = '<path d="M10 4L8 20M16 4l-2 16M4 9h16M4 15h16"/>'
MARKS = {
    "question": QUESTION,
    "help": QUESTION,
    "form": '<path d="M4 20h4L19 9l-4-4L4 16zM13 7l4 4"/>',  # A pencil
    "command": '<path d="M4 17l6-5-6-5M12 19h8"/>',  # A prompt
    "feature": '<rect x="2" y="7" width="20" height="10" rx="5"/><circle cx="16" cy="12" r="2.5"/>',
    "log page": '<path d="M6 2h9l5 5v15H6zM15 2v5h5M9 13h7M9 17h7"/>',  # A page
    "log_page": '<path d="M6 2h9l5 5v15H6zM15 2v5h5M9 13h7M9 17h7"/>',
    "structure": STRUCTURE,
    "register": STRUCTURE,
    "acronym": '<path d="M5 20l7-16 7 16M8 14h8"/>',  # A letter
    "name": '<path d="M5 20l7-16 7 16M8 14h8"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    "identifier": NUMBER,
    "value": NUMBER,
    "status": NUMBER,
    "section": '<path d="M2 5h6a4 4 0 0 1 4 4v11a3 3 0 0 0-3-3H2zM22 5h-6a4 4 0 0 0-4 4v11a3 3 0 0 1 3-3h7z"/>',
    "errata": '<path d="M12 3l10 18H2zM12 10v4M12 17h.01"/>',  # A warning
}  # fmt: skip


def mark(kind: str) -> str:
    """The SVG icon of 'kind', or "" where 'kind' has no icon"""

    drawn = MARKS.get(kind)
    if not drawn:
        return ""
    return f'<svg class="mark" viewBox="0 0 24 24" aria-hidden="true">{drawn}</svg>'


def said(read: str) -> str:
    """What a question was read as, given as 'read', such as
    "command('Write', dword=12)", in words as HTML, such as
    'command <span class="what">Write</span>, cdw12'. Where 'read' has
    another form, the escaped 'read'."""

    form = re.fullmatch(r"(\w+)\((.*)\)", read)
    if not form:
        return html.escape(read)
    try:
        call = ast.parse(f"f({form[2]})", mode="eval").body
        if not isinstance(call, ast.Call):
            return html.escape(read)
        named = [ast.literal_eval(arg) for arg in call.args]
        given = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    except (SyntaxError, ValueError):
        return html.escape(read)
    if len(named) != 1:
        return html.escape(read)
    kind = form[1].replace("_", " ")
    words = [
        f'{kind} <span class="what">{html.escape(str(named[0]))}</span>'
        if named[0]
        else kind
    ]
    if given.get("dword") is not None:
        words.append(f"cdw{given['dword']}")
    words += [word for word in ("opcode", "describe") if given.get(word)]
    return ", ".join(words)


def marked(status: str) -> str:
    """The status of an answer, 'status', as HTML tags. The first tag shows
    the icon of the query and, in words, what the question was read as, with
    'status' as its tooltip. The number of lookups gets a tag only when it
    is more than one or when a language model chose the lookup. The last
    two tags show what the answer cites and how long it took."""

    parts = status.split(" | ")
    read = re.fullmatch(r"read as (.*)", parts[0])
    if not read or len(parts) != 4:
        return f'<span class="tag">{html.escape(status)}</span>'
    query = re.match(r"(\w+)\(", read[1])
    lookups, took, found = parts[1:]
    tags = [
        f'<span class="tag" title="{html.escape(status, quote=True)}">'
        f"{mark(query[1]) if query else ''}{said(read[1])}</span>"
    ]
    count, _, chosen = lookups.partition(", ")
    shown = [lookups if count != "1 lookup" else chosen, found, took]
    tags += [f'<span class="tag">{html.escape(tag)}</span>' for tag in shown if tag]
    return "".join(tags)


# The text of a figure can contain HTML; with "html" off, markdown-it
# escapes it instead of rendering it
MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")


def rendered(markdown: str) -> str:
    """'markdown' rendered as HTML, with every link, such as a citation,
    opening in a new tab"""

    return MARKDOWN.render(markdown).replace(
        "<a href=", '<a target="_blank" rel="noopener" href='
    )


def not_known(question: str, vocabulary: Vocabulary, answer: str) -> str:
    """The note for a question that is not known: the reason, up to five
    questions it may have meant, each with a name from the data model in
    place of the name asked about, and a link to the question forms"""

    why = re.sub(r"\s*`sate help` says what can be asked\.", "", answer).strip()
    understood = understand(question, vocabulary)
    argument = understood.argument or question
    named = re.compile(re.escape(argument), re.I)

    def instead(name: str) -> str:
        """'question' with 'name' in place of the text it asked about"""

        if not named.search(question):
            return name
        return named.sub(lambda _: name, question, count=1)

    meant = [instead(name) for name in vocabulary.near(argument, understood.query)]
    links = ", ".join(
        f'<a href="?q={quote_plus(asked)}">{html.escape(asked)}</a>' for asked in meant
    )
    return (
        '<div class="note" role="note">'
        f"<p><strong>NOTE</strong> {html.escape(why)}</p>"
        + (f"<p>Did you mean {links}?</p>" if meant else "")
        + "<p>Name a command, a feature or a log page by its name or "
        "identifier, a structure, a register, or a field by its acronym. "
        '<a href="?q=help">The forms of a question</a> shows them all, with '
        "examples.</p></div>"
    )


def across(spec: SpecDocument) -> str:
    """The number of documents in 'spec', as a link that opens their table"""

    count = len(spec.documents)
    return (
        f'across <a class="documents" href="#documents">{count} '
        f"document{'' if count == 1 else 's'}</a>"
    )


def manifest(spec: SpecDocument) -> str:
    """The table of the documents in 'spec'. Each row gives the short name
    of a document that NVM Express publishes, or else its title, its file
    name, linked to the PDF where NVM Express publishes it, and the first 12
    characters of its SHA-256."""

    rows = []
    for name, meta in spec.documents.items():
        known = senfd.published.name_of(meta.sha256) or name
        url = senfd.published.url_of(meta.sha256)
        file = html.escape(meta.file or "")
        if url:
            file = f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{file}</a>'
        sha256 = meta.sha256 or ""
        digest = (
            f'<code title="{html.escape(sha256)}">{html.escape(sha256[:12])}</code>'
        )
        rows.append(
            (
                known.lower(),
                f"<tr><td>{html.escape(known)}</td><td>{file}</td><td>{digest}</td></tr>",
            )
        )
    body = "\n".join(row for _, row in sorted(rows))
    return (
        "<p><strong>The documents the data model is made from.</strong> Every "
        "answer cites one of them; where NVM Express publishes it, the file "
        "links to the PDF.</p>\n"
        "<table><thead><tr><th>Document</th><th>File</th><th>SHA-256</th></tr>"
        f"</thead><tbody>\n{body}\n</tbody></table>"
    )


def page(
    spec: SpecDocument,
    vocabulary: Vocabulary,
    question: str,
    answer: str,
    status: str,
) -> str:
    """The HTML page with 'question' in the input field and its answer
    below. The question forms are in a dialog that the ? button opens."""

    body = ""
    if question.strip():
        said = (
            not_known(question, vocabulary, answer)
            if status.endswith("| not known")
            else rendered(answer)
        )
        body = f'<p class="status">{marked(status)}</p>{said}'

    return PAGE.format(
        version=html.escape(senfd.__version__),
        logo=LOGO,
        favicon=quote(LOGO),
        question=html.escape(question, quote=True),
        # An answer page leaves the input field unfocused, so the arrow and
        # page keys scroll the answer; the start page focuses the field
        focus="" if question else "autofocus ",
        holds=html.escape(holds(vocabulary)),
        across=across(spec),
        manifest=manifest(spec),
        body=body,
        forms=rendered(FORMS),
        themes=themed(),
        chooser=chooser(),
        known=json.dumps(list(THEMES)),
        modes=json.dumps(list(MODES)),
        theme=next(iter(THEMES)),
        marks=json.dumps({kind: mark(kind) for kind in MARKS}),
    )


class Bearer:
    """An ASGI wrapper that passes a request to 'app' only when the request
    sends "Authorization: Bearer <token>", and answers 401 otherwise"""

    def __init__(self, app: ASGIApp, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        given = dict(scope["headers"]).get(b"authorization", b"")
        if hmac.compare_digest(given, self.expected):
            await self.app(scope, receive, send)
            return
        refused = PlainTextResponse(
            "A bearer token is needed", 401, headers={"WWW-Authenticate": "Bearer"}
        )
        await refused(scope, receive, send)


def app(spec: SpecDocument, mcp_token: Optional[str] = None) -> Starlette:
    """The Starlette application that answers from 'spec'. With
    'mcp_token', it also serves the tools of sate-mcp at /mcp to requests
    that send the token."""

    vocabulary = Vocabulary.of(spec)
    _ = vocabulary.names  # Compile the pattern of names before the first request

    async def index(request: Request) -> HTMLResponse:
        question = request.query_params.get("q", "")
        answer, status = "", ""
        if question.strip():
            try:
                answer, status = exchange(spec, question, vocabulary, said_as=False)
            except Exception as exc:  # Report a failed lookup on the page
                answer, status = "", f"sate failed to answer: {exc}"
        return HTMLResponse(page(spec, vocabulary, question, answer, status))

    async def complete(request: Request) -> JSONResponse:
        typed = request.query_params.get("q", "")
        return JSONResponse(
            {
                "offers": [offer._asdict() for offer in completions(vocabulary, typed)],
            }
        )

    routes = [Route("/", index), Route("/complete", complete)]
    if not mcp_token:
        return Starlette(routes=routes)

    from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
    from mcp.server.transport_security import TransportSecuritySettings

    from senfd.sate import mcp

    mcp.answer_from(spec)
    # With stateless_http, the server keeps no session, so a client keeps
    # working after the server restarts. MCP's check of the Host header
    # accepts only local host names, and a reverse proxy forwards the public
    # host name, so the check is off and the token protects /mcp.
    mcp.server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    manager = mcp.server.session_manager
    routes.append(Route("/mcp", Bearer(StreamableHTTPASGIApp(manager), mcp_token)))
    return Starlette(routes=routes, lifespan=lambda _: manager.run())


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask the data model questions on a web page, answered as by sate"
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=f"The merged data model (default: {senfd.query.default_spec_path()})",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listen on this address (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Listen on this port (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        spec = senfd.query.load(args.spec)
    except OSError as exc:
        print(f"sate-web: no data model to answer from: {exc}", file=sys.stderr)
        return 1

    serve(spec, args.host, args.port)
    return 0


def open_when_started(server: "uvicorn.Server", url: str, timeout: float = 30) -> bool:
    """Open 'url' in the default browser once 'server', a uvicorn.Server,
    listens. Returns False when the server has not started within 'timeout'
    seconds, and then opens nothing."""

    import time
    import webbrowser

    waited = 0.0
    while not server.started:
        if waited >= timeout:
            return False
        time.sleep(0.1)
        waited += 0.1
    webbrowser.open(url)
    return True


def serve(spec: SpecDocument, host: str, port: int, browse: bool = False) -> None:
    """Serve sate-web answering from 'spec' on 'host' and 'port' until the
    process is stopped. With 'browse', open the page in the default browser
    once the server listens."""

    import threading

    import uvicorn

    config = uvicorn.Config(
        app(spec, os.environ.get("SATE_MCP_TOKEN")), host=host, port=port
    )
    server = uvicorn.Server(config)
    if browse:
        threading.Thread(
            target=open_when_started,
            args=(server, f"http://{host}:{port}/"),
            daemon=True,
        ).start()
    server.run()


# The small logo of senfd, a flower of four mustard petals, drawn in the
# title button and given as the favicon. Its details are dark for a light
# background; the title button, which is always dark, lightens them.
LOGO = (
    '<svg class="logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"'
    ' aria-hidden="true"><g fill="#D79921" stroke="#282828" stroke-width="1.65">'
    '<rect x="3.6" y="3.6" width="11.5" height="11.5" rx="3.3"/>'
    '<rect x="16.9" y="3.6" width="11.5" height="11.5" rx="3.3"/>'
    '<rect x="3.6" y="16.9" width="11.5" height="11.5" rx="3.3"/>'
    '<rect x="16.9" y="16.9" width="11.5" height="11.5" rx="3.3"/></g>'
    '<circle cx="16" cy="16" r="3.25" fill="#282828"/></svg>'
)

PAGE = """<!doctype html>
<html lang="en" data-theme="{theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>sate</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon}">
<script>
// Apply the stored theme and mode before the page is drawn, so the page
// does not flash in the first theme's colours
try {{
  const theme = localStorage.getItem("theme");
  if ({known}.includes(theme)) document.documentElement.dataset.theme = theme;
  const mode = localStorage.getItem("mode");
  if ({modes}.includes(mode)) document.documentElement.dataset.mode = mode;
}} catch (error) {{}}
</script>
<style>
{themes}
[hidden] {{ display: none !important; }}
* {{ box-sizing: border-box; }}
/* Set on html, so every rem size scales with it, and in percent, so it
   scales with the font size set in the browser */
html {{ font-size: 125%; }}
/* The header, the page and the footer in a column. min-height puts the
   footer at the bottom of the window when the page is shorter than it */
body {{
  margin: 0; background: var(--bg); color: var(--fg);
  font: 1rem/1.5 system-ui, sans-serif;
  display: flex; flex-direction: column; min-height: 100vh;
}}
.page {{ flex: 1; width: 100%; padding: 1.25rem 1.5rem 1rem; }}
/* Limit the width of the page's children rather than of the page, so the
   sticky question form spans the window like the header and the footer.
   :where() gives the rule no specificity, so a child's own max-width wins */
:where(.page > *, form.ask > *) {{ max-width: 87rem; }}
/* Limit a note to 75 characters per line; tables use the full width */
.note {{ max-width: 75ch; }}
/* The header spans the window with a muted background, so it reads as a
   navigation bar and draws less attention than the input field */
header {{
  display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
  padding: 0.5rem 1.5rem; background: var(--chosen);
  border-bottom: 1px solid var(--line);
}}
header h1 {{
  margin: 0; font-size: 1.1rem; flex: 1;
  display: flex; gap: 0.6rem; align-items: center;
}}
header h1 a {{ color: inherit; text-decoration: none; }}
/* The title button looks the same in every theme and mode: the logo's
   dark variant, mustard on Gruvbox's dark background */
header h1 a.home {{
  display: inline-flex; gap: 0.5rem; align-items: center;
  padding: 0.2rem 0.65rem 0.2rem 0.4rem; border: 1px solid #7a706a;
  border-radius: 6px; background: #282828;
}}
header h1 a.home:hover, header h1 a.home:focus-visible {{ border-color: #fabd2f; }}
header h1 .logo {{ width: 1.6rem; height: 1.6rem; }}
header h1 .logo g {{ stroke: none; }}
header h1 .logo circle {{ fill: #ebdbb2; }}
/* As tall as the logo. The letters have no descenders, so they sit low in
   their line; lifting them centres them on the logo */
header h1 .name {{
  color: #D79921; font-size: 1.75rem; line-height: 1; letter-spacing: 0.01em;
  position: relative; top: -0.09em;
}}
header h1 .version {{ color: var(--dim); font-size: 0.75rem; font-weight: normal; }}
header nav {{ display: flex; gap: 0.5rem; flex-wrap: wrap; font-size: 0.85rem; }}
header nav a, header nav label, header nav button {{
  display: inline-flex; gap: 0.4rem; align-items: center;
  padding: 0.2rem 0.65rem; border: 1px solid var(--line); border-radius: 6px;
  font: inherit; color: var(--fg); background: var(--bg);
  text-decoration: none; cursor: pointer;
}}
header nav a:hover, header nav label:hover, header nav button:hover,
header nav a:focus-visible, header nav button:focus-visible,
header nav label:focus-within {{ border-color: var(--accent); }}
header nav select {{
  font: inherit; color: var(--fg); background: var(--bg);
  border: none; padding: 0; cursor: pointer;
}}
header nav svg {{
  color: var(--accent); width: 1rem; height: 1rem; fill: none; stroke: currentColor;
  stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
}}
.holds {{ color: var(--dim); font-size: 0.95rem; }}
/* The status of an answer: small tags in the secondary text colour */
.status {{
  display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.75rem 0;
  color: var(--dim); font-size: 0.8rem;
}}
.status .tag {{
  display: inline-flex; align-items: center; padding: 0 0.55rem;
  border: 1px solid var(--line); border-radius: 999px;
}}
.status .what {{ color: var(--fg); margin-left: 0.25em; }}
.status svg.mark {{ margin-right: 0.35em; }}
form {{ position: relative; margin: 0; }}
/* The question form sticks to the top of the window while the answer
   scrolls under it. The script adds .stuck, which draws a line under the
   form, once the page is scrolled */
form.ask {{
  max-width: none; position: sticky; top: 0; z-index: 2; background: var(--bg);
  margin: 0 -1.5rem; padding: 0.5rem 1.5rem;
}}
form.ask.stuck {{ border-bottom: 1px solid var(--line); }}
.field {{ display: flex; gap: 0.5rem; }}
input {{
  flex: 1; min-width: 0; padding: 0.6rem 0.75rem; font: inherit;
  font-family: ui-monospace, monospace;
  color: var(--fg); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px;
}}
input:focus {{ outline: 2px solid var(--accent); outline-offset: -1px; }}
.help {{
  flex: none; width: 2.6rem; display: grid; place-items: center;
  border: 1px solid var(--line); border-radius: 6px;
  color: var(--accent); font-weight: bold; text-decoration: none;
}}
.help:hover, .help:focus {{ border-color: var(--accent); }}
.holds {{ margin: 1rem 0 0.25rem; }}
a.documents {{ color: inherit; text-decoration: underline dotted; }}
.keys {{ margin: 0.25rem 0 1rem; color: var(--dim); font-size: 0.9rem; }}
kbd {{
  font-family: ui-monospace, monospace; font-size: 0.9em;
  border: 1px solid var(--line); border-radius: 3px; padding: 0 0.25em;
}}
dialog {{
  max-width: min(48rem, calc(100vw - 2rem)); max-height: calc(100vh - 4rem);
  overflow: auto; padding: 1rem 1.25rem;
  background: var(--bg); color: var(--fg);
  border: 1px solid var(--line); border-radius: 8px;
}}
dialog#documents {{ max-width: min(76rem, calc(100vw - 2rem)); }}
dialog::backdrop {{ background: rgb(0 0 0 / 0.4); }}
dialog form {{ margin: 0; text-align: right; }}
dialog button {{
  font: inherit; font-size: 0.95rem; color: var(--fg); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px; padding: 0.2rem 0.6rem;
  cursor: pointer;
}}
ul.menu {{
  position: absolute; z-index: 1; left: 1.5rem; right: 1.5rem; margin: 2px 0 0;
  max-width: 87rem;
  padding: 0; list-style: none; max-height: 20rem; overflow-y: auto;
  background: var(--bg); border: 1px solid var(--line); border-radius: 6px;
}}
ul.menu li {{
  display: flex; justify-content: space-between; gap: 1rem;
  padding: 0.3rem 0.75rem; cursor: pointer;
  font-family: ui-monospace, monospace; font-size: 0.95rem;
}}
ul.menu li .kind {{ color: var(--dim); }}
ul.menu li .swap {{ font-weight: 700; }}
svg.mark {{
  width: 1em; height: 1em; margin-right: 0.5em; vertical-align: -0.15em;
  fill: none; stroke: var(--accent); stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
}}
/* The selected completion gets a frame in the link colour, which has at
   least 4.5:1 contrast with the page in every theme. A tinted background
   strong enough to see would lower the contrast of the text */
ul.menu li.chosen {{
  background: var(--chosen);
  box-shadow: inset 4px 0 0 var(--accent), inset 0 0 0 1px var(--accent);
}}
ul.menu li.chosen .kind {{ color: var(--fg); }}
main {{ overflow-x: auto; }}
a {{ color: var(--accent); }}
code {{ font-family: ui-monospace, monospace; font-size: 0.9em; }}
table {{ border-collapse: collapse; margin: 0.5rem 0 1rem; font-size: 0.95rem; }}
th, td {{
  border: 1px solid var(--line); padding: 0.25rem 0.5rem;
  text-align: left; vertical-align: top;
}}
h3 {{ font-size: 1.15rem; }}
.note {{
  margin: 0.5rem 0 1rem; padding: 0.5rem 1rem;
  background: var(--note); border-left: 4px solid var(--warn); border-radius: 4px;
}}
.note p {{ margin: 0.4rem 0; }}
.note strong {{ color: var(--warn); letter-spacing: 0.05em; margin-right: 0.4rem; }}
blockquote {{ margin: 0; padding-left: 0.75rem; border-left: 3px solid var(--line); }}
/* Small secondary text, so the footer draws less attention than the field */
footer {{
  padding: 0.4rem 1.5rem; border-top: 1px solid var(--line);
  color: var(--dim); font-size: 0.75rem; line-height: 1.4;
}}
footer p {{ margin: 0; }}
</style>
</head>
<body>
<header>
<h1><a class="home" href=".">{logo}<span class="name">sate</span></a><span class="version">v{version}</span></h1>
<nav>
<a href="https://safl.dk/senfd/" target="_blank" rel="noopener"
 title="The documentation of senfd and sate"><svg viewBox="0 0 24 24"
 aria-hidden="true"><path d="M2 5h6a4 4 0 0 1 4 4v11a3 3 0 0 0-3-3H2z"/><path
 d="M22 5h-6a4 4 0 0 0-4 4v11a3 3 0 0 1 3-3h7z"/></svg>Documentation</a>
<a href="https://github.com/safl/senfd" target="_blank" rel="noopener"
 title="The source of senfd and sate, on GitHub"><svg viewBox="0 0 24 24"
 aria-hidden="true"><path d="M8 6l-6 6 6 6M16 6l6 6-6 6M14 4l-4 16"/></svg>Source</a>
<label id="theme" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path
 d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-.9-.7-1.2-.7-2 0-.8.6-1.5
 1.5-1.5H17a4 4 0 0 0 4-4c0-5-4-9-9-9z"/><circle cx="7.5" cy="11" r="1"/><circle
 cx="10.5" cy="7" r="1"/><circle cx="15" cy="8" r="1"/></svg><select
 aria-label="Theme" title="The theme">
{chooser}
</select></label>
<button id="mode" type="button" hidden><svg viewBox="0 0 24 24"
 aria-hidden="true"><circle cx="12" cy="12" r="9"/><path
 d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg><span>Auto</span></button>
</nav>
</header>
<div class="page">
<p class="holds">Ask about any of {holds}, {across}</p>
<form class="ask" method="get" action="." autocomplete="off">
<div class="field">
<input id="q" name="q" value="{question}" placeholder="Ask, as: cdw12 of write"
 {focus}spellcheck="false" autocapitalize="off" aria-label="Question">
<a class="help" id="help" href="?q=help" title="The forms of a question (F1)"
 aria-label="The forms of a question">?</a>
</div>
<ul class="menu" id="menu" hidden></ul>
</form>
<p class="keys"><kbd>Ctrl</kbd>+<kbd>I</kbd> goes to the field and <kbd>Esc</kbd>
leaves it, <kbd>Tab</kbd>
completes a name or an acronym, <kbd>?</kbd> in an empty field shows the
questions to ask, and <kbd>F1</kbd> or the <kbd>?</kbd> beside the field the
forms of a question.</p>
<dialog id="forms">
<form method="dialog"><button>Close</button></form>
{forms}
</dialog>
<dialog id="documents">
<form method="dialog"><button>Close</button></form>
{manifest}
</dialog>
<main>{body}</main>
</div>
<footer><p>
Not endorsed by NVM Express. What sate says can be wrong: every answer
consults a data model constructed from reading specification documents, and
errors in that process are possible. Thus, always check the citation that
sate gives you. It will point you to where sate got its answer from.
</p></footer>
<script>
const input = document.getElementById("q");
const menu = document.getElementById("menu");
const forms = document.getElementById("forms");
const MARKS = {marks};
const root = document.documentElement;
const chooser = document.getElementById("theme");
const choice = chooser.querySelector("select");
const toggle = document.getElementById("mode");
let offers = [], chosen = -1, asked = 0, pointer = "";

function typed() {{ return input.value.slice(0, input.selectionStart); }}

// Fetch the completions of the text before the cursor, and show them
async function update() {{
  const number = ++asked;
  const response = await fetch("complete?q=" + encodeURIComponent(typed()));
  if (!response.ok || number !== asked) return;
  const found = await response.json();
  offers = found.offers;
  chosen = -1;
  show();
}}

function show() {{
  menu.replaceChildren(...offers.map((offer, at) => {{
    const item = document.createElement("li");
    const shown = document.createElement("span");
    const kind = document.createElement("span");
    shown.innerHTML = MARKS[offer.kind] || "";  // SVG from MARKS, not user text
    // A question's names are marked, as the ones to swap for one's own
    for (const [text, kind] of offer.parts.length ? offer.parts : [[offer.shown, ""]]) {{
      if (!kind) {{ shown.append(text); continue; }}
      const name = document.createElement("b");
      name.className = "swap";
      name.textContent = text;
      shown.append(name);
    }}
    kind.textContent = offer.kind;
    kind.className = "kind";
    item.append(shown, kind);
    item.addEventListener("mousemove", (event) => {{
      const here = [event.screenX, event.screenY].join();
      if (here === pointer) return;  // The menu was redrawn, the mouse did not move
      pointer = here;
      chosen = at;
      highlight(false);
    }});
    item.addEventListener("mousedown", (event) => {{
      event.preventDefault();
      choose(offer);
    }});
    return item;
  }}));
  menu.hidden = offers.length === 0;
  highlight(true);
}}

// Mark the selected completion. 'scroll' is true for the arrow keys, which
// scroll it into view, and false for the mouse, which is already on it
function highlight(scroll) {{
  [...menu.children].forEach((item, at) => item.classList.toggle("chosen", at === chosen));
  if (scroll && chosen >= 0) menu.children[chosen].scrollIntoView({{ block: "nearest" }});
}}

// Put the completion in the field and close the menu at once, so a second
// Enter or Tab before the new completions arrive cannot insert it twice
function take(offer) {{
  const before = typed();
  const kept = before.slice(0, before.length + offer.start) + offer.text;
  input.value = kept + input.value.slice(input.selectionStart);
  input.setSelectionRange(kept.length, kept.length);
  input.focus();
  close();
}}

// Enter or a click inserts the completion and submits the question, except
// for a question form, whose <placeholders> still need filling
function choose(offer) {{
  take(offer);
  if (offer.kind === "question") update();
  else input.form.requestSubmit();
}}

// When the pointer leaves the menu, clear the selection, so Enter submits
// the text as typed
menu.addEventListener("mouseleave", () => {{
  chosen = -1;
  pointer = "";
  highlight(false);
}});

function close() {{ offers = []; chosen = -1; show(); }}

// The theme and the mode (auto, light or dark), stored in localStorage
function remember(key, value) {{
  try {{
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  }} catch (error) {{}}
}}

choice.value = root.dataset.theme;
choice.addEventListener("change", () => {{
  root.dataset.theme = choice.value;
  remember("theme", choice.value);
}});

function mode() {{ return root.dataset.mode || "auto"; }}

function labelled() {{
  const now = mode();
  toggle.querySelector("span").textContent = now[0].toUpperCase() + now.slice(1);
  toggle.title = `Mode: ${{now}}; click for the next`;
}}

toggle.addEventListener("click", () => {{
  const modes = ["auto", ...{modes}];
  const next = modes[(modes.indexOf(mode()) + 1) % modes.length];
  if (next === "auto") delete root.dataset.mode;
  else root.dataset.mode = next;
  remember("mode", next === "auto" ? null : next);
  labelled();
}});
labelled();
chooser.hidden = toggle.hidden = false;  // They stay hidden without JavaScript

// Open 'dialog', or close it if it is open
function shown(dialog) {{
  if (dialog.open) dialog.close();
  else dialog.showModal();
}}

// F1 and the ? button beside the field open or close the question forms
function help() {{ shown(forms); }}

const documents = document.getElementById("documents");
document.querySelector("a.documents").addEventListener("click", (event) => {{
  event.preventDefault();
  shown(documents);
}});

for (const link of document.querySelectorAll('a[href="?q=help"]')) {{
  link.addEventListener("click", (event) => {{
    event.preventDefault();
    help();
  }});
}}
document.addEventListener("keydown", (event) => {{
  if (event.key !== "F1") return;
  event.preventDefault();
  help();
}});

// Ctrl+I focuses the input field and selects its text, so typing replaces
// the question
document.addEventListener("keydown", (event) => {{
  if (!event.ctrlKey || event.key.toLowerCase() !== "i") return;
  event.preventDefault();
  if (forms.open) forms.close();
  if (documents.open) documents.close();
  input.focus();
  input.select();
}});

// A printable key pressed outside the field focuses the field and selects
// its text, so the key starts a new question
document.addEventListener("keydown", (event) => {{
  const typing = event.key.length === 1 && event.key !== " ";
  if (!typing || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest("input, select, button, dialog")) return;
  input.focus();
  input.select();
}});

// Add .stuck to the question form, which draws a line under it, once the
// line above the form has scrolled out of view
const ask = document.querySelector("form.ask");
new IntersectionObserver(([above]) => {{
  ask.classList.toggle("stuck", !above.isIntersecting);
}}).observe(document.querySelector(".holds"));
for (const dialog of [forms, documents]) {{
  dialog.addEventListener("click", (event) => {{
    if (event.target === dialog) dialog.close();  // A click on the backdrop
  }});
}}

// With the menu closed, the arrow keys and Page Up and Page Down scroll the
// page even when the input field has focus. An arrow key scrolls 40 pixels;
// a page key scrolls the window height less the question form and 40 pixels
const LINE = 40;
function page() {{ return window.innerHeight - ask.offsetHeight - LINE; }}
function scroll(by) {{ window.scrollBy({{ top: by }}); }}

// Typing opens the menu, and emptying the field closes it
input.addEventListener("input", () => (input.value ? update() : close()));
input.addEventListener("blur", close);
input.addEventListener("keydown", (event) => {{
  if (event.key === "?" && !input.value) {{
    update();
    event.preventDefault();
    return;
  }}
  if (event.key === "PageDown" || event.key === "PageUp") {{
    close();
    scroll(event.key === "PageDown" ? page() : -page());
    event.preventDefault();
    return;
  }}
  if (menu.hidden) {{
    if (event.key === "Tab" && !event.shiftKey) update();
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") {{
      scroll(event.key === "ArrowDown" ? LINE : -LINE);
    }} else if (event.key === "Escape") input.blur();
    else return;
    event.preventDefault();
    return;
  }}
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {{
    const step = event.key === "ArrowDown" ? 1 : -1;
    chosen = (chosen + step + offers.length) % offers.length;
    highlight(true);
  }} else if (event.key === "Tab") {{
    take(offers[Math.max(chosen, 0)]);
    update();
  }} else if (event.key === "Enter" && chosen >= 0) {{
    choose(offers[chosen]);
  }} else if (event.key === "Escape") {{
    close();
  }} else {{
    return;
  }}
  event.preventDefault();
}});
</script>
</body>
</html>
"""
