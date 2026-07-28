#!/usr/bin/env python3
"""Render and validate a case link chart from entities.jsonl and events.jsonl.

Phase 2, standard library only (CONTRACT.md section 10). No network. Read-only:
the case directory is never written to.

    python graph.py cases/acme-corp-2026-07                  # mermaid, the default
    python graph.py cases/acme-corp-2026-07 --format dot
    python graph.py cases/acme-corp-2026-07 --format text
    python graph.py cases/acme-corp-2026-07 --validate       # pre-report gate
    python graph.py --selfcheck

--validate is the mechanical half of the identity-confusion guard (PLAN.md section 4,
non-negotiable 5), which is otherwise enforced only in prose. Run it before rendering
and before compiling a report: a chart of unvalidated entities draws an unresolved
identity as one confident node, which is the exact error candidate_group exists to
prevent. It checks entities.jsonl only; events.jsonl is rendered, not validated,
beyond flagging an actor_entity that has no entity row.

Node styling carries meaning, never decoration: shape is the entity class, border
weight is the confidence band, and a candidate_group renders as a cluster labelled
UNRESOLVED with dashed member edges. The legend is emitted as comments inside the
source so the file stays valid when piped to disk.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, NamedTuple

# scripts/selectors.py, not the stdlib `selectors` module: when this file runs as a
# script its own directory is sys.path[0], so the local module wins. Imported from
# anywhere else the stdlib module answers and has no normalize(), which raises
# ImportError and drops to the fallback below. Normalization only affects duplicate
# detection, so degrading is safe; guessing a different normal form would not be.
try:
    from selectors import normalize as _normalize  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on how this file is loaded
    _normalize = None

# CONTRACT.md section 4. Exact strings, no synonyms, no plurals.
SELECTOR_TYPES: tuple[str, ...] = (
    "email", "username", "person_name", "phone", "domain", "subdomain", "ip", "asn",
    "netblock", "url", "ssl_cert", "company", "company_number", "address", "photo",
    "video", "document", "crypto_address", "tx_hash", "vehicle_plate", "vessel",
    "aircraft", "coordinates", "file_hash", "social_profile", "breach_record",
)

# CONTRACT.md section 6: source reliability letter + information credibility digit.
GRADES = frozenset(letter + digit for letter in "ABCDEF" for digit in "123456")

# CONTRACT.md section 7 key set for an entities.jsonl line.
REQUIRED_FIELDS = (
    "id", "type", "value", "first_seen", "grade", "sources", "candidate_group", "notes",
)

RE_ENTITY_ID = re.compile(r"^e-[0-9]+$")
RE_GROUP_ID = re.compile(r"^cg-[0-9]+$")
# A merge note has to NAME its linking datapoint by canonical type (40-analysis.md).
RE_LINKING_DATAPOINT = re.compile(r"\b(" + "|".join(SELECTOR_TYPES) + r")\b")

_FAMILY_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("person", ("person_name", "username", "email", "phone", "social_profile")),
    ("org", ("company", "company_number")),
    ("infra", ("domain", "subdomain", "ip", "asn", "netblock", "url", "ssl_cert")),
    ("place", ("address", "coordinates")),
    ("artifact", ("photo", "video", "document", "file_hash", "breach_record")),
    ("chain", ("crypto_address", "tx_hash")),
    ("transport", ("vehicle_plate", "vessel", "aircraft")),
)
FAMILY: dict[str, str] = {t: fam for fam, types in _FAMILY_TYPES for t in types}

MERMAID_SHAPE = {
    "person": ("([", "])"),
    "org": ("{{", "}}"),
    "infra": ("[", "]"),
    "place": ("[/", "/]"),
    "artifact": ("[[", "]]"),
    "chain": ("[(", ")]"),
    "transport": ("((", "))"),
    "event": ("{", "}"),
    "other": ("[", "]"),
}
DOT_SHAPE = {
    "person": "ellipse",
    "org": "hexagon",
    "infra": "box",
    "place": "parallelogram",
    "artifact": "note",
    "chain": "cylinder",
    "transport": "circle",
    "event": "diamond",
    "other": "box",
}
MERMAID_BAND = {
    "strong": "stroke-width:3px",
    "moderate": "stroke-width:1.5px",
    "weak": "stroke-dasharray:6,stroke-width:1px",
}
DOT_BAND = {
    "strong": 'penwidth=3',
    "moderate": 'penwidth=1.4',
    "weak": 'penwidth=1, style="dashed"',
}
SHAPE_WORDS = {
    "mermaid": ("stadium person/account, hexagon company, rectangle infrastructure, "
                "parallelogram place, subroutine artifact, cylinder crypto, "
                "circle transport, rhombus event"),
    "dot": ("ellipse person/account, hexagon company, box infrastructure, "
            "parallelogram place, note artifact, cylinder crypto, "
            "circle transport, diamond event"),
    "text": "the type column carries the entity class",
}

CANDIDATE_EDGE_LABEL = "candidate group, unresolved"


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> tuple[list[tuple[int, dict]], list[tuple[int, str]]]:
    """Return ([(lineno, object)], [(lineno, error)]). Blank lines are skipped.

    A malformed line is reported, never guessed at and never silently dropped.
    """
    records: list[tuple[int, dict]] = []
    errors: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append((n, f"line is not valid JSON ({exc.msg})"))
            continue
        if not isinstance(obj, dict):
            errors.append((n, "line is valid JSON but not an object"))
            continue
        records.append((n, obj))
    return records, errors


def latest_by_id(records: Iterable[tuple[int, dict]]) -> dict[str, dict]:
    """Last row per id wins. entities.jsonl is append-only: a later row supersedes,
    and insertion order is the order the id was first seen, so charts are stable."""
    out: dict[str, dict] = {}
    for _, rec in records:
        eid = rec.get("id")
        if isinstance(eid, str) and eid:
            out[eid] = rec
    return out


def norm_value(value: object, type_: object) -> str:
    """Canonical form used for duplicate detection, from selectors.py where available."""
    v, t = str(value or ""), str(type_ or "")
    if _normalize is not None:
        try:
            return _normalize(v, t)
        except Exception:  # a normaliser that crashes must not take the validator down
            pass
    return " ".join(v.split()).lower()


def band(grade: object) -> str:
    """Confidence band for rendering. The Admiralty pair printed on the node is
    authoritative; this is a three-way visual projection of it and nothing more.
    Reliability grades the source, credibility grades the claim, and they are never
    collapsed into one score (41-confidence.md) - which is why the pair is always
    on the node. An unusable grade renders weak: a malformed entity must never look
    more confident than a graded one."""
    g = str(grade or "").strip()
    if g not in GRADES:
        return "weak"
    letter, digit = g[0], g[1]
    if letter in "AB" and digit in "12":
        return "strong"
    if letter in "EF" or digit in "456":
        return "weak"
    return "moderate"


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

class Violation(NamedTuple):
    rule: str
    entity: str
    line: int
    problem: str
    fix: str


def _groups_ever(records: Iterable[tuple[int, dict]]) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """Group membership across every row, not just the latest.

    A merge row may clear candidate_group to null; membership still has to count the
    sibling, or resolving one half of a pair would silently look like a singleton.
    """
    members: dict[str, list[str]] = {}
    of_id: dict[str, set[str]] = {}
    for _, rec in records:
        eid, cg = rec.get("id"), rec.get("candidate_group")
        if not isinstance(eid, str) or not isinstance(cg, str) or not cg:
            continue
        if eid not in members.setdefault(cg, []):
            members[cg].append(eid)
        of_id.setdefault(eid, set()).add(cg)
    return members, of_id


def validate(records: list[tuple[int, dict]], errors: list[tuple[int, str]]) -> list[Violation]:
    """Every rule that can be checked mechanically against entities.jsonl."""
    out: list[Violation] = []

    for line, msg in errors:
        out.append(Violation(
            "bad-record", "?", line, msg,
            "one JSON object per line, UTF-8, no trailing comma; re-append the row correctly",
        ))

    rows_by_id: dict[str, list[tuple[int, dict]]] = {}
    for line, rec in records:
        eid = rec.get("id")
        if not isinstance(eid, str) or not RE_ENTITY_ID.match(eid):
            out.append(Violation(
                "bad-record", str(eid), line, f"id {eid!r} is not of the form e-<n>",
                "give the row a stable case-unique id e-<n>; never reuse or renumber one",
            ))
            continue
        rows_by_id.setdefault(eid, []).append((line, rec))

        missing = [f for f in REQUIRED_FIELDS if f not in rec]
        if missing:
            out.append(Violation(
                "bad-record", eid, line,
                "missing required field(s): " + ", ".join(missing),
                "CONTRACT.md section 7 fixes the key set; candidate_group may be null and "
                "notes may be empty, but both keys must be present",
            ))

        type_ = rec.get("type")
        if type_ not in SELECTOR_TYPES:
            out.append(Violation(
                "bad-type", eid, line, f"type {type_!r} is not a canonical selector type",
                "use one exact string from CONTRACT.md section 4 - no synonyms, no plurals; "
                "adding a type means amending section 4 first",
            ))

        grade = rec.get("grade")
        if grade not in GRADES:
            out.append(Violation(
                "bad-grade", eid, line, f"grade {grade!r} is outside the Admiralty set",
                "grade the source A-F and the claim 1-6 separately, e.g. A3 or C3; read "
                "references/41-confidence.md before assigning one",
            ))

        sources = rec.get("sources")
        if not isinstance(sources, list) or not [s for s in sources if str(s).strip()]:
            out.append(Violation(
                "no-sources", eid, line, "sources is empty or absent",
                "provenance or it does not exist: cite the ledger ts or the URL the value "
                "came from, or delete the row",
            ))

        cg = rec.get("candidate_group")
        if cg is not None and (not isinstance(cg, str) or not RE_GROUP_ID.match(cg)):
            out.append(Violation(
                "bad-record", eid, line, f"candidate_group {cg!r} is neither null nor cg-<n>",
                "null means no ambiguity was found, which is itself a claim; otherwise cg-<n>",
            ))

    # Same type, same normalized value, different ids, no group in common.
    seen: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for eid, rows in rows_by_id.items():
        line, rec = rows[-1]
        type_ = rec.get("type")
        if type_ not in SELECTOR_TYPES:
            continue
        key = (str(type_), norm_value(rec.get("value"), type_))
        if not key[1]:
            continue
        seen.setdefault(key, []).append((line, eid))

    members, groups_of = _groups_ever(records)

    for (type_, value), hits in seen.items():
        if len(hits) < 2:
            continue
        first_line, first_id = hits[0]
        for line, eid in hits[1:]:
            if groups_of.get(eid, set()) & groups_of.get(first_id, set()):
                continue
            out.append(Violation(
                "dup-value", eid, line,
                f"same type {type_} and same normalized value as {first_id} "
                f"(line {first_line}), different id, no shared candidate_group",
                f"if they might be the same thing put {eid} and {first_id} in one "
                "candidate_group cg-<n>; if they are the same observation recorded twice, "
                "drop the duplicate row",
            ))

    for cg, ids in members.items():
        if len(ids) == 1:
            eid = ids[0]
            line = rows_by_id[eid][-1][0] if eid in rows_by_id else 0
            out.append(Violation(
                "singleton-group", eid, line,
                f"candidate_group {cg} has one member; a group of one asserts nothing",
                "either the ambiguity resolved, and candidate_group should be null on a new "
                "appended row, or the sibling candidate was never recorded - append it",
            ))
            continue
        # A merge shows up as one id carrying more than one row: append-only, so the
        # superseding row keeps the id and gains a note.
        for eid in ids:
            rows = rows_by_id.get(eid, [])
            if len(rows) < 2:
                continue
            notes = " ".join(str(rec.get("notes") or "") for _, rec in rows)
            if RE_LINKING_DATAPOINT.search(notes):
                continue
            out.append(Violation(
                "merge-unlinked", eid, rows[-1][0],
                f"{eid} was superseded inside candidate_group {cg} but no linking datapoint "
                "is named in notes",
                "name the datapoint in notes: its canonical type, its literal value, its "
                "source, its retrieval ts and its grade. 'Multiple weak signals' is not a "
                "name, and Tier-3 datapoints never merge (references/40-analysis.md)",
            ))

    return sorted(out, key=lambda v: (v.line, v.rule, v.entity))


def render_validation(case: Path, records: list, violations: list[Violation]) -> str:
    entities = latest_by_id(records)
    members, _ = _groups_ever(records)
    head = (f"VALIDATE {case}: {len(records)} entity rows, {len(entities)} entities, "
            f"{len(members)} candidate group(s)")
    if not violations:
        return "\n".join([
            head,
            "PASS 0 violations. Nothing here clears the human checks in "
            "references/40-analysis.md; it clears the mechanical ones only.",
        ])
    rules = sorted({v.rule for v in violations})
    lines = [head, f"FAIL {len(violations)} violation(s), rules: {', '.join(rules)}", ""]
    for v in violations:
        lines.append(f"{v.entity} (line {v.line}) {v.rule}: {v.problem}")
        lines.append(f"    fix: {v.fix}")
    lines += ["", "Do not render a chart or compile a report over a failing case."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def legend(fmt: str) -> list[str]:
    return [
        "LEGEND - node styling is meaning, not decoration.",
        "shape = entity class: " + SHAPE_WORDS[fmt] + ".",
        "border = confidence band: thick strong (A-B with 1-2), plain moderate,",
        "  dashed weak (E-F, or credibility 4-6, or ungraded). The Admiralty pair printed",
        "  on every node is authoritative; the band never collapses the two axes into one",
        "  score. Reliability grades the source, credibility grades the claim.",
        "dashed edge labelled '" + CANDIDATE_EDGE_LABEL + "' inside an UNRESOLVED cluster",
        "  = candidate_group. Members are not the same entity, and no attribute of one",
        "  transfers to another, until a named linking datapoint says so.",
    ]


def _clip(s: str, n: int = 44) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def esc(text: object) -> str:
    """Mermaid-safe label text.

    Every structural character becomes a numeric entity, so a label can never open or
    close a shape, a link label or a quoted string. `#` goes first or later
    substitutions would be re-escaped.
    """
    t = " ".join(str(text).split())
    for a, b in (
        ("#", "#35;"), ('"', "#quot;"), ("<", "#lt;"), (">", "#gt;"), ("|", "#124;"),
        ("[", "#91;"), ("]", "#93;"), ("(", "#40;"), (")", "#41;"),
        ("{", "#123;"), ("}", "#125;"), ("\\", "#92;"),
    ):
        t = t.replace(a, b)
    return t


def nid(raw: str) -> str:
    """Diagram-safe node id. Entity ids are e-<n> and group ids cg-<n>, so the only
    substitution is the hyphen."""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(raw))


def _family(type_: object) -> str:
    return FAMILY.get(str(type_), "other")


def _entity_parts(eid: str, ent: dict) -> list[str]:
    return [f"{eid} {ent.get('type', '?')}", _clip(ent.get("value", "")), str(ent.get("grade") or "ungraded")]


def _event_parts(evid: str, ev: dict) -> list[str]:
    ts = str(ev.get("ts") or "?")
    precision = str(ev.get("precision") or "?")
    return [f"{evid} {ts} ({precision})", _clip(ev.get("description", "")),
            str(ev.get("grade") or "ungraded")]


class Chart(NamedTuple):
    entities: dict[str, dict]          # id -> latest row
    groups: dict[str, list[str]]       # cg -> member ids, current state
    events: list[tuple[str, dict]]     # (ev-<n>, row)
    edges: list[tuple[str, str, str]]  # (src, dst, kind) kind: attributed|candidate|event
    missing: list[str]                 # referenced ids with no entity row


def build_chart(records: list, event_records: list) -> Chart:
    entities = latest_by_id(records)
    groups: dict[str, list[str]] = {}
    for eid, ent in entities.items():
        cg = ent.get("candidate_group")
        if isinstance(cg, str) and cg:
            groups.setdefault(cg, []).append(eid)

    missing: list[str] = []

    def ref(target: object) -> str | None:
        t = str(target or "")
        if not t:
            return None
        if t not in entities and t not in missing:
            missing.append(t)
        return t

    edges: list[tuple[str, str, str]] = []
    for eid, ent in entities.items():
        target = ref(ent.get("attributed_to"))
        if target:
            edges.append((eid, target, "attributed"))
    # Chain the members of a group rather than joining every pair: n-1 edges say the
    # same thing as n(n-1)/2 and stay readable at n>3.
    for ids in groups.values():
        for a, b in zip(ids, ids[1:]):
            edges.append((a, b, "candidate"))

    events: list[tuple[str, dict]] = []
    for n, (_, ev) in enumerate(event_records, start=1):
        evid = f"ev-{n}"
        events.append((evid, ev))
        actor = ref(ev.get("actor_entity"))
        if actor:
            edges.append((actor, evid, "event"))
    events.sort(key=lambda pair: str(pair[1].get("ts") or ""))
    return Chart(entities, groups, events, edges, missing)


def render_mermaid(chart: Chart) -> str:
    lines = [f"%% {line}" for line in legend("mermaid")]
    lines.append("flowchart TD")
    grouped = {eid for ids in chart.groups.values() for eid in ids}

    def node(node_id: str, family: str, parts: list[str]) -> str:
        open_, close = MERMAID_SHAPE[family]
        label = "<br/>".join(esc(p) for p in parts if str(p).strip())
        return f'{nid(node_id)}{open_}"{label}"{close}'

    for cg, ids in chart.groups.items():
        lines.append(f'    subgraph {nid(cg)}["UNRESOLVED {esc(cg)}"]')
        for eid in ids:
            lines.append("        " + node(eid, _family(chart.entities[eid].get("type")),
                                           _entity_parts(eid, chart.entities[eid])))
        lines.append("    end")
    for eid, ent in chart.entities.items():
        if eid not in grouped:
            lines.append("    " + node(eid, _family(ent.get("type")), _entity_parts(eid, ent)))
    for evid, ev in chart.events:
        lines.append("    " + node(evid, "event", _event_parts(evid, ev)))
    for eid in chart.missing:
        lines.append("    " + node(eid, "other", [eid, "referenced, no entity row"]))

    for src, dst, kind in chart.edges:
        if kind == "attributed":
            lines.append(f"    {nid(src)} -->|attributed_to| {nid(dst)}")
        elif kind == "candidate":
            lines.append(f"    {nid(src)} -.->|{CANDIDATE_EDGE_LABEL}| {nid(dst)}")
        else:
            lines.append(f"    {nid(src)} --- {nid(dst)}")

    bands: dict[str, list[str]] = {}
    for eid, ent in chart.entities.items():
        bands.setdefault(band(ent.get("grade")), []).append(nid(eid))
    for evid, ev in chart.events:
        bands.setdefault(band(ev.get("grade")), []).append(nid(evid))
    for eid in chart.missing:
        bands.setdefault("weak", []).append(nid(eid))
    for name, style in MERMAID_BAND.items():
        if bands.get(name):
            lines.append(f"    classDef {name} {style}")
            lines.append(f"    class {','.join(bands[name])} {name}")
    return "\n".join(lines)


def _dot_label(parts: list[str]) -> str:
    body = "\\n".join(" ".join(str(p).split()) for p in parts if str(p).strip())
    return body.replace("\\", "\\\\").replace('"', '\\"').replace("\\\\n", "\\n")


def render_dot(chart: Chart) -> str:
    lines = [f"// {line}" for line in legend("dot")]
    lines += ["digraph osint_case {", '    graph [rankdir="TB"];', '    node [fontsize=10];']
    grouped = {eid for ids in chart.groups.values() for eid in ids}

    def node(node_id: str, family: str, parts: list[str], grade: object) -> str:
        return (f'    {nid(node_id)} [label="{_dot_label(parts)}", '
                f'shape={DOT_SHAPE[family]}, {DOT_BAND[band(grade)]}];')

    for cg, ids in chart.groups.items():
        lines.append(f"    subgraph cluster_{nid(cg)} {{")
        lines.append(f'        label="UNRESOLVED {cg}"; style="dashed";')
        for eid in ids:
            ent = chart.entities[eid]
            lines.append("    " + node(eid, _family(ent.get("type")),
                                       _entity_parts(eid, ent), ent.get("grade")))
        lines.append("    }")
    for eid, ent in chart.entities.items():
        if eid not in grouped:
            lines.append(node(eid, _family(ent.get("type")), _entity_parts(eid, ent), ent.get("grade")))
    for evid, ev in chart.events:
        lines.append(node(evid, "event", _event_parts(evid, ev), ev.get("grade")))
    for eid in chart.missing:
        lines.append(node(eid, "other", [eid, "referenced, no entity row"], None))

    for src, dst, kind in chart.edges:
        if kind == "attributed":
            lines.append(f'    {nid(src)} -> {nid(dst)} [label="attributed_to"];')
        elif kind == "candidate":
            lines.append(f'    {nid(src)} -> {nid(dst)} [label="{CANDIDATE_EDGE_LABEL}", '
                         'style="dashed", dir=none];')
        else:
            lines.append(f'    {nid(src)} -> {nid(dst)} [label="event", arrowhead=none];')
    lines.append("}")
    return "\n".join(lines)


def render_text(chart: Chart, case: Path) -> str:
    lines = [
        f"GRAPH {case}: {len(chart.entities)} entities, {len(chart.events)} events, "
        f"{len(chart.groups)} unresolved group(s)",
        "",
        "NODES",
        f"  {'id':<8}{'type':<16}{'band':<10}{'grade':<7}value",
    ]
    for eid, ent in chart.entities.items():
        lines.append(f"  {eid:<8}{str(ent.get('type', '?')):<16}{band(ent.get('grade')):<10}"
                     f"{str(ent.get('grade') or '-'):<7}{_clip(ent.get('value', ''), 60)}")
    if chart.missing:
        lines.append("")
        lines.append("REFERENCED WITH NO ENTITY ROW")
        for eid in chart.missing:
            lines.append(f"  {eid}")
    if chart.groups:
        lines.append("")
        lines.append("UNRESOLVED GROUPS")
        for cg, ids in chart.groups.items():
            lines.append(f"  {cg:<8}{', '.join(ids)}")
    lines.append("")
    lines.append("EDGES")
    if not chart.edges:
        lines.append("  none")
    for src, dst, kind in chart.edges:
        arrow = {"attributed": "--attributed_to-->",
                 "candidate": f"<..{CANDIDATE_EDGE_LABEL}..>",
                 "event": "--event-->"}[kind]
        lines.append(f"  {src} {arrow} {dst}")
    if chart.events:
        lines.append("")
        lines.append("EVENTS")
        for evid, ev in chart.events:
            lines.append(f"  {evid:<8}{str(ev.get('ts', '?')):<24}"
                         f"{str(ev.get('precision', '?')):<8}{str(ev.get('actor_entity', '?')):<8}"
                         f"{str(ev.get('grade') or '-'):<6}{_clip(ev.get('description', ''), 60)}")
    lines.append("")
    lines += legend("text")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graph.py",
        description="Render a case link chart from entities.jsonl and events.jsonl, "
                    "or validate entities.jsonl as a pre-report gate.",
        epilog="Exit codes: 0 ok, 1 validation violations found, 2 usage error, "
               "3 case directory or entities.jsonl unreadable. Read-only: nothing in "
               "the case directory is written.",
    )
    p.add_argument("case", nargs="?", metavar="CASE_DIR",
                   help="case directory holding entities.jsonl and events.jsonl")
    p.add_argument("--format", choices=("mermaid", "dot", "text"), default="mermaid",
                   help="output format (default: mermaid, which renders natively in "
                        "markdown and artifacts)")
    p.add_argument("--validate", action="store_true",
                   help="check entities.jsonl and exit non-zero on any violation; "
                        "renders nothing")
    p.add_argument("--selfcheck", action="store_true",
                   help="run internal assertions and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selfcheck:
        return demo()
    if not args.case:
        parser.error("CASE_DIR is required unless --selfcheck is given")

    case = Path(args.case)
    entities_path = case / "entities.jsonl"
    if not entities_path.is_file():
        print(f"error: {entities_path} not found - is {case} a case directory?", file=sys.stderr)
        return 3
    try:
        records, errors = load_jsonl(entities_path)
    except OSError as exc:
        print(f"error: cannot read {entities_path}: {exc}", file=sys.stderr)
        return 3

    if args.validate:
        violations = validate(records, errors)
        print(render_validation(case, records, violations))
        return 1 if violations else 0

    events_path = case / "events.jsonl"
    event_records: list[tuple[int, dict]] = []
    if events_path.is_file():
        try:
            event_records, event_errors = load_jsonl(events_path)
        except OSError as exc:
            print(f"error: cannot read {events_path}: {exc}", file=sys.stderr)
            return 3
        for line, msg in event_errors:
            print(f"warning: {events_path} line {line}: {msg}", file=sys.stderr)

    violations = validate(records, errors)
    if violations:
        print(f"warning: {len(violations)} validation violation(s) in {entities_path}. "
              "Run --validate and fix them before this chart goes near a report.",
              file=sys.stderr)

    chart = build_chart(records, event_records)
    if args.format == "mermaid":
        print(render_mermaid(chart))
    elif args.format == "dot":
        print(render_dot(chart))
    else:
        print(render_text(chart, case))
    return 0


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

CLEAN = [
    # A2, not A1: an authoritative registry record consistent with other collected
    # material. One authoritative source alone never reaches A1 - only the
    # self-authenticating, independently mirrored CT entry in CLEAN_EVENTS does.
    (1, {"id": "e-1", "type": "domain", "value": "acme.example",
         "first_seen": "2026-07-28T09:00:00Z", "grade": "A2",
         "sources": ["2026-07-28T09:00:00Z"], "candidate_group": None,
         "notes": "RDAP registry record"}),
    (2, {"id": "e-2", "type": "person_name", "value": "Jan Novak",
         "first_seen": "2026-07-28T09:10:00Z", "grade": "C3",
         "sources": ["https://example.test/a"], "candidate_group": "cg-1",
         "notes": "resolvable by company_number on the filing"}),
    (3, {"id": "e-3", "type": "person_name", "value": "Jan Novak",
         "first_seen": "2026-07-28T09:11:00Z", "grade": "C3",
         "sources": ["https://example.test/b"], "candidate_group": "cg-1", "notes": ""}),
    (4, {"id": "e-4", "type": "email", "value": "jan@acme.example",
         "first_seen": "2026-07-28T09:20:00Z", "grade": "B2",
         "sources": ["2026-07-28T09:20:00Z"], "candidate_group": None,
         "notes": "", "attributed_to": "e-2"}),
    # A merge: same id appended again, naming the linking datapoint.
    (5, {"id": "e-3", "type": "person_name", "value": "Jan Novak",
         "first_seen": "2026-07-28T09:11:00Z", "grade": "B2",
         "sources": ["https://example.test/b", "https://example.test/c"],
         "candidate_group": "cg-1",
         "notes": "merged with e-2: company_number = 01234567 in two primary records "
                  "(Companies House, retrieved 2026-07-28T10:00:00Z, A2)"}),
]

CLEAN_EVENTS = [
    (1, {"ts": "2024-11-30", "actor_entity": "e-1",
         "description": "Certificate issued for mail.acme.example", "grade": "A1",
         "sources": ["https://crt.sh"], "precision": "day"}),
]

DIRTY = [
    (1, {"id": "e-10", "type": "domain", "value": "Acme.Example.",
         "first_seen": "2026-07-28T09:00:00Z", "grade": "A3",
         "sources": ["ts"], "candidate_group": None, "notes": ""}),
    (2, {"id": "e-11", "type": "domain", "value": "acme.example",
         "first_seen": "2026-07-28T09:01:00Z", "grade": "A3",
         "sources": ["ts"], "candidate_group": None, "notes": ""}),
    (3, {"id": "e-12", "type": "username", "value": "jnovak",
         "first_seen": "2026-07-28T09:02:00Z", "grade": "C3",
         "sources": ["ts"], "candidate_group": "cg-9", "notes": ""}),
    (4, {"id": "e-13", "type": "ip", "value": "192.0.2.1",
         "first_seen": "2026-07-28T09:03:00Z", "grade": "B7",
         "sources": ["ts"], "candidate_group": None, "notes": ""}),
    (5, {"id": "e-14", "type": "e_mail", "value": "a@example.test",
         "first_seen": "2026-07-28T09:04:00Z", "grade": "C3",
         "sources": ["ts"], "candidate_group": None, "notes": ""}),
    (6, {"id": "e-15", "type": "phone", "value": "+14155550100",
         "first_seen": "2026-07-28T09:05:00Z", "grade": "C3",
         "sources": [], "candidate_group": None, "notes": ""}),
    (7, {"id": "e-16", "type": "company", "value": "Acme Holdings",
         "first_seen": "2026-07-28T09:06:00Z", "grade": "A3",
         "sources": ["ts"], "candidate_group": "cg-8", "notes": ""}),
    (8, {"id": "e-17", "type": "company", "value": "Acme Holdings AS",
         "first_seen": "2026-07-28T09:07:00Z", "grade": "A3",
         "sources": ["ts"], "candidate_group": "cg-8", "notes": ""}),
    (9, {"id": "e-16", "type": "company", "value": "Acme Holdings",
         "first_seen": "2026-07-28T09:06:00Z", "grade": "A2",
         "sources": ["ts"], "candidate_group": "cg-8",
         "notes": "same as e-17, they look alike"}),
]


def _rules(violations: list[Violation]) -> set[str]:
    return {v.rule for v in violations}


def _entities_hit(violations: list[Violation], rule: str) -> set[str]:
    return {v.entity for v in violations if v.rule == rule}


def demo() -> int:
    # --- validation: does not fire on a clean graph -------------------------
    clean = validate(CLEAN, [])
    assert clean == [], f"clean graph produced violations: {clean}"

    # An entity with no ambiguity, an unresolved pair sharing a value inside one
    # candidate_group, and a merge naming its datapoint must all pass. A validator
    # that never passes is as useless as one that never fires.
    assert validate([CLEAN[0]], []) == []

    # --- validation: every rule fires on a crafted violation ----------------
    dirty = validate(DIRTY, [(99, "line is not valid JSON (Expecting value)")])
    fired = _rules(dirty)
    expected = {"bad-record", "bad-type", "bad-grade", "no-sources", "dup-value",
                "singleton-group", "merge-unlinked"}
    assert fired == expected, f"rules fired {sorted(fired)}, expected {sorted(expected)}"

    assert _entities_hit(dirty, "dup-value") == {"e-11"}, "trailing-dot domain must normalize equal"
    assert _entities_hit(dirty, "singleton-group") == {"e-12"}
    assert _entities_hit(dirty, "bad-grade") == {"e-13"}
    assert _entities_hit(dirty, "bad-type") == {"e-14"}
    assert _entities_hit(dirty, "no-sources") == {"e-15"}
    assert _entities_hit(dirty, "merge-unlinked") == {"e-16"}, \
        "a merge note with no named datapoint type must fire"
    assert all(v.fix for v in dirty), "every violation states what to do about it"
    assert all(v.line for v in dirty if v.rule != "singleton-group")

    # One rule at a time, so no rule is passing only because another masks it.
    only_dup = validate(DIRTY[:2], [])
    assert _rules(only_dup) == {"dup-value"}
    merged_ok = [DIRTY[6], DIRTY[7], dict_row(DIRTY[8], notes="merged with e-17: "
                 "company_number = 01234567 in two primary records (A2)")]
    assert _rules(validate(merged_ok, [])) == set(), "a named datapoint clears merge-unlinked"

    # Grades are the Admiralty pair, never one axis. A3 is not strong; E1 is not either.
    assert band("A1") == "strong" and band("B2") == "strong"
    assert band("A3") == "moderate" and band("C1") == "moderate"
    assert band("E1") == "weak" and band("F6") == "weak" and band("B4") == "weak"
    assert band(None) == "weak" and band("Z9") == "weak"

    # --- rendering ----------------------------------------------------------
    chart = build_chart(CLEAN, CLEAN_EVENTS)
    assert set(chart.entities) == {"e-1", "e-2", "e-3", "e-4"}
    assert chart.groups == {"cg-1": ["e-2", "e-3"]}
    assert ("e-4", "e-2", "attributed") in chart.edges
    assert ("e-2", "e-3", "candidate") in chart.edges
    assert ("e-1", "ev-1", "event") in chart.edges
    assert chart.missing == []

    mm = render_mermaid(chart)
    assert mm.splitlines()[-1].strip().startswith("class ")
    assert "flowchart TD" in mm
    assert 'subgraph cg_1["UNRESOLVED cg-1"]' in mm
    assert f"e_2 -.->|{CANDIDATE_EDGE_LABEL}| e_3" in mm
    assert "e_4 -->|attributed_to| e_2" in mm
    assert "classDef weak stroke-dasharray:6,stroke-width:1px" not in mm  # nothing weak here
    assert "classDef strong" in mm and "classDef moderate" in mm
    assert "%% LEGEND" in mm and "%% shape = entity class" in mm, "legend must ship in the source"
    assert "A1" in mm and "C3" in mm, "the Admiralty pair belongs on the node"

    # Mermaid plausibility: balanced, every referenced id declared, nothing unescaped.
    for open_, close in ("[]", "()", "{}"):
        assert mm.count(open_) == mm.count(close), f"unbalanced {open_}{close} in mermaid output"
    body = [ln.strip() for ln in mm.splitlines() if not ln.startswith("%%")]
    assert body.count("end") == sum(1 for ln in body if ln.startswith("subgraph"))
    declared = set(re.findall(r"^([A-Za-z0-9_]+)[\[\({]", "\n".join(body), re.M))
    referenced = set(re.findall(r"^([A-Za-z0-9_]+) [-.]", "\n".join(body), re.M))
    referenced |= set(re.findall(r"[->.|] ([A-Za-z0-9_]+)$", "\n".join(body), re.M))
    assert referenced <= declared, f"edge references an undeclared node: {referenced - declared}"

    nasty = [(1, {"id": "e-1", "type": "url",
                  "value": 'he said "x" <b> #1 | [drop} \\ (a)',
                  "first_seen": "2026-07-28T09:00:00Z", "grade": "C3",
                  "sources": ["ts"], "candidate_group": None, "notes": ""})]
    nm = render_mermaid(build_chart(nasty, []))
    label = [ln for ln in nm.splitlines() if ln.strip().startswith("e_1[")][0]
    inner = label.split('"')[1]
    for segment in inner.split("<br/>"):  # the separator is the only markup allowed
        for ch in '"<>|[]{}()\\':
            assert ch not in segment, f"{ch!r} survived escaping into a mermaid label"
    assert "#35;" in inner and "#quot;" in inner
    assert label.count('"') == 2, "exactly one quoted label per node"
    for open_, close in ("[]", "()", "{}"):
        assert nm.count(open_) == nm.count(close), "escaping must keep the source balanced"

    # A dangling actor_entity becomes a declared, visibly-flagged node, not a silent one.
    orphan = build_chart(CLEAN, [(1, {"ts": "2025-01-01", "actor_entity": "e-99",
                                      "description": "x", "grade": "C3",
                                      "sources": ["ts"], "precision": "day"})])
    assert orphan.missing == ["e-99"]
    om = render_mermaid(orphan)
    assert "e_99[" in om and "referenced, no entity row" in om

    dot = render_dot(chart)
    assert dot.startswith("// LEGEND")
    assert "digraph osint_case {" in dot and dot.rstrip().endswith("}")
    assert 'subgraph cluster_cg_1 {' in dot and 'label="UNRESOLVED cg-1"' in dot
    assert dot.count("{") == dot.count("}")
    assert f'label="{CANDIDATE_EDGE_LABEL}", style="dashed", dir=none' in dot
    assert "shape=ellipse" in dot and "shape=box" in dot and "shape=diamond" in dot
    dn = render_dot(build_chart(nasty, []))
    assert '\\"x\\"' in dn, "dot labels escape their own quotes"

    txt = render_text(chart, Path("cases/demo"))
    assert "UNRESOLVED GROUPS" in txt and "cg-1" in txt
    assert "e-4 --attributed_to--> e-2" in txt
    assert f"e-2 <..{CANDIDATE_EDGE_LABEL}..> e-3" in txt
    assert "LEGEND" in txt and "border = confidence band" in txt
    assert txt.isascii(), "output must survive a Windows console codepage"
    assert render_mermaid(chart).isascii() and render_dot(chart).isascii()

    # Empty case: renders, does not crash, does not invent nodes.
    empty = build_chart([], [])
    assert "flowchart TD" in render_mermaid(empty)
    assert "none" in render_text(empty, Path("cases/empty"))
    assert validate([], []) == []

    # Every canonical selector type has a shape, and every shape family is reachable.
    assert set(FAMILY) == set(SELECTOR_TYPES), "a selector type has no node shape"
    assert set(FAMILY.values()) | {"event", "other"} == set(MERMAID_SHAPE) == set(DOT_SHAPE)
    for open_, close in MERMAID_SHAPE.values():
        assert len(open_) == len(close), "shape delimiters must pair"

    # Rendering output states the validation posture rather than assuming it.
    report = render_validation(Path("cases/demo"), DIRTY, dirty)
    assert report.startswith("VALIDATE cases") and "FAIL" in report
    assert "fix:" in report and "Do not render a chart" in report
    assert "PASS 0 violations" in render_validation(Path("cases/demo"), CLEAN, [])

    print("selfcheck ok")
    return 0


def dict_row(row: tuple[int, dict], **overrides) -> tuple[int, dict]:
    """Copy a fixture row with fields replaced. Test helper only."""
    line, data = row
    merged = dict(data)
    merged.update(overrides)
    return line, merged


if __name__ == "__main__":
    sys.exit(main())
