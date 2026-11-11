# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import hashlib
import io
import subprocess
import tomllib
from pathlib import Path
from typing import List

import pytest

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
    assert senfd.published.name_of(base["sha256"]) == "Base 2.4"
    assert senfd.published.name_of("0" * 64) is None


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


PDF = b"%PDF-1.7 a published document"


@pytest.fixture
def table(monkeypatch):
    """One published document, whose PDF is PDF, at a URL that serves it"""

    document = {
        "name": "Base 9.9",
        "file": "base.pdf",
        "url": "https://nvmexpress.org/base.pdf",
        "sha256": hashlib.sha256(PDF).hexdigest(),
    }
    monkeypatch.setattr(senfd.published, "documents", lambda: [document])
    return document


def serving(monkeypatch, content: bytes) -> List[str]:
    """Make urlopen serve 'content'; returns the URLs requested"""

    requested: List[str] = []

    def urlopen(request, timeout):
        requested.append(request.full_url)
        assert request.get_header("User-agent") == senfd.published.AGENT
        return io.BytesIO(content)

    monkeypatch.setattr(senfd.published.urllib.request, "urlopen", urlopen)
    return requested


def test_fetched_downloads_a_missing_pdf(tmp_path, monkeypatch, table):
    requested = serving(monkeypatch, PDF)

    assert senfd.published.fetched(tmp_path / "pdfs", say=lambda _: None) == [
        tmp_path / "pdfs" / "base.pdf"
    ]
    assert requested == [table["url"]]
    assert (tmp_path / "pdfs" / "base.pdf").read_bytes() == PDF


def test_fetched_keeps_a_pdf_with_the_right_hash(tmp_path, monkeypatch, table):
    (tmp_path / "base.pdf").write_bytes(PDF)
    requested = serving(monkeypatch, b"not fetched")

    senfd.published.fetched(tmp_path, say=lambda _: None)

    assert requested == []


def test_fetched_replaces_a_pdf_with_another_hash(tmp_path, monkeypatch, table):
    (tmp_path / "base.pdf").write_bytes(b"an older revision")
    serving(monkeypatch, PDF)

    senfd.published.fetched(tmp_path, say=lambda _: None)

    assert (tmp_path / "base.pdf").read_bytes() == PDF


def test_fetched_keeps_nothing_of_a_download_with_another_hash(
    tmp_path, monkeypatch, table
):
    serving(monkeypatch, b"a replaced document")

    with pytest.raises(ValueError, match="NVM Express may have replaced it"):
        senfd.published.fetched(tmp_path, say=lambda _: None)
    assert list(tmp_path.iterdir()) == []


def test_make_data_model_writes_the_merged_data_model(tmp_path):
    spec = tmp_path / "cache" / "merged.spec.document.json"

    made = senfd.published.make_data_model(
        [Path("example") / "example.docx"], spec, say=lambda _: None
    )

    assert made == spec
    assert SpecDocument.model_validate_json(spec.read_text()).meta.stem == "merged"
    assert sorted(p.name for p in spec.parent.iterdir()) == [spec.name]


def test_make_data_model_writes_nothing_when_senfd_fails(tmp_path):
    spec = tmp_path / "merged.spec.document.json"

    with pytest.raises(subprocess.CalledProcessError):
        senfd.published.make_data_model(
            [tmp_path / "missing.pdf"], spec, say=lambda _: None
        )
    assert not spec.exists()


def test_make_data_model_writes_nothing_when_senfd_makes_none(tmp_path, monkeypatch):
    monkeypatch.setattr(senfd.published.subprocess, "run", lambda *a, **k: None)
    spec = tmp_path / "merged.spec.document.json"

    with pytest.raises(ValueError, match="made no data model"):
        senfd.published.make_data_model([], spec, say=lambda _: None)
    assert not spec.exists()
