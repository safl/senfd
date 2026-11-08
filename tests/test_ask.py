# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

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
        ("Is there a log page about foo, and what is its id?", "log_page('foo')"),
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
    assert senfd.ask.terms("hey, what FID does ding use?") == ["ding"]
    assert senfd.ask.unmentioned("Where is the hyperdrive?", ["| 30 | FUA |"]) == [
        "hyperdrive"
    ]


def offered(vocabulary, typed):
    return [text for text, _, _ in vocabulary.completions(typed, most=1000)]


def test_a_name_completes_from_where_it_starts_in_the_question(vocabulary):
    assert vocabulary.completions("opcode of foo sta")[0] == (
        "Foo Statistics",
        -len("foo sta"),
        "log page",
    )
    assert offered(vocabulary, "What is foo cap")[0] == "Foo Capabilities"


def test_the_words_of_questions_complete_first(vocabulary):
    assert offered(vocabulary, "o")[0] == "opcode of "
    assert offered(vocabulary, "cdw1")[:2] == ["cdw10 of ", "cdw11 of "]


def test_names_complete_before_acronyms_unless_typed_in_capitals(vocabulary):
    names = offered(vocabulary, "Which bits of fo")
    assert names.index("Foo Get") < names.index("FOOCAP")
    capitals = offered(vocabulary, "Which bits of FO")
    assert capitals.index("FOOCAP") < capitals.index("Foo Get")


@pytest.mark.parametrize(
    "typed, kind",
    [
        ("log page ", "log page"),
        ("What is feature ", "feature"),
        ("opcode of ", "command"),
        ("cdw10 of ", "command"),
        ("structure foo", "structure"),
    ],
)
def test_after_the_words_of_a_kind_its_names_come_first(vocabulary, typed, kind):
    kinds = [k for _, _, k in vocabulary.completions(typed, most=1000)]
    asked = kinds.count(kind)
    assert asked >= 2 and kinds[:asked] == [kind] * asked


def test_what_is_typed_out_is_not_offered_again(vocabulary):
    assert "Ding" not in offered(vocabulary, "opcode of Ding")
    assert offered(vocabulary, "zzz") == []


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
    assert senfd.ask.main(["--spec", spec, "--raw", "opcode", "of", "ding"]) == 0
    assert "opcode 01h" in capsys.readouterr().out


def test_the_language_model_is_asked_for_a_lookup_by_its_schema():
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    asked = {}

    class Server(BaseHTTPRequestHandler):
        def do_POST(self):
            asked.update(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            chosen = {"query": "command", "argument": "ding", "dword": 10}
            body = json.dumps(
                {"choices": [{"message": {"content": json.dumps(chosen)}}]}
            )
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.handle_request, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    chosen = senfd.ask.choose(url, [{"role": "user", "content": "FCNT?"}])
    server.server_close()
    assert str(chosen) == "command('ding', dword=10)"
    schema = asked["response_format"]["json_schema"]["schema"]
    assert schema == senfd.ask.SCHEMA and asked["temperature"] == 0


def test_without_the_extra_questions_are_read_a_line_at_a_time(
    spec, monkeypatch, capsys
):
    import builtins

    lines = iter(["opcode of ding"])

    def given(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(builtins, "input", given)
    real = builtins.__import__

    def without_the_extra(name, *args, **kwargs):
        if name.startswith(("prompt_toolkit", "rich")):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_the_extra)
    assert senfd.ask.interact(spec) == 0
    out = capsys.readouterr().out
    assert "Ask about a command" in out and "opcode 01h" in out


def test_a_command_named_with_its_command_set_is_the_command(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.ask.Understood("command", "Foobar Ding", 10))
    text, tried = senfd.ask.respond(spec, "What is FCNT of Ding?", vocabulary, "x")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('Ding', dword=10)"]


def test_an_answer_is_rendered_where_it_can_be(capsys):
    pytest.importorskip("rich")
    senfd.ask.show("| Bits | Name |\n|---|---|\n| 30 | Force Unit Access |")
    out = capsys.readouterr().out
    assert "Force Unit Access" in out and "|---|" not in out
    senfd.ask.show("| a |", raw=True)
    assert capsys.readouterr().out == "| a |\n"


@pytest.mark.parametrize(
    "question, choices",
    [
        ("What is the opcode of Foo Set?", ["Foo Get"] * 3),
        ("Which fields are in CDW10 of Ding?", ["Dong"] * 3),
        # Named by a word of several commands' names, it names none of them
        ("What is the opcode of Foo Directive?", ["Foo Directive Send"] * 3),
    ],
)
def test_a_language_model_choosing_another_command_is_not_shown(
    spec, vocabulary, monkeypatch, question, choices
):
    choosing(monkeypatch, *(senfd.ask.Understood("command", c) for c in choices))
    text, tried = senfd.ask.respond(spec, question, vocabulary, llm="x")
    assert "so this is not known" in text
    assert len(tried) == 3


def test_a_language_model_told_it_chose_another_command_may_choose_again(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.ask.Understood("command", "Foo Get"),
        senfd.ask.Understood("command", "foo set"),
    )
    text, tried = senfd.ask.respond(
        spec, "What is the opcode of Foo Set?", vocabulary, llm="x"
    )
    assert "### Foo Set" in text
    assert told[-1].startswith("The question is about Foo Set")


def test_a_register_the_model_lacks_is_said_to_the_language_model(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.ask.Understood("register", "NOPE"),
        senfd.ask.Understood("register", "foocap"),
    )
    text, _ = senfd.ask.respond(spec, "What is FOOCAP?", vocabulary, llm="x")
    assert told[-1].startswith("No register NOPE")
    assert "FOOCAP - Foo Capabilities" in text


def test_a_list_of_what_a_name_matches_is_no_answer_to_a_language_model(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, *[senfd.ask.Understood("structure", "foo")] * 3)
    text, _ = senfd.ask.respond(spec, "What is the foo?", vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_question_without_terms_grounds_no_choice_of_a_language_model(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.ask.Understood("command", "ding"))
    text, _ = senfd.ask.respond(spec, "What is the opcode?", vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_name_of_generic_words_is_spotted():
    vocabulary = senfd.ask.Vocabulary(commands={"Set Features"})
    assert senfd.ask.spot("What is the opcode of Set Features?", vocabulary) == (
        "command",
        "Set Features",
    )


@pytest.mark.parametrize(
    "question, expected",
    [
        ("feature 0x07", ["07h"]),
        ("What is CSTS.RDY?", ["csts", "rdy"]),
        ("Which bit is FUA, at offset 3?", ["fua"]),
        ("What is the opcode of Ding in NVMe 2.0?", ["ding"]),
    ],
)
def test_the_terms_of_a_question_are_what_an_answer_must_mention(question, expected):
    assert senfd.ask.terms(question) == expected


def test_mentioning_is_of_whole_words():
    assert senfd.ask.unmentioned("opcode of format", ["Information"]) == ["format"]


@pytest.mark.parametrize(
    "question, understood",
    [
        ("What is the opcode of Ding in NVMe 2.0?", "command('Ding')"),
        ("opcode of migrate", "command('Foo Migrate')"),
        ("What is FOOCAP of Ding?", "register('FOOCAP')"),
    ],
)
def test_a_question_asking_for_an_opcode_is_of_a_command(
    vocabulary, question, understood
):
    assert str(senfd.ask.understand(question, vocabulary)) == understood


def test_a_language_model_not_answering_is_said_so(spec, vocabulary, monkeypatch):
    def unreachable(url, messages):
        raise OSError("connection refused")

    monkeypatch.setattr(senfd.ask, "choose", unreachable)
    text = senfd.ask.reply(spec, "opcode of ding", vocabulary, "http://nowhere")
    assert text.startswith("The language model at http://nowhere did not choose")


def test_a_model_not_there_is_said_so(capsys):
    assert senfd.ask.main(["--spec", "/no/such/model.json", "opcode of ding"]) == 1
    assert "no data model to answer from" in capsys.readouterr().err


@pytest.mark.parametrize(
    "question, choice",
    [
        # Of the kind the question asks of
        ("What is log page C0h?", senfd.ask.Understood("feature", "c0h")),
        ("What is feature C1h?", senfd.ask.Understood("log_page", "c1h")),
        # Of the dword the question asks of
        ("dword 10 of ding", senfd.ask.Understood("command", "ding", 11)),
        # A command's opcode, not a search mentioning it
        ("What is the opcode of Ding?", senfd.ask.Understood("search", "FCNT")),
        # A register named by its acronym, not a search mentioning it
        ("What is register FOOCAP?", senfd.ask.Understood("search", "FOOCAP")),
    ],
)
def test_a_language_model_choosing_another_kind_of_answer_is_not_shown(
    spec, vocabulary, monkeypatch, question, choice
):
    choosing(monkeypatch, *[choice] * 3)
    text, _ = senfd.ask.respond(spec, question, vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_field_named_as_a_kind_in_a_command_is_of_the_command(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.ask.Understood("command", "foo get"))
    text, _ = senfd.ask.respond(
        spec, "Where is the feature identifier in Foo Get?", vocabulary, llm="x"
    )
    assert "so this is not known" not in text


def test_a_search_asked_for_is_answered(spec, vocabulary):
    text, _ = senfd.ask.respond(spec, "search FCNT", vocabulary)
    assert "so this is not known" not in text


def test_a_command_named_in_a_structure_s_name_does_not_answer_for_it(spec, vocabulary):
    vocabulary = senfd.ask.Vocabulary(
        commands=set(vocabulary.commands),
        structures=set(vocabulary.structures) | {"Ding Report"},
    )
    command = senfd.ask.Understood("command", "Ding")
    lines = senfd.ask.answer(spec, command, vocabulary)
    question = "What is the Ding Report structure?"
    assert senfd.ask.elsewhere(question, command, lines, vocabulary) == "Ding Report"


def test_a_field_acronym_that_is_a_register_s_too_is_of_the_structure_named(
    vocabulary,
):
    understood = senfd.ask.understand(
        "What is the FOOCAP field of the Foo Descriptor structure?", vocabulary
    )
    assert str(understood) == "structure('Foo Descriptor')"


@pytest.mark.parametrize(
    "question, understood, shows",
    [
        ("help", "help('')", "| a command, with its dwords |"),
        ("section 1.2", "section('1.2')", "- example 1.2 Ding command"),
        ("errata", "errata('')", "Command Zing: opcode is not a value"),
        ("search FCNT", "search('fcnt')", "15:00 Foo Count (FCNT)"),
        ("FCNT", "acronym('FCNT')", "15:00 Foo Count (FCNT)"),
        ("C0h", "identifier('c0h')", "### Feature C0h Foo Config"),
        ("structure foo descriptor", "structure('foo descriptor')", "**Foo Descriptor"),
        (
            "log page foo events",
            "log_page('foo events')",
            "### Log page C1h Foo Events",
        ),
        ("feature foo config", "feature('foo config')", "### Feature C0h Foo Config"),
        # Part of a name, of no kind the question says, is looked up by name
        ("joined layout", "name('joined layout')", "**Foo Joined Layout"),
    ],
)
def test_each_form_of_question_is_answered_by_its_lookup(
    spec, vocabulary, question, understood, shows
):
    text, tried = senfd.ask.respond(spec, question, vocabulary)
    assert tried == [understood]
    assert shows in text


@pytest.mark.parametrize(
    "choice, shown",
    [
        (senfd.ask.Understood("structure", "foo entry"), False),
        (senfd.ask.Understood("structure", "foo descriptor"), True),
    ],
)
def test_a_lookup_by_name_is_of_the_thing_the_question_names(
    spec, vocabulary, monkeypatch, choice, shown
):
    choosing(monkeypatch, *[choice] * 3)
    text, _ = senfd.ask.respond(
        spec, "What is the Foo Descriptor structure?", vocabulary, llm="x"
    )
    assert ("so this is not known" not in text) == shown


def session_answering(monkeypatch, *typed):
    """Have senfd-ask's prompt read 'typed', as if at a terminal, and keep the
    session it makes"""

    import prompt_toolkit
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    made = []
    real = prompt_toolkit.PromptSession

    def session(*args, **kwargs):
        pipe = stack.enter_context(create_pipe_input())
        for line in typed:
            pipe.send_text(line + "\r")
        pipe.close()
        made.append(real(*args, input=pipe, output=DummyOutput(), **kwargs))
        return made[-1]

    import contextlib

    stack = contextlib.ExitStack()
    monkeypatch.setattr(prompt_toolkit, "PromptSession", session)
    return made, stack


def test_the_session_answers_each_question_until_the_input_ends(
    spec, monkeypatch, capsys
):
    made, stack = session_answering(monkeypatch, "opcode of ding", "", "C0h")
    with stack:
        assert senfd.ask.interact(spec) == 0
    out = capsys.readouterr().out
    assert "Ask about a command" in out
    assert "Ding: Foobar command, opcode 01h" in out
    assert "Feature C0h Foo Config" in out


def test_the_session_completes_the_names_of_the_model(spec, monkeypatch, capsys):
    from prompt_toolkit.document import Document

    made, stack = session_answering(monkeypatch)
    with stack:
        senfd.ask.interact(spec)
    assert "Ask about a command" in capsys.readouterr().out
    completer = made[0].completer
    shown = list(completer.get_completions(Document("opcode of Foo Sta"), None))
    assert (shown[0].text, shown[0].start_position) == ("Foo Statistics", -7)
    assert shown[0].display_meta_text == "log page"


def test_without_a_question_the_command_line_opens_the_session(monkeypatch, capsys):
    made, stack = session_answering(monkeypatch, "opcode of ding")
    model = str(Path("example") / "output" / "merged.spec.document.json")
    with stack:
        assert senfd.ask.main(["--spec", model]) == 0
    assert "opcode 01h" in capsys.readouterr().out


def test_a_register_named_by_one_generic_word_is_not_spotted_by_it():
    vocabulary = senfd.ask.Vocabulary(structures={"CMD - Command"})
    assert senfd.ask.spot("Which command is it?", vocabulary) is None
    assert senfd.ask.spot("What is the CMD - Command register?", vocabulary) == (
        "register",
        "CMD",
    )


def test_a_section_is_asked_for_by_its_number(spec, vocabulary):
    text, tried = senfd.ask.respond(spec, "section 1", vocabulary)
    assert tried == ["section('1')"]
    assert "- example 1.2 Ding command" in text


def test_an_opcode_asked_of_a_word_of_several_commands_is_not_known(spec, vocabulary):
    text, _ = senfd.ask.respond(spec, "opcode of foo directive", vocabulary)
    assert "the question names several commands rather than one" in text
