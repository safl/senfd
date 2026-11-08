# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import hashlib
from argparse import Namespace
from pathlib import Path
from typing import List, Type

from senfd.documents.base import Converter
from senfd.documents.normalized import FromFigureDocument as FromPlainDocument
from senfd.documents.plain import FromDocx, FromPdf
from senfd.documents.spec import FromNormalizedDocument
from senfd.errors import Error

CONVERTERS: List[Type[Converter]] = [
    FromDocx,
    FromPdf,
    FromPlainDocument,
    FromNormalizedDocument,
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def process(input: Path, output: Path, args: Namespace) -> List[Error]:
    all_errors = []

    for converter in CONVERTERS:
        if not converter.is_applicable(input):
            continue

        document, errors = converter.convert(input, args)
        all_errors += errors
        if converter in (FromDocx, FromPdf):
            document.meta.file = input.name
            document.meta.sha256 = sha256_of(input)

        document.to_html_file(output, all_errors)
        json_path = document.to_json_file(output)

        all_errors += process(json_path, output, args)

    return all_errors
