from pathlib import Path

import pytest

import senfd.ask
import senfd.query


@pytest.fixture(scope="module")
def spec():
    return senfd.query.load(Path("example") / "output" / "merged.spec.document.json")


@pytest.fixture(scope="module")
def vocabulary(spec):
    return senfd.ask.Vocabulary.of(spec)


@pytest.mark.parametrize(
    "question, understood",
    [
        ("opcode of ding", "command('Ding')"),
        ("What is in cdw10 of the Ding command?", "command('Ding', dword=10)"),
        ("Where is FCNT?", "acronym('FCNT')"),
        ("feature C0h", "feature('c0h')"),
        ("What is log page C0h?", "log_page('c0h')"),
        ("C0h", "identifier('c0h')"),
        ("Which bits of FOOCAP are there?", "register('FOOCAP')"),
        ("What is the foo statistics log page?", "log_page('Foo Statistics')"),
        ("What does section 1.2 describe?", "section('1.2')"),
        ("errata", "errata('')"),
        ("help", "help('')"),
    ],
)
def test_a_question_is_understood_by_its_words_names_and_acronyms(
    vocabulary, question, understood
):
    assert str(senfd.ask.understand(question, vocabulary)) == understood


def test_an_answer_says_what_the_question_was_understood_as(spec, vocabulary):
    text, tried = senfd.ask.respond(spec, "cdw10 of ding", vocabulary)
    assert text.startswith("_Understood as `command('Ding', dword=10)`_")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('Ding', dword=10)"]


def test_what_the_model_does_not_have_is_said_to_be_not_known(spec, vocabulary):
    for question in ("teleport", "Which bit of cdw10 of Ding is the hyperdrive?"):
        text, _ = senfd.ask.respond(spec, question, vocabulary)
        assert "so this is not known" in text


def test_an_answer_not_mentioning_a_term_of_the_question_is_not_shown():
    assert senfd.ask.terms("Which bit of CDW12 of Write is FUA?") == [
        "cdw12",
        "write",
        "fua",
    ]
    assert senfd.ask.unmentioned("Where is the hyperdrive?", ["| 30 | FUA |"]) == [
        "hyperdrive"
    ]


def test_names_and_acronyms_complete_after_the_words_of_questions(vocabulary):
    words = vocabulary.words()
    assert words[: len(senfd.ask.WORDS)] == senfd.ask.WORDS
    assert "Ding" in words and "FCNT" in words and "Foo Statistics" in words


def choosing(monkeypatch, *choices):
    given = iter(choices)
    told = []

    def choose(url, messages):
        told.append(messages[-1]["content"])
        return next(given)

    monkeypatch.setattr(senfd.ask, "choose", choose)
    return told


def test_a_language_model_chooses_the_lookup_and_writes_nothing(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.ask.Understood("command", "ding", 10))
    text, tried = senfd.ask.respond(spec, "What is FCNT?", vocabulary, llm="x")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('ding', dword=10)"]


def test_a_lookup_found_wanting_is_said_to_the_language_model(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.ask.Understood("command", "zing"),
        senfd.ask.Understood("search", "foo"),
        senfd.ask.Understood("unknown"),
    )
    text, tried = senfd.ask.respond(spec, "What is the hyperdrive?", vocabulary, "x")
    assert told[1] == "No command 'zing'; choose another."
    assert told[2].startswith("The answer does not mention hyperdrive")
    assert "so this is not known" in text and len(tried) == 3


def test_the_command_line_answers_a_question(capsys):
    spec = str(Path("example") / "output" / "merged.spec.document.json")
    assert senfd.ask.main(["--spec", spec, "opcode", "of", "ding"]) == 0
    assert "opcode 01h" in capsys.readouterr().out
