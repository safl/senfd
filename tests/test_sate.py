# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import re
from dataclasses import replace
from pathlib import Path

import pytest

import senfd.sate
import senfd.sate.answering
import senfd.sate.completion
import senfd.sate.session
import senfd.sate.reading
import senfd.query
import senfd.sate.cli
from senfd.sate import grounding, language_model, lookup, phrasing, reading
from senfd.sate.completion import completions, recognised
from senfd.sate.vocabulary import Vocabulary


@pytest.fixture(scope="module")
def spec():
    return senfd.query.load(Path("example") / "output" / "merged.spec.document.json")


@pytest.fixture(scope="module")
def vocabulary(spec):
    return senfd.sate.Vocabulary.of(spec)


@pytest.mark.parametrize(
    "question, understood",
    [
        ("opcode of ding", "command('Ding', opcode=True)"),
        ("What is in cdw10 of the Ding command?", "command('Ding', dword=10)"),
        ("Where is FCNT?", "acronym('FCNT')"),
        ("feature C0h", "feature('c0h')"),
        ("What is log page C0h?", "log_page('c0h')"),
        ("C0h", "identifier('c0h')"),
        ("cns of foo namespace", "value('cns foo namespace')"),
        ("cns of foo namespaces", "value('cns foo namespaces')"),
        ("lpi of foo statistics", "log_page('foo statistics')"),
        ("fid of foo config", "feature('Foo Config')"),
        ("lpi C0h", "log_page('c0h')"),
        # The field asked of is the one written last, by its name and acronym;
        # where what the question names has no field of that acronym, the
        # acronym is looked up wherever it is
        # An entry of a table of values, by its name
        ("What is the value of the Foo Element?", "value('Foo Element')"),
        ("What is the value of foo error Foo Element?", "value('Foo Element')"),
        (
            "At which bytes of the Foo Directive Send command is Foo Key (FKEY)?",
            "acronym('FKEY')",
        ),
        (
            "At which bytes of the Foo Descriptor is BARCTL Foo Key (FKEY)?",
            "structure('Foo Descriptor')",
        ),
        ("Which bits of FOOCAP are there?", "register('FOOCAP')"),
        ("What is the foo statistics log page?", "log_page('Foo Statistics')"),
        ("What does section 1.2 describe?", "section('1.2')"),
        ("Is there a log page about foo, and what is its id?", "log_page('foo')"),
        ("errata", "errata('')"),
        ("help", "help('')"),
        ("What is status code 82h?", "value('status code 82h')"),
        ("status 0x82", "status('82h')"),
        ("status code 0x82", "value('status code 82h')"),
        ("SC 0x81", "value('status code 81h')"),
        ("what does status 0x4281 mean?", "status('4281h')"),
        ("status: 4281h", "status('4281h')"),
        ("status bad", "name('status bad')"),
        ("dw3 0x80050007", "status('dw3 80050007h')"),
        ("dword 3 80050007h", "status('dw3 80050007h')"),
        ("sct=2 sc=0x81", "status('sct 2h sc 81h')"),
        ("SC 81h SCT 2", "status('sct 2h sc 81h')"),
        ("what does SCT 1 SC 80h mean for Ding?", "status('sct 1h sc 80h of Ding')"),
        ("SCT 7h", "value('status code type 7h')"),
        ("CNS 1Ch", "value('cns 1ch')"),
        ("What is the status code of Foo Lost?", "value('status code foo lost')"),
        ("What are the status codes of Ding?", "value('status code ding')"),
        ("Which CNS value gives the Foo namespace data?", "value('cns foo namespace')"),
        ("Where is SCT?", "name('sct')"),
        ("the status code type field of Ding", "command('Ding')"),
    ],
)
def test_a_question_is_understood_by_its_words_names_and_acronyms(
    vocabulary, question, understood
):
    assert str(senfd.sate.understand(question, vocabulary)) == understood


def test_an_answer_says_what_the_question_was_understood_as(spec, vocabulary):
    text, tried = senfd.sate.respond(spec, "cdw10 of ding", vocabulary)
    assert text.startswith("_Understood as `command('Ding', dword=10)`_")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('Ding', dword=10)"]


def test_what_the_model_does_not_have_is_said_to_be_not_known(spec, vocabulary):
    for question in ("teleport", "Which bit of cdw10 of Ding is the hyperdrive?"):
        text, _ = senfd.sate.respond(spec, question, vocabulary)
        assert "so this is not known" in text


def test_a_value_is_answered_from_its_table_with_where_it_is(spec, vocabulary):
    text, _ = senfd.sate.respond(
        spec, "Which CNS value gives the Foo namespace data?", vocabulary
    )
    assert "- **1Ch** Foo namespace data, CNS value of Identify [example, 2," in text
    text, _ = senfd.sate.respond(spec, "What is status code 83h?", vocabulary)
    assert "- **83h** Foo Late, Command Specific status code of Foo Get [" in text
    text, _ = senfd.sate.respond(spec, "What is status code 99h?", vocabulary)
    assert "so this is not known" in text


def test_an_answer_not_mentioning_a_term_of_the_question_is_not_shown():
    assert phrasing.terms("Which bit of CDW12 of Write is FUA?") == [
        "cdw12",
        "write",
        "fua",
    ]
    assert phrasing.terms("hey, what FID does ding use?") == ["ding"]
    assert grounding.unmentioned("Where is the hyperdrive?", ["| 30 | FUA |"]) == [
        "hyperdrive"
    ]


def test_an_identifier_alone_also_finds_the_status_codes_and_other_values(
    spec, vocabulary
):
    """C0h is a feature, a log page and a Generic Command status code"""

    text, tried = senfd.sate.respond(spec, "C0h", vocabulary)

    assert tried == ["identifier('c0h')"]
    assert "### Feature C0h Foo Config" in text
    assert "### Log page C0h Foo Statistics" in text
    assert "**C0h** Foo Invalid, Generic Command status code" in text
    assert "log page identifier of Get Log Page" not in text
    assert "requirement of Foo Feature" not in text


def test_a_field_found_by_its_acronym_is_of_the_structure_named_by_its_rest():
    """The question names "Foo Namespace", which is the rest of "Identify -
    Foo Namespace" and a part of the name of the structure holding MAXF"""

    vocabulary = Vocabulary(
        structures={
            "Identify - Foo Namespace",
            "Bar Command Set specific Foo Namespace",
        },
        acronyms={"MAXF"},
    )
    question = "At which bytes of the Bar Command Set Foo Namespace data structure is Max Foo (MAXF)?"
    lines = ["- Bar Command Set specific Foo Namespace [x]: 03:02 Max Foo (MAXF)"]

    assert (
        grounding.elsewhere(
            question, senfd.sate.Understood("acronym", "MAXF"), lines, vocabulary
        )
        is None
    )


def test_a_register_acronym_in_the_name_of_the_field_asked_of_is_no_register():
    vocabulary = Vocabulary(
        structures={"Foo Descriptor", "ID - Identifiers"},
        acronyms={"ID", "FKEY"},
        registers={"ID"},
    )
    question = "At which bytes of the Foo Descriptor is Foo ID Key (FKEY)?"
    lines = ["**Foo Descriptor, bytes [x]**", "", "| 03:00 | Foo ID Key | FKEY |"]

    assert (
        grounding.elsewhere(
            question,
            senfd.sate.Understood("structure", "Foo Descriptor"),
            lines,
            vocabulary,
        )
        is None
    )


def test_a_term_of_the_captions_of_the_document_cited_counts_as_mentioned():
    """NBFT names the subject of the Boot document, in its captions and
    section titles, though not in the figure that answers"""

    vocabulary = Vocabulary(documents={"Boot 1.4": " nbft elements nbft overview "})
    lines = [
        "- SSNS Flags Field [Boot 1.4, 3.2.2.5.1, Figure 18, page 32]: 02 (USFLAG)"
    ]

    assert grounding.unmentioned("NBFT SSNS Flags USFLAG", lines, vocabulary) == []
    assert grounding.unmentioned("NBFT SSNS Flags USFLAG", lines) == ["nbft"]
    assert grounding.unmentioned("HFI SSNS Flags USFLAG", lines, vocabulary) == ["hfi"]


@pytest.mark.parametrize(
    "question, understood",
    [
        # The table by its title, in the singular, and an entry of it
        (
            "What is the PDU type of the Foo Response PDU (FooResp)?",
            "value('Foo PDU Types FooResp')",
        ),
        # The table by the header of its column of codes, and an entry of it
        (
            "What is the descriptor type designator of the Bar Descriptor?",
            "value('descriptor type designator Bar Descriptor')",
        ),
        # An entry by its symbol
        ("At which offset is the Foo Doorbell (FOODBL)?", "value('FOODBL')"),
    ],
)
def test_a_question_naming_a_table_of_codes_and_an_entry_is_read_as_the_entry(
    question, understood
):
    vocabulary = Vocabulary(
        structures={"Foo Response PDU (FooResp)"},
        tables=[
            ("Foo PDU Types", {"opcode"}, {"FooResp"}),
            ("Foo Elements", {"descriptor type designator"}, {"Bar Descriptor"}),
            ("Foo Property Definitions", {"start"}, {"Foo Doorbell (Admin)"}),
        ],
        symbols={"FOODBL"},
    )

    assert str(senfd.sate.reading.understand(question, vocabulary)) == understood


def test_the_words_spelled_out_by_an_acronym_mentioned_need_no_mention():
    lines = ["- 3h HFI Descriptor [Boot 1.4, 3.2.1, Figure 6]: NBFT"]
    question = "the HFI Descriptor in the NVMe Boot Firmware Table (NBFT)?"

    assert grounding.unmentioned(question, lines) == []
    assert grounding.unmentioned("the HFI Descriptor in the Firmware Table", lines) == [
        "firmware",
        "table",
    ]


def test_a_value_asked_in_hex_is_mentioned_with_leading_zeros_too():
    """ "cns 0x5" is read as 5h, and the data model writes the value as 05h"""

    answer = ["- **05h** Identify I/O Command Set specific Namespace, CNS value"]
    assert grounding.unmentioned("cns 0x5", answer) == []
    assert grounding.unmentioned("CNS 05h", answer) == []
    assert grounding.unmentioned("cns 0x50", answer) == ["50h"]
    assert grounding.unmentioned("cns 0x0", ["- **00h** Namespace, CNS value"]) == []


def offered(vocabulary, typed):
    return [text for text, *_ in completions(vocabulary, typed, most=1000)]


def test_a_name_completes_from_where_it_starts_in_the_question(vocabulary):
    assert completions(vocabulary, "opcode of foo sta")[0][:4] == (
        "Foo Statistics",
        -len("foo sta"),
        "log page",
        "Foo Statistics",
    )
    assert offered(vocabulary, "What is foo cap")[0] == "Foo Capabilities"


def test_the_words_of_questions_complete_first(vocabulary):
    assert offered(vocabulary, "o")[0] == "opcode of "
    assert offered(vocabulary, "cdw1")[:2] == ["cdw10 of ", "cdw11 of "]
    assert offered(vocabulary, "sta")[0] == "status code "


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
    kinds = [k for _, _, k, _, _ in completions(vocabulary, typed, most=1000)]
    asked = kinds.count(kind)
    assert asked >= 2 and kinds[:asked] == [kind] * asked


def test_with_nothing_typed_the_questions_to_ask_are_offered(vocabulary):
    offered = completions(vocabulary, "")
    shown = [o.shown for o in offered if o.kind == "question"]
    assert shown == [
        "what is the opcode of Ding?",
        "which bit of cdw10 of Ding is FCNT?",
        "which bits of cdw10 of Ding are FCNT?",
        "what are the fields of the Bar?",
        "which feature is Foo Odd?",
        "which log page is Foo Events?",
        "what is status code 02h?",
    ]
    assert [o.text for o in offered if o.kind == "form"] == phrasing.WORDS


def test_a_question_begun_completes_to_the_questions_it_may_be(vocabulary):
    offer = completions(vocabulary, "which b")[0]
    assert (offer.text, offer.start, offer.kind) == ("which bit of cdw", -7, "question")
    assert offer.shown == "which bit of cdw10 of Ding is FCNT?"
    assert offer.parts == (
        ("which bit of cdw", ""),
        ("10", "name"),
        (" of ", ""),
        ("Ding", "name"),
        (" is ", ""),
        ("FCNT", "acronym"),
        ("?", ""),
    )


def test_each_question_shown_is_read_as_its_form_is(vocabulary):
    """An example question asks what its form asks, so choosing it and typing
    one's own names over the example's gives the same reading"""

    for offer in completions(vocabulary, ""):
        if offer.kind == "question":
            assert senfd.sate.understand(offer.shown, vocabulary).query != "help", (
                offer.shown
            )


def test_the_examples_are_write_and_its_fields_where_there_are(vocabulary):
    from senfd.sate.completion import examples

    vocabulary = replace(
        vocabulary,
        commands=vocabulary.commands | {"Write"},
        structures=vocabulary.structures | {"Completion Queue Entry: Status Field"},
        fields={**vocabulary.fields, ("write", 12): ["LR", "FUA", "PRINFO"]},
    )
    found = examples(vocabulary)

    assert (found["command"], found["dword"]) == ("Write", "12")
    assert (found["acronym"], found["acronyms"]) == ("FUA", "PRINFO")
    assert (found["status"], found["sct"], found["sc"]) == ("0x4281", "1", "80h")


def test_after_is_the_acronyms_of_what_is_asked_of_come_first(vocabulary):
    assert offered(vocabulary, "which bits of cdw10 of Ding are ")[0] == "FCNT"
    assert offered(vocabulary, "which bits of FOOCAP are ")[0] == "FL"


def test_the_words_names_and_acronyms_of_a_question_are_recognised(vocabulary):
    text = "Which bits of cdw10 of the Ding command are FCNT?"
    assert [(text[s:e], kind) for s, e, kind in recognised(vocabulary, text)] == [
        ("cdw10 of", "word"),
        ("Ding", "name"),
        ("FCNT", "acronym"),
    ]


def test_the_field_asked_of_is_said_and_its_row_marked(spec, vocabulary):
    for question in (
        "Which bits of cdw10 of Ding are FCNT?",
        "Which bits of cdw10 of Ding are the foo count?",
    ):
        text = senfd.sate.reply(spec, question, vocabulary)
        assert "| **15:00** | **Foo Count** | **FCNT** |" in text
        assert text.endswith(
            "> **FCNT**, Foo Count, is bits 15:00 of cdw10 of Ding "
            "[example, 1.2, Figure 2, page 2]"
        )
    assert "is bits" not in senfd.sate.reply(spec, "cdw10 of ding", vocabulary)


def test_the_field_asked_of_is_said_with_a_linked_citation():
    """A data model of the published PDFs links each citation to its page"""

    url = "https://example.org/spec.pdf#page=2"
    markdown = (
        f"### Ding: Foo command, opcode C0h [example, 1.2, Figure 1, page 1]({url})\n"
        "\n"
        f"**cdw10 [example, 1.2, Figure 2, page 2]({url})**\n"
        "\n"
        "| Bits | Name | Acronym |\n"
        "|---|---|---|\n"
        "| 15:00 | Foo Count | FCNT |"
    )
    text = senfd.sate.answering.focused("Which bits are FCNT?", markdown)
    assert text.endswith(
        "> **FCNT**, Foo Count, is bits 15:00 of cdw10 of Ding "
        f"[example, 1.2, Figure 2, page 2]({url})"
    )


def test_the_bottom_line_reads_the_question_as_it_is_typed(vocabulary):
    assert senfd.sate.session.reading_so_far("", vocabulary).startswith(
        " Ask of 8 commands"
    )
    assert senfd.sate.session.reading_so_far(
        "which bits of cdw10 of Ding", vocabulary
    ) == (" Read as command('Ding', dword=10)")
    assert "language model" in senfd.sate.session.reading_so_far(
        "ding", vocabulary, llm="x"
    )


@pytest.mark.parametrize(
    "typed, next",
    [
        ("which bit of cdw10 of", " Next, a command: Tab lists them"),
        (
            "which bit of cdw10 of Ding is ",
            " Next, a field of cdw10 of Ding: Tab lists them",
        ),
        (
            "which bit of cdw",
            " Next, the number of a dword, as cdw12: then of and a command",
        ),
        ("log page ", " Next, a log page: Tab lists them"),
    ],
)
def test_the_bottom_line_says_what_comes_next(vocabulary, typed, next):
    assert senfd.sate.session.reading_so_far(typed, vocabulary) == next


def test_an_answer_says_how_it_was_found(spec, vocabulary):
    _, status = senfd.sate.exchange(spec, "cdw10 of ding", vocabulary)
    read, lookups, took, cites = status.split(" | ")
    assert read == "read as command('Ding', dword=10)"
    assert lookups == "1 lookup"
    assert took.endswith(" ms")
    assert cites == "cites 2 figures"
    _, status = senfd.sate.exchange(spec, "teleport", vocabulary)
    assert status.endswith(" | not known")


def test_a_word_of_no_meaning_alone_completes_nothing(vocabulary):
    assert offered(vocabulary, "which bit of cdw10 of") == ["cdw10 of "]
    assert offered(vocabulary, "the hyperdrive of") == []


def test_a_name_typed_in_full_is_listed_first(vocabulary):
    assert offered(vocabulary, "opcode of Ding")[:1] == ["Ding"]
    assert offered(vocabulary, "zzz") == []


def choosing(monkeypatch, *choices):
    given = iter(choices)
    told = []

    def choose(url, messages, model=None):
        told.append(messages[-1]["content"])
        return next(given)

    monkeypatch.setattr(language_model, "choose", choose)
    return told


def test_a_language_model_chooses_the_lookup_and_writes_nothing(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.sate.Understood("command", "ding", 10))
    text, tried = senfd.sate.respond(spec, "What is FCNT?", vocabulary, llm="x")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('ding', dword=10)"]


def test_a_language_model_may_choose_the_tables_of_values(
    spec, vocabulary, monkeypatch
):
    assert "value" in language_model.SCHEMA["properties"]["query"]["enum"]
    choosing(monkeypatch, senfd.sate.Understood("value", "status code foo lost"))
    text, tried = senfd.sate.respond(
        spec, "Which status is returned when a foo is lost?", vocabulary, llm="x"
    )
    assert "82h" in text and "Foo Lost" in text
    assert tried == ["value('status code foo lost')"]


def test_a_lookup_found_wanting_is_said_to_the_language_model(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.sate.Understood("command", "zing"),
        senfd.sate.Understood("search", "foo"),
        senfd.sate.Understood("unknown"),
    )
    text, tried = senfd.sate.respond(spec, "What is the hyperdrive?", vocabulary, "x")
    assert told[1] == "No command 'zing'; choose another."
    assert told[2].startswith("The answer does not mention hyperdrive")
    assert "so this is not known" in text and len(tried) == 3


def test_the_command_line_answers_a_question(capsys):
    spec = str(Path("example") / "output" / "merged.spec.document.json")
    assert senfd.sate.main(["--spec", spec, "--raw", "opcode", "of", "ding"]) == 0
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
    chosen = language_model.choose(url, [{"role": "user", "content": "FCNT?"}])
    server.server_close()
    assert str(chosen) == "command('ding', dword=10)"
    schema = asked["response_format"]["json_schema"]["schema"]
    assert schema == language_model.SCHEMA and asked["temperature"] == 0
    assert "model" not in asked


def test_the_language_model_asked_for_is_named_to_a_server_with_several():
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
    language_model.choose(url, [{"role": "user", "content": "FCNT?"}], "qwen2.5-7b")
    server.server_close()
    assert asked["model"] == "qwen2.5-7b"


def test_the_name_of_a_language_model_reaches_the_server(spec, vocabulary, monkeypatch):
    named = []

    def choose(url, messages, model=None):
        named.append(model)
        return senfd.sate.Understood("command", "ding", 10)

    monkeypatch.setattr(language_model, "choose", choose)
    senfd.sate.reply(spec, "FCNT?", vocabulary, "x", "qwen2.5-7b")
    assert named == ["qwen2.5-7b"]


def test_the_name_of_a_language_model_is_no_first_word_of_a_question():
    from senfd.sate.cli import first_word

    assert first_word(["--llm-model", "command", "what is FCNT"]) == 2


def test_a_command_named_with_its_command_set_is_the_command(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.sate.Understood("command", "Foobar Ding", 10))
    text, tried = senfd.sate.respond(spec, "What is FCNT of Ding?", vocabulary, "x")
    assert "| 15:00 | Foo Count | FCNT |" in text
    assert tried == ["command('Ding', dword=10)"]


def test_an_answer_is_rendered_where_it_can_be(capsys):
    pytest.importorskip("rich")
    senfd.sate.cli.show("| Bits | Name |\n|---|---|\n| 30 | Force Unit Access |")
    out = capsys.readouterr().out
    assert "Force Unit Access" in out and "|---|" not in out
    senfd.sate.cli.show("| a |", raw=True)
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
    choosing(monkeypatch, *(senfd.sate.Understood("command", c) for c in choices))
    text, tried = senfd.sate.respond(spec, question, vocabulary, llm="x")
    assert "so this is not known" in text
    assert len(tried) == 3


def test_a_language_model_told_it_chose_another_command_may_choose_again(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.sate.Understood("command", "Foo Get"),
        senfd.sate.Understood("command", "foo set"),
    )
    text, tried = senfd.sate.respond(
        spec, "What is the opcode of Foo Set?", vocabulary, llm="x"
    )
    assert "### Foo Set" in text
    assert told[-1].startswith("The question is about Foo Set")


def test_a_register_the_model_lacks_is_said_to_the_language_model(
    spec, vocabulary, monkeypatch
):
    told = choosing(
        monkeypatch,
        senfd.sate.Understood("register", "NOPE"),
        senfd.sate.Understood("register", "foocap"),
    )
    text, _ = senfd.sate.respond(spec, "What is FOOCAP?", vocabulary, llm="x")
    assert told[-1].startswith("No register NOPE")
    assert "FOOCAP - Foo Capabilities" in text


def test_a_list_of_what_a_name_matches_is_no_answer_to_a_language_model(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, *[senfd.sate.Understood("structure", "foo")] * 3)
    text, _ = senfd.sate.respond(spec, "What is the foo?", vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_question_without_terms_grounds_no_choice_of_a_language_model(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.sate.Understood("command", "ding"))
    text, _ = senfd.sate.respond(spec, "What is the opcode?", vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_name_of_generic_words_is_spotted():
    vocabulary = senfd.sate.Vocabulary(commands={"Set Features"})
    assert reading.spot("What is the opcode of Set Features?", vocabulary) == (
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
    assert phrasing.terms(question) == expected


def test_mentioning_is_of_whole_words():
    assert grounding.unmentioned("opcode of format", ["Information"]) == ["format"]


@pytest.mark.parametrize(
    "question, understood",
    [
        ("What is the opcode of Ding in NVMe 2.0?", "command('Ding', opcode=True)"),
        ("opcode of migrate", "command('Foo Migrate', opcode=True)"),
        ("What is FOOCAP of Ding?", "register('FOOCAP')"),
    ],
)
def test_a_question_asking_for_an_opcode_is_of_a_command(
    vocabulary, question, understood
):
    assert str(senfd.sate.understand(question, vocabulary)) == understood


def test_a_language_model_not_answering_is_said_so(spec, vocabulary, monkeypatch):
    def unreachable(url, messages, model=None):
        raise OSError("connection refused")

    monkeypatch.setattr(language_model, "choose", unreachable)
    text = senfd.sate.reply(spec, "opcode of ding", vocabulary, "http://nowhere")
    assert text.startswith("The language model at http://nowhere did not choose")


def test_a_model_not_there_is_said_so(capsys):
    assert senfd.sate.main(["--spec", "/no/such/model.json", "opcode of ding"]) == 1
    assert "no data model to answer from" in capsys.readouterr().err


@pytest.mark.parametrize(
    "question, choice",
    [
        # Of the kind the question asks of
        ("What is log page C0h?", senfd.sate.Understood("feature", "c0h")),
        ("What is feature C1h?", senfd.sate.Understood("log_page", "c1h")),
        # Of the dword the question asks of
        ("dword 10 of ding", senfd.sate.Understood("command", "ding", 11)),
        # A command's opcode, not a search mentioning it
        ("What is the opcode of Ding?", senfd.sate.Understood("search", "FCNT")),
        # A register named by its acronym, not a search mentioning it
        ("What is register FOOCAP?", senfd.sate.Understood("search", "FOOCAP")),
    ],
)
def test_a_language_model_choosing_another_kind_of_answer_is_not_shown(
    spec, vocabulary, monkeypatch, question, choice
):
    choosing(monkeypatch, *[choice] * 3)
    text, _ = senfd.sate.respond(spec, question, vocabulary, llm="x")
    assert "so this is not known" in text


def test_a_field_named_as_a_kind_in_a_command_is_of_the_command(
    spec, vocabulary, monkeypatch
):
    choosing(monkeypatch, senfd.sate.Understood("command", "foo get"))
    text, _ = senfd.sate.respond(
        spec, "Where is the feature identifier in Foo Get?", vocabulary, llm="x"
    )
    assert "so this is not known" not in text


def test_a_search_asked_for_is_answered(spec, vocabulary):
    text, _ = senfd.sate.respond(spec, "search FCNT", vocabulary)
    assert "so this is not known" not in text


def test_a_structure_is_named_by_what_its_command_qualifies(spec, vocabulary):
    question = "At which byte of the Foo Namespace data structure is FSZE?"
    assert reading.spot(question, vocabulary) == (
        "structure",
        "Identify - Foo Namespace",
    )
    text, _ = senfd.sate.respond(spec, question, vocabulary)
    assert "**Identify - Foo Namespace, bytes [example, 4, Figure 36" in text
    assert "| 07:00 | Foo Size | FSZE |" in text
    # A word after the dash is a qualifier, "Data" of "Dong - Data", not a name
    assert reading.spot("What is the Dong data?", vocabulary) == (
        "structure",
        "Dong - Data",
    )
    assert reading.spot("Is there a log page about foo?", vocabulary) is None
    assert phrasing.terms("the opcode of the NVMe-MI VPD Read command") == [
        "vpd",
        "read",
    ]


def test_the_identifier_of_a_name_a_command_and_a_log_page_share_is_the_log_page_s(
    vocabulary,
):
    both = senfd.sate.Vocabulary(
        commands=set(vocabulary.commands) | {"Get Log Page"},
        log_pages=set(vocabulary.log_pages) | {"Ding"},
    )
    understood = senfd.sate.understand("What is the Log Page Identifier of Ding?", both)
    assert str(understood) == "log_page('ding')"
    assert str(senfd.sate.understand("the LID of Ding", both)) == "log_page('ding')"
    # The identifier in the command carrying the log pages is the command's
    carrier = senfd.sate.understand("the log page identifier of Get Log Page", both)
    assert str(carrier) == "command('Get Log Page')"
    assert reading.kind_asked("the feature identifier for foo") == "feature"


def test_a_command_named_in_a_structure_s_name_does_not_answer_for_it(spec, vocabulary):
    vocabulary = senfd.sate.Vocabulary(
        commands=set(vocabulary.commands),
        structures=set(vocabulary.structures) | {"Ding Report"},
    )
    command = senfd.sate.Understood("command", "Ding")
    lines = lookup.answer(spec, command)
    question = "What is the Ding Report structure?"
    assert grounding.elsewhere(question, command, lines, vocabulary) == "Ding Report"


def test_a_field_acronym_that_is_a_register_s_too_is_of_the_structure_named(
    vocabulary,
):
    understood = senfd.sate.understand(
        "What is the FOOCAP field of the Foo Descriptor structure?", vocabulary
    )
    assert str(understood) == "structure('Foo Descriptor')"


@pytest.mark.parametrize(
    "question, understood, shows",
    [
        (
            "help",
            "help('')",
            "| `dwords of write` | the opcode, command-dwords and fields |",
        ),
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
    text, tried = senfd.sate.respond(spec, question, vocabulary)
    assert tried == [understood]
    assert shows in text


@pytest.mark.parametrize(
    "choice, shown",
    [
        (senfd.sate.Understood("structure", "foo entry"), False),
        (senfd.sate.Understood("structure", "foo descriptor"), True),
    ],
)
def test_a_lookup_by_name_is_of_the_thing_the_question_names(
    spec, vocabulary, monkeypatch, choice, shown
):
    choosing(monkeypatch, *[choice] * 3)
    text, _ = senfd.sate.respond(
        spec, "What is the Foo Descriptor structure?", vocabulary, llm="x"
    )
    assert ("so this is not known" not in text) == shown


def session_answering(monkeypatch, *typed):
    """Have sate's prompt read 'typed', as if at a terminal, and keep the
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
    monkeypatch.setattr(senfd.sate.session, "PromptSession", session)
    return made, stack


def test_the_session_answers_each_question_until_the_input_ends(
    spec, monkeypatch, capsys
):
    made, stack = session_answering(monkeypatch, "opcode of ding", "", "C0h")
    with stack:
        assert senfd.sate.session.interact(spec) == 0
    out = capsys.readouterr().out
    assert "sate answers these forms of question" in out
    assert "Ding: Foobar command, opcode 01h" in out
    assert "Feature C0h Foo Config" in out


def test_the_session_completes_the_names_of_the_model(spec, monkeypatch, capsys):
    from prompt_toolkit.document import Document

    made, stack = session_answering(monkeypatch)
    with stack:
        senfd.sate.session.interact(spec)
    assert "sate answers these forms of question" in capsys.readouterr().out
    completer = made[0].completer
    shown = list(completer.get_completions(Document("opcode of Foo Sta"), None))
    assert (shown[0].text, shown[0].start_position) == ("Foo Statistics", -7)
    assert shown[0].display_meta_text == "log page"


def test_the_session_shows_what_it_recognises_and_how_it_reads(
    spec, vocabulary, monkeypatch, capsys
):
    from prompt_toolkit.document import Document

    made, stack = session_answering(monkeypatch)
    with stack:
        senfd.sate.session.interact(spec, source=Path("model.json"))
    out = capsys.readouterr().out
    assert "sate" in out and "8 commands" in out and "model.json" in out
    session = made[0]
    fragments = session.lexer.lex_document(Document("cdw10 of Ding"))(0)
    assert ("class:name", "Ding") in fragments
    shown = "".join(text for _, text in session.bottom_toolbar())
    assert "Ask of 8 commands" in shown and "Enter take it" in shown  # Its menu is open
    typed = "".join(
        text for _, text in senfd.sate.session.toolbar("cdw10 of Ding", vocabulary)
    )
    assert "Read as command('Ding', dword=10)" in typed
    assert session.key_bindings.get_bindings_for_keys(("?",))
    assert session.key_bindings.get_bindings_for_keys(("f1",))


def test_the_questions_asked_are_kept_for_the_next_session(
    spec, monkeypatch, capsys, tmp_path
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    made, stack = session_answering(monkeypatch, "opcode of ding")
    with stack:
        senfd.sate.session.interact(spec)
    capsys.readouterr()
    assert "opcode of ding" in (tmp_path / "senfd" / "ask-history").read_text()


def test_without_a_question_the_command_line_opens_the_session(monkeypatch, capsys):
    made, stack = session_answering(monkeypatch, "opcode of ding")
    model = str(Path("example") / "output" / "merged.spec.document.json")
    with stack:
        assert senfd.sate.main(["--spec", model]) == 0
    assert "opcode 01h" in capsys.readouterr().out


def test_a_register_named_by_one_generic_word_is_not_spotted_by_it():
    vocabulary = senfd.sate.Vocabulary(structures={"CMD - Command"})
    assert reading.spot("Which command is it?", vocabulary) is None
    assert reading.spot("What is the CMD - Command register?", vocabulary) == (
        "register",
        "CMD",
    )


def test_a_section_is_asked_for_by_its_number(spec, vocabulary):
    text, tried = senfd.sate.respond(spec, "section 1", vocabulary)
    assert tried == ["section('1')"]
    assert "- example 1.2 Ding command" in text


def test_an_opcode_asked_of_a_word_of_several_commands_is_not_known(spec, vocabulary):
    text, _ = senfd.sate.respond(spec, "opcode of foo directive", vocabulary)
    assert "the question names several commands rather than one" in text


def test_is_alone_does_not_ask_for_an_acronym(vocabulary):
    assert senfd.sate.completion.wanted("what is ", vocabulary) == ""
    assert not senfd.sate.session.reading_so_far("what is ", vocabulary).startswith(
        " Next"
    )


def test_a_begun_question_offers_only_the_questions_it_may_be(vocabulary):
    assert {kind for _, _, kind, _, _ in completions(vocabulary, "which ")} == {
        "question"
    }


def test_a_one_letter_acronym_comes_after_the_longer(vocabulary):
    vocabulary = senfd.sate.Vocabulary(acronyms={"F", "FCNT"})
    shown = offered(vocabulary, "f")
    assert shown.index("FCNT") < shown.index("F")


@pytest.mark.parametrize(
    "plural, word",
    [
        ("queues", "queue"),
        ("pages", "page"),
        ("status", "status"),
        ("address", "address"),
        ("analysis", "analysis"),
    ],
)
def test_a_plural_s_is_taken_off_and_no_other(plural, word):
    assert phrasing.singular(plural) == word


def test_a_question_naming_nothing_is_answered_by_the_help(vocabulary):
    for question in ("[", "(", "what is the"):
        assert str(senfd.sate.understand(question, vocabulary)) == "help('')"


def test_a_dotted_acronym_is_recognised_whole_or_by_its_parts(spec, vocabulary):
    spans = recognised(vocabulary, "FOOCAP.FL and fcnt")
    assert [kind for _, _, kind in spans] == ["acronym", "acronym", "acronym"]
    assert "> **FL**" in senfd.sate.reply(
        spec, "Which bit of FOOCAP is FOOCAP.FL?", vocabulary
    )


def test_a_command_resolved_by_its_name_is_a_new_reading(spec, vocabulary):
    given = senfd.sate.Understood("command", "Admin Ding")
    taken = lookup.resolved(spec, given, vocabulary)
    assert given.argument == "Admin Ding" and taken.argument == "Ding"


@pytest.mark.parametrize(
    "text, menu, first",
    [
        ("", False, " ? questions"),
        ("ding", False, " Tab complete"),
        ("ding", True, " Tab, Up, Down choose"),
    ],
)
def test_the_keys_shown_are_those_that_do_something_now(text, menu, first):
    assert senfd.sate.session.keys(text, menu).startswith(first)


def test_enter_in_the_menu_takes_the_completion_and_asks_nothing():
    class Buffer:
        complete_state = object()

    class Event:
        current_buffer = Buffer()

    event = Event()
    senfd.sate.session.take_completion(event)
    assert event.current_buffer.complete_state is None


def test_the_line_under_an_answer_marks_what_is_not_known():
    line = senfd.sate.session.status_of("read as x | 1 lookup | 1.0 ms | not known")
    assert line.plain == "read as x | 1 lookup | 1.0 ms | not known"
    assert any(span.style == "yellow" for span in line.spans)


def test_the_fields_said_are_the_quoted_lines_ending_an_answer():
    markdown = "| a | b |\n\n> **FL**, Foo, is bit 0\n>\n> **FC**, Fc, is bit 1"
    assert senfd.sate.session.said(markdown) == (
        "> **FL**, Foo, is bit 0\n>\n> **FC**, Fc, is bit 1"
    )


def test_a_failed_lookup_ends_the_answer_not_the_session(spec, monkeypatch, capsys):
    def failing(*args, **kwargs):
        raise ValueError("broken")

    monkeypatch.setattr(senfd.sate.session, "exchange", failing)
    made, stack = session_answering(monkeypatch, "opcode of ding", "C0h")
    with stack:
        assert senfd.sate.session.interact(spec) == 0
    assert capsys.readouterr().out.count("failed to answer") == 2


def test_the_session_answer_does_not_say_twice_what_it_was_read_as(spec, vocabulary):
    markdown, status = senfd.sate.exchange(
        spec, "cdw10 of ding", vocabulary, said_as=False
    )
    assert "Understood as" not in markdown and status.startswith("read as")


def test_a_feature_by_identifier_is_that_feature_whatever_carries_it(spec, vocabulary):
    carrying = senfd.sate.Vocabulary(
        commands=set(vocabulary.commands) | {"Set Features"},
        features=set(vocabulary.features),
    )
    question = "What is feature C0h of Set Features?"
    understood = senfd.sate.understand(question, carrying)
    assert str(understood) == "feature('c0h')"
    lines = lookup.answer(spec, understood)
    assert grounding.elsewhere(question, understood, lines, carrying) is None


def test_which_kind_is_asked_of_though_a_command_lends_it_a_word(vocabulary):
    understood = senfd.sate.understand(
        "Which log page reports the Ding reads?", vocabulary
    )
    assert understood.query == "log_page"
    understood = senfd.sate.understand("What is the opcode of Ding?", vocabulary)
    assert understood.query == "command"


def test_a_feature_is_found_by_the_field_it_holds(spec, vocabulary):
    text = senfd.sate.reply(spec, "Which feature sets the foo level?", vocabulary)
    assert "### Feature C0h Foo Config" in text
    assert "> **" in text and "Foo Level" in text


def test_a_generic_word_is_no_term_in_its_plural_either():
    assert phrasing.terms("Which feature sets the foo levels?") == ["foo", "level"]


def test_the_table_of_forms_is_at_most_80_columns_wide_and_answers_are_not(
    monkeypatch,
):
    monkeypatch.setenv("COLUMNS", "133")
    assert senfd.sate.session.console_for(phrasing.HELP).width == 80
    assert senfd.sate.session.console_for("- an answer").width == 133
    monkeypatch.setenv("COLUMNS", "60")
    assert senfd.sate.session.console_for(phrasing.HELP).width == 60


def test_the_one_shot_answer_is_as_wide_as_the_terminal(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "133")
    senfd.sate.cli.show("- " + "word " * 60)
    lines = capsys.readouterr().out.splitlines()
    assert max(len(line) for line in lines) > 80


def test_the_status_of_an_answer_comes_before_the_answer():
    """The status says how sate read the question; above the answer, a
    reader does not take it for a part of the answer"""

    import io

    from rich.console import Console

    out = io.StringIO()
    console = Console(file=out, width=80, color_system=None)
    senfd.sate.session.show(
        console, "cdw12 of write", "Force Unit Access", "read as x | 1 lookup"
    )
    text = out.getvalue()

    assert text.index("cdw12 of write") < text.index("read as x")
    assert text.index("read as x") < text.index("Force Unit Access")


def test_an_answer_opens_with_a_rule_naming_the_question_and_pages_when_tall(
    monkeypatch,
):
    import contextlib
    import io

    from rich.console import Console

    paged = []

    @contextlib.contextmanager
    def pager(self, pager=None, styles=False, links=False):
        paged.append((styles, links))  # Colour kept, and the citations' links
        yield

    monkeypatch.setattr(Console, "pager", pager)
    out = io.StringIO()
    console = Console(file=out, width=60, height=12, force_terminal=False)
    short = "| Bits | Name |\n|---|---|\n| 30 | Force Unit Access |"
    senfd.sate.session.show(console, "which bit is FUA", short, "right")
    assert "which bit is FUA" in out.getvalue().splitlines()[0] and not paged
    rows = "\n".join(
        f"| {n} | field {n} with a description long enough to wrap the line |"
        for n in range(8)
    )
    tall = "| Bits | Name |\n|---|---|\n" + rows + "\n> FUA is bit 30"
    senfd.sate.session.show(console, "cdw12 of write", tall, "right")
    assert paged == [(True, True)]
    assert "FUA is bit 30" in out.getvalue()  # Said again after the pager


@pytest.mark.parametrize(
    "question, understood",
    [
        ("describe cdw10 of ding", "command('Ding', dword=10, describe=True)"),
        ("explain FOOCAP", "register('FOOCAP', describe=True)"),
        ("describe feature C0h", "feature('c0h', describe=True)"),
        (
            "Describe the foo statistics log page",
            "log_page('Foo Statistics', describe=True)",
        ),
        ("describe", "help('', describe=True)"),
    ],
)
def test_a_question_led_by_describe_asks_for_the_descriptions_too(
    vocabulary, question, understood
):
    assert str(senfd.sate.understand(question, vocabulary)) == understood


def test_an_answer_asked_to_describe_gives_the_descriptions(spec, vocabulary):
    text, tried = senfd.sate.respond(spec, "describe cdw10 of ding", vocabulary)
    assert tried == ["command('Ding', dword=10, describe=True)"]
    assert "| Bits | Name | Acronym | Description |" in text
    assert "| 15:00 | Foo Count | FCNT | How many. |" in text
    plain, _ = senfd.sate.respond(spec, "cdw10 of ding", vocabulary)
    assert "Description" not in plain and "How many" not in plain
    structure, _ = senfd.sate.respond(spec, "explain FOOCAP", vocabulary)
    assert "| Description |" in structure


def test_describe_is_a_form_offered_and_told_of():
    assert "describe " in phrasing.WORDS
    assert "`describe cdw12 of write`" in phrasing.HELP
    assert phrasing.QUESTION_WORDS.search("explain CSTS") is not None
    assert "explain" in phrasing.GENERIC


def test_the_table_of_forms_gives_one_example_a_row():
    rows = [
        line
        for line in phrasing.FORMS.splitlines()
        if line.startswith("| ") and not line.startswith("| Question")
    ]
    assert "| Question | sate answers with |" in phrasing.FORMS
    assert rows
    assert [row for row in rows if not re.match(r"\| `[^`]+` \| [^`|]+ \|$", row)] == []


def test_each_row_of_the_table_of_forms_takes_at_most_two_lines():
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console(width=80)
    lines = [
        "".join(segment.text for segment in line).rstrip()
        for line in console.render_lines(
            Markdown(phrasing.FORMS), console.options, pad=False
        )
    ]
    table = lines[[n for n, line in enumerate(lines) if "─" in line][0] + 1 :]
    heights = []
    for line in table:
        if not line:
            continue
        if line.startswith("  "):
            heights[-1] += 1
        else:
            heights.append(1)
    assert len(heights) == 19
    assert max(heights) <= 2


@pytest.mark.parametrize(
    "typed, kind",
    [
        ("fid of ", "feature"),
        ("feature identifier of ", "feature"),
        ("lid of ", "log page"),
        ("lpi of ", "log page"),
        ("dwords of ", "command"),
        ("register ", "register"),
        ("offset of ", "register"),
        ("cns of ", "structure"),
    ],
)
def test_after_the_words_of_a_basic_question_every_name_of_its_kind_is_offered(
    typed, kind
):
    from senfd.sate.completion import completions
    from senfd.sate.vocabulary import Vocabulary

    vocabulary = Vocabulary(
        commands={"Write", "Read"},
        features={"Arbitration", "Timestamp"},
        log_pages={"Error Information", "Firmware Slot Information"},
        structures={
            "CSTS - Controller Status",
            "CC - Controller Configuration",
            "Identify - Identify Namespace",
            "Identify Controller",
            "Timestamp Change Event Format (Event Type 03h)",
        },
        registers={"CSTS", "CC"},
        cns={"Identify - Identify Namespace", "Identify Controller"},
    )
    names = {
        "feature": vocabulary.features,
        "log page": vocabulary.log_pages,
        "command": vocabulary.commands,
        "register": {"CSTS - Controller Status", "CC - Controller Configuration"},
        "structure": {"Identify - Identify Namespace", "Identify Controller"},
    }[kind]

    offered = completions(vocabulary, typed)

    assert {o.text for o in offered} == names
    assert {o.kind for o in offered} == {kind}


def test_a_structure_named_by_a_cns_entry_is_one_that_a_cns_value_returns(
    vocabulary,
):
    """CNS 1Ch of the example returns "Foo namespace data" """

    assert vocabulary.cns == {"Identify - Foo Namespace"}


def test_after_the_words_of_a_kind_only_names_of_that_kind_are_offered():
    from senfd.sate.completion import completions
    from senfd.sate.vocabulary import Vocabulary

    vocabulary = Vocabulary(
        features={"Timestamp", "Power Management"},
        structures={"Timestamp Change Event Format (Event Type 03h)"},
    )
    offered = completions(vocabulary, "which feature is Timest")
    assert [(o.text, o.kind) for o in offered] == [("Timestamp", "feature")]
    # The feature typed in full is listed, without the longer structure name
    offered = completions(vocabulary, "which feature is Timestamp")
    assert [(o.text, o.kind) for o in offered] == [("Timestamp", "feature")]
    # Asked of a structure, the figure of the event is what is offered
    offered = completions(vocabulary, "structure Timestamp")
    assert [o.kind for o in offered] == ["structure"]


def test_the_opcode_asked_alone_is_answered_alone(spec, vocabulary):
    from senfd.sate.lookup import answer

    lines = answer(spec, senfd.sate.understand("opcode of ding", vocabulary))
    assert len(lines) == 1 and "opcode 01h" in lines[0] and "Ding" in lines[0]
    whole = answer(spec, senfd.sate.understand("ding", vocabulary))
    assert len(whole) > 1 and whole[0] == lines[0]


def test_a_field_searched_for_with_describe_has_its_description(spec, vocabulary):
    from senfd.sate.lookup import answer

    plain = answer(spec, senfd.sate.understand("FCNT", vocabulary))
    told = answer(spec, senfd.sate.understand("describe FCNT", vocabulary))
    assert any("Foo Count" in line for line in plain)
    assert not any("How many." in line for line in plain)
    assert any("Foo Count" in line and "How many." in line for line in told)


@pytest.mark.parametrize(
    "text, query, near",
    [
        ("dimg", "command", ["Ding"]),
        ("foo", "command", ["Foo Get", "Foo Set", "Foo Migrate"]),
        ("foo statistic", "log_page", ["Foo Statistics"]),
        ("fcnt", "", ["FCNT", "RCNT"]),
        ("c0h", "feature", []),
    ],
)
def test_near_suggests_names_for_an_unknown_question(vocabulary, text, query, near):
    assert vocabulary.near(text, query, most=3) == near


def test_a_name_typed_in_full_is_listed_in_any_case(vocabulary):
    assert offered(vocabulary, "Ding")[:1] == ["Ding"]
    assert offered(vocabulary, "ding")[:1] == ["Ding"]


def test_the_session_menu_colours_the_names_of_a_question(vocabulary):
    offer = completions(vocabulary, "which b")[0]

    assert senfd.sate.session.shown(offer)[:4] == [
        ("", "which bit of cdw"),
        ("class:name", "10"),
        ("", " of "),
        ("class:name", "Ding"),
    ]
    assert ("class:acronym", "FCNT") in senfd.sate.session.shown(offer)
    plain = completions(vocabulary, "opcode of di")[0]
    assert senfd.sate.session.shown(plain) == [("", "Ding")]
