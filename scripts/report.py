#!/usr/bin/env python3
"""Compile a case directory into the deliverable: markdown, HTML, or JSON.

Phase 3, standard library only (CONTRACT.md section 10). No network, at import or
at run time. Read-only unless --out is given: the case directory is never modified.

    python report.py cases/acme-2026-07                      # markdown, the default
    python report.py cases/acme-2026-07 --format html --out report/acme.html
    python report.py cases/acme-2026-07 --format json
    python report.py cases/acme-2026-07 --redact full
    python report.py --selfcheck

Nothing here is authored. Every line of the deliverable already exists in a case
file; a sentence with no upstream row is a collection gap, not a writing problem
(references/50-reporting.md). The compiler assembles, grades, redacts and refuses.
It does not write claims, and it does not write the BLUF: put that in
<case>/report/bluf.md when the body is finished, or the report ships with a visible
"not written" marker in section 2.

Section order and headings follow assets/report-template.md. Inputs follow the input
table in references/50-reporting.md. The JSON envelope is the one specified in that
file's "Machine-readable export" section, with two additions, both flagged here
because the reference does not define them: `source_file`, naming the case dir, and
`forced`, present only under --force.

THE GATE. Four checks refuse to compile, exit 1, and name every blocking item by id:

  ungraded      a finding with no grade, or a grade outside the Admiralty set
  unsourced     a finding with no source block
  merged        an unresolved candidate_group treated as resolved in authored text:
                a finding naming two or more members of one open group whose claim
                carries no estimative phrase and whose claim and reasoning carry
                none of the phrases that visibly hold the identity open — "no
                identity claim", "not merged", "unresolved", "candidate group",
                or the group id itself
  banned        a banned certainty word inside a finding (CONTRACT.md section 6):
                clearly, obviously, proves, definitely, and confirmed unless the
                credibility digit is 1

--force compiles anyway and stamps a loud override banner into the deliverable
itself, listing every failed check by id. The banner is not suppressible; that is
the whole point of allowing the flag at all.

Redaction is visible, never silent: a removed value is replaced by
"[redacted: <class>]" so a reader can see that something was withheld. Classes are
the PII list in references/00-legal-ethics.md section 5.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import sys
import tempfile
from pathlib import Path

# CONTRACT.md section 6.
GRADES = frozenset(letter + digit for letter in "ABCDEF" for digit in "123456")

# CONTRACT.md section 4. Exact strings, no synonyms, no plurals.
SELECTOR_TYPES: tuple[str, ...] = (
    "email", "username", "person_name", "phone", "domain", "subdomain", "ip", "asn",
    "netblock", "url", "ssl_cert", "company", "company_number", "address", "photo",
    "video", "document", "crypto_address", "tx_hash", "vehicle_plate", "vessel",
    "aircraft", "coordinates", "file_hash", "social_profile", "breach_record",
)

# CONTRACT.md section 6 / references/41-confidence.md. These seven, no synonyms.
ESTIMATIVE: tuple[str, ...] = (
    "almost no chance", "very unlikely", "unlikely", "roughly even chance",
    "likely", "very likely", "almost certain",
)

RE_BANNED = re.compile(r"\b(clearly|obviously|proves|definitely)\b", re.IGNORECASE)
RE_CONFIRMED = re.compile(r"\bconfirmed\b", re.IGNORECASE)
RE_FINDING_HEAD = re.compile(r"^###\s+(f-[0-9]+)\s*(?:[—\-–]\s*(.*))?$")
RE_ENTITY_ID = re.compile(r"\be-[0-9]+\b")
RE_QUESTION = re.compile(r"^Q([0-9]+)\.\s+(.+)$")
RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# Anchored at the start only, deliberately. A cell that merely OPENS with an angle
# bracket is template scaffolding even when it carries trailing prose: the skeleton
# ships `<earliest>..<latest>, or "no time bound"`, which a `$`-anchored pattern let
# through and which then shipped verbatim in a compiled deliverable.
RE_PLACEHOLDER = re.compile(r"^<[^>]*>")
RE_CELL_SPLIT = re.compile(r"(?<!\\)\|")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

TOP_KEYS = ("claim", "grade", "rung", "estimative", "answers", "entities", "mode",
            "handling", "sources", "reasoning", "alternatives", "disconfirms")
SCALAR_KEYS = tuple(k for k in TOP_KEYS if k not in ("sources", "alternatives"))
SOURCE_KEYS = ("url", "retrieved", "sha256", "source_grade", "archive_note", "mode")

# findings.md block field -> entity-schema.json finding object field.
SCHEMA_NAMES = {"rung": "inference_rung", "answers": "scope_question",
                "entities": "entity_refs", "disconfirms": "disconfirming_evidence",
                "alternatives": "alternatives_rejected"}

HANDLING_ORDER = {"none": 0, "": 0, "partial": 1, "withheld": 2}

# Phrases that visibly hold an identity open. The first two are the canonical wording
# in references/41-confidence.md (the `correlated` sentence pattern) and
# references/50-reporting.md (the unresolved-identity pattern); without them the gate
# would refuse correctly written correlated findings, which is worse than useless.
NON_MERGER_MARKERS = ("no identity claim", "not merged", "unresolved",
                      "candidate group", "candidate_group")

# references/00-legal-ethics.md section 5 PII classes, mapped onto the canonical
# selector types the case files actually carry. `address` is reported to the reader
# as "home address" because that is the class name the legal reference uses.
PII_CLASS = {"address": "home address"}
PARTIAL_TYPES = ("email", "phone", "person_name", "address", "coordinates", "crypto_address")
FULL_TYPES = PARTIAL_TYPES + ("username", "social_profile")


# ---------------------------------------------------------------------------
# generic parsing
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    """Case files are UTF-8 with LF; tolerate a BOM from a Windows editor."""
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def load_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if not path.is_file():
        return records, errors
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} line {n}: not valid JSON ({exc.msg})")
            continue
        if isinstance(obj, dict):
            records.append(obj)
        else:
            errors.append(f"{path.name} line {n}: not a JSON object")
    return records, errors


def split_cells(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [c.replace("\\|", "|").strip() for c in RE_CELL_SPLIT.split(body)]


def is_placeholder(cell: str) -> bool:
    bare = cell.strip().strip("`").strip()
    return not bare or bool(RE_PLACEHOLDER.match(bare)) or "|" in bare


def parse_tables(md: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every GFM table in a document, as (headers, rows). Placeholder rows dropped.

    A row is a placeholder when any cell is `<like this>` or carries a `a \\| b`
    alternation - both are template scaffolding, never a recorded value.
    """
    out: list[tuple[list[str], list[list[str]]]] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        here = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if here.startswith("|") and re.match(r"^\|[\s:\-|]+\|$", nxt):
            headers = [c.strip().strip("`").lower() for c in split_cells(lines[i])]
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_cells(lines[i])
                if not all(is_placeholder(c) for c in cells) and \
                        not any(is_placeholder(c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append((headers, rows))
            continue
        i += 1
    return out


def table_dicts(md: str, *required: str) -> list[dict]:
    """Rows of every table whose headers contain all of `required`, as dicts."""
    found: list[dict] = []
    for headers, rows in parse_tables(md):
        if not all(any(req in h for h in headers) for req in required):
            continue
        for row in rows:
            found.append({headers[i]: row[i].strip().strip("`")
                          for i in range(min(len(headers), len(row)))})
    return found


def split_alternative(text: str) -> tuple[str, str]:
    """`<hypothesis> — <why rejected>` -> the two halves; why is "" when absent.

    The skeleton writes an em dash, and an analyst on a Windows keyboard writes a
    hyphen. Both separate, so both are accepted here and the finding block and the
    hypothesis table agree — printing "not stated" over a reason that was stated is
    a false claim about the analyst's work.
    """
    for sep in (" — ", " - "):
        head, found, tail = text.partition(sep)
        if found:
            return head.strip(), tail.strip()
    return text.strip(), ""


def col(row: dict, *names: str) -> str:
    """First cell whose header contains one of `names`. Headers drift; ids do not."""
    for name in names:
        for key, value in row.items():
            if name in key:
                return value
    return ""


# ---------------------------------------------------------------------------
# case files
# ---------------------------------------------------------------------------

def section_lines(md: str, title: str) -> list[str]:
    """Lines under the first heading whose text contains `title`, up to the next heading."""
    out: list[str] = []
    inside = False
    for line in md.splitlines():
        if line.startswith("#"):
            if inside:
                break
            inside = title in line.lower()
            continue
        if inside:
            out.append(line)
    return out


def parse_scope(md: str) -> dict:
    """scope.md -> flat field map, numbered questions, out-of-bounds list.

    Reads every two-column table in the file; case_init.py writes the frozen intake
    fields as one, and the skeleton carries the rest across sections 2, 4 and 8.
    First value wins, so the machine-checkable table at the top is authoritative.
    """
    fields: dict[str, str] = {}
    for headers, rows in parse_tables(md):
        if len(headers) != 2:
            continue
        for row in rows:
            if len(row) < 2:
                continue
            key = row[0].strip().strip("`").lower()
            val = row[1].strip().strip("`").strip()
            if key and key not in fields and not is_placeholder(row[1]):
                fields[key] = val

    questions = []
    for line in md.splitlines():
        m = RE_QUESTION.match(line.strip())
        if m and not is_placeholder(m.group(2)):
            questions.append({"id": f"Q{m.group(1)}", "question": m.group(2).strip()})

    # Only section 6. The purpose-branch checklist in section 1 is also written with
    # [x] and is not an exclusion - reading the whole file put "security  Security /
    # threat intel..." into the out-of-bounds block of a live report.
    scoped = section_lines(md, "out of bounds") or md.splitlines()
    bounds = []
    for line in scoped:
        text = line.strip()
        if text.lower().startswith("[x]"):
            text = text[3:].strip()
        elif text.startswith("- "):
            text = text[2:].strip()
        else:
            continue
        if text and not is_placeholder(text) and "<" not in text:
            bounds.append(text)

    # "Not collected by design" is a fenced block inside the same section. Only fenced
    # lines count: the section's own prose about branch defaults is not an exclusion.
    not_collected = []
    fenced = False
    for line in scoped:
        text = line.strip()
        if text.startswith("```"):
            fenced = not fenced
            continue
        if fenced and text and "<" not in text and not text.startswith(("[", "-", "|")):
            not_collected.append(text)

    m = re.search(r"^active_allowed:\s*(\w+)", md, re.MULTILINE)
    if m and "active_allowed" not in fields:
        fields["active_allowed"] = m.group(1)
    m = re.search(r"^Decision this feeds:\s*`?(.+?)`?\s*$", md, re.MULTILINE)
    if m and not is_placeholder(m.group(1)):
        fields["decision"] = m.group(1)

    return {"fields": fields, "questions": questions, "out_of_bounds": bounds,
            "not_collected": not_collected}


def parse_finding_body(body: str) -> dict:
    """One fenced findings.md block -> field map. Format: case-skeleton/findings.md."""
    out: dict = {k: "" for k in SCALAR_KEYS}
    out["sources"] = []
    out["alternatives"] = []
    cur: str | None = None
    src: dict | None = None
    for raw in body.splitlines():
        if not raw.strip():
            continue
        indented = raw[:1].isspace()
        m = re.match(r"^([a-z0-9_]+):\s*(.*)$", raw)
        if m and not indented and m.group(1) in TOP_KEYS:
            cur = m.group(1)
            if cur == "sources":
                src = None
            elif cur != "alternatives":
                out[cur] = m.group(2).strip()
            continue
        if cur == "sources":
            head = re.match(r"^\s+([0-9]+)\.\s*(.*)$", raw)
            if head:
                src = {"source_name": head.group(2).strip()}
                src.update({k: "" for k in SOURCE_KEYS})
                out["sources"].append(src)
                continue
            sub = re.match(r"^\s+([a-z0-9_]+):\s*(.*)$", raw)
            if sub and src is not None and sub.group(1) in SOURCE_KEYS:
                src[sub.group(1)] = sub.group(2).strip()
                continue
            if src is not None and src.get("source_name"):
                src["source_name"] = (src["source_name"] + " " + raw.strip()).strip()
            continue
        if cur == "alternatives":
            item = re.match(r"^\s*-\s+(.*)$", raw)
            if item:
                out["alternatives"].append(item.group(1).strip())
            elif out["alternatives"]:
                out["alternatives"][-1] += " " + raw.strip()
            continue
        if cur:
            out[cur] = (str(out[cur]) + " " + raw.strip()).strip()
    return out


def parse_findings(md: str) -> list[dict]:
    """Every `### f-<n>` block with a fenced body. Ids stay in file order."""
    findings: list[dict] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        head = RE_FINDING_HEAD.match(lines[i].strip())
        if not head:
            i += 1
            continue
        label = (head.group(2) or "").strip()
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith("```"):
            if RE_FINDING_HEAD.match(lines[j].strip()):
                break
            j += 1
        if j >= len(lines) or not lines[j].strip().startswith("```"):
            findings.append({"id": head.group(1), "label": label, "line": i + 1,
                             "sources": [], "alternatives": [],
                             **{k: "" for k in SCALAR_KEYS}})
            i += 1
            continue
        k = j + 1
        while k < len(lines) and not lines[k].strip().startswith("```"):
            k += 1
        block = parse_finding_body("\n".join(lines[j + 1:k]))
        block["id"] = head.group(1)
        block["label"] = label
        block["line"] = i + 1
        block["entities"] = [e for e in RE_ENTITY_ID.findall(str(block.get("entities", "")))]
        findings.append(block)
        i = k + 1
    return findings


def parse_gaps(md: str) -> dict:
    negatives = table_dicts(md, "coverage", "meaning")
    questions = table_dicts(md, "scope q", "status")
    unresolved = table_dicts(md, "candidate_group")
    nextcol = table_dicts(md, "closes", "notifies")
    return {"negatives": negatives, "questions": questions,
            "unresolved": unresolved, "next_collection": nextcol}


def load_sources_csv() -> dict[str, dict[str, str]]:
    """assets/sources.csv name -> row, for the source class column. Optional."""
    path = Path(__file__).resolve().parent.parent / "assets" / "sources.csv"
    if not path.is_file():
        return {}
    import csv
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {row["name"]: row for row in csv.DictReader(fh) if row.get("name")}


class Case:
    """Everything read off disk, parsed, before any judgement is applied."""

    def __init__(self, path: Path):
        self.path = path
        self.scope = parse_scope(read_text(path / "scope.md"))
        self.findings = parse_findings(read_text(path / "findings.md"))
        self.gaps = parse_gaps(read_text(path / "gaps.md"))
        self.entities, self.entity_errors = load_jsonl(path / "entities.jsonl")
        self.events, self.event_errors = load_jsonl(path / "events.jsonl")
        self.ledger, self.ledger_errors = load_jsonl(path / "ledger.jsonl")
        self.evidence = {}
        evd = path / "evidence"
        if evd.is_dir():
            for f in sorted(evd.iterdir()):
                if f.is_file():
                    self.evidence[f.stem] = f.stat().st_size

    @property
    def entity_by_id(self) -> dict[str, dict]:
        """Last write wins: entities.jsonl is append-only, a merge re-appends the id."""
        out: dict[str, dict] = {}
        for ent in self.entities:
            eid = ent.get("id")
            if isinstance(eid, str):
                out[eid] = ent
        return out


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

class Blocker:
    __slots__ = ("check", "item", "detail")

    def __init__(self, check: str, item: str, detail: str):
        self.check = check
        self.item = item
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"Blocker({self.check}, {self.item}, {self.detail})"

    def line(self) -> str:
        return f"[{self.check}] {self.item}: {self.detail}"


def open_candidate_groups(case: Case) -> dict[str, list[str]]:
    """Groups with two or more members and no member note naming a resolution.

    Resolution is recorded the way graph.py --validate demands it: a note that says
    the link was merged or resolved AND names the linking datapoint by canonical
    selector type. Anything less leaves the group open.
    """
    members: dict[str, list[str]] = {}
    resolved: set[str] = set()
    for eid, ent in case.entity_by_id.items():
        group = ent.get("candidate_group")
        if not isinstance(group, str) or not group:
            continue
        members.setdefault(group, []).append(eid)
        note = str(ent.get("notes", "")).lower()
        named = any(re.search(r"\b" + t + r"\b", note) for t in SELECTOR_TYPES)
        if named and re.search(r"\b(merged|resolved|resolves)\b", note):
            resolved.add(group)
    return {g: sorted(m) for g, m in members.items()
            if len(m) > 1 and g not in resolved}


def graph_blockers(case: Case) -> list[Blocker]:
    """graph.py --validate, run inside this gate rather than only alongside it.

    skills/osint/SKILL.md section 2 says the report "refuses to compile without it" and
    commands/osint-report.md section 1a instructs the agent to run it with "Exit 1 -> stop".
    That made the claim true of the prose flow and not of the script; this closes it.
    A case with no entities.jsonl, or a build with no graph.py, is not blocked by absence.
    """
    path = case.path / "entities.jsonl"
    if not path.is_file():
        return []
    try:
        import graph  # scripts/graph.py, this file's own directory
        records, errors = graph.load_jsonl(path)
        violations = graph.validate(records, errors)
    except Exception:  # pragma: no cover - depends on how this file is loaded
        return []
    return [Blocker("graph", v.entity, f"{v.rule} (entities.jsonl line {v.line}): {v.problem}")
            for v in violations]


def gate(case: Case) -> list[Blocker]:
    """The four refusals plus graph.py --validate. Every blocking item is named by its id."""
    blockers: list[Blocker] = []

    for f in case.findings:
        grade = str(f.get("grade", "")).strip().strip("`").upper()
        if not grade:
            blockers.append(Blocker("ungraded", f["id"], "no grade field"))
        elif grade not in GRADES:
            blockers.append(Blocker("ungraded", f["id"],
                                    f"grade {grade!r} is not an Admiralty grade A1-F6"))
        if not f.get("sources"):
            blockers.append(Blocker("unsourced", f["id"], "no source block"))
        else:
            for n, src in enumerate(f["sources"], 1):
                if not src.get("url") and not src.get("source_name"):
                    blockers.append(Blocker("unsourced", f["id"],
                                            f"source {n} has neither a name nor a url"))

        text = " ".join(str(f.get(k, "")) for k in
                        ("label", "claim", "reasoning", "disconfirms")) + \
            " " + " ".join(f.get("alternatives", []))
        for word in sorted({m.group(1).lower() for m in RE_BANNED.finditer(text)}):
            blockers.append(Blocker("banned", f["id"],
                                    f"banned certainty word {word!r} "
                                    "(CONTRACT.md section 6)"))
        if RE_CONFIRMED.search(text) and not grade.endswith("1"):
            blockers.append(Blocker("banned", f["id"],
                                    f"'confirmed' with credibility digit "
                                    f"{grade[1:] or '?'}; permitted only at digit 1"))

    groups = open_candidate_groups(case)
    for group, members in groups.items():
        for f in case.findings:
            prose = " ".join(str(f.get(k, "")) for k in ("claim", "reasoning"))
            named = {e for e in RE_ENTITY_ID.findall(prose)} | set(f.get("entities", []))
            hit = sorted(named & set(members))
            if len(hit) < 2:
                continue
            estimative = str(f.get("estimative", "")).strip().strip("`").lower()
            hedged = estimative in ESTIMATIVE
            flagged = any(w in prose.lower() for w in NON_MERGER_MARKERS + (group,))
            if not hedged and not flagged:
                blockers.append(Blocker(
                    "merged", f["id"],
                    f"treats open candidate_group {group} ({', '.join(hit)}) as resolved: "
                    "no estimative phrase and no 'unresolved' marker in claim or reasoning"))

    blockers.extend(graph_blockers(case))
    return blockers


# ---------------------------------------------------------------------------
# redaction
# ---------------------------------------------------------------------------

def marker(type_: str) -> str:
    return f"[redacted: {PII_CLASS.get(type_, type_)}]"


def redact_value(type_: str, value: str, mode: str) -> str:
    """A visible masked form. Never a silent deletion - the reader must see the hole."""
    if mode == "none" or not value:
        return value
    if mode == "full":
        return marker(type_) if type_ in FULL_TYPES else value
    if type_ not in PARTIAL_TYPES:
        return value
    if type_ == "email":
        local, _, domain = value.partition("@")
        if not domain:
            return marker("email")
        return f"{local[:1]}****@{domain}"
    if type_ == "phone":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7:
            return marker("phone")
        return f"+{digits[:1]} {digits[1:4]} *** ##{digits[-2:]}"
    if type_ == "person_name":
        parts = [p for p in re.split(r"\s+", value.strip()) if p]
        return ".".join(p[0].upper() for p in parts) + "." if parts else marker("person_name")
    if type_ == "address":
        # 50-reporting.md: street and city kept, house or unit number removed.
        stripped = re.sub(r"^\s*[0-9]+[A-Za-z]?[\s,]+", "", value)
        return f"[redacted: house number] {stripped}" if stripped != value else value
    if type_ == "coordinates":
        # Rounded coordinates still locate, so partial is the same as full here.
        return marker("coordinates")
    if type_ == "crypto_address":
        return f"{value[:6]}...{value[-4:]}" if len(value) > 12 else value
    return value


class Redactor:
    """Applies the case's redaction default to values and to authored prose."""

    def __init__(self, mode: str, entities: list[dict]):
        self.mode = mode
        self.map: dict[str, str] = {}
        for ent in entities:
            type_ = str(ent.get("type", ""))
            value = str(ent.get("value", ""))
            masked = redact_value(type_, value, mode)
            if masked != value and value:
                self.map[value] = masked
        self.order = sorted(self.map, key=len, reverse=True)

    def value(self, type_: str, value: str) -> str:
        return redact_value(str(type_), str(value), self.mode)

    def text(self, s: str) -> str:
        """Prose only. Never run over a URL, a hash, a grade or the out-of-bounds list."""
        if self.mode == "none" or not s:
            return s
        out = str(s)
        for raw in self.order:
            if raw in out:
                out = out.replace(raw, self.map[raw])
        # Emails that never became an entity still leave the building otherwise.
        return RE_EMAIL.sub(lambda m: redact_value("email", m.group(0), self.mode), out)


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------

def grade_of(f: dict) -> str:
    return str(f.get("grade", "")).strip().strip("`").upper()


def iso_window(case: Case) -> str:
    stamps = sorted(str(r.get("ts", "")) for r in case.ledger if r.get("ts"))
    return f"{stamps[0]}/{stamps[-1]}" if stamps else "no ledger rows"


def scope_value(case: Case, *names: str, default: str = "unrecorded") -> str:
    for name in names:
        val = case.scope["fields"].get(name)
        if val:
            return val
    return default


def question_status(case: Case, qid: str) -> str:
    for row in case.gaps["questions"]:
        if col(row, "scope q").strip().upper() == qid.upper():
            status = col(row, "status")
            if status:
                return status
    answered = [f["id"] for f in case.findings if qid.upper() in
                str(f.get("answers", "")).upper()]
    return "answered" if answered else "unanswered"


def findings_for(case: Case, qid: str) -> list[str]:
    return [f["id"] for f in case.findings if qid.upper() in str(f.get("answers", "")).upper()]


def build_hypotheses(case: Case, red: Redactor) -> list[dict]:
    """Section 9, from the `alternatives` lines across all findings, deduplicated."""
    seen: dict[str, dict] = {}
    for f in case.findings:
        for item in f.get("alternatives", []):
            text = red.text(item.strip())
            if not text:
                continue
            hypothesis, basis = split_alternative(text)
            hypothesis = hypothesis.rstrip(".")
            key = hypothesis.lower()
            status = "rejected" if basis.lower().startswith("rejected") else "live"
            if status == "rejected":
                basis = re.sub(r"^rejected\s+because\s+", "", basis, flags=re.IGNORECASE)
            if key in seen:
                seen[key]["findings"].append(f["id"])
                continue
            seen[key] = {"id": "", "hypothesis": hypothesis, "status": status,
                         "basis": basis or "not stated in the finding",
                         "findings": [f["id"]]}
    out = list(seen.values())
    for n, h in enumerate(out, 1):
        h["id"] = f"H{n}"
    return out


def build_evidence(case: Case, findings: list[dict]) -> list[dict]:
    rows: dict[str, dict] = {}
    for f in findings:
        for src in f.get("sources", []):
            sha = str(src.get("sha256", "")).strip().strip("`")
            if not RE_SHA256.match(sha):
                continue
            row = rows.setdefault(sha, {
                "sha256": sha, "source_name": src.get("source_name", ""),
                "url": src.get("url", ""), "retrieved": src.get("retrieved", ""),
                "mode": src.get("mode") or f.get("mode", ""),
                "bytes": case.evidence.get(sha), "cited_by": []})
            row["cited_by"].append(f["id"])
    return sorted(rows.values(), key=lambda r: r["sha256"])


def build_source_reliability(case: Case, findings: list[dict]) -> list[dict]:
    catalogue = load_sources_csv()
    per: dict[str, dict] = {}
    for f in findings:
        names = [str(s.get("source_name", "")).strip() for s in f.get("sources", [])]
        for src in f.get("sources", []):
            name = str(src.get("source_name", "")).strip()
            if not name:
                continue
            letter = str(src.get("source_grade", "")).strip().strip("`").upper()[:1]
            row = per.setdefault(name, {
                "source_name": name,
                "class": catalogue.get(name, {}).get("category", "unclassified"),
                "reliability": letter or "F",
                "basis": "as it behaved in this case",
                "findings": [], "sole_support_for": []})
            # Worst letter observed wins: a source is graded at its weakest showing.
            if letter and letter > row["reliability"]:
                row["reliability"] = letter
            row["findings"].append(f["id"])
            if len({n for n in names if n}) == 1:
                row["sole_support_for"].append(f["id"])
    return sorted(per.values(), key=lambda r: r["source_name"].lower())


def grade_distribution(findings: list[dict]) -> dict[str, int]:
    dist = {"A1-B2": 0, "A3-B3": 0, "C1-C3": 0, "D1-F3": 0, "digit 4-6": 0,
            "rung speculated": 0}
    for f in findings:
        g = grade_of(f)
        if len(g) != 2:
            continue
        letter, digit = g[0], g[1]
        if digit in "456":
            dist["digit 4-6"] += 1
        elif letter in "AB" and digit in "12":
            dist["A1-B2"] += 1
        elif letter in "AB" and digit == "3":
            dist["A3-B3"] += 1
        elif letter == "C":
            dist["C1-C3"] += 1
        else:
            dist["D1-F3"] += 1
        if str(f.get("rung", "")).strip() == "speculated":
            dist["rung speculated"] += 1
    return dist


def build_bluf(case: Case, red: Redactor) -> dict:
    """The compiler does not author claims. It carries a BLUF the case supplies."""
    for candidate in (case.path / "report" / "bluf.md", case.path / "bluf.md"):
        if candidate.is_file():
            raw = read_text(candidate)
            grade = ""
            would = ""
            body: list[str] = []
            for line in raw.splitlines():
                m = re.match(r"^\s*(grade|would_change):\s*(.+)$", line, re.IGNORECASE)
                if m:
                    if m.group(1).lower() == "grade":
                        grade = m.group(2).strip().strip("`").upper()
                    else:
                        would = m.group(2).strip()
                    continue
                if not line.strip().startswith("#"):
                    body.append(line)
            text = red.text(" ".join(" ".join(body).split()))
            return {"text": text, "grade": grade, "would_change": would,
                    "words": len(text.split()), "source": str(candidate.name)}
    return {"text": "[BLUF not written — write it last, from the finished body, and put it "
                    "in report/bluf.md; the compiler does not author claims]",
            "grade": "", "would_change": "", "words": 0, "source": ""}


def build_model(case: Case, red: Redactor, blockers: list[Blocker], forced: bool,
                report_version: int, generated: str) -> dict:
    entity_by_id = case.entity_by_id
    findings = sorted(case.findings, key=lambda f: int(f["id"].split("-")[1]))
    cited_entities = {e for f in findings for e in f.get("entities", [])}

    handling = max((HANDLING_ORDER.get(str(f.get("handling", "")).strip(), 0)
                    for f in findings), default=0)
    handling_word = {0: "none", 1: "partial", 2: "withheld"}[handling]

    scope_questions = [{"id": q["id"], "question": q["question"],
                        "status": question_status(case, q["id"]),
                        "findings": findings_for(case, q["id"])}
                       for q in case.scope["questions"]]

    negatives = []
    for row in case.gaps["negatives"]:
        coverage = col(row, "coverage").lower()
        negatives.append({
            "type": col(row, "selector"), "value": red.text(col(row, "value")),
            "source": col(row, "source"), "query": col(row, "query"),
            "checked": col(row, "when"), "mode": col(row, "mode") or "passive",
            "coverage": coverage or "unknown",
            "informative": coverage not in ("no", "unknown", ""),
            "id": col(row, "#")})

    open_groups = open_candidate_groups(case)
    unresolved = []
    for group, members in sorted(open_groups.items()):
        row = next((r for r in case.gaps["unresolved"]
                    if col(r, "candidate_group") == group), {})
        unresolved.append({
            "candidate_group": group, "members": members,
            "shares": red.text(col(row, "share")) or "not recorded in gaps.md",
            "resolves": col(row, "resolve") or "not recorded in gaps.md",
            "breaks": col(row, "break") or "not recorded in gaps.md"})

    gaps_rows = [{"scope_question": q["id"], "status": q["status"],
                  "missing": red.text(next((col(r, "missing") for r in case.gaps["questions"]
                                            if col(r, "scope q").upper() == q["id"]), ""))}
                 for q in scope_questions if q["status"] != "answered"]

    next_collection = [{
        "id": col(row, "#") or f"r-{n}", "action": col(row, "action"),
        "closes": col(row, "closes"), "mode": col(row, "mode") or "passive",
        "notifies_target": col(row, "notifies").lower() in ("yes", "true"),
        "cost": col(row, "cost"), "authority_needed": col(row, "auth")}
        for n, row in enumerate(case.gaps["next_collection"], 1)]

    dossiers = []
    for eid in sorted(cited_entities | set(), key=lambda e: int(e.split("-")[1])):
        ent = entity_by_id.get(eid)
        if ent is None:
            dossiers.append({"id": eid, "type": "unknown", "value":
                             "[not in entities.jsonl]", "first_seen": "", "grade": "",
                             "rung": "", "candidate_group": "", "findings": [],
                             "attributed_to": "", "notes": ""})
            continue
        dossiers.append({
            "id": eid, "type": ent.get("type", ""),
            "value": red.value(ent.get("type", ""), ent.get("value", "")),
            "first_seen": ent.get("first_seen", ""), "grade": ent.get("grade", ""),
            "rung": ent.get("inference_rung", "not recorded"),
            "candidate_group": ent.get("candidate_group") or "none",
            "findings": [f["id"] for f in findings if eid in f.get("entities", [])],
            "attributed_to": ent.get("attributed_to") or "not attributed",
            "notes": red.text(str(ent.get("notes", "")))})

    timeline = []
    for ev in sorted(case.events, key=lambda e: str(e.get("ts", ""))):
        actor = str(ev.get("actor_entity", ""))
        ent = entity_by_id.get(actor, {})
        timeline.append({
            "ts": ev.get("ts", ""), "precision": ev.get("precision", ""),
            "actor_entity": actor,
            "actor_value": red.value(ent.get("type", ""), ent.get("value", "")),
            "description": red.text(str(ev.get("description", ""))),
            "grade": ev.get("grade", ""), "rung": ev.get("inference_rung", ""),
            "sources": ev.get("sources", [])})

    modes = {"passive": 0, "active": 0}
    classes: dict[str, dict] = {}
    catalogue = load_sources_csv()
    for row in case.ledger:
        mode = str(row.get("mode", ""))
        if mode in modes:
            modes[mode] += 1
        name = str(row.get("source", "")).strip()
        if not name or name == "n/a":
            continue
        cls = catalogue.get(name, {}).get("category", "unclassified")
        bucket = classes.setdefault(cls, {"class": cls, "sources": set(), "modes": set(),
                                          "coverage": catalogue.get(name, {}).get(
                                              "jurisdiction_notes", "")})
        bucket["sources"].add(name)
        bucket["modes"].add(mode or "passive")
    source_classes = [{"class": c["class"], "sources": sorted(c["sources"]),
                       "modes": sorted(c["modes"]),
                       "coverage": c["coverage"] or "not recorded in sources.csv"}
                      for c in sorted(classes.values(), key=lambda c: c["class"])]

    sequence = [red.text(str(r.get("query", ""))) + "  ->  " + red.text(str(r.get("result", "")))
                for r in case.ledger if r.get("action") == "pivot"]

    active_rows = [r for r in case.ledger if str(r.get("mode", "")) == "active"]

    export_findings = []
    for f in findings:
        estimative = str(f.get("estimative", "")).strip().strip("`")
        withheld = str(f.get("handling", "")).strip() == "withheld"
        obj = {
            "id": f["id"],
            "claim": "[withheld — see handling note]" if withheld else red.text(f.get("claim", "")),
            "grade": grade_of(f),
            "inference_rung": str(f.get("rung", "")).strip(),
            "estimative": estimative if estimative in ESTIMATIVE else None,
            "mode": str(f.get("mode", "")).strip() or "passive",
            "sources": [{"source_name": s.get("source_name", ""), "url": s.get("url", ""),
                         "retrieved": s.get("retrieved", ""),
                         "sha256": s.get("sha256") or None,
                         "reliability": str(s.get("source_grade", "")).strip().upper()[:1],
                         **({"archive_note": s["archive_note"]} if s.get("archive_note") else {}),
                         **({"mode": s["mode"]} if s.get("mode") else {})}
                        for s in f.get("sources", [])],
            "reasoning": red.text(f.get("reasoning", "")),
            "disconfirming_evidence": red.text(f.get("disconfirms", "")),
            "entity_refs": f.get("entities", []),
            "scope_question": str(f.get("answers", "")).strip(),
            "alternatives_rejected": [
                {"hypothesis": h, "why_rejected": why or "not stated"}
                for h, why in (split_alternative(a) for a in f.get("alternatives", []))],
            "handling": str(f.get("handling", "")).strip() or "none",
        }
        export_findings.append(obj)

    model = {
        "case_id": scope_value(case, "slug", "case_id", default=case.path.name),
        "generated": generated,
        "report_version": report_version,
        "purpose": scope_value(case, "purpose"),
        "classification": scope_value(case, "classification"),
        "handling": handling_word,
        "period_covered": scope_value(case, "period_covered", default="no time bound"),
        "collection_window": iso_window(case),
        "scope_questions": scope_questions,
        "bluf": build_bluf(case, red),
        "findings": export_findings,
        # 50-reporting.md calls these "the JSONL lines unchanged", and in the same
        # section requires "the same redaction as the markdown - an export is a
        # deliverable, not a debug dump". The redaction rule wins: shipping raw values
        # in the JSON while masking them in the markdown would defeat both.
        "entities": [dict(e, value=red.value(e.get("type", ""), e.get("value", "")),
                          notes=red.text(str(e.get("notes", ""))))
                     for e in case.entities],
        "events": [dict(e, description=red.text(str(e.get("description", ""))))
                   for e in sorted(case.events, key=lambda e: str(e.get("ts", "")))],
        "negative_results": negatives,
        "hypotheses": build_hypotheses(case, red),
        "gaps": gaps_rows,
        "next_collection": next_collection,
        "evidence": build_evidence(case, findings),
        "source_reliability": build_source_reliability(case, findings),
        "source_file": str(case.path),
        # -- rendering only, stripped from the JSON export --------------------
        "_blocks": findings,
        "_dossiers": dossiers,
        "_timeline": timeline,
        "_unresolved": unresolved,
        "_source_classes": source_classes,
        "_sequence": sequence,
        "_modes": modes,
        "_active_rows": active_rows,
        "_scope": case.scope,
        "_distribution": grade_distribution(findings),
        "_redaction": red.mode,
        "_case_path": str(case.path),
        "_parse_errors": case.entity_errors + case.event_errors + case.ledger_errors,
        "_evidence_dir": case.evidence,
    }
    if forced:
        model["forced"] = {"overridden": True,
                           "failed_checks": [b.line() for b in blockers]}
    return model


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------

def md_table(headers: list[str], rows: list[list[str]], empty: str = "") -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    if not rows:
        return "\n".join(out) + ("\n\n*" + empty + "*" if empty else "")
    for row in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in row]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def force_banner_md(model: dict) -> list[str]:
    forced = model.get("forced")
    if not forced:
        return []
    lines = ["> ## !! COMPILED UNDER --force — THE PRE-DELIVERY GATE WAS OVERRIDDEN !!",
             ">",
             "> This document did **not** pass the compile gate. It was produced anyway on an",
             "> explicit override. The checks below failed and were not fixed. Treat every",
             "> affected finding as undeliverable until they are.",
             ">"]
    for item in forced["failed_checks"]:
        lines.append(f">   - {item}")
    lines.append(">")
    lines.append("> Do not circulate this document without the failures above resolved.")
    lines.append("")
    return lines


def render_markdown(model: dict) -> str:
    out: list[str] = []
    add = out.append
    case_id = model["case_id"]

    add(f"# `{case_id}` — OSINT case report")
    add("")
    out.extend(force_banner_md(model))
    add("---")
    add("")

    # 1 -----------------------------------------------------------------
    scope_fields = model["_scope"]["fields"]
    add("## 1. Header")
    add("")
    add(md_table(["Field", "Value"], [
        ["Case id", f"`{case_id}`"],
        ["Requester", scope_fields.get("requester", "unrecorded")],
        ["Purpose", model["purpose"]],
        ["Authority", scope_fields.get("authority", "unrecorded") + " / " +
         scope_fields.get("authority_ref", "no reference recorded")],
        ["Jurisdiction", scope_fields.get("jurisdiction", "unrecorded")],
        ["Period covered", model["period_covered"]],
        ["Collection window", model["collection_window"]],
        ["Analyst", scope_fields.get("analyst", "unrecorded")],
        ["Classification / handling", f"{model['classification']} / {model['handling']}"],
        ["Report version", f"{model['report_version']}, {model['generated']}"],
        ["Target category", scope_fields.get("target_category", "unrecorded")],
        ["Redaction applied", model["_redaction"]],
    ]))
    add("")
    add("**Handling caveat.** This report contains information collected from public sources "
        f"under the authority named above. It is {model['classification']} and intended for "
        f"{scope_fields.get('share_with', 'the requester')}. Do not redistribute outside that "
        "group without written agreement from the requester. Findings are graded; ungraded "
        "assertions do not appear in this document. Nothing here is a legal determination, and "
        "nothing here is investment, compliance, or legal advice.")
    add("")

    # 2 -----------------------------------------------------------------
    bluf = model["bluf"]
    add("## 2. Bottom Line Up Front")
    add("")
    add(bluf["text"])
    add("")
    if bluf["words"]:
        add(f"*{bluf['words']} words. Under 150 is the ceiling (50-reporting.md).*")
        add("")
    add(f"**Confidence in the BLUF as a whole:** "
        f"{bluf['grade'] or '[not stated in report/bluf.md]'} — the weakest link in the chain "
        "that supports it, not an average.")
    add("")
    add(f"**What would change this assessment:** "
        f"{bluf['would_change'] or '[not stated in report/bluf.md]'}")
    add("")

    # 3 -----------------------------------------------------------------
    add("## 3. Scope and authority as recorded")
    add("")
    add("**Questions asked**")
    add("")
    add(md_table(["#", "Question", "Status", "Findings"],
                 [[q["id"], q["question"], q["status"], ", ".join(q["findings"]) or "none"]
                  for q in model["scope_questions"]],
                 empty="No numbered questions recorded in scope.md. A case with no question "
                       "has no stop condition."))
    add("")
    add(f"**Decision this supports:** {scope_fields.get('decision', 'unrecorded in scope.md')}")
    add("")
    add("**Out of bounds** — declared at intake, enforced throughout. Never redacted.")
    add("")
    add("```")
    for item in model["_scope"]["out_of_bounds"] or ["(none recorded in scope.md)"]:
        add(item)
    add("```")
    add("")
    active = str(scope_fields.get("active_allowed", "false")).lower() in ("true", "yes")
    add(f"**Active collection:** active_allowed: {'yes' if active else 'no'}. "
        + (f"{len(model['_active_rows'])} ledger row(s) recorded as active."
           if model["_active_rows"] else
           "No ledger row is recorded as active; all collection was passive."))
    add("")
    if model["_active_rows"] and not active:
        add("> **Scope conflict:** active rows exist in `ledger.jsonl` while `scope.md` records "
            "`active_allowed: false`. Resolve before delivery.")
        add("")

    # 4 -----------------------------------------------------------------
    add("## 4. Methodology and limitations")
    add("")
    add("**Sources consulted, by class** — the full list is section 11.")
    add("")
    add(md_table(["Class", "Sources used", "Passive/active", "Coverage caveat"],
                 [[c["class"], ", ".join(c["sources"]), "/".join(c["modes"]), c["coverage"]]
                  for c in model["_source_classes"]],
                 empty="No source rows in ledger.jsonl."))
    add("")
    add("**Collection sequence** — pivot rows from `ledger.jsonl`, in order.")
    add("")
    add("```")
    for line in model["_sequence"] or ["(no pivot rows recorded in ledger.jsonl)"]:
        add(line)
    add("```")
    add("")
    negatives = model["negative_results"]
    informative = sum(1 for n in negatives if n["informative"])
    add(f"**Collection volume.** {len(model['_modes']) and ''}"
        f"{model['_modes']['passive'] + model['_modes']['active']} ledger actions "
        f"({model['_modes']['passive']} passive, {model['_modes']['active']} active); "
        f"{len(negatives)} recorded negative result(s), coverage adequate on {informative}.")
    add("")
    add("**Not collected, by design** — PII minimization is a control, stated as one.")
    add("")
    rows = [[item, "out of bounds per scope.md section 6"]
            for item in model["_scope"]["out_of_bounds"]]
    rows += [[item, "recorded in scope.md as not collected by design"]
             for item in model["_scope"]["not_collected"]]
    add(md_table(["Not collected", "Why"], rows,
                 empty="scope.md records no exclusions. That is itself a finding about the "
                       "case, not an omission from this report."))
    add("")
    add("**Limitations**")
    add("")
    lim: list[list[str]] = []
    sole = [(s["source_name"], s["sole_support_for"]) for s in model["source_reliability"]
            if s["sole_support_for"]]
    for name, ids in sole:
        lim.append([f"Single-source dependency on {name}",
                    "sole support for " + ", ".join(ids)])
    for n in negatives:
        if not n["informative"]:
            lim.append([f"Coverage {n['coverage']} on {n['source']}",
                        "its negative result supports nothing"])
    if model["_unresolved"]:
        lim.append(["Unresolved identity",
                    "candidate group(s) " +
                    ", ".join(u["candidate_group"] for u in model["_unresolved"]) +
                    " are not merged anywhere in this report"])
    add(md_table(["Limitation", "Effect on findings"], lim,
                 empty="No single-source dependency, no uninformative negative, no open "
                       "candidate group."))
    add("")
    add("**Identity resolution.** " + (
        "Open candidate groups: " +
        "; ".join(f"{u['candidate_group']} ({', '.join(u['members'])})"
                  for u in model["_unresolved"]) +
        ". None is merged in this report; see section 10."
        if model["_unresolved"] else
        "No candidate group is open. Every entity in section 6 stands alone."))
    add("")

    # 5 -----------------------------------------------------------------
    add("## 5. Key findings")
    add("")
    if not model["_blocks"]:
        add("*No findings in `findings.md`. A report with no findings is a collection gap.*")
        add("")
    for f, exp in zip(model["_blocks"], model["findings"]):
        add(f"### {f['id']} — {f.get('label') or 'unlabelled'}")
        add("")
        add("```")
        add(f"claim:      {exp['claim']}")
        add(f"grade:      {exp['grade']}")
        add(f"rung:       {exp['inference_rung']}")
        add(f"estimative: {exp['estimative'] or 'none'}")
        add(f"answers:    {exp['scope_question'] or 'none — see gaps.md'}")
        add(f"entities:   {', '.join(exp['entity_refs']) or 'none'}")
        add(f"mode:       {exp['mode']}")
        add(f"handling:   {exp['handling']}")
        add("")
        add("sources:")
        for n, src in enumerate(exp["sources"], 1):
            add(f"  {n}. {src['source_name']}")
            add(f"     url:       {src['url']}")
            add(f"     retrieved: {src['retrieved']}")
            add(f"     sha256:    {src['sha256'] or 'none'}")
            if src.get("archive_note"):
                add(f"     archive_note: {src['archive_note']}")
            add(f"     source_grade: {src['reliability']}")
        add("")
        add(f"reasoning:  {exp['reasoning']}")
        add("")
        add("alternatives:")
        for alt in exp["alternatives_rejected"] or [{"hypothesis": "none recorded",
                                                     "why_rejected": ""}]:
            why = f" — {alt['why_rejected']}" if alt["why_rejected"] else ""
            add(f"  - {alt['hypothesis']}{why}")
        add("")
        add(f"disconfirms: {exp['disconfirming_evidence']}")
        add("```")
        add("")

    # 6 -----------------------------------------------------------------
    add("## 6. Entity dossiers")
    add("")
    if not model["_dossiers"]:
        add("*No entity carries a finding. Entities with no findings stay in "
            "`entities.jsonl` and out of the report.*")
        add("")
    for d in model["_dossiers"]:
        add(f"### {d['id']} — {d['type']}: {d['value']}")
        add("")
        add(md_table(["Field", "Value"], [
            ["Type", d["type"]], ["Value", d["value"]],
            ["First seen in case", d["first_seen"]], ["Grade", d["grade"]],
            ["Rung", d["rung"]], ["Candidate group", d["candidate_group"]],
            ["Findings", ", ".join(d["findings"]) or "none"],
            ["Attributed to", d["attributed_to"]],
        ]))
        add("")
        if d["notes"]:
            add(d["notes"])
            add("")

    # 7 -----------------------------------------------------------------
    add("## 7. Timeline")
    add("")
    add(md_table(["When", "Precision", "Entity", "Event", "Grade", "Rung", "Source"],
                 [[t["ts"], t["precision"], f"{t['actor_entity']} {t['actor_value']}".strip(),
                   t["description"], t["grade"], t["rung"] or "not recorded",
                   ", ".join(str(s) for s in t["sources"])]
                  for t in model["_timeline"]],
                 empty="`events.jsonl` is empty. Nothing in this case is anchored in time."))
    add("")
    add("*A row with `precision: approx` is a derived time and is never a precise one.*")
    add("")

    # 8 -----------------------------------------------------------------
    add("## 8. Link chart")
    add("")
    chart = model.get("_chart")
    if chart:
        add("```mermaid")
        add(chart)
        add("```")
    else:
        add("*Not generated here. Run "
            "`python ${CLAUDE_PLUGIN_ROOT}/scripts/graph.py <case> --format mermaid` "
            "and paste the source into this section, or `/osint:osint-graph`.*")
    add("")

    # 9 -----------------------------------------------------------------
    add("## 9. Alternative hypotheses considered")
    add("")
    add(md_table(["#", "Hypothesis", "Status", "Basis", "Findings"],
                 [[h["id"], h["hypothesis"], h["status"], h["basis"], ", ".join(h["findings"])]
                  for h in model["hypotheses"]],
                 empty="No `alternatives` line in any finding. A report with no rejected "
                       "hypothesis did collection, not analysis."))
    add("")

    # 10 ----------------------------------------------------------------
    add("## 10. Gaps and recommended next collection")
    add("")
    add("**Checked, found nothing**")
    add("")
    add(md_table(["Selector", "Value", "Source", "When", "Coverage", "Meaning of absence"],
                 [[n["type"], n["value"], n["source"], n["checked"], n["coverage"],
                   "informative" if n["informative"] else "uninformative"]
                  for n in negatives],
                 empty="No negative result recorded in gaps.md. A case with no logged "
                       "negatives has not been investigated."))
    add("")
    add("**Unresolved identities**")
    add("")
    add(md_table(["Candidate group", "Members", "What they share", "Would resolve it",
                  "Would break it"],
                 [[u["candidate_group"] + " (unresolved)", ", ".join(u["members"]),
                   u["shares"], u["resolves"], u["breaks"]]
                  for u in model["_unresolved"]],
                 empty="No candidate group is open."))
    add("")
    add("**Open questions**")
    add("")
    add(md_table(["Scope Q", "Status", "What is missing"],
                 [[g["scope_question"], g["status"], g["missing"] or "not recorded in gaps.md"]
                  for g in model["gaps"]],
                 empty="Every scope question is answered."))
    add("")
    add("**Recommended next collection**")
    add("")
    add(md_table(["#", "Action", "Closes", "Mode", "Notifies target", "Cost",
                  "Authority needed"],
                 [[r["id"], r["action"], r["closes"], r["mode"],
                   "yes" if r["notifies_target"] else "no", r["cost"], r["authority_needed"]]
                  for r in model["next_collection"]],
                 empty="No next collection proposed in gaps.md section 3."))
    add("")

    # 11 ----------------------------------------------------------------
    add("## 11. Evidence appendix")
    add("")
    add(md_table(["#", "sha256", "Source name", "URL", "Retrieved (UTC)", "Mode", "Bytes",
                  "Cited by"],
                 [[str(n), f"`{e['sha256']}`", e["source_name"], e["url"], e["retrieved"],
                   e["mode"], str(e["bytes"]) if e["bytes"] is not None
                   else "MISSING from evidence/", ", ".join(e["cited_by"])]
                  for n, e in enumerate(model["evidence"], 1)],
                 empty="No finding cites an archived artifact."))
    add("")
    missing = [e["sha256"] for e in model["evidence"] if e["bytes"] is None]
    if missing:
        add("**Hashes cited but absent from `evidence/`** — the integrity chain is broken for "
            "these and the citing findings are not deliverable until it is repaired.")
        add("")
        for sha in missing:
            add(f"- `{sha}`")
        add("")
    noarchive = [[s["source_name"], s["url"], s.get("archive_note", "no reason recorded"), ""]
                 for f in model["findings"] for s in f["sources"] if not s["sha256"]]
    add("**Artifacts that could not be archived**")
    add("")
    add(md_table(["Source", "URL", "Why no snapshot", "Third-party archive"], noarchive,
                 empty="Every cited source carries a hash."))
    add("")

    # 12 ----------------------------------------------------------------
    add("## 12. Source reliability summary")
    add("")
    add(md_table(["Source", "Class", "Reliability", "Basis", "Findings", "Sole support for"],
                 [[s["source_name"], s["class"], s["reliability"], s["basis"],
                   ", ".join(s["findings"]), ", ".join(s["sole_support_for"]) or "none"]
                  for s in model["source_reliability"]],
                 empty="No source cited by any finding."))
    add("")
    dist = model["_distribution"]
    add("**Grade distribution**")
    add("")
    add("```")
    add("   ".join(f"{k}: {v}" for k, v in dist.items()))
    add("```")
    add("")

    # handling ----------------------------------------------------------
    add("## Handling and redaction note")
    add("")
    add(md_table(["Field", "Value"], [
        ["Redaction default applied", model["_redaction"]],
        ["Redaction performed by", f"scripts/report.py, {model['generated']}"],
        ["Unredacted copy location", f"`{model['_case_path']}` — never attached to this "
                                     "deliverable"],
        ["Recipients", scope_fields.get("share_with", "unrecorded in scope.md")],
        ["Retention", scope_fields.get("retention", "unrecorded in scope.md")],
    ]))
    add("")
    add("- Natural-person identifiers are masked in the body and held in the case directory. "
        "A removed value is replaced by a visible `[redacted: <class>]` marker, never deleted "
        "silently.")
    add("- Entity ids, evidence hashes, grades, rungs, estimative wording and the "
        "out-of-bounds list are never redacted.")
    add("- A withheld finding keeps its id, grade, rung and disconfirms line, with the claim "
        "replaced by `[withheld — see handling note]`.")
    add("")

    # checklist ---------------------------------------------------------
    add("## Pre-delivery checklist")
    add("")
    add("*Mechanical boxes are ticked by the compiler. The rest are the analyst's, and are "
        "run against this document, not from memory.*")
    add("")
    add("```")
    for text, state in checklist(model):
        add(f"[{state}] {text}")
    add("```")
    add("")
    if model["_parse_errors"]:
        add("**Parse warnings**")
        add("")
        for err in model["_parse_errors"]:
            add(f"- {err}")
        add("")
    add(f"*Compiled by `scripts/report.py` from `{model['_case_path']}` at "
        f"{model['generated']}. Redaction: {model['_redaction']}.*")
    return "\n".join(out).rstrip() + "\n"


def checklist(model: dict) -> list[tuple[str, str]]:
    """The template's pre-delivery list, with the mechanical boxes already decided."""
    findings = model["findings"]
    graded = all(f["grade"] in GRADES for f in findings) and bool(findings)
    sourced = all(f["sources"] for f in findings) and bool(findings)
    hashed = all(any(s["sha256"] for s in f["sources"]) for f in findings) and bool(findings)
    disconf = all(f["disconfirming_evidence"] for f in findings) and bool(findings)
    in_scope = all(f["scope_question"] for f in findings) and bool(findings)
    hashes_ok = all(e["bytes"] is not None for e in model["evidence"])
    q_ok = bool(model["scope_questions"])
    bluf_ok = model["bluf"]["words"] > 0 and model["bluf"]["words"] < 150
    negatives_ok = bool(model["negative_results"]) and all(
        n["coverage"] for n in model["negative_results"])
    approx_ok = all(not (t["precision"] == "approx" and "T" in str(t["ts"]))
                    for t in model["_timeline"])
    forced = "forced" in model

    def box(ok: bool) -> str:
        return "x" if ok and not forced else " "

    return [
        ("Every finding carries an Admiralty grade", box(graded)),
        ("Every finding has at least one source", box(sourced)),
        ("Every finding cites at least one archived hash", box(hashed)),
        ("Every finding keeps its disconfirms line", box(disconf)),
        ("No finding answers a question absent from scope.md", box(in_scope)),
        ("Every hash cited appears in section 11 and exists in evidence/", box(hashes_ok)),
        ("Every scope question appears in section 3 with a status", box(q_ok)),
        ("BLUF is written and under 150 words", box(bluf_ok)),
        ("Negative results present with coverage on every row", box(negatives_ok)),
        ("No approx-precision event is rendered as a precise time", box(approx_ok)),
        ("Every unresolved candidate group is in section 10 and merged nowhere", box(True)),
        ("The redaction default from scope.md was applied", box(True)),
        ("No banned certainty word appears in a finding", box(not forced)),
        ("Header values match scope.md exactly", box(True)),
        ("Section 8 contains the generated chart, not the template example",
         box(bool(model.get("_chart")))),
        ("BLUF is not contradicted anywhere below it — ANALYST", " "),
        ("Audience emphasis applied for the declared purpose — ANALYST", " "),
        ("Every probabilistic sentence uses one of the seven ICD 203 phrases — ANALYST", " "),
    ]


# ---------------------------------------------------------------------------
# html
# ---------------------------------------------------------------------------

CSS = """
:root{
  --bg:#ffffff; --fg:#15181d; --muted:#5b6270; --line:#d7dbe2; --panel:#f5f6f8;
  --code:#f0f2f5; --rule:#e3e6eb; --alert-bg:#fff3e0; --alert-fg:#6b3200;
  --alert-line:#c2660a;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1216; --fg:#e4e7ec; --muted:#98a1b0; --line:#2b313a; --panel:#161a20;
    --code:#12161b; --rule:#242a32; --alert-bg:#2a1c08; --alert-fg:#ffd9a0;
    --alert-line:#d9860f;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
main{max-width:60rem;margin:0 auto;padding:2rem 1.25rem 5rem}
h1{font-size:1.65rem;margin:0 0 .25rem;letter-spacing:-.01em}
h2{font-size:1.2rem;margin:2.5rem 0 .75rem;padding-top:.75rem;border-top:1px solid var(--rule)}
h3{font-size:1rem;margin:1.75rem 0 .5rem;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
p{margin:.6rem 0}
.sub{color:var(--muted);font-size:.85rem;margin:0 0 1.5rem}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:.75rem 0;
  border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;min-width:34rem;font-size:.85rem}
th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--line);
  vertical-align:top}
th{background:var(--panel);font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
pre{background:var(--code);border:1px solid var(--line);border-radius:6px;padding:.8rem;
  overflow-x:auto;font-size:.8rem;line-height:1.45}
code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.85em}
.empty{color:var(--muted);font-style:italic;font-size:.85rem}
.note{color:var(--muted);font-size:.85rem}
.alert{background:var(--alert-bg);color:var(--alert-fg);border:3px solid var(--alert-line);
  border-radius:6px;padding:1rem 1.25rem;margin:1.5rem 0}
.alert h2{border:none;margin:.25rem 0 .5rem;padding:0;font-size:1.1rem;letter-spacing:.02em}
.alert ul{margin:.5rem 0 .25rem;padding-left:1.25rem}
.alert li{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.8rem}
/* Grades read without colour: the text is the grade, and the border style repeats the
   reliability letter so it survives a greyscale print. */
.g{display:inline-block;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
  font-weight:700;font-size:.8rem;padding:0 .35rem;border-radius:3px;
  border:2px solid currentColor;white-space:nowrap}
.g-A{border-width:3px;border-style:solid}
.g-B{border-width:2px;border-style:solid}
.g-C{border-width:2px;border-style:dashed}
.g-D{border-width:2px;border-style:dotted}
.g-E{border-width:3px;border-style:double}
.g-F{border-width:1px;border-style:dotted;font-style:italic}
.redacted{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.85em;
  border-bottom:1px dashed currentColor}
@media print{
  :root{--bg:#fff;--fg:#000;--muted:#333;--line:#999;--panel:#fff;--code:#fff;
    --rule:#000;--alert-bg:#fff;--alert-fg:#000;--alert-line:#000}
  body{font-size:10.5pt}
  main{max-width:none;padding:0}
  .tw{overflow:visible;border:none}
  table{min-width:0;font-size:9pt}
  pre{white-space:pre-wrap;word-break:break-word;font-size:8.5pt;page-break-inside:avoid}
  h2{page-break-after:avoid}
  h3{page-break-after:avoid}
  .block{page-break-inside:avoid}
  .alert{border:3px solid #000}
}
"""


def esc(text: object) -> str:
    return html_mod.escape(str(text), quote=True)


def html_grade(grade: str) -> str:
    g = str(grade).strip().upper()
    if len(g) != 2 or g not in GRADES:
        return f'<span class="g g-F">{esc(g or "ungraded")}</span>'
    return f'<span class="g g-{g[0]}">{esc(g)}</span>'


def html_table(headers: list[str], rows: list[list[str]], empty: str = "",
               grade_cols: tuple[int, ...] = ()) -> str:
    if not rows:
        return f'<p class="empty">{esc(empty)}</p>' if empty else ""
    out = ['<div class="tw"><table><thead><tr>']
    out += [f"<th>{esc(h)}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for i, cell in enumerate(row):
            out.append("<td>" + (html_grade(cell) if i in grade_cols and cell
                                 else esc(cell)) + "</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_html(model: dict) -> str:
    """One self-contained file. No external request of any kind: no link, no script src,
    no font, no image. Source URLs render as text, never as an anchor."""
    o: list[str] = []
    add = o.append
    scope_fields = model["_scope"]["fields"]

    add("<!doctype html>")
    add('<html lang="en"><head><meta charset="utf-8">')
    add('<meta name="viewport" content="width=device-width,initial-scale=1">')
    add(f"<title>{esc(model['case_id'])} — OSINT case report</title>")
    add(f"<style>{CSS}</style>")
    add("</head><body><main>")
    add(f"<h1>{esc(model['case_id'])} — OSINT case report</h1>")
    add(f'<p class="sub">Report version {esc(model["report_version"])} · '
        f'{esc(model["generated"])} · redaction: {esc(model["_redaction"])} · '
        f'handling: {esc(model["handling"])}</p>')

    if model.get("forced"):
        add('<div class="alert"><h2>!! COMPILED UNDER --force — THE PRE-DELIVERY GATE WAS '
            "OVERRIDDEN !!</h2>")
        add("<p>This document did <strong>not</strong> pass the compile gate. It was produced "
            "anyway on an explicit override. The checks below failed and were not fixed. "
            "Treat every affected finding as undeliverable until they are.</p><ul>")
        for item in model["forced"]["failed_checks"]:
            add(f"<li>{esc(item)}</li>")
        add("</ul><p>Do not circulate this document without the failures above resolved.</p>"
            "</div>")

    add("<h2>1. Header</h2>")
    add(html_table(["Field", "Value"], [
        ["Case id", model["case_id"]],
        ["Requester", scope_fields.get("requester", "unrecorded")],
        ["Purpose", model["purpose"]],
        ["Authority", scope_fields.get("authority", "unrecorded")],
        ["Jurisdiction", scope_fields.get("jurisdiction", "unrecorded")],
        ["Period covered", model["period_covered"]],
        ["Collection window", model["collection_window"]],
        ["Analyst", scope_fields.get("analyst", "unrecorded")],
        ["Classification / handling", f"{model['classification']} / {model['handling']}"],
        ["Target category", scope_fields.get("target_category", "unrecorded")],
        ["Redaction applied", model["_redaction"]],
    ]))
    add("<p>This report contains information collected from public sources under the authority "
        "named above. Findings are graded; ungraded assertions do not appear. Nothing here is a "
        "legal determination, and nothing here is investment, compliance, or legal advice.</p>")

    add("<h2>2. Bottom Line Up Front</h2>")
    add(f"<p>{esc(model['bluf']['text'])}</p>")
    add(f"<p class=\"note\">Confidence in the BLUF as a whole: "
        f"{html_grade(model['bluf']['grade']) if model['bluf']['grade'] else '[not stated]'} "
        f"— the weakest link, not an average. What would change it: "
        f"{esc(model['bluf']['would_change'] or '[not stated in report/bluf.md]')}</p>")

    add("<h2>3. Scope and authority as recorded</h2>")
    add(html_table(["#", "Question", "Status", "Findings"],
                   [[q["id"], q["question"], q["status"], ", ".join(q["findings"]) or "none"]
                    for q in model["scope_questions"]],
                   empty="No numbered questions recorded in scope.md."))
    add("<p><strong>Out of bounds</strong> — declared at intake, never redacted.</p>")
    add("<pre>" + esc("\n".join(model["_scope"]["out_of_bounds"] or
                                ["(none recorded in scope.md)"])) + "</pre>")
    active = str(scope_fields.get("active_allowed", "false")).lower() in ("true", "yes")
    add(f"<p>Active collection: active_allowed <strong>{'yes' if active else 'no'}</strong>; "
        f"{len(model['_active_rows'])} active ledger row(s).</p>")

    add("<h2>4. Methodology and limitations</h2>")
    add(html_table(["Class", "Sources used", "Passive/active", "Coverage caveat"],
                   [[c["class"], ", ".join(c["sources"]), "/".join(c["modes"]), c["coverage"]]
                    for c in model["_source_classes"]],
                   empty="No source rows in ledger.jsonl."))
    add("<p><strong>Collection sequence</strong></p>")
    add("<pre>" + esc("\n".join(model["_sequence"] or
                                ["(no pivot rows recorded in ledger.jsonl)"])) + "</pre>")
    add("<p><strong>Not collected, by design</strong></p>")
    add(html_table(["Not collected", "Why"],
                   [[i, "out of bounds per scope.md section 6"]
                    for i in model["_scope"]["out_of_bounds"]],
                   empty="scope.md records no exclusions."))

    add("<h2>5. Key findings</h2>")
    for f, exp in zip(model["_blocks"], model["findings"]):
        add('<div class="block">')
        add(f"<h3>{esc(exp['id'])} — {esc(f.get('label') or 'unlabelled')} "
            f"{html_grade(exp['grade'])}</h3>")
        add(f"<p>{esc(exp['claim'])}</p>")
        add(html_table(["Field", "Value"], [
            ["rung", exp["inference_rung"]],
            ["estimative", exp["estimative"] or "none"],
            ["answers", exp["scope_question"] or "none"],
            ["entities", ", ".join(exp["entity_refs"]) or "none"],
            ["mode", exp["mode"]], ["handling", exp["handling"]],
        ]))
        add(html_table(["#", "Source", "URL", "Retrieved", "sha256", "Reliability"],
                       [[str(n), s["source_name"], s["url"], s["retrieved"],
                         s["sha256"] or "none", s["reliability"]]
                        for n, s in enumerate(exp["sources"], 1)],
                       empty="No source."))
        add(f"<p><strong>reasoning</strong> {esc(exp['reasoning'])}</p>")
        if exp["alternatives_rejected"]:
            add("<p><strong>alternatives</strong></p><ul>")
            for alt in exp["alternatives_rejected"]:
                add(f"<li>{esc(alt['hypothesis'])} — {esc(alt['why_rejected'])}</li>")
            add("</ul>")
        add(f"<p><strong>disconfirms</strong> {esc(exp['disconfirming_evidence'])}</p>")
        add("</div>")
    if not model["_blocks"]:
        add('<p class="empty">No findings in findings.md.</p>')

    add("<h2>6. Entity dossiers</h2>")
    add(html_table(["id", "Type", "Value", "First seen", "Grade", "Rung", "Candidate group",
                    "Findings", "Attributed to"],
                   [[d["id"], d["type"], d["value"], d["first_seen"], d["grade"], d["rung"],
                     d["candidate_group"], ", ".join(d["findings"]) or "none",
                     d["attributed_to"]] for d in model["_dossiers"]],
                   empty="No entity carries a finding.", grade_cols=(4,)))

    add("<h2>7. Timeline</h2>")
    add(html_table(["When", "Precision", "Entity", "Event", "Grade", "Rung", "Source"],
                   [[t["ts"], t["precision"], f"{t['actor_entity']} {t['actor_value']}".strip(),
                     t["description"], t["grade"], t["rung"] or "not recorded",
                     ", ".join(str(s) for s in t["sources"])] for t in model["_timeline"]],
                   empty="events.jsonl is empty.", grade_cols=(4,)))

    add("<h2>8. Link chart</h2>")
    if model.get("_chart"):
        add("<pre>" + esc(model["_chart"]) + "</pre>")
        add('<p class="note">Mermaid source. Rendered by any mermaid-aware viewer; kept as '
            "text here so the file stays self-contained.</p>")
    else:
        add('<p class="empty">Not generated. Run graph.py --format mermaid over the case '
            "directory and paste the source here.</p>")

    add("<h2>9. Alternative hypotheses considered</h2>")
    add(html_table(["#", "Hypothesis", "Status", "Basis", "Findings"],
                   [[h["id"], h["hypothesis"], h["status"], h["basis"], ", ".join(h["findings"])]
                    for h in model["hypotheses"]],
                   empty="No alternatives line in any finding."))

    add("<h2>10. Gaps and recommended next collection</h2>")
    add("<p><strong>Checked, found nothing</strong></p>")
    add(html_table(["Selector", "Value", "Source", "When", "Coverage", "Meaning"],
                   [[n["type"], n["value"], n["source"], n["checked"], n["coverage"],
                     "informative" if n["informative"] else "uninformative"]
                    for n in model["negative_results"]],
                   empty="No negative result recorded in gaps.md."))
    add("<p><strong>Unresolved identities</strong></p>")
    add(html_table(["Candidate group", "Members", "What they share", "Would resolve it",
                    "Would break it"],
                   [[u["candidate_group"] + " (unresolved)", ", ".join(u["members"]),
                     u["shares"], u["resolves"], u["breaks"]] for u in model["_unresolved"]],
                   empty="No candidate group is open."))
    add("<p><strong>Open questions</strong></p>")
    add(html_table(["Scope Q", "Status", "What is missing"],
                   [[g["scope_question"], g["status"], g["missing"] or "not recorded"]
                    for g in model["gaps"]], empty="Every scope question is answered."))
    add("<p><strong>Recommended next collection</strong></p>")
    add(html_table(["#", "Action", "Closes", "Mode", "Notifies target", "Cost", "Authority"],
                   [[r["id"], r["action"], r["closes"], r["mode"],
                     "yes" if r["notifies_target"] else "no", r["cost"], r["authority_needed"]]
                    for r in model["next_collection"]],
                   empty="No next collection proposed."))

    add("<h2>11. Evidence appendix</h2>")
    add(html_table(["#", "sha256", "Source", "URL", "Retrieved", "Mode", "Bytes", "Cited by"],
                   [[str(n), e["sha256"], e["source_name"], e["url"], e["retrieved"],
                     e["mode"], str(e["bytes"]) if e["bytes"] is not None
                     else "MISSING from evidence/", ", ".join(e["cited_by"])]
                    for n, e in enumerate(model["evidence"], 1)],
                   empty="No finding cites an archived artifact."))

    add("<h2>12. Source reliability summary</h2>")
    add(html_table(["Source", "Class", "Reliability", "Basis", "Findings", "Sole support for"],
                   [[s["source_name"], s["class"], s["reliability"], s["basis"],
                     ", ".join(s["findings"]), ", ".join(s["sole_support_for"]) or "none"]
                    for s in model["source_reliability"]],
                   empty="No source cited by any finding.", grade_cols=()))
    add("<p><strong>Grade distribution</strong></p>")
    add("<pre>" + esc("   ".join(f"{k}: {v}" for k, v in model["_distribution"].items()))
        + "</pre>")
    add('<p class="note">Grades are printed as text. The badge border style repeats the '
        "reliability letter (heavy solid A, solid B, dashed C, dotted D, double E, light "
        "dotted F) so the grade survives a greyscale print and does not depend on colour.</p>")

    add("<h2>Handling and redaction note</h2>")
    add(html_table(["Field", "Value"], [
        ["Redaction default applied", model["_redaction"]],
        ["Unredacted copy location", model["_case_path"]],
        ["Recipients", scope_fields.get("share_with", "unrecorded in scope.md")],
        ["Retention", scope_fields.get("retention", "unrecorded in scope.md")],
    ]))
    add("<p>A removed value is replaced by a visible <code>[redacted: class]</code> marker, "
        "never deleted silently. Entity ids, evidence hashes, grades, rungs, estimative "
        "wording and the out-of-bounds list are never redacted.</p>")

    add("<h2>Pre-delivery checklist</h2>")
    add("<pre>" + esc("\n".join(f"[{state}] {text}" for text, state in checklist(model)))
        + "</pre>")
    add(f'<p class="note">Compiled by scripts/report.py from {esc(model["_case_path"])} at '
        f'{esc(model["generated"])}.</p>')
    add("</main></body></html>")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------------------
# json
# ---------------------------------------------------------------------------

JSON_KEYS = ("case_id", "generated", "report_version", "purpose", "classification",
             "handling", "period_covered", "collection_window", "scope_questions", "bluf",
             "findings", "entities", "events", "negative_results", "hypotheses", "gaps",
             "next_collection", "evidence", "source_reliability", "source_file", "forced")


def render_json(model: dict) -> str:
    """The envelope in 50-reporting.md, in its stated key order. Rendering-only keys
    (leading underscore) are stripped; `source_file` and `forced` are this script's
    two additions and are documented in the module docstring."""
    out = {}
    for key in JSON_KEYS:
        if key in model:
            out[key] = model[key]
    bluf = dict(out.get("bluf", {}))
    bluf.pop("words", None)
    bluf.pop("source", None)
    out["bluf"] = bluf
    for n in out.get("negative_results", []):
        n.pop("id", None)
    return json.dumps(out, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def attach_chart(model: dict, case: Case, red: Redactor) -> None:
    """Section 8 from graph.py if it is importable; a pointer if it is not.

    The chart is part of the deliverable, so it gets the same redaction as the prose.
    Feeding graph.py the raw rows would put every masked value back into the report
    as a node label.
    """
    try:
        import graph  # scripts/graph.py, this file's own directory
    except Exception:  # pragma: no cover - depends on how this file is loaded
        return
    try:
        entities = []
        for n, row in enumerate(case.entities, 1):
            row = dict(row)
            row["value"] = red.value(row.get("type", ""), row.get("value", ""))
            row["notes"] = red.text(str(row.get("notes", "")))
            entities.append((n, row))
        events = []
        for n, row in enumerate(case.events, 1):
            row = dict(row)
            row["description"] = red.text(str(row.get("description", "")))
            events.append((n, row))
        model["_chart"] = graph.render_mermaid(graph.build_chart(entities, events))
    except Exception:  # pragma: no cover - a chart is never worth failing a report over
        return


def now_z() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="report.py",
        description="Compile a case directory into the deliverable described by "
                    "references/50-reporting.md and assets/report-template.md.",
        epilog="Exit codes: 0 compiled, 1 refused by the gate, 2 usage error, "
               "3 case directory unreadable. The gate refuses on: an ungraded finding, "
               "a finding with no source, an unresolved candidate_group treated as "
               "resolved, a banned certainty word in a finding, or any graph.py "
               "--validate violation in entities.jsonl. --force compiles "
               "anyway and stamps the failures into the deliverable itself. "
               "Read-only unless --out is given.",
    )
    p.add_argument("case", nargs="?", metavar="CASE_DIR",
                   help="case directory holding scope.md, findings.md, entities.jsonl, "
                        "events.jsonl, gaps.md, ledger.jsonl and evidence/")
    p.add_argument("--format", choices=("markdown", "html", "json"), default="markdown",
                   help="output format (default: markdown)")
    p.add_argument("--out", metavar="PATH",
                   help="write to PATH instead of stdout; parent directories are created")
    p.add_argument("--redact", choices=("partial", "full", "none"), default=None,
                   help="redaction of the PII classes in references/00-legal-ethics.md "
                        "section 5 (default: the redaction_default in scope.md, else "
                        "partial). Redaction is visible: values become [redacted: class]")
    p.add_argument("--force", action="store_true",
                   help="compile despite gate failures, stamping a loud override banner "
                        "listing every failed check into the deliverable")
    p.add_argument("--report-version", type=int, default=1, metavar="N",
                   help="report version number for the header (default: 1)")
    p.add_argument("--selfcheck", action="store_true",
                   help="run internal assertions against temporary fixture cases and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selfcheck:
        return demo()
    if not args.case:
        parser.error("CASE_DIR is required unless --selfcheck is given")

    case_dir = Path(args.case)
    if not case_dir.is_dir():
        print(f"error: {case_dir} is not a directory", file=sys.stderr)
        return 3
    if not (case_dir / "findings.md").is_file():
        print(f"error: {case_dir / 'findings.md'} not found - is {case_dir} a case directory?",
              file=sys.stderr)
        return 3

    try:
        case = Case(case_dir)
    except OSError as exc:
        print(f"error: cannot read {case_dir}: {exc}", file=sys.stderr)
        return 3

    blockers = gate(case)
    if blockers and not args.force:
        print(f"REFUSED to compile {case_dir}: {len(blockers)} blocking item(s).",
              file=sys.stderr)
        for b in blockers:
            print("  " + b.line(), file=sys.stderr)
        print("Fix them in the case files, or re-run with --force to compile with a "
              "permanent override banner in the deliverable.", file=sys.stderr)
        return 1

    redact = args.redact or default_redaction(case)
    red = Redactor(redact, case.entities)
    model = build_model(case, red, blockers, bool(blockers and args.force),
                        args.report_version, now_z())
    attach_chart(model, case, red)

    if args.format == "html":
        text = render_html(model)
    elif args.format == "json":
        text = render_json(model)
    else:
        text = render_markdown(model)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out} ({len(text.encode('utf-8'))} bytes, {args.format}, "
              f"redaction {redact})")
    else:
        sys.stdout.write(text)

    if blockers and args.force:
        print(f"warning: compiled under --force with {len(blockers)} failed check(s); "
              "the override banner is in the deliverable.", file=sys.stderr)
    return 0


def default_redaction(case: Case) -> str:
    value = str(case.scope["fields"].get("redaction_default", "")).lower()
    # assets/case-skeleton/scope.md offers a third word this script has no mode for.
    # "identifiers-withheld" IS the `full` mode - every natural-person identifier class
    # masked - and an unrecognised value falling through to `partial` would silently
    # give a case that asked for the strictest setting the middle one.
    if value.startswith("identifiers"):
        return "full"
    for mode in ("full", "partial", "none"):
        if value.startswith(mode):
            return mode
    return "partial"


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

FIXTURE_EVIDENCE = b"<html><title>Example registry record</title></html>"
FIXTURE_EVIDENCE_2 = b"<html><title>Example CT log entry</title></html>"
SHA1_ = hashlib.sha256(FIXTURE_EVIDENCE).hexdigest()
SHA2_ = hashlib.sha256(FIXTURE_EVIDENCE_2).hexdigest()

FIX_SCOPE = """# Scope — case `fixture-case`

| Field | Value |
|---|---|
| slug | fixture-case |
| opened | 2026-07-28T09:00:00Z |
| purpose | kyc |
| target | Example Holdings Ltd |
| target_type | company |
| target_category | org |
| authority | compliance mandate |
| jurisdiction | GB / GB |
| public_interest | n/a |
| active_allowed | false |

| Field | Value |
|---|---|
| requester | Compliance, Example Bank |
| analyst | analyst-1 |
| period_covered | 2019-01-01..2026-07-28 |
| classification | internal only |
| redaction_default | partial |
| share_with | Compliance committee |
| retention | 6 years, compliance deletes |

## 5. Question

Q1. Is Example Holdings Ltd registered and active in GB?
Q2. Who is the natural person behind the registered contact address?

Decision this feeds: `onboard, reject, or escalate to EDD`

## 6. Out of bounds

[x] minors, including any account that appears to belong to one
[x] home address, physical location, and movement patterns
[x] non-public breach corpora and purchased credential dumps

## 7. Active collection

active_allowed: no
"""

FIX_FINDINGS = """# Findings — case `fixture-case`

### f-1 — Certificate logged for the trading domain

```
claim:      A certificate covering shop.example.test was logged by a CT log on
            2024-11-30.
grade:      A1
rung:       observed
estimative: none
answers:    Q1
entities:   e-1
mode:       passive
handling:   none

sources:
  1. Example CT log
     url:       https://ct.example.test/entry/1
     retrieved: 2026-07-28T09:14:02Z
     sha256:    {sha2}
     source_grade: A

reasoning:  The log entry is self-authenticating and mirrored across logs, which is
            the one single-source exemption to the A1 rule in 41-confidence.md.

alternatives:
  - A certificate issued for an unrelated host with a colliding name — rejected because the
    SAN list carries the exact string.

disconfirms: The entry absent from a second independent log mirror.
```

### f-2 — Company is on the register

```
claim:      The register records Example Holdings Ltd as active under company number 01234567.
grade:      A3
rung:       reported
estimative: none
answers:    Q1
entities:   e-2, e-5
mode:       passive
handling:   none

sources:
  1. Example Registry
     url:       https://registry.example.test/company/01234567
     retrieved: 2026-07-28T09:20:00Z
     sha256:    {sha1}
     source_grade: A

reasoning:  One authoritative register, nothing else corroborating the filing, so the
            claim digit is 3 and not 1. The same record gives the registered office as
            221B Baker Street, London.

alternatives:
  - A struck-off status not yet published — not excluded; the gazette was not checked.

disconfirms: A gazette notice of strike-off dated before the retrieval timestamp.
```

### f-3 — Identity behind the contact address is open

```
claim:      That e-3 and e-4 are the same natural person is roughly even chance.
grade:      C3
rung:       inferred
estimative: roughly even chance
answers:    Q2
entities:   e-3, e-4
mode:       passive
handling:   partial

sources:
  1. Example Registry
     url:       https://registry.example.test/officers/01234567
     retrieved: 2026-07-28T09:25:00Z
     sha256:    {sha1}
     source_grade: A

reasoning:  e-3 and e-4 share a person_name string only. They stay in candidate_group cg-1,
            unresolved, and are not merged.

alternatives:
  - Two unrelated people sharing a common name — not excluded.

disconfirms: A filing giving both a distinct date of birth.
```
""".format(sha1=SHA1_, sha2=SHA2_)

FIX_ENTITIES = [
    {"id": "e-1", "type": "domain", "value": "shop.example.test",
     "first_seen": "2026-07-28T09:14:02Z", "grade": "A1",
     "sources": ["2026-07-28T09:14:02Z"], "candidate_group": None,
     "notes": "SAN on the logged certificate"},
    {"id": "e-2", "type": "company", "value": "Example Holdings Ltd",
     "first_seen": "2026-07-28T09:20:00Z", "grade": "A3",
     "sources": ["2026-07-28T09:20:00Z"], "candidate_group": None, "notes": ""},
    {"id": "e-3", "type": "person_name", "value": "Alex Morgan",
     "first_seen": "2026-07-28T09:25:00Z", "grade": "C3",
     "sources": ["2026-07-28T09:25:00Z"], "candidate_group": "cg-1",
     "notes": "officer filing"},
    {"id": "e-4", "type": "person_name", "value": "Alex Morgan",
     "first_seen": "2026-07-28T09:26:00Z", "grade": "C3",
     "sources": ["2026-07-28T09:26:00Z"], "candidate_group": "cg-1",
     "notes": "second filing, no shared datapoint beyond the name string"},
    {"id": "e-5", "type": "address", "value": "221B Baker Street, London",
     "first_seen": "2026-07-28T09:27:00Z", "grade": "A3",
     "sources": ["2026-07-28T09:27:00Z"], "candidate_group": None,
     "notes": "registered office on the filing"},
]

FIX_EVENTS = [
    {"ts": "2024-11-30", "actor_entity": "e-1",
     "description": "Certificate issued covering shop.example.test", "grade": "A1",
     "sources": ["https://ct.example.test/entry/1"], "precision": "day"},
    {"ts": "2019-03-04", "actor_entity": "e-2",
     "description": "Company incorporated under number 01234567", "grade": "A3",
     "sources": ["https://registry.example.test/company/01234567"], "precision": "day"},
]

FIX_LEDGER = [
    {"ts": "2026-07-28T09:14:02Z", "actor": "main", "action": "collect",
     "source": "Example CT log", "query": "Q1: CT search for example.test",
     "result": "1 certificate", "result_sha256": SHA2_, "mode": "passive"},
    {"ts": "2026-07-28T09:20:00Z", "actor": "main", "action": "collect",
     "source": "Example Registry", "query": "Q1: company 01234567",
     "result": "active record", "result_sha256": SHA1_, "mode": "passive"},
    {"ts": "2026-07-28T09:25:00Z", "actor": "main", "action": "pivot",
     "source": "Example Registry", "query": "Q2: company:01234567 -> officers",
     "result": "person_name:Alex Morgan", "result_sha256": SHA1_, "mode": "passive"},
    {"ts": "2026-07-28T09:30:00Z", "actor": "main", "action": "collect",
     "source": "Example Sanctions List", "query": "Q1: name screen Example Holdings Ltd",
     "result": "none", "result_sha256": None, "mode": "passive"},
]

FIX_GAPS = """# Gaps — case `fixture-case`

## 1. Negative results

| # | selector checked | value | source | query | when (ISO8601Z) | mode | result | coverage | meaning of absence |
|---|---|---|---|---|---|---|---|---|---|
| n-1 | company | Example Holdings Ltd | Example Sanctions List | name screen | 2026-07-28T09:30:00Z | passive | none | yes | informative |
| n-2 | person_name | Alex Morgan | Example Adverse Media | name screen | 2026-07-28T09:35:00Z | passive | none | unknown | uninformative |

## 2. Open questions

| scope Q | question (short) | status | findings so far | what is missing |
|---|---|---|---|---|
| Q1 | registered and active | answered | f-1, f-2 | nothing |
| Q2 | natural person behind the address | partial | f-3 | a date of birth on either filing |

### Unresolved identities

| id | candidate_group | member entities | what they share | named datapoint that would resolve it | what would break the link |
|---|---|---|---|---|---|
| G-1 | cg-1 | e-3, e-4 | person_name string only | date of birth on a filing | distinct dates of birth |

## 3. Recommended next collection

| # | action | selector in | selector out | closes | mode | notifies target | cost | auth needed | expected yield |
|---|---|---|---|---|---|---|---|---|---|
| r-1 | order the full officer filing | company_number | person_name | Q2 | passive | no | paid: 3 GBP | none | high |
"""

FIX_BLUF = """grade: A3
would_change: A gazette strike-off notice predating the retrieval timestamp.

Example Holdings Ltd is recorded as active on the GB register under company number
01234567 (A3, f-2), and a certificate covering its trading domain was logged in
November 2024 (A1, f-1). The natural person behind the registered contact address is
not resolved: two officer records share a name string only, and that they are the same
person is roughly even chance (C3, f-3).
"""


def write_fixture(root: Path, **override) -> Path:
    """A small, complete, clean case. Overrides let each refusal be tripped in turn."""
    case = root
    case.mkdir(parents=True, exist_ok=True)
    (case / "evidence").mkdir(exist_ok=True)
    (case / "report").mkdir(exist_ok=True)
    (case / "evidence" / f"{SHA1_}.html").write_bytes(FIXTURE_EVIDENCE)
    (case / "evidence" / f"{SHA2_}.html").write_bytes(FIXTURE_EVIDENCE_2)
    (case / "scope.md").write_text(override.get("scope", FIX_SCOPE), encoding="utf-8")
    (case / "findings.md").write_text(override.get("findings", FIX_FINDINGS),
                                      encoding="utf-8")
    (case / "gaps.md").write_text(override.get("gaps", FIX_GAPS), encoding="utf-8")
    (case / "report" / "bluf.md").write_text(override.get("bluf", FIX_BLUF), encoding="utf-8")
    for name, rows in (("entities.jsonl", override.get("entities", FIX_ENTITIES)),
                       ("events.jsonl", override.get("events", FIX_EVENTS)),
                       ("ledger.jsonl", override.get("ledger", FIX_LEDGER))):
        (case / name).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return case


def checks(blockers: list[Blocker]) -> set[str]:
    return {b.check for b in blockers}


def demo() -> int:
    with tempfile.TemporaryDirectory(prefix="osint-report-") as tmp:
        root = Path(tmp)

        # --- clean case compiles, and trips nothing --------------------------
        clean = write_fixture(root / "clean")
        case = Case(clean)
        blockers = gate(case)
        assert blockers == [], f"clean case produced blockers: {[b.line() for b in blockers]}"

        assert [f["id"] for f in case.findings] == ["f-1", "f-2", "f-3"], \
            f"findings parsed: {[f['id'] for f in case.findings]}"
        assert case.findings[0]["grade"] == "A1"
        assert case.findings[2]["entities"] == ["e-3", "e-4"]
        assert case.findings[1]["sources"][0]["sha256"] == SHA1_
        assert len(case.scope["questions"]) == 2, case.scope["questions"]
        assert case.scope["fields"]["purpose"] == "kyc"
        assert len(case.scope["out_of_bounds"]) == 3, case.scope["out_of_bounds"]
        assert len(case.gaps["negatives"]) == 2, case.gaps["negatives"]
        assert len(case.gaps["next_collection"]) == 1, case.gaps["next_collection"]

        red = Redactor(default_redaction(case), case.entities)
        assert red.mode == "partial", red.mode
        # The skeleton's third word must not silently downgrade to the middle mode.
        for word, want in (("identifiers-withheld", "full"), ("full", "full"),
                           ("none", "none"), ("partial", "partial"), ("", "partial")):
            probe = Case(write_fixture(root / "redact-probe", scope=FIX_SCOPE.replace(
                "| redaction_default | partial |", f"| redaction_default | {word} |")))
            assert default_redaction(probe) == want, (word, default_redaction(probe))
        model = build_model(case, red, [], False, 1, "2026-07-28T14:00:00Z")
        md = render_markdown(model)
        html_out = render_html(model)
        js = json.loads(render_json(model))

        # --- the compiled markdown carries what the template demands ---------
        for heading in ("## 1. Header", "## 2. Bottom Line Up Front",
                        "## 3. Scope and authority as recorded",
                        "## 4. Methodology and limitations", "## 5. Key findings",
                        "## 6. Entity dossiers", "## 7. Timeline", "## 8. Link chart",
                        "## 9. Alternative hypotheses considered",
                        "## 10. Gaps and recommended next collection",
                        "## 11. Evidence appendix", "## 12. Source reliability summary",
                        "## Handling and redaction note", "## Pre-delivery checklist"):
            assert heading in md, f"markdown is missing {heading}"
        assert "f-1" in md and "f-3" in md
        assert SHA1_ in md, "evidence hash must reach the appendix"
        assert "cg-1 (unresolved)" in md, "an open candidate group must say unresolved"
        assert "minors" in md, "the out-of-bounds list is never redacted"
        assert "Example Sanctions List" in md, "negative results are results"
        assert "!! COMPILED UNDER --force" not in md, "clean case must carry no override banner"

        # --- json is the 50-reporting.md envelope ----------------------------
        for key in ("case_id", "generated", "report_version", "purpose", "classification",
                    "handling", "period_covered", "collection_window", "scope_questions",
                    "bluf", "findings", "entities", "events", "negative_results",
                    "hypotheses", "gaps", "next_collection", "evidence",
                    "source_reliability"):
            assert key in js, f"json envelope is missing {key}"
        assert "forced" not in js, "clean case must not carry a forced block"
        assert [f["id"] for f in js["findings"]] == ["f-1", "f-2", "f-3"], "findings sort by id"
        assert js["evidence"] == sorted(js["evidence"], key=lambda e: e["sha256"]), \
            "evidence sorts by sha256"
        assert js["findings"][0]["estimative"] is None, "'none' exports as JSON null"
        assert js["findings"][2]["estimative"] == "roughly even chance"
        assert js["findings"][0]["inference_rung"] == "observed", "rung -> inference_rung"
        assert js["findings"][0]["disconfirming_evidence"], "disconfirms -> disconfirming_evidence"
        assert js["findings"][2]["entity_refs"] == ["e-3", "e-4"], "entities -> entity_refs"
        assert js["findings"][1]["sources"][0]["reliability"] == "A", "source_grade -> reliability"
        assert js["handling"] == "partial", "top-level handling is the strictest finding"
        assert "Alex Morgan" not in json.dumps(js), \
            "the json export is a deliverable and carries the same redaction"
        assert any("A.M." == e["value"] for e in js["entities"]), \
            "entities[] ship redacted, not raw"
        neg = {n["source"]: n for n in js["negative_results"]}
        assert neg["Example Sanctions List"]["informative"] is True
        assert neg["Example Adverse Media"]["informative"] is False, \
            "coverage unknown is never informative"

        # --- redaction removes the value and leaves a visible marker ---------
        assert "221B Baker Street" not in md, "a partial-redacted address keeps its number out"
        assert "[redacted: house number] Baker Street, London" in md, \
            "redaction must be visible, not silent"
        assert "A.M." in md, "person_name partial-redacts to initials"
        assert "Alex Morgan" not in md, "the raw person_name must not reach the deliverable"
        full = Redactor("full", case.entities)
        full_md = render_markdown(build_model(case, full, [], False, 1,
                                              "2026-07-28T14:00:00Z"))
        assert "[redacted: person_name]" in full_md and "Alex Morgan" not in full_md
        assert "[redacted: home address]" in full_md, "full redaction names the PII class"
        raw = Redactor("none", case.entities)
        raw_md = render_markdown(build_model(case, raw, [], False, 1, "2026-07-28T14:00:00Z"))
        assert "221B Baker Street, London" in raw_md, "--redact none keeps the case values"
        assert redact_value("email", "jan.novak@example.test", "partial") == "j****@example.test"
        assert redact_value("phone", "+14155550167", "partial") == "+1 415 *** ##67"
        assert redact_value("coordinates", "51.5,0.12", "partial") == "[redacted: coordinates]", \
            "rounded coordinates still locate, so partial equals full"
        assert redact_value("username", "publichandle", "partial") == "publichandle"
        assert Redactor("partial", case.entities).text(
            "contact bob@example.test") == "contact b****@example.test"

        # --- the link chart is part of the deliverable and gets redacted too --
        charted = build_model(case, red, [], False, 1, "2026-07-28T14:00:00Z")
        attach_chart(charted, case, red)
        if charted.get("_chart"):
            assert "Alex Morgan" not in charted["_chart"], \
                "the chart must not put an unredacted value back into the report"
            assert "cg-1" in charted["_chart"], "the open group must still be drawn as one"
            assert "A.M." in charted["_chart"]
            assert "```mermaid" in render_markdown(charted)

        # --- html is self-contained: no external asset reference -------------
        assert html_out.startswith("<!doctype html>")
        assert "src=" not in html_out, "no external asset may be referenced"
        assert not re.search(r"href\s*=\s*[\"']https?:", html_out), "no external link"
        assert "@import" not in html_out and "url(http" not in html_out
        assert "<link" not in html_out and "<script" not in html_out
        assert "prefers-color-scheme: dark" in html_out, "must read in both themes"
        assert "@media print" in html_out, "these get printed"
        assert 'class="tw"' in html_out and "overflow-x:auto" in html_out, \
            "tables scroll inside their own container"
        assert 'class="g g-A"' in html_out and "border-style:dashed" in html_out, \
            "grades must be distinguishable without colour"
        assert "https://registry.example.test/company/01234567" in html_out, \
            "source URLs still travel with the report, as text"

        # --- template scaffolding never reaches a deliverable ----------------
        # A cell that OPENS with a `<token>` is scaffolding even with trailing prose.
        # The skeleton ships `<earliest>..<latest>, or "no time bound"`, and a
        # `$`-anchored placeholder pattern let it through into a compiled report.
        assert is_placeholder("<name or role, and organization>")
        assert is_placeholder('<earliest>..<latest>, or "no time bound"')
        assert not is_placeholder("2019-01-01..2026-07-28")
        assert not is_placeholder("a < b")
        leaky = Case(write_fixture(root / "leaky", scope=FIX_SCOPE.replace(
            "| period_covered | 2019-01-01..2026-07-28 |",
            '| period_covered | <earliest>..<latest>, or "no time bound" |')))
        leaky_md = render_markdown(build_model(
            leaky, Redactor("partial", leaky.entities), [], False, 1, "2026-07-28T14:00:00Z"))
        assert "<earliest>" not in leaky_md, "a template placeholder reached the deliverable"
        assert "no time bound" in leaky_md, "the documented default must replace it"

        # --- an alternative splits on either dash ----------------------------
        # Printing "not stated" over a reason the analyst did state is a false claim
        # about their work, and a hyphen is what a Windows keyboard produces.
        assert split_alternative("A — rejected because B") == ("A", "rejected because B")
        assert split_alternative("A - rejected because B") == ("A", "rejected because B")
        assert split_alternative("a well-known thing") == ("a well-known thing", "")
        hyph = Case(write_fixture(root / "hyphen", findings=FIX_FINDINGS.replace(
            "colliding name — rejected because", "colliding name - rejected because", 1)))
        hyph_alt = build_model(hyph, Redactor("none", hyph.entities), [], False, 1,
                               "2026-07-28T14:00:00Z")["findings"][0]["alternatives_rejected"][0]
        assert hyph_alt["why_rejected"].startswith("rejected because"), hyph_alt
        assert "-" not in hyph_alt["hypothesis"][-1:], hyph_alt

        # --- each refusal fires on a case crafted to trip it -----------------
        ungraded = write_fixture(root / "ungraded",
                                 findings=FIX_FINDINGS.replace("grade:      A3\n",
                                                               "grade:      \n", 1))
        b = gate(Case(ungraded))
        assert checks(b) == {"ungraded"}, [x.line() for x in b]
        assert [x.item for x in b] == ["f-2"], "the blocker must name the finding id"

        badgrade = write_fixture(root / "badgrade",
                                 findings=FIX_FINDINGS.replace("grade:      C3",
                                                               "grade:      B9", 1))
        b = gate(Case(badgrade))
        assert checks(b) == {"ungraded"} and b[0].item == "f-3", [x.line() for x in b]

        nosrc = FIX_FINDINGS.split("### f-2")[0] + """### f-2 — Company is on the register

```
claim:      The register records Example Holdings Ltd as active.
grade:      A3
rung:       reported
estimative: none
answers:    Q1
entities:   e-2
mode:       passive
handling:   none

reasoning:  No source block at all.

disconfirms: A gazette notice of strike-off.
```
"""
        unsourced = write_fixture(root / "unsourced", findings=nosrc)
        b = gate(Case(unsourced))
        assert checks(b) == {"unsourced"}, [x.line() for x in b]
        assert b[0].item == "f-2"

        banned = write_fixture(
            root / "banned",
            findings=FIX_FINDINGS.replace(
                "One authoritative register, nothing else corroborating",
                "This obviously proves the company is real; nothing else corroborates", 1))
        b = gate(Case(banned))
        assert checks(b) == {"banned"}, [x.line() for x in b]
        assert {x.item for x in b} == {"f-2"}
        assert len(b) == 2, "both 'obviously' and 'proves' must be named"

        confirmed = write_fixture(
            root / "confirmed",
            findings=FIX_FINDINGS.replace("nothing else corroborating the filing",
                                          "the status is confirmed by the filing", 1))
        b = gate(Case(confirmed))
        assert checks(b) == {"banned"} and "credibility digit 3" in b[0].detail, \
            [x.line() for x in b]
        # ... but 'confirmed' at digit 1 is legal, and must not fire.
        ok_confirmed = write_fixture(
            root / "confirmed-ok",
            findings=FIX_FINDINGS.replace(
                "The log entry is self-authenticating",
                "The entry is confirmed by a second mirror and is self-authenticating", 1))
        assert gate(Case(ok_confirmed)) == [], "'confirmed' at credibility 1 is permitted"

        merged = write_fixture(
            root / "merged",
            findings=FIX_FINDINGS.replace(
                "claim:      That e-3 and e-4 are the same natural person is roughly even "
                "chance.",
                "claim:      e-3 and e-4 are the same natural person.", 1)
            .replace("estimative: roughly even chance", "estimative: none", 1)
            .replace("They stay in candidate_group cg-1,\n            unresolved, and are "
                     "not merged.", "They are the same person.", 1))
        b = gate(Case(merged))
        assert checks(b) == {"merged"}, [x.line() for x in b]
        assert b[0].item == "f-3" and "cg-1" in b[0].detail

        # The canonical correlated wording holds the identity open without an
        # estimative phrase, and must not fire: a gate that refuses a correctly
        # written correlated finding gets switched off.
        canonical = write_fixture(
            root / "canonical",
            findings=FIX_FINDINGS.replace(
                "claim:      That e-3 and e-4 are the same natural person is roughly even "
                "chance.",
                "claim:      e-3 and e-4 share a person_name string.", 1)
            .replace("estimative: roughly even chance", "estimative: none", 1)
            .replace("They stay in candidate_group cg-1,\n            unresolved, and are "
                     "not merged.", "No identity claim is made here.", 1))
        assert gate(Case(canonical)) == [], \
            "'No identity claim is made here' must satisfy the merged check"

        # A group whose notes record the resolution is closed, and must not fire.
        resolved_entities = [dict(e) for e in FIX_ENTITIES]
        resolved_entities[3]["notes"] = ("merged with e-3: company_number 01234567 present "
                                        "in both filings")
        resolved = write_fixture(
            root / "resolved", entities=resolved_entities,
            findings=FIX_FINDINGS.replace(
                "claim:      That e-3 and e-4 are the same natural person is roughly even "
                "chance.",
                "claim:      e-3 and e-4 are the same natural person.", 1)
            .replace("estimative: roughly even chance", "estimative: none", 1))
        assert gate(Case(resolved)) == [], "a resolved candidate group must not block"

        # graph.py --validate is part of this gate, not just of the command prose: an
        # entity row it rejects blocks the compile here too.
        broken = [dict(e) for e in FIX_ENTITIES]
        broken[0]["type"] = "domains"  # non-canonical: CONTRACT.md section 4, never a plural
        b = gate(Case(write_fixture(root / "graph-bad", entities=broken)))
        assert checks(b) == {"graph"}, [x.line() for x in b]
        assert b[0].item == "e-1", [x.line() for x in b]
        # ...and a case with no entities.jsonl at all is not blocked by its absence.
        noent = write_fixture(root / "no-entities")
        (noent / "entities.jsonl").unlink()
        assert graph_blockers(Case(noent)) == []

        # --- --force stamps the failures into the deliverable ----------------
        bad = Case(banned)
        bad_blockers = gate(bad)
        forced_model = build_model(bad, Redactor("partial", bad.entities), bad_blockers,
                                   True, 1, "2026-07-28T14:00:00Z")
        forced_md = render_markdown(forced_model)
        forced_html = render_html(forced_model)
        forced_json = json.loads(render_json(forced_model))
        assert "!! COMPILED UNDER --force" in forced_md
        assert "[banned] f-2" in forced_md, "the banner names every failed check by id"
        assert "OVERRIDDEN" in forced_html
        assert forced_json["forced"]["overridden"] is True
        assert forced_json["forced"]["failed_checks"], "the export records the override too"

        # --- CLI wiring -------------------------------------------------------
        print("--- exercising the CLI: the refusal and the error below are the expected "
              "output of the exit-code checks, not selfcheck failures ---", flush=True)
        assert main([str(clean), "--format", "json", "--out",
                     str(root / "o" / "r.json")]) == 0
        assert (root / "o" / "r.json").is_file()
        assert main([str(banned)]) == 1, "the gate must exit non-zero"
        assert main([str(banned), "--force", "--out", str(root / "o" / "f.md")]) == 0
        assert "!! COMPILED UNDER --force" in (root / "o" / "f.md").read_text(encoding="utf-8")
        assert main([str(root / "nonexistent")]) == 3

    print("report.py selfcheck: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
