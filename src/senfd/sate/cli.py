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
from senfd.sate.vocabulary import Vocabulary


def show(markdown: str, raw: bool = False) -> None:
    """Print 'markdown' rendered, or as it is where 'raw'"""

    if raw:
        print(markdown)
        return
    from rich.console import Console
    from rich.markdown import Markdown

    Console().print(Markdown(markdown))


def first_word(argv: List[str]) -> Optional[int]:
    """Where in 'argv' its first word is, past the options and their values"""

    at = 0
    while at < len(argv):
        if argv[at] in ("--spec", "--llm"):
            at += 2
        elif argv[at].startswith("-"):
            at += 1
        else:
            return at
    return None


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    at = first_word(argv)
    if at is not None and argv[at] in senfd.query.LOOKUPS:
        # A lookup by its name, as "sate command write 12"; a question put in
        # quotes is one word, and read as a question
        return senfd.query.run(
            "sate",
            argv[at:] + argv[:at],
            senfd.query.LOOKUPS,
            "Look up a command, feature, log page, structure, section or value",
        )
    parser = argparse.ArgumentParser(
        description="Ask the data model questions, as of an expert who answers at once"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help=(
            "Answer this, and leave; or look up "
            f"{', '.join(senfd.query.LOOKUPS)}, as 'sate command write 12'"
        ),
    )
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
    from senfd.sate.session import interact

    return interact(spec, args.llm, args.spec)
