# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""The interactive session, made for someone who does not yet know how to ask.

It opens with the questions it answers in a menu; completes each part of a
question by the kind of name that comes next; colours the words, names and
acronyms it recognises; and says at the bottom how the question is read so
far, above the keys. Under each answer, a line says how it was found.

Of the extra 'ask': prompt_toolkit for the prompt, rich for the answers.
"""

import os
from pathlib import Path
from typing import Callable, Iterator, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import FileHistory, History, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown

import senfd
import senfd.query
from senfd.ask.answering import exchange
from senfd.ask.completion import completions, recognised, wanted
from senfd.ask.phrasing import HELP
from senfd.ask.reading import understand
from senfd.ask.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument

KEYS = " Tab complete | ? questions | Up, Down history | F1 forms | Ctrl-D leave"

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
    """How the question typed so far is read, what kind of name comes next in
    it, or, before one is begun, what can be asked of"""

    if not text.strip():
        return f" Ask of {holds(vocabulary)}"
    kind = wanted(text if text.endswith(" ") else text + " ")
    if kind:
        article = "an" if kind[0] in "aeiou" else "a"
        return f" Next, {article} {kind}: Tab lists them"
    understood = understand(text, vocabulary)
    if llm:
        return (
            f" By its words, read as {understood}; the language model reads it at Enter"
        )
    return f" Read as {understood}"


def toolbar(
    text: str, vocabulary: Vocabulary, llm: Optional[str] = None
) -> StyleAndTextTuples:
    """The two lines at the bottom of the session: how the question typed so
    far is read, and the keys"""

    return [
        ("class:bottom-toolbar.reading", reading_so_far(text, vocabulary, llm)),
        ("", "\n"),
        ("class:bottom-toolbar.keys", KEYS + (f" | --llm {llm}" if llm else "")),
    ]


def history() -> History:
    """The questions asked before, kept in the cache beside the data model;
    in memory only where that cannot be written"""

    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    try:
        (cache / "senfd").mkdir(parents=True, exist_ok=True)
        return FileHistory(str(cache / "senfd" / "ask-history"))
    except OSError:
        return InMemoryHistory()


def interact(
    spec: SpecDocument, llm: Optional[str] = None, source: Optional[Path] = None
) -> int:
    """Ask questions of 'spec', each answered as it is asked, until the input
    ends; 'source' is the file it was read from, shown at the start"""

    vocabulary = Vocabulary.of(spec)
    console = Console()
    console.print(f"[bold]senfd-ask {senfd.__version__}[/bold]  {holds(vocabulary)}")
    shown = str(source or senfd.query.default_spec_path())
    console.print(f"[dim]{shown.replace(str(Path.home()), '~', 1)}[/dim]")
    console.print(Markdown(HELP))

    keys = KeyBindings()

    @keys.add("?", filter=Condition(lambda: not session.default_buffer.text))
    def questions(event: KeyPressEvent) -> None:
        """'?' on an empty line: the menu of the questions to ask"""
        event.current_buffer.start_completion(select_first=False)

    @keys.add("f1")
    def forms(event: KeyPressEvent) -> None:
        """F1: the forms a question can take, with examples"""
        run_in_terminal(lambda: console.print(Markdown(HELP)))

    recognised(vocabulary, "")  # The pattern of names, built before the first key
    session: PromptSession[str] = PromptSession(
        completer=Names(vocabulary),
        complete_while_typing=True,
        history=history(),
        lexer=Recognised(vocabulary),
        key_bindings=keys,
        style=STYLE,
        bottom_toolbar=lambda: toolbar(session.default_buffer.text, vocabulary, llm),
    )
    opening = True  # The first prompt opens with the menu of questions
    while True:
        try:
            question = session.prompt(
                "ask> ",
                pre_run=session.default_buffer.start_completion if opening else None,
            )
        except (EOFError, KeyboardInterrupt):
            return 0
        opening = False
        if question.strip():
            markdown, status = exchange(spec, question, vocabulary, llm)
            console.print(Markdown(markdown))
            console.print(f"[dim]{status}[/dim]", highlight=False)
