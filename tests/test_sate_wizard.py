# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import shutil
import socket
from pathlib import Path
from typing import Dict, List

import pytest

import senfd.published
import senfd.query
from senfd.sate import web, wizard

SPEC = Path("example") / "output" / "merged.spec.document.json"


@pytest.fixture
def setup(tmp_path, monkeypatch) -> Dict[str, List]:
    """The wizard with its data model at tmp_path, with downloading, making
    and serving recorded rather than done"""

    done: Dict[str, List] = {"fetched": [], "made": [], "served": []}
    spec = tmp_path / "merged.spec.document.json"
    monkeypatch.setenv("SENFD_SPEC", str(spec))
    monkeypatch.setattr(wizard, "interactive", lambda: True)

    def fetched(directory):
        done["fetched"].append(directory)
        return [directory / "base.pdf"]

    def make_data_model(documents, to):
        done["made"].append((documents, to))
        shutil.copy(SPEC, to)
        return to

    def serve(spec, host, port, browse=False):
        done["served"].append((host, port, browse))

    monkeypatch.setattr(senfd.published, "fetched", fetched)
    monkeypatch.setattr(senfd.published, "make_data_model", make_data_model)
    monkeypatch.setattr(web, "serve", serve)
    return done


def never(prompt):
    raise AssertionError(f"asked: {prompt}")


def test_the_plan_names_each_document_and_the_terms(tmp_path):
    plan = wizard.plan(tmp_path / "merged.spec.document.json", tmp_path / "pdfs")

    for document in senfd.published.documents():
        assert f"  {document['name']}\n" in plan
    assert "only members of NVM Express to make and use it" in plan
    assert str(tmp_path / "pdfs") in plan


def test_the_wizard_makes_the_data_model_when_answered_yes(setup, tmp_path, capsys):
    assert wizard.main(["--port", "8123"], ask=lambda _: "y") == 0

    assert setup["fetched"] == [tmp_path / "published"]
    assert setup["made"] == [
        ([tmp_path / "published" / "base.pdf"], tmp_path / "merged.spec.document.json")
    ]
    assert setup["served"][0][2] is True
    assert "There is no data model at" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_the_wizard_downloads_nothing_unless_answered_yes(setup, answer):
    assert wizard.main([], ask=lambda _: answer) == 1

    assert setup == {"fetched": [], "made": [], "served": []}


@pytest.mark.parametrize("stop", [EOFError, KeyboardInterrupt])
def test_the_wizard_takes_ctrl_c_or_ctrl_d_as_no(setup, stop):
    def ask(prompt):
        raise stop

    assert wizard.main([], ask=ask) == 1
    assert setup["fetched"] == []


def test_the_wizard_does_not_ask_with_yes(setup):
    assert wizard.main(["--yes", "--no-browser"], ask=never) == 0

    assert len(setup["made"]) == 1
    assert setup["served"][0][2] is False


def test_the_wizard_without_a_terminal_asks_for_yes(setup, monkeypatch, capsys):
    monkeypatch.setattr(wizard, "interactive", lambda: False)

    assert wizard.main([], ask=never) == 1
    assert "sate-preview-wizard --yes" in capsys.readouterr().err
    assert setup["fetched"] == []


def test_the_wizard_serves_an_existing_data_model_without_asking(setup, tmp_path):
    shutil.copy(SPEC, tmp_path / "merged.spec.document.json")

    assert wizard.main([], ask=never) == 0

    assert setup["fetched"] == [] and setup["made"] == []
    assert len(setup["served"]) == 1


def test_the_wizard_reports_a_failed_download(setup, monkeypatch, capsys):
    def fetched(directory):
        raise ValueError("base.pdf has the SHA-256 0000")

    monkeypatch.setattr(senfd.published, "fetched", fetched)

    assert wizard.main(["--yes"]) == 1
    assert "sate-preview-wizard: base.pdf has the SHA-256 0000" in (
        capsys.readouterr().err
    )
    assert setup["served"] == []


def test_free_port_passes_over_a_port_in_use():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]

        assert wizard.free_port("127.0.0.1", port) > port


def test_the_wizard_stops_on_ctrl_c_while_making(setup, monkeypatch, capsys):
    def make_data_model(documents, to):
        raise KeyboardInterrupt

    monkeypatch.setattr(senfd.published, "make_data_model", make_data_model)

    assert wizard.main(["--yes"]) == 1
    assert "Stopped; the wizard made no data model." in capsys.readouterr().err
    assert setup["served"] == []
