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
