# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import tomllib
from pathlib import Path

import senfd.published
from senfd.documents.base import DocumentMeta
from senfd.documents.spec import SpecDocument, linked

MANIFEST = Path("tests/public/documents.toml")
BASE = "NVM Express Base Specification, Revision 2-4 Ratified 2026-07-31"


def test_the_published_documents_are_those_the_tests_read():
    tested = {d["sha256"]: d for d in tomllib.loads(MANIFEST.read_text())["document"]}
    published = {d["sha256"]: d for d in senfd.published.documents()}
    assert set(tested) == set(published)
    for sha256, document in tested.items():
        assert published[sha256]["url"] == document["url"]
        assert published[sha256]["file"] == document["file"]


def test_a_published_document_is_known_by_its_hash():
    base = next(d for d in senfd.published.documents() if d["name"] == "Base 2.4")
    assert senfd.published.url_of(base["sha256"]) == base["url"]
    assert senfd.published.url_of("0" * 64) is None
    assert senfd.published.url_of(None) is None


def test_a_citation_of_a_published_document_links_to_its_page():
    base = next(d for d in senfd.published.documents() if d["name"] == "Base 2.4")
    spec = SpecDocument()
    spec.documents[BASE] = DocumentMeta(
        stem=BASE, file=base["file"], sha256=base["sha256"]
    )
    spec.documents["Other"] = DocumentMeta(stem="Other")
    lines = [
        "cdw10 [Base 2.4, 5.2.13, Figure 203, page 213, PDF page 238]",
        "Reserved [Base 2.4, Figure 7]",
        "elsewhere [Other, 1.2, Figure 3, page 4]",
        "| 31:16 | Not a citation [in brackets] |",
    ]
    assert linked(spec, lines) == [
        f"cdw10 [Base 2.4, 5.2.13, Figure 203, page 213, PDF page 238]({base['url']}#page=238)",
        f"Reserved [Base 2.4, Figure 7]({base['url']})",
        "elsewhere [Other, 1.2, Figure 3, page 4]",
        "| 31:16 | Not a citation [in brackets] |",
    ]
    # A data model of documents no hash knows is left as it is
    assert linked(SpecDocument(), lines) == lines
