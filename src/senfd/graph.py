# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
The data model as a graph, for the map of sate-web: a node for each
document, command set, command, feature, log page, structure and table of
values, and an edge for each relation the data model records between them.
A node of a figure is keyed by the document's short name and the figure
number, as "st:Base 2.4:93", so a citation of sate leads to it.
"""

from typing import Any, Dict, List, Optional, Tuple

from senfd.documents.spec import (
    Bits,
    Dwords,
    Entry,
    Source,
    SpecDocument,
    document_name,
)

Node = Dict[str, Any]
Edge = Dict[str, Any]

# The kinds of structures that the groups of a document hold, and their titles
GROUPS = {
    "register": "Registers",
    "data_structure": "Data structures",
    "log_page": "Log page layouts",
    "data_buffer": "Data buffers",
    "other": "Other figures",
    "status_values": "Status values",
    "values": "Tables of values",
}


def figure_key(source: Source) -> str:
    """The key of the figure of 'source', as "Base 2.4:93" """

    return f"{document_name(source.document)}:{source.figure_nr}"


class Graph:
    """The nodes and the edges, an edge merging the labels of a relation
    given more than once"""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[Tuple[str, str], Edge] = {}
        self.figures: Dict[str, str] = {}

    def node(self, nid: str, kind: str, label: str, **extra: Any) -> Node:
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "kind": kind, "label": label, **extra}
        return self.nodes[nid]

    def edge(self, source: str, target: str, label: str, kind: str = "link") -> None:
        if source == target or source not in self.nodes or target not in self.nodes:
            return
        edge = self.edges.setdefault(
            (source, target), {"s": source, "t": target, "kind": kind, "labels": []}
        )
        if label and label not in edge["labels"]:
            edge["labels"].append(label)

    def of(self, source: Optional[Source]) -> Optional[str]:
        """The node of the figure of 'source', if the graph has one"""

        return self.figures.get(figure_key(source)) if source else None


def where(source: Source) -> Dict[str, Any]:
    return {
        "doc": document_name(source.document),
        "figure": source.figure_nr,
        "section": source.section,
        "section_title": source.section_title,
        "page": source.page_nr,
    }


def entry_of(entry: Entry) -> Dict[str, Any]:
    return {
        "value": entry.value,
        "name": entry.name,
        "desc": entry.description,
        "columns": {k: v for k, v in entry.columns.items() if v},
    }


def rows_of(fields: List[Bits], depth: int = 0, case: str = "") -> List[Dict[str, Any]]:
    """The fields of a layout as the rows of a table, nested fields and the
    fields of each case below their field"""

    rows: List[Dict[str, Any]] = []
    for field in fields:
        row: Dict[str, Any] = {
            "range": field.range,
            "acronym": field.acronym,
            "name": field.name,
            "desc": field.description,
            "depth": depth,
            "values": [entry_of(e) for e in field.values],
            "links": [s for s in (field.structure, field.values_in) if s],
            "refers": [e.refers_to.source for e in field.values if e.refers_to],
        }
        if case:
            row["case"] = case
        rows.append(row)
        rows += rows_of(field.fields, depth + 1)
        for c in field.cases:
            when = ", ".join(w.name for w in c.when) or "all other values"
            if c.selector_in:
                row.setdefault("selectors", []).append((c.selector_in, c.selector))
            rows += rows_of(c.fields, depth + 1, f"{c.selector} = {when}")
            if c.values:
                rows.append(
                    {
                        "range": "",
                        "name": c.name or "",
                        "desc": "",
                        "depth": depth + 1,
                        "case": f"{c.selector} = {when}",
                        "values": [entry_of(e) for e in c.values],
                        "links": [],
                        "refers": [e.refers_to.source for e in c.values if e.refers_to],
                    }
                )
    return rows


def dword_rows(dwords: List[Dwords], side: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for dw in dwords:
        span = f"{dw.lower}" if dw.upper == dw.lower else f"{dw.lower}-{dw.upper}"
        name = f"{side} Dword {span}" + (f" if {dw.condition}" if dw.condition else "")
        rows.append(
            {"header": True, "name": name, "desc": f"Figure {dw.source.figure_nr}"}
        )
        rows += rows_of(dw.fields, 1)
    return rows


def graph_of(spec: SpecDocument) -> Dict[str, Any]:
    """The graph of 'spec', as a dictionary for JSON: its 'nodes', its
    'edges', and 'figures', the node of each figure by its key"""

    g = Graph()
    g.node("home", "home", "NVMe specifications")
    documents = (
        set(spec.documents)
        | {s.source.document for s in spec.structures}
        | {v.source.document for v in spec.values}
    )
    base = {d: document_name(d) for d in sorted(documents)}

    def group(document: str, kind: str) -> str:
        doc = document_name(document)
        gid = f"grp:{doc}:{kind}"
        g.node(gid, "group", f"{doc}: {GROUPS.get(kind, kind)}", where={"doc": doc})
        g.edge(f"doc:{doc}", gid, "", "contains")
        return gid

    for document, name in base.items():
        g.node(f"doc:{name}", "doc", name, title=document)
        g.edge("home", f"doc:{name}", "", "contains")

    for structure in spec.structures:
        nid = f"st:{figure_key(structure.source)}"
        g.node(
            nid,
            "structure",
            structure.name,
            sub=structure.kind,
            where=where(structure.source),
            rows=rows_of(structure.fields),
        )
        g.figures.setdefault(figure_key(structure.source), nid)
        if structure.kind not in ("command_dword", "completion_dword", "example"):
            g.edge(
                group(structure.source.document, structure.kind), nid, "", "contains"
            )
    for values in spec.values:
        nid = f"val:{figure_key(values.source)}"
        g.node(
            nid,
            "values",
            values.name or GROUPS.get(values.kind, values.kind),
            sub=values.kind,
            where=where(values.source),
            entries=[entry_of(e) for e in values.entries],
        )
        g.figures.setdefault(figure_key(values.source), nid)
        kind = "status_values" if values.kind == "status_values" else "values"
        if values.kind != "example":
            g.edge(group(values.source.document, kind), nid, "", "contains")

    # The commands of each status value, by its figure and value
    affects: Dict[Tuple[str, str], List[str]] = {}
    for key, command_set in spec.command_sets.items():
        cid = f"cs:{key}"
        g.node(cid, "cmdset", command_set.name)
        g.edge("home", cid, "", "contains")
        for name, command in command_set.commands.items():
            mid = f"cmd:{key}:{name}"
            rows = dword_rows(command.sqe, "SQE") + dword_rows(command.cqe, "CQE")
            for op in command.operations:
                selectors = ", ".join(f"{k}={v}" for k, v in op.selectors.items())
                rows.append(
                    {"header": True, "name": f"Operation {op.name}", "desc": selectors}
                )
                rows += dword_rows(op.sqe, "SQE") + dword_rows(op.cqe, "CQE")
            g.node(
                mid,
                "command",
                command.name,
                opcode=command.opcode,
                where=where(command.source),
                rows=rows,
            )
            g.edge(cid, mid, f"{command.opcode:02X}h", "contains")
            # The figure of the opcodes, which sate cites for a command
            g.figures.setdefault(figure_key(command.source), cid)
            for dw in command.sqe + command.cqe:
                g.figures.setdefault(figure_key(dw.source), mid)
            for table in command.status_values:
                g.edge(mid, f"val:{figure_key(table)}", "status values")
            for code in command.status_codes:
                g.edge(mid, f"val:{figure_key(code.source)}", f"status {code.value}")
                affects.setdefault((figure_key(code.source), code.value), []).append(
                    mid
                )
            for op in command.operations:
                for st in spec.structures:
                    if st.name in op.structures:
                        g.edge(
                            mid, f"st:{figure_key(st.source)}", f"{op.name} transfers"
                        )

    g.node("features", "group", "Features")
    g.node("log_pages", "group", "Log pages")
    g.edge("home", "features", "", "contains")
    g.edge("home", "log_pages", "", "contains")
    for key, feature in spec.features.items():
        fid = f"feat:{key}"
        g.node(
            fid,
            "feature",
            feature.name,
            identifier=feature.identifier,
            where=where(feature.source),
            rows=dword_rows(feature.sqe, "SQE") + dword_rows(feature.cqe, "CQE"),
        )
        g.edge("features", fid, f"{feature.identifier:02X}h", "contains")
        for dw in feature.sqe + feature.cqe:
            g.figures.setdefault(figure_key(dw.source), fid)
    for key, log_page in spec.log_pages.items():
        lid = f"lp:{key}"
        g.node(
            lid,
            "logpage",
            log_page.name,
            identifier=log_page.identifier,
            where=where(log_page.source),
        )
        g.edge("log_pages", lid, f"{log_page.identifier:02X}h", "contains")
        if log_page.structure:
            g.edge(lid, f"st:{figure_key(log_page.structure.source)}", "layout")

    # The links of the fields, and the values a value refers to
    for node in g.nodes.values():
        for row in node.get("rows", []):
            targets = [g.of(s) for s in row.pop("links", [])]
            row["targets"] = [t for t in targets if t]
            for t in row["targets"]:
                g.edge(node["id"], t, row.get("acronym") or row.get("name") or "")
            for s in row.pop("refers", []):
                t = g.of(s)
                if t:
                    g.edge(
                        node["id"], t, f"{row.get('acronym') or ''} values", "refers"
                    )
            # The figure of the field whose value selects a case of the row
            for s, selector in row.pop("selectors", []):
                t = g.of(s)
                if t:
                    row.setdefault("selected_by", {})[selector] = t
                    g.edge(node["id"], t, f"{selector}, case of {row.get('acronym')}")

    # What a CNS value selects, by the Command Set Identifier where it is of
    # another document; and the documents the Command Set Identifiers name
    csi = {
        e.document: e.value
        for values in spec.values
        for e in values.entries
        if e.document
    }
    for values in spec.values:
        vid = f"val:{figure_key(values.source)}"
        for entry, shown in zip(values.entries, g.nodes[vid]["entries"]):
            commands = affects.get((figure_key(values.source), entry.value))
            if commands:
                shown["commands"] = commands
            if entry.document:
                shown["document"] = f"doc:{document_name(entry.document)}"
                g.edge(vid, shown["document"], entry.value, "csi")
            for source in entry.selects:
                t = g.of(source)
                if not t:
                    continue
                label, kind = f"CNS {entry.value}", "cns"
                if source.document != values.source.document:
                    if (
                        entry.columns.get("csi", "").startswith("Y")
                        and source.document in csi
                    ):
                        label, kind = f"{label} CSI {csi[source.document]}", "csi"
                    else:
                        label += f" in {document_name(source.document)}"
                shown.setdefault("selects", []).append([t, label])
                g.edge(vid, t, label, kind)

    return {
        "nodes": list(g.nodes.values()),
        "edges": list(g.edges.values()),
        "figures": g.figures,
        "documents": sorted(base.values()),
    }
