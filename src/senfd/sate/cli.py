# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""sate on the command line: a question answered, or a session"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import senfd.query
from senfd.sate.answering import reply
from senfd.sate.phrasing import HELP
from senfd.sate.vocabulary import Vocabulary
from senfd.documents.spec import SpecDocument


def show(markdown: str, raw: bool = False) -> None:
    """Print 'markdown' rendered, where the extra 'sate' is installed and not
    'raw', else as it is"""

    if not raw:
        try:
            from rich.console import Console
            from rich.markdown import Markdown
        except ImportError:
            pass
        else:
            Console().print(Markdown(markdown))
            return
    print(markdown)


def plain(spec: SpecDocument, llm: Optional[str] = None) -> int:
    """A session without the extra 'sate': a question a line, answered in
    Markdown, until the input ends"""

    vocabulary = Vocabulary.of(spec)
    print(HELP)
    while True:
        try:
            question = input("> ")
        except EOFError:
            return 0
        print(reply(spec, question, vocabulary, llm))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask the data model questions, as of an expert who answers at once"
    )
    parser.add_argument("question", nargs="*", help="Answer this, and leave")
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=f"The merged data model (default: {senfd.query.default_spec_path()})",
    )
    parser.add_argument(
        "--raw", action="store_true", help="Print an answer as Markdown, unrendered"
    )
    parser.add_argument(
        "--llm",
        default=None,
        metavar="URL",
        help="Have the language model served at URL understand the questions",
    )
    args = parser.parse_args(argv)
    try:
        spec = senfd.query.load(args.spec)
    except OSError as exc:
        print(f"sate: no data model to answer from: {exc}", file=sys.stderr)
        return 1
    if args.question:
        question = " ".join(args.question)
        show(reply(spec, question, Vocabulary.of(spec), args.llm), args.raw)
        return 0
    try:
        from senfd.sate.session import interact
    except ImportError:
        return plain(spec, args.llm)
    return interact(spec, args.llm, args.spec)
