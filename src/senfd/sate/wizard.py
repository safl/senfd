# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
sate-preview-wizard: set up sate-web on this machine and open it

    pipx run --spec senfd sate-preview-wizard

When there is no data model at the default path, the wizard says what it
will download and asks before making the data model, because only members
of NVM Express may make and use it. The wizard then starts sate-web and
opens it in the browser. With --yes, the wizard does not ask.
"""

import argparse
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

import senfd.published
import senfd.query

TERMS = """\
The data model is made from the NVMe specifications, and the terms of the
specifications allow only members of NVM Express to make and use it. The
data model stays on this machine. Do not share it."""


def free_port(host: str, start: int) -> int:
    """The first port from 'start' up that a server can listen on at 'host'"""

    for port in range(start, start + 100):
        with socket.socket() as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise OSError(f"no free port from {start} to {start + 99} on {host}")


def plan(spec: Path, pdfs: Path) -> str:
    """The text that says what the wizard will download and make"""

    documents = senfd.published.documents()
    names = "\n".join(f"  {document['name']}" for document in documents)
    return f"""\
There is no data model at {spec}.

The wizard can make one. It downloads these {len(documents)} specifications
from nvmexpress.org into {pdfs}, and checks each against its SHA-256:

{names}

senfd then reads them, which takes a few minutes and up to 500 MB of
memory, and writes the data model to {spec}. This happens once; later runs
start sate-web straight away.

{TERMS}
"""


def interactive() -> bool:
    return sys.stdin.isatty()


def agreed(ask: Callable[[str], str]) -> bool:
    """Whether the reader answers yes to making the data model"""

    try:
        answer = ask(
            "Are you a member of NVM Express, and shall the wizard make the "
            "data model? [y/N] "
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ("y", "yes")


def main(argv: Optional[List[str]] = None, ask: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Make the data model where there is none, then start sate-web and "
            "open it in the browser"
        )
    )
    parser.add_argument(
        "--yes", action="store_true", help="make the data model without asking"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="the first port to try listening on (default: %(default)s)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="do not open the browser"
    )
    args = parser.parse_args(argv)

    spec = senfd.query.default_spec_path()
    if not spec.exists():
        pdfs = spec.parent / "published"
        print(plan(spec, pdfs), flush=True)
        if not args.yes:
            if not interactive():
                print(
                    "sate-preview-wizard: there is no terminal to ask in; run "
                    "sate-preview-wizard --yes to make the data model",
                    file=sys.stderr,
                )
                return 1
            if not agreed(ask):
                print("The wizard downloaded nothing and made no data model.")
                return 1
        try:
            documents = senfd.published.fetched(pdfs)
            senfd.published.make_data_model(documents, spec)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"sate-preview-wizard: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nStopped; the wizard made no data model.", file=sys.stderr)
            return 1
        print(f"The data model is at {spec}.\n")

    from senfd.sate import web

    loaded = senfd.query.load(spec)
    host = "127.0.0.1"
    port = free_port(host, args.port)
    print(f"sate-web answers at http://{host}:{port}/ until you press Ctrl-C.")
    web.serve(loaded, host, port, browse=not args.no_browser)
    return 0
