# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""The interactive session, made for someone who does not yet know how to ask.

It opens with the questions it answers in a menu; completes each part of a
question by the kind of name that comes next; colours the words, names and
acronyms it recognises; and says at the bottom how the question is read so
far, above the keys. Under each answer, a line says how it was found.

prompt_toolkit draws the prompt, and rich the answers.
"""

import os
import re
from pathlib import Path
from typing import Callable, Iterator, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, completion_is_selected, has_completions
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import FileHistory, History, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.text import Text

import senfd
import senfd.query
from senfd.sate.answering import exchange
from senfd.sate.completion import completions, recognised, wanted
from senfd.sate.phrasing import HELP
from senfd.sate.reading import understand
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument

STYLE = Style.from_dict(
    {
        "word": "ansicyan",
        "name": "bold ansigreen",
        "acronym": "bold ansiyellow",
        "bottom-toolbar": "noreverse bg:ansiblack ansiwhite",
        "bottom-toolbar.reading": "bold",
        "bottom-toolbar.keys": "ansibrightblack",
    }
)


class Names(Completer):
    """Completes a question by what the data model names"""

    def __init__(self, vocabulary: Vocabulary):
        self.vocabulary = vocabulary

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        for offer in completions(self.vocabulary, document.text_before_cursor):
            yield Completion(
                offer.text, offer.start, display=offer.shown, display_meta=offer.kind
            )


class Recognised(Lexer):
    """Colours the words of questions, names and acronyms of a question"""

    def __init__(self, vocabulary: Vocabulary):
        self.vocabulary = vocabulary

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:
        def line(number: int) -> StyleAndTextTuples:
            text = document.lines[number]
            fragments: StyleAndTextTuples = []
            at = 0
            for span in recognised(self.vocabulary, text):
                fragments.append(("", text[at : span.start]))
                fragments.append((f"class:{span.kind}", text[span.start : span.end]))
                at = span.end
            fragments.append(("", text[at:]))
            return fragments

        return line


def holds(vocabulary: Vocabulary) -> str:
    """What the data model holds, as counted for a person"""

    return (
        f"{len(vocabulary.commands)} commands, {len(vocabulary.features)} "
        f"features, {len(vocabulary.log_pages)} log pages, "
        f"{len(vocabulary.structures)} structures"
    )


def reading_so_far(text: str, vocabulary: Vocabulary, llm: Optional[str] = None) -> str:
    """How the question typed so far is read, or what comes next in it, as a
    dword number after "cdw" or the acronyms of what is asked of after "is";
    before a question is begun, what can be asked of"""

    if not text.strip():
        return f" Ask of {holds(vocabulary)}"
    if re.search(r"\bcdw$", text, re.I):
        return " Next, the number of a dword, as cdw12: then of and a command"
    after = text if text.endswith(" ") else text + " "
    kind = wanted(after, vocabulary)
    if kind == "acronym":
        understood = understand(after, vocabulary)
        dword = f"cdw{understood.dword} of " if understood.dword is not None else ""
        return f" Next, a field of {dword}{understood.argument}: Tab lists them"
    if kind:
        article = "an" if kind[0] in "aeiou" else "a"
        return f" Next, {article} {kind}: Tab lists them"
    understood = understand(text, vocabulary)
    if llm:
        return (
            f" By its words, read as {understood}; the language model reads it at Enter"
        )
    return f" Read as {understood}"


def keys(text: str, menu: bool, llm: Optional[str] = None) -> str:
    """The keys that do something now: in the menu, choosing; on an empty
    line, finding a question; else, completing and asking"""

    if menu:
        line = " Tab, Up, Down choose | Enter take it | Esc close"
    elif not text:
        line = " ? questions | Up, Down history | F1 forms | Ctrl-D leave"
    else:
        line = " Tab complete | Enter ask | F1 forms | Ctrl-D leave"
    return line + (f" | --llm {llm}" if llm else "")


def toolbar(
    text: str, vocabulary: Vocabulary, llm: Optional[str] = None, menu: bool = False
) -> StyleAndTextTuples:
    """The two lines at the bottom of the session: how the question typed so
    far is read, and the keys that do something now"""

    return [
        ("class:bottom-toolbar.reading", reading_so_far(text, vocabulary, llm)),
        ("", "\n"),
        ("class:bottom-toolbar.keys", keys(text, menu, llm)),
    ]


def history() -> History:
    """The questions asked before, kept under $XDG_CACHE_HOME/senfd, by
    default ~/.cache/senfd, or in memory where that cannot be written"""

    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    try:
        (cache / "senfd").mkdir(parents=True, exist_ok=True)
        return FileHistory(str(cache / "senfd" / "ask-history"))
    except OSError:
        return InMemoryHistory()


def take_completion(event: KeyPressEvent) -> None:
    """Enter in the menu: take what is chosen and close the menu, rather than
    ask the question, which is often only begun, as "which bit of cdw" """

    event.current_buffer.complete_state = None


def status_of(status: str) -> Text:
    """The line under an answer: what it was read as, then how it was found,
    and whether it is known"""

    read, *rest = status.split(" | ")
    line = Text(read, style="cyan")
    for part in rest:
        line.append(" | ", style="dim")
        line.append(part, style="yellow" if part == "not known" else "dim green")
    return line


def said(markdown: str) -> str:
    """The lines ending an answer that say where the fields asked of are"""

    lines = markdown.rstrip("\n").split("\n")
    end = len(lines)
    while end and lines[end - 1].startswith(">"):
        end -= 1
    return "\n".join(lines[end:])


def height_of(console: Console, answer: Markdown) -> int:
    """The lines 'answer' takes on 'console', rendered at its width: a table
    of few rows wraps to many lines"""

    return len(console.render_lines(answer, console.options, pad=False))


def show(console: Console, question: str, markdown: str, status: str) -> None:
    """An answer, opened by a rule naming the question, so that where each
    answer starts stands out when scrolling back; paged from its top where it
    stands taller than the terminal, its citations still links, and left on
    the screen when the pager is quit, with where the fields asked of are and
    the line under it shown after the pager too"""

    console.rule(f"[bold]{escape(question.strip())}[/bold]", align="left")
    answer = Markdown(markdown)
    if height_of(console, answer) + 4 > console.size.height:
        # Colour, stay on the screen when quit, and no pager for one screen
        os.environ.setdefault("LESS", "-RFX")
        with console.pager(styles=True, links=True):
            console.print(answer)
        if said(markdown):
            console.print(Markdown(said(markdown)))
    else:
        console.print(answer)
    console.print(status_of(status))


def interact(
    spec: SpecDocument, llm: Optional[str] = None, source: Optional[Path] = None
) -> int:
    """Ask questions of 'spec', each answered as it is asked, until the input
    ends; 'source' is the file it was read from, shown at the start"""

    vocabulary = Vocabulary.of(spec)
    console = Console()
    console.print(f"[bold]sate {senfd.__version__}[/bold]  {holds(vocabulary)}")
    shown = str(source or senfd.query.default_spec_path())
    console.print(f"[dim]{shown.replace(str(Path.home()), '~', 1)}[/dim]")
    console.print(Markdown(HELP))

    bindings = KeyBindings()
    menu = has_completions & completion_is_selected
    bindings.add("enter", filter=menu)(take_completion)

    @bindings.add("escape", filter=has_completions)
    def close(event: KeyPressEvent) -> None:
        """Esc: close the menu"""
        event.current_buffer.cancel_completion()

    @bindings.add("?", filter=Condition(lambda: not session.default_buffer.text))
    def questions(event: KeyPressEvent) -> None:
        """'?' on an empty line: the menu of the questions to ask"""
        event.current_buffer.start_completion(select_first=False)

    @bindings.add("f1")
    def forms(event: KeyPressEvent) -> None:
        """F1: the forms a question can take, with examples"""
        run_in_terminal(lambda: console.print(Markdown(HELP)))

    _ = vocabulary.names  # The pattern of names, built before the first key
    session: PromptSession[str] = PromptSession(
        completer=Names(vocabulary),
        complete_while_typing=True,
        history=history(),
        lexer=Recognised(vocabulary),
        key_bindings=bindings,
        style=STYLE,
        bottom_toolbar=lambda: toolbar(
            session.default_buffer.text,
            vocabulary,
            llm,
            session.default_buffer.complete_state is not None,
        ),
    )
    opening = True  # The first prompt opens with the menu of questions
    while True:
        try:
            question = session.prompt(
                "sate> ",
                pre_run=session.default_buffer.start_completion if opening else None,
            )
        except (EOFError, KeyboardInterrupt):
            return 0
        opening = False
        if not question.strip():
            continue
        try:
            markdown, status = exchange(spec, question, vocabulary, llm, said_as=False)
        except Exception as exc:  # A lookup failing ends the answer, not the session
            console.print(f"[red]sate failed to answer:[/red] {exc}", highlight=False)
            continue
        show(console, question, markdown, status)
