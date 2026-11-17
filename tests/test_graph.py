# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import json
from pathlib import Path

import senfd.query
from senfd.graph import graph_of

SPEC = Path("example") / "output" / "merged.spec.document.json"


def test_every_edge_of_the_graph_joins_two_of_its_nodes():
    graph = graph_of(senfd.query.load(SPEC))
    ids = {n["id"] for n in graph["nodes"]}
    assert len(ids) == len(graph["nodes"])
    assert all(e["s"] in ids and e["t"] in ids for e in graph["edges"])
    assert set(graph["figures"].values()) <= ids
    json.dumps(graph)


def test_each_command_feature_log_page_and_structure_is_a_node():
    spec = senfd.query.load(SPEC)
    graph = graph_of(spec)
    kinds = [n["kind"] for n in graph["nodes"]]
    assert kinds.count("command") == sum(
        len(c.commands) for c in spec.command_sets.values()
    )
    assert kinds.count("feature") == len(spec.features)
    assert kinds.count("logpage") == len(spec.log_pages)
    assert kinds.count("structure") == len(
        {(s.source.document, s.source.figure_nr) for s in spec.structures}
    )


def test_a_field_s_structure_is_an_edge_labelled_with_the_field():
    """Foo Entry 0 and Foo Entry 1 of the example are laid out by the
    structure "Foo Entry" """

    spec = senfd.query.load(SPEC)
    graph = graph_of(spec)
    nodes = {n["id"]: n for n in graph["nodes"]}
    linked = [
        (nodes[e["s"]]["label"], e["labels"])
        for e in graph["edges"]
        if e["kind"] == "link" and nodes[e["t"]]["label"] == "Foo Entry"
    ]
    assert linked and all(
        "Foo Entry 0" in labels or "Foo Entry 1" in labels for _, labels in linked
    )


def test_a_citation_s_figure_leads_to_its_node():
    """sate cites "example, 3.1, Figure 87, page 87"; the key of the figure
    is the document's short name and the figure number"""

    graph = graph_of(senfd.query.load(SPEC))
    nodes = {n["id"]: n for n in graph["nodes"]}
    figures = graph["figures"]
    assert nodes[figures["example:87"]]["label"] == "Foo Entry"
    # The dwords of a command lead to the command
    command = next(
        n for n in graph["nodes"] if n["kind"] == "command" and n.get("rows")
    )
    first = command["rows"][0]["desc"].removeprefix("Figure ")
    assert figures[f"example:{first}"] == command["id"]
    # The figure of the opcodes leads to the command set
    for node in graph["nodes"]:
        if node["kind"] == "command":
            key = f"{node['where']['doc']}:{node['where']['figure']}"
            assert nodes[figures[key]]["kind"] in ("cmdset", "command")


def test_a_cns_value_of_another_command_set_is_labelled_with_its_csi():
    """CNS 05h of Base selects the I/O Command Set specific Identify
    Namespace of each command set, labelled by its Command Set Identifier"""

    from senfd.documents.spec import link_selections
    from test_spec import selections_document

    document, base, foo, bar = selections_document()
    link_selections(document)
    graph = graph_of(document)
    labels = sorted(
        x for e in graph["edges"] if e["kind"] == "csi" for x in e["labels"]
    )
    assert "CNS 05h CSI 00h" in labels and "CNS 05h CSI 01h" in labels
    # CNS 00h cites the document, which the CSI does not select
    cited = [x for e in graph["edges"] if e["kind"] == "cns" for x in e["labels"]]
    assert "CNS 00h in Foo 1.3" in cited
    # The Command Set Identifiers lead to the documents they name
    assert any(e["t"] == "doc:Foo 1.3" for e in graph["edges"] if e["kind"] == "csi")


def test_a_command_set_says_its_kind_and_its_csi():
    """The map says that the Common I/O commands are no command set, and
    gives an I/O command set its CSI"""

    from senfd.documents.spec import CommandSet, SpecDocument

    document = SpecDocument()
    document.command_sets = {
        "common_io": CommandSet(name="Common I/O", kind="common_io"),
        "nvm": CommandSet(name="NVM", kind="io", identifier=0),
    }
    nodes = {n["id"]: n for n in graph_of(document)["nodes"]}
    assert "no command set" in nodes["cs:common_io"]["about"]
    assert nodes["cs:common_io"]["badge"] == "I/O commands"
    assert nodes["cs:common_io"]["csi"] is None
    assert (nodes["cs:nvm"]["about"], nodes["cs:nvm"]["csi"]) == ("I/O command set", 0)


def test_a_command_leads_to_each_status_value_that_affects_it():
    from senfd.documents.spec import (
        Command,
        CommandSet,
        Entry,
        Source,
        SpecDocument,
        Values,
        link_selections,
    )

    document = SpecDocument()
    document.command_sets = {
        "admin": CommandSet(
            name="Admin",
            commands={
                "abort": Command(
                    name="Abort", opcode=8, source=Source(document="Base", figure_nr=1)
                ),
                "identify": Command(
                    name="Identify",
                    opcode=6,
                    source=Source(document="Base", figure_nr=1),
                ),
            },
        )
    }
    document.values = [
        Values(
            kind="status_values",
            name="Status Code",
            source=Source(document="Base", figure_nr=104),
            entries=[
                Entry(value="00h", columns={"commands_affected": "Abort"}),
                Entry(value="01h", columns={"commands_affected": "Identify"}),
            ],
        )
    ]
    link_selections(document)
    graph = graph_of(document)
    nodes = {n["id"]: n for n in graph["nodes"]}

    edge = next(
        e
        for e in graph["edges"]
        if e["s"] == "cmd:admin:abort" and e["t"] == "val:Base:104"
    )
    assert edge["labels"] == ["status 00h"]
    shown = nodes["val:Base:104"]["entries"]
    assert shown[0]["commands"] == ["cmd:admin:abort"]
    # The command after one with status values keeps the key of its set
    assert shown[1]["commands"] == ["cmd:admin:identify"]


def test_a_case_leads_to_the_figure_of_its_controlling_field():
    """DPTR of Figure 93 has cases by PSDT of Figure 92"""

    from senfd.documents.spec import (
        Bits,
        Case,
        Selected,
        Source,
        SpecDocument,
        Structure,
        link_selectors,
    )

    def bits(acronym, unit="bits", **more):
        return Bits(
            unit=unit,
            upper=1,
            lower=0,
            range="1:0",
            acronym=acronym,
            name=acronym,
            role="field",
            kind="span",
            width=2,
            **more,
        )

    def structure(figure_nr, fields):
        return Structure(
            name=f"Figure {figure_nr}",
            kind="data_structure",
            unit="bytes",
            source=Source(document="Base", figure_nr=figure_nr),
            fields=fields,
        )

    cdw0 = structure(92, [bits("PSDT")])
    cases = [
        Case(
            selector="PSDT", when=[Selected(name="00b", value=0)], fields=[bits("PRP1")]
        )
    ]
    common = structure(
        93,
        [
            bits("CDW0", unit="bytes", structure=cdw0.source),
            bits("DPTR", description="If CDW0.PSDT is cleared to 00b", cases=cases),
        ],
    )
    document = SpecDocument()
    document.structures = [cdw0, common]
    link_selectors(document)
    graph = graph_of(document)
    nodes = {n["id"]: n for n in graph["nodes"]}

    edge = next(
        e for e in graph["edges"] if e["s"] == "st:Base:93" and e["t"] == "st:Base:92"
    )
    assert "PSDT, case of DPTR" in edge["labels"]
    dptr = next(r for r in nodes["st:Base:93"]["rows"] if r.get("acronym") == "DPTR")
    assert dptr["selected_by"] == {"PSDT": "st:Base:92"}
