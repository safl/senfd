# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import shutil
from pathlib import Path
from typing import Optional

import senfd.identity
import senfd.published
from senfd.documents.base import DocumentMeta
from senfd.documents.spec import SpecDocument, merge


def package(tmp_path: Path) -> Path:
    """A copy of senfd's source, to change"""

    copied = tmp_path / "senfd"
    shutil.copytree(Path(senfd.identity.__file__).parent, copied)
    return copied


def test_the_senfd_hash_is_that_of_its_source():
    assert senfd.identity.senfd_sha256() == senfd.identity.tree_sha256(
        Path(senfd.identity.__file__).parent
    )


def test_the_senfd_hash_changes_with_the_source_that_reads(tmp_path):
    copied = package(tmp_path)
    before = senfd.identity.tree_sha256(copied)

    (copied / "published.toml").write_text("changed")

    assert senfd.identity.tree_sha256(copied) != before


def test_the_senfd_hash_leaves_out_sate_and_what_is_not_shipped(tmp_path):
    copied = package(tmp_path)
    before = senfd.identity.tree_sha256(copied)

    (copied / "sate" / "web.py").write_text("changed")
    (copied / "notes.txt").write_text("not shipped")
    (copied / "__pycache__").mkdir(exist_ok=True)
    (copied / "__pycache__" / "x.py").write_text("compiled")

    assert senfd.identity.tree_sha256(copied) == before


def test_the_input_hash_is_of_the_set_of_documents():
    one, two = "1" * 64, "2" * 64

    assert senfd.identity.input_sha256([one, two]) == senfd.identity.input_sha256(
        [two, one]
    )
    assert senfd.identity.input_sha256([one]) != senfd.identity.input_sha256([one, two])


def of(*hashes: Optional[str]) -> SpecDocument:
    """A data model made from documents with the SHA-256s 'hashes'"""

    return SpecDocument(documents={f"of {h}": DocumentMeta(sha256=h) for h in hashes})


def test_merge_records_the_input_and_combined_hashes():
    merged = merge([of("1" * 64), of("2" * 64)])

    assert merged.meta.format == senfd.identity.FORMAT
    assert merged.meta.senfd_sha256 == senfd.identity.senfd_sha256()
    assert merged.meta.input_sha256 == senfd.identity.input_sha256(["1" * 64, "2" * 64])
    assert merged.meta.combined_sha256 == senfd.identity.combined_sha256(
        merged.meta.input_sha256, merged.meta.senfd_sha256
    )


def test_merge_records_no_input_hash_for_a_document_of_unknown_hash():
    merged = merge([of("1" * 64), of(None)])

    assert merged.meta.input_sha256 is None
    assert merged.meta.combined_sha256 is None


def test_the_published_input_hash_is_that_of_a_data_model_of_them_all():
    hashes = [d["sha256"] for d in senfd.published.documents()]

    assert merge([of(*hashes)]).meta.input_sha256 == (
        senfd.published.published_input_sha256()
    )
