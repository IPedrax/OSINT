#!/usr/bin/env python3
"""Scaffold an OSINT case directory and seed its ledger with the frozen scope.

Phase 0, standard library only (CONTRACT.md section 10). Windows-safe: pathlib
throughout, no hardcoded separators, no network calls at import time.

    python case_init.py --root ./cases --slug acme-corp-2026-07 \
        --purpose security --target acme.example --target-type domain \
        --target-category org --question "Which assets are unmanaged?" \
        --authority "Engagement letter ACME-2026-114" --jurisdiction "US-DE / UK"

Exit codes: 0 ok; 1 a required field is blank, the slug sanitises to nothing or to a
reserved Windows device name, --target-type is not a CONTRACT.md section 4 type, or an
--in-bounds substring matches no ticked exclusion / carries a blank reason;
2 argparse usage error, including an out-of-range --purpose or --target-category,
an unpaired --in-bounds/--in-bounds-reason, or --purpose self_audit without
--out-of-bounds "any third party";
3 case already exists (never clobbered). An unsafe slug is silently rewritten to
[a-z0-9-] rather than rejected, so read the case path the script prints back.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PURPOSES = ("security", "journalism", "kyc", "self_audit", "education")

TARGET_CATEGORIES = ("org", "public-figure", "self", "private-individual")

# CONTRACT.md section 4, exact strings, same order. No synonyms, no plurals.
SELECTOR_TYPES = (
    "email", "username", "person_name", "phone", "domain", "subdomain", "ip", "asn",
    "netblock", "url", "ssl_cert", "company", "company_number", "address", "photo",
    "video", "document", "crypto_address", "tx_hash", "vehicle_plate", "vessel",
    "aircraft", "coordinates", "file_hash", "social_profile", "breach_record",
)

# CONTRACT.md section 7, exact names and order. Nothing else goes in a ledger row.
LEDGER_FIELDS = (
    "ts",
    "actor",
    "action",
    "source",
    "query",
    "result",
    "result_sha256",
    "mode",
)

# PLAN.md section 2: default play order per purpose branch.
FIRST_PLAY = {
    "security": "/osint:osint-infra   (then media, crypto)",
    "journalism": "/osint:osint-verify  (then geoint, corporate, identity)",
    "kyc": "/osint:osint-corporate  (then identity, adverse media)",
    "self_audit": "/osint:osint-identity  (then infra, media)",
    "education": "any play, sanctioned target only",
}

# references/00-legal-ethics.md section 2 puts a mandated missing-persons or court-ordered
# locate on the `security` branch, and its selector is a person, not infrastructure. Keyed on
# the selector so a domain engagement (the ordinary security case) is untouched.
PERSON_SELECTORS = frozenset(
    {"person_name", "email", "username", "phone", "social_profile"}
)

# A case whose recorded question IS an officer/UBO question cannot have officer lookups
# excluded for its life; scope.md section 6 makes the tick binding until the case closes.
RE_OFFICER_QUESTION = re.compile(
    r"\b(officers?|directors?|directorships?|shareholders?|beneficial owners?"
    r"|UBOs?|PSCs?)\b",
    re.I,
)


def first_play(purpose: str, target_type: str) -> str:
    """Branch default, overridden for a security-branch locate on a person."""
    if purpose == "security" and target_type in PERSON_SELECTORS:
        return "/osint:osint-identity  (then corporate, media)"
    return FIRST_PLAY[purpose]

_SLUG_MAX = 64

# Reserved device names are unusable as directory names on Windows.
_WIN_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{n}" for n in range(1, 10)]
    + [f"lpt{n}" for n in range(1, 10)]
)


def utc_now() -> str:
    """UTC ISO8601 with a literal Z, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_slug(raw: str) -> str:
    """Lowercase, collapse anything not [a-z0-9] to single hyphens, strip ends.

    Path traversal, drive letters and spaces cannot survive this, so the result
    is always a single filesystem-safe directory name.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (raw or "").strip().lower()).strip("-")
    slug = slug[:_SLUG_MAX].strip("-")
    if not slug:
        raise ValueError("slug is empty after sanitisation; give it letters or digits")
    if slug in _WIN_RESERVED:
        raise ValueError(f"slug {slug!r} is a reserved Windows device name")
    return slug


def find_skeleton(start: Path | None = None) -> Path | None:
    """Locate assets/case-skeleton/ relative to this script, if it exists."""
    base = (start or Path(__file__).resolve().parent).parent
    candidate = base / "assets" / "case-skeleton"
    return candidate if candidate.is_dir() else None


def _numbered_questions(question: str) -> str:
    """Q1..Qn from a newline-separated --question value. Ids are minted here."""
    lines = [q.strip() for q in question.splitlines() if q.strip()]
    return "\n".join(f"Q{i}. {q}" for i, q in enumerate(lines, 1))


def scope_table(
    slug: str,
    ts: str,
    purpose: str,
    target: str,
    target_type: str,
    target_category: str,
    authority: str,
    jurisdiction: str,
    public_interest: str,
    active_allowed: bool,
) -> str:
    """The frozen intake fields, machine-checkable, identical in both scope paths."""
    return f"""| Field | Value |
|---|---|
| slug | {slug} |
| opened | {ts} |
| purpose | {purpose} |
| target | {target} |
| target_type | {target_type or "unrecorded"} |
| target_category | {target_category} |
| authority | {authority} |
| jurisdiction | {jurisdiction} |
| public_interest | {public_interest or "n/a"} |
| active_allowed | {json.dumps(active_allowed)} |"""


_POSTURE = """- Passive only unless `active_allowed` is true above, and then only per-action with a fresh
  confirmation naming that action.
- Provenance on every finding: source URL, retrieval timestamp, sha256 of an archived copy,
  Admiralty source grade plus credibility grade. Otherwise it stays out of `findings.md`.
- Negative results are logged in `gaps.md`.
- No entity merge without a named linking datapoint; hold candidates in a `candidate_group`.
- `jurisdiction` may be recorded as `unknown` — that is a valid answer. A blank is what fails.
- Sub-questions are appended as `Q2.`, `Q3.` ... by an `## Amendment` block; findings cite them
  by id."""


def render_scope(
    slug: str,
    ts: str,
    purpose: str,
    target: str,
    target_category: str,
    question: str,
    authority: str,
    jurisdiction: str,
    out_of_bounds: list[str],
    active_allowed: bool,
    target_type: str = "",
    public_interest: str = "",
    decision: str = "",
) -> str:
    """Fallback scope.md, used only when no skeleton scope.md was copied in."""
    bounds = "\n".join(f"- {item}" for item in out_of_bounds) or "- (none recorded)"
    return f"""# Case {slug}

Frozen {ts}. These answers are the authorization for this case. Do not edit a line
above the amendment marker; append an `## Amendment <UTC-ts>` section instead.

{scope_table(slug, ts, purpose, target, target_type, target_category, authority,
             jurisdiction, public_interest, active_allowed)}

## Question

{_numbered_questions(question)}

Decision this feeds: `{decision.strip() or 'UNRECORDED — fill before collecting'}`

The case closes when this question is answered or shown unanswerable. Findings that do
not bear on it do not enter the report.

## Out of bounds

{bounds}

## Standing posture

{_POSTURE}

## Amendments

Append below. Each amendment also gets an `action:"scope"` row in `ledger.jsonl`.
"""


# Exact placeholder strings in assets/case-skeleton/scope.md. A template edit that breaks
# one of these fails demo() rather than silently shipping an unfilled slot.
def fill_scope(
    template: str,
    slug: str,
    ts: str,
    purpose: str,
    target: str,
    target_type: str,
    target_category: str,
    question: str,
    authority: str,
    jurisdiction: str,
    out_of_bounds: list[str],
    active_allowed: bool,
    public_interest: str = "",
    decision: str = "",
) -> str:
    """Substitute recorded values into the skeleton template, preserving its sections."""
    # §9 is the machine record that the gate ran and accepted. case_init.py only ever runs on
    # an accepted intake — a refusal is written to cases/_refusals.jsonl and no case dir is
    # created — so the result is known here and must not ship as an unfilled placeholder.
    gate_result = "accepted-with-limits" if out_of_bounds else "accepted"
    limits = "; ".join(out_of_bounds) if out_of_bounds else "none"
    slots = [
        ("# Scope — case `<slug>`", f"# Scope — case `{slug}`"),
        (
            "Selected branch: `<security|journalism|kyc|self_audit|education>`",
            f"Selected branch: `{purpose}`\n\n### Recorded at intake, frozen\n\n"
            + scope_table(slug, ts, purpose, target, target_type, target_category,
                          authority, jurisdiction, public_interest, active_allowed),
        ),
        ("| `case_id` | `<slug, kebab-case, no personal names>` |", f"| `case_id` | `{slug}` |"),
        ("| `opened` | `<ISO8601Z>` |", f"| `opened` | `{ts}` |"),
        ("| `target` | `<the selector or name the case starts from>` |", f"| `target` | `{target}` |"),
        (
            "| `target_type` | `<canonical selector type: domain, company, username, email, person_name, ...>` |",
            f"| `target_type` | `{target_type or 'unrecorded'}` |",
        ),
        (
            "| `target_category` | `<org \\| public-figure \\| self \\| private-individual>` |",
            f"| `target_category` | `{target_category}` |",
        ),
        (
            "| `authority` | `<what permits this work: engagement letter, assignment, mandate, self>` |",
            f"| `authority` | `{authority}` |",
        ),
        (
            "| `jurisdiction` | `<requester jurisdiction>` / `<target jurisdiction(s)>` |",
            f"| `jurisdiction` | `{jurisdiction}` |",
        ),
        ("Q1. <question>\nQ2. <question>\nQ3. <question>", _numbered_questions(question)),
        (
            "Decision this feeds: `<what the requester will do differently depending on the answer>`",
            f"Decision this feeds: `{decision.strip() or 'UNRECORDED — fill before collecting'}`",
        ),
        ("| `gate_run_by` | `<main session \\| analyst name>` |", "| `gate_run_by` | `main session` |"),
        ("| `gate_ts` | `<ISO8601Z>` |", f"| `gate_ts` | `{ts}` |"),
        (
            "| `gate_result` | `<accepted \\| accepted-with-limits \\| refused>` |",
            f"| `gate_result` | `{gate_result}` |",
        ),
        (
            '| `limits_imposed` | `<what was narrowed and why, or "none">` |',
            f"| `limits_imposed` | `{limits}` |",
        ),
        ("| `refusal_reason` | `<one line, if refused>` |", "| `refusal_reason` | `n/a — accepted` |"),
        ("active_allowed: <yes | no>", f"active_allowed: {'yes' if active_allowed else 'no'}"),
        (
            "[ ] <case-specific exclusion>\n[ ] <case-specific exclusion>",
            "\n".join(f"[x] {b}" for b in out_of_bounds) or "[ ] <case-specific exclusion>",
        ),
    ]
    for old, new in slots:
        if old not in template:
            raise ValueError(f"scope.md template has no slot for: {old.splitlines()[0]!r}")
        template = template.replace(old, new, 1)
    template = template.replace(f"[ ] {purpose} ", f"[x] {purpose} ", 1)
    if purpose != "kyc":
        # Officer/associate lookups are the kyc mandate and nothing else's; every other
        # branch gets them excluded rather than left silently permissive. Exception: a
        # recorded question that asks about an officer, director, shareholder, UBO or PSC
        # is that lookup, so ticking it would make the case refuse its own Q1.
        officer = RE_OFFICER_QUESTION.search(question or "")
        officers_line = "[ ] associated parties, officers and shareholders"
        if officer:
            template = template.replace(
                officers_line,
                f"{officers_line}  — in bounds: the recorded question asks about "
                f"{officer.group(0).lower()}",
                1,
            )
        else:
            template = template.replace(officers_line, "[x]" + officers_line[3:], 1)
        colleagues = "[ ] employer or colleagues not named in the question"
        template = template.replace(colleagues, "[x]" + colleagues[3:], 1)
    if public_interest:
        template += (
            f"\n## Public-interest test\n\n{public_interest}\n\n"
            "A finding about a private individual that cannot cite this comes out at report time.\n"
        )
    return template


def apply_in_bounds(text: str, pairs: list[tuple[str, str]]) -> str:
    """Untick a standing `[x]` exclusion, recording why on the same line.

    `assets/case-skeleton/scope.md` section 6 already sanctions this: "Unchecking one requires
    a one-line reason on the same line naming what in the recorded question needs it." Nothing
    is unticked by default — this runs only on an explicit operator flag, and only after
    `/osint:osint-scope` section 4's refusal screen has already passed.
    """
    for needle, reason in pairs:
        needle, reason = (needle or "").strip(), (reason or "").strip()
        if not needle:
            raise ValueError("--in-bounds needs a substring of a standing exclusion")
        if not reason:
            raise ValueError(
                f"--in-bounds {needle!r} needs a non-blank --in-bounds-reason naming what "
                "in the recorded question needs it"
            )
        hit = next(
            (
                ln
                for ln in text.splitlines()
                if ln.startswith("[x] ") and needle.lower() in ln.lower()
            ),
            None,
        )
        if hit is None:
            raise ValueError(
                f"--in-bounds {needle!r} matches no ticked exclusion in scope.md section 6"
            )
        text = text.replace(hit, f"[ ] {hit[4:]}  — in bounds: {reason}", 1)
    return text


def init_case(
    root: Path,
    slug: str,
    purpose: str,
    target: str,
    target_category: str,
    question: str,
    authority: str,
    jurisdiction: str,
    out_of_bounds: list[str] | None = None,
    in_bounds: list[tuple[str, str]] | None = None,
    active_allowed: bool = False,
    skeleton: Path | None = None,
    ts: str | None = None,
    target_type: str = "",
    public_interest: str = "",
    decision: str = "",
) -> Path:
    """Create cases/<slug>/ and seed it. Raises rather than overwriting anything."""
    purpose = (purpose or "").strip()
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {', '.join(PURPOSES)}; got {purpose!r}")
    target_category = (target_category or "").strip()
    if target_category not in TARGET_CATEGORIES:
        raise ValueError(
            f"target_category must be one of {', '.join(TARGET_CATEGORIES)}; "
            f"got {target_category!r}"
        )
    for label, value in (
        ("target", target),
        ("question", question),
        ("authority", authority),
        ("jurisdiction", jurisdiction),
    ):
        if not (value or "").strip():
            raise ValueError(f"{label} is required and cannot be blank")
    target_type = (target_type or "").strip()
    if target_type and target_type not in SELECTOR_TYPES:
        raise ValueError(f"target_type must be a CONTRACT.md section 4 selector type; got {target_type!r}")

    bounds = [b.strip() for b in (out_of_bounds or []) if b.strip()]
    stamp = ts or utc_now()
    case = Path(root) / safe_slug(slug)
    if case.exists():
        raise FileExistsError(f"case already exists: {case}")

    if skeleton is not None and Path(skeleton).is_dir():
        shutil.copytree(Path(skeleton), case)
    else:
        case.mkdir(parents=True)

    for sub in ("evidence", "report"):
        (case / sub).mkdir(exist_ok=True)

    # The skeleton scope.md is an authorization template with sections (out-of-bounds,
    # active-collection techniques, signature block, handling, gate result) the arguments
    # do not carry. Fill it in place; only render a fresh one when no template was copied.
    scope_path = case / "scope.md"
    fields = dict(
        slug=case.name,
        ts=stamp,
        purpose=purpose,
        target=target.strip(),
        target_type=target_type,
        target_category=target_category,
        question=question.strip(),
        authority=authority.strip(),
        jurisdiction=jurisdiction.strip(),
        out_of_bounds=bounds,
        active_allowed=active_allowed,
        public_interest=(public_interest or "").strip(),
        decision=(decision or "").strip(),
    )
    if scope_path.exists():
        scope_text = fill_scope(scope_path.read_text(encoding="utf-8"), **fields)
    else:
        scope_text = render_scope(**fields)
    try:
        scope_text = apply_in_bounds(scope_text, list(in_bounds or []))
    except ValueError:
        # A rejected case never leaves a half-scaffolded directory behind.
        shutil.rmtree(case, ignore_errors=True)
        raise
    scope_path.write_text(scope_text, encoding="utf-8", newline="\n")

    # Templates copied from the skeleton carry <slug> placeholders and a worked example.
    # Neither may reach a real case: the example ids collide with the analyst's first two.
    for name in ("findings.md", "gaps.md", "README.md"):
        path = case / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").replace("<slug>", case.name)
        head, marker, rest = text.partition("## Worked example — delete before use")
        if marker:
            _, _, tail = rest.partition("## Blank block — copy this")
            text = head + "## Blank block — copy this" + tail
        path.write_text(text, encoding="utf-8", newline="\n")

    for name, seed in (
        ("entities.jsonl", ""),
        ("events.jsonl", ""),
        (
            "findings.md",
            f"# Findings — {case.name}\n\n"
            "One finding per subsection. Each carries source URL, retrieval timestamp,\n"
            "`result_sha256` of the archived copy, and an Admiralty grade (e.g. `B2`).\n",
        ),
        (
            "gaps.md",
            f"# Gaps — {case.name}\n\n"
            "Negative results, unanswered questions, and the next collection step.\n"
            "Absence of evidence is a result; record it here rather than dropping it.\n",
        ),
    ):
        path = case / name
        if not path.exists():
            path.write_text(seed, encoding="utf-8", newline="\n")

    row = dict(
        zip(
            LEDGER_FIELDS,
            (
                stamp,
                "main",
                "scope",
                "osint-scope",
                question.strip(),
                (
                    f"case opened; target={target.strip()}; "
                    f"target_type={target_type or 'unrecorded'}; purpose={purpose}; "
                    f"target_category={target_category}; authority={authority.strip()}; "
                    f"jurisdiction={jurisdiction.strip()}; "
                    f"public_interest={'set' if fields['public_interest'] else 'unset'}; "
                    f"question_ids={','.join(f'Q{i}' for i in range(1, len(_numbered_questions(question).splitlines()) + 1))}; "
                    f"active_allowed={json.dumps(active_allowed)}; "
                    f"out_of_bounds=[{'; '.join(bounds) or 'none'}]; "
                    f"in_bounds=[{'; '.join(f'{n} ({r})' for n, r in (in_bounds or [])) or 'none'}]"
                ),
                None,
                "passive",
            ),
        )
    )
    # Append only. Never rewrite ledger.jsonl (CONTRACT.md section 10).
    with (case / "ledger.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return case


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="case_init.py",
        description="Scaffold an OSINT case directory and seed its ledger with the frozen scope.",
        epilog="Exit codes: 1 invalid field, 2 usage error, 3 case already exists.",
    )
    p.add_argument("--slug", help="case slug; sanitised to [a-z0-9-]")
    p.add_argument("--purpose", choices=PURPOSES, help="declared purpose branch")
    p.add_argument("--target", help="primary selector or entity under investigation")
    p.add_argument(
        "--target-category", choices=TARGET_CATEGORIES, help="what kind of target it is"
    )
    p.add_argument(
        "--target-type",
        choices=SELECTOR_TYPES,
        default="",
        help="canonical selector type of --target (CONTRACT.md section 4)",
    )
    p.add_argument(
        "--question",
        help="the falsifiable question this case answers; newline-separate for Q1..Qn",
    )
    p.add_argument("--authority", help="engagement, mandate, assignment, or 'own asset'")
    p.add_argument(
        "--jurisdiction",
        help='target / requester / publication jurisdictions, or "unknown"',
    )
    p.add_argument(
        "--public-interest",
        default="",
        help="journalism + private-individual only: the public-interest justification, verbatim",
    )
    p.add_argument(
        "--out-of-bounds",
        action="append",
        default=[],
        metavar="TEXT",
        help="explicit exclusion; repeat per item",
    )
    p.add_argument(
        "--in-bounds",
        action="append",
        default=[],
        metavar="TEXT",
        help="substring of a standing scope.md section 6 exclusion to untick for this case; "
        "needs a matching --in-bounds-reason. Repeat per item",
    )
    p.add_argument(
        "--in-bounds-reason",
        action="append",
        default=[],
        metavar="TEXT",
        help="one line naming what in the recorded question needs the matching --in-bounds "
        "exclusion unticked; written onto that line in scope.md",
    )
    p.add_argument(
        "--active-allowed",
        action="store_true",
        help="authorize target-observable steps; defaults to false",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("cases"),
        help=(
            "cases directory; always pass ${CLAUDE_PROJECT_DIR}/cases from a skill or "
            "command. The ./cases default is for direct CLI use only"
        ),
    )
    p.add_argument(
        "--skeleton",
        type=Path,
        default=None,
        help="template directory to copy (default: autodetect assets/case-skeleton)",
    )
    p.add_argument(
        "--decision",
        default="",
        help="what the requester does differently depending on the answer; scope.md §5 says a "
        "case with no decision attached has no stop condition",
    )
    p.add_argument("--selfcheck", action="store_true", help="run internal assertions and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.selfcheck:
        return demo()

    missing = [
        flag
        for flag, value in (
            ("--slug", args.slug),
            ("--purpose", args.purpose),
            ("--target", args.target),
            ("--target-category", args.target_category),
            ("--question", args.question),
            ("--authority", args.authority),
            ("--jurisdiction", args.jurisdiction),
        )
        if not value
    ]
    if missing:
        parser.error("missing required arguments: " + " ".join(missing))

    if len(args.in_bounds) != len(args.in_bounds_reason):
        parser.error(
            "--in-bounds and --in-bounds-reason are a pair: "
            f"got {len(args.in_bounds)} and {len(args.in_bounds_reason)}"
        )
    # The self_audit branch's only structural guard against a third-party target being
    # laundered through it. commands/osint-scope.md section 6 requires the flag; nothing
    # else enforced it.
    if args.purpose == "self_audit" and not any(
        "third party" in b.lower() for b in args.out_of_bounds
    ):
        parser.error(
            'self_audit requires --out-of-bounds "any third party" '
            "(commands/osint-scope.md section 6)"
        )

    try:
        case = init_case(
            root=args.root,
            slug=args.slug,
            purpose=args.purpose,
            target=args.target,
            target_category=args.target_category,
            question=args.question,
            authority=args.authority,
            jurisdiction=args.jurisdiction,
            out_of_bounds=args.out_of_bounds,
            in_bounds=list(zip(args.in_bounds, args.in_bounds_reason)),
            active_allowed=args.active_allowed,
            skeleton=args.skeleton if args.skeleton is not None else find_skeleton(),
            target_type=args.target_type,
            public_interest=args.public_interest,
            decision=args.decision,
        )
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("resume it or choose another slug; nothing was modified.", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"case: {case}")
    print(f"scope frozen in {case / 'scope.md'}, opening row in {case / 'ledger.jsonl'}")
    print(f"next: {first_play(args.purpose, args.target_type)}")
    if not args.active_allowed:
        print("posture: passive only (active_allowed=false)")
    if not args.decision.strip():
        print(
            "warning: no --decision recorded. scope.md section 5: a case with no decision "
            "attached has no stop condition. Fill it before collecting.",
            file=sys.stderr,
        )
    return 0


def demo() -> int:
    assert safe_slug("Acme Corp / 2026") == "acme-corp-2026"
    assert safe_slug("..\\..\\etc\\passwd") == "etc-passwd"
    assert safe_slug("--Trailing--") == "trailing"
    assert safe_slug("C:\\Temp\\Case") == "c-temp-case"
    assert len(safe_slug("x" * 200)) == _SLUG_MAX
    for bad in ("", "   ", "///", "con", "NUL", ".."):
        try:
            safe_slug(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"safe_slug accepted {bad!r}")

    assert find_skeleton() == Path(__file__).resolve().parent.parent / "assets" / "case-skeleton"

    good = dict(
        slug="Demo Case",
        purpose="kyc",
        target="0123456",
        target_category="org",
        question="Is the beneficial owner sanctioned or PEP-linked?",
        authority="Compliance mandate CM-9",
        jurisdiction="GB",
        out_of_bounds=["family members", "  "],
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "cases"
        case = init_case(root=root, **good)
        assert case == root / "demo-case", case

        for rel in (
            "scope.md",
            "ledger.jsonl",
            "entities.jsonl",
            "events.jsonl",
            "findings.md",
            "gaps.md",
            "evidence",
            "report",
        ):
            assert (case / rel).exists(), rel
        assert (case / "evidence").is_dir() and (case / "report").is_dir()
        assert (case / "entities.jsonl").read_text(encoding="utf-8") == ""
        assert (case / "events.jsonl").read_text(encoding="utf-8") == ""

        scope = (case / "scope.md").read_text(encoding="utf-8")
        assert "| active_allowed | false |" in scope, "active_allowed must default to false"
        assert good["question"] in scope
        assert "Q1. " + good["question"] in scope, "scope questions must be minted as Q1..Qn"
        assert "- family members" in scope
        assert "- \n" not in scope, "blank out_of_bounds entry leaked into scope.md"

        lines = (case / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, lines
        row = json.loads(lines[0])
        assert tuple(row) == LEDGER_FIELDS, tuple(row)
        assert row["action"] == "scope"
        assert row["actor"] == "main"
        assert row["mode"] == "passive"
        assert row["result_sha256"] is None
        assert row["query"] == good["question"]
        assert "active_allowed=false" in row["result"]
        assert "target=0123456" in row["result"], "the ledger must record the target verbatim"
        assert "question_ids=Q1" in row["result"]
        assert "out_of_bounds=[family members]" in row["result"], "blank exclusion leaked"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["ts"]), row["ts"]

        # Clobber refusal: same slug, and slugs that collide after sanitisation.
        for clobber in ("Demo Case", "demo--case"):
            try:
                init_case(root=root, **{**good, "slug": clobber})
            except FileExistsError:
                pass
            else:
                raise AssertionError(f"clobbered an existing case via {clobber!r}")
        assert len((case / "ledger.jsonl").read_text(encoding="utf-8").splitlines()) == 1

        # Enum and blank-field validation, each before anything is written.
        for field, value in (
            ("purpose", "revenge"),
            ("purpose", ""),
            ("purpose", "kyc-aml"),
            ("target_category", "frenemy"),
            ("target_category", "individual"),
            ("target_type", "domains"),
            ("question", "   "),
            ("target", ""),
            ("authority", ""),
            ("jurisdiction", ""),
        ):
            try:
                init_case(root=root, **{**good, "slug": "reject-me", field: value})
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted {field}={value!r}")
        assert not (root / "reject-me").exists(), "rejected case left a directory behind"

        # active_allowed=true is recorded in both places.
        active = init_case(root=root, **{**good, "slug": "active-case", "active_allowed": True})
        assert "| active_allowed | true |" in (active / "scope.md").read_text(encoding="utf-8")
        assert "active_allowed=true" in json.loads(
            (active / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )["result"]

        # A skeleton directory is copied, and its extra files survive.
        skel = Path(tmp) / "skel"
        (skel / "evidence").mkdir(parents=True)
        (skel / "README.md").write_text("template\n", encoding="utf-8")
        (skel / "findings.md").write_text("# from skeleton\n", encoding="utf-8")
        from_skel = init_case(root=root, **{**good, "slug": "with-skeleton"}, skeleton=skel)
        assert (from_skel / "README.md").read_text(encoding="utf-8") == "template\n"
        assert (from_skel / "findings.md").read_text(encoding="utf-8") == "# from skeleton\n"
        assert (from_skel / "scope.md").read_text(encoding="utf-8").startswith("# Case with-skeleton")

        # The real skeleton: template is filled, not replaced, and ships no placeholder
        # or worked example into a live case.
        real = find_skeleton()
        assert real is not None
        live = init_case(
            root=root,
            **{**good, "slug": "live-case", "target_type": "company_number"},
            skeleton=real,
        )
        for name in ("scope.md", "findings.md", "gaps.md", "README.md"):
            body = (live / name).read_text(encoding="utf-8")
            assert "<slug>" not in body, f"{name} shipped an unfilled <slug>"
        scope = (live / "scope.md").read_text(encoding="utf-8")
        for must in (
            "Selected branch: `kyc`",
            "[x] kyc ",
            "[ ] associated parties, officers and shareholders",  # kyc: stays off
            "| `case_id` | `live-case` |",
            "| `target_type` | `company_number` |",
            "| target_type | company_number |",
            "active_allowed: no",
            "[x] family members",
            "### Authorization signature",
            "## 9. Intake gate result",
            "Q1. " + good["question"],
        ):
            assert must in scope, f"scope.md lost or failed to fill: {must!r}"
        assert "<question>" not in scope

        # The gate-result block and the decision line are load-bearing: scope.md section 5 says
        # a case with no decision has no stop condition, and section 9 is the only machine record
        # that the gate ran. Neither may ship as an unfilled placeholder.
        for leaked in (
            "<main session \\| analyst name>",
            "<accepted \\| accepted-with-limits \\| refused>",
            "<what the requester will do differently depending on the answer>",
            "<one line, if refused>",
        ):
            assert leaked not in scope, f"scope.md shipped an unfilled placeholder: {leaked!r}"
        assert "| `gate_run_by` | `main session` |" in scope
        assert "| `gate_result` | `accepted-with-limits` |" in scope, "out_of_bounds implies limits"
        assert "| `limits_imposed` | `family members` |" in scope
        assert "Decision this feeds: `UNRECORDED — fill before collecting`" in scope, (
            "an omitted --decision must be visibly unrecorded, not silently blank"
        )
        decided = init_case(
            root=root,
            **{**good, "slug": "decided-case"},
            skeleton=real,
            decision="whether to onboard the counterparty",
        )
        assert "Decision this feeds: `whether to onboard the counterparty`" in (
            decided / "scope.md"
        ).read_text(encoding="utf-8")
        sec = init_case(
            root=root,
            **{
                **good,
                "slug": "sec-case",
                "purpose": "security",
                "question": "Which internet-facing assets are unmanaged or expired?",
            },
            skeleton=real,
        )
        sec_scope = (sec / "scope.md").read_text(encoding="utf-8")
        assert "[x] associated parties, officers and shareholders" in sec_scope, (
            "officer/associate lookups must default OFF-limits outside the kyc branch"
        )
        assert "[x] employer or colleagues not named in the question" in sec_scope
        assert "[x] security " in sec_scope

        # ...but a non-kyc case whose recorded question IS the officer question must not
        # have that question excluded for the life of the case. The sibling colleagues
        # line keeps ticking regardless.
        for slug, question, term in (
            ("ubo-case", "Do all three properties trace to one beneficial owner?",
             "beneficial owner"),
            ("psc-case", "Is the PSC on all three filings the same person?", "psc"),
            ("dir-case", "Does the tendering company's directorship overlap her family?",
             "directorship"),
        ):
            # "directory listings" must not read as a directorship question.
            assert not RE_OFFICER_QUESTION.search(
                "Which directory listings expose my address?"
            ), "the officer guard over-fires on 'directory'"
            ubo = init_case(
                root=root,
                **{**good, "slug": slug, "purpose": "journalism", "question": question},
                skeleton=real,
            )
            ubo_scope = (ubo / "scope.md").read_text(encoding="utf-8")
            assert (
                "[ ] associated parties, officers and shareholders  — in bounds: "
                f"the recorded question asks about {term}" in ubo_scope
            ), f"{slug}: the scaffold excluded its own recorded question"
            assert "[x] employer or colleagues not named in the question" in ubo_scope, (
                f"{slug}: the sibling exclusion must still tick outside kyc"
            )

        # --in-bounds unticks one standing exclusion and records why on the same line.
        addr = "home address, physical location, and movement patterns"
        selfaud = init_case(
            root=root,
            **{**good, "slug": "self-case", "purpose": "self_audit",
               "target_category": "self", "out_of_bounds": ["any third party"]},
            skeleton=real,
            in_bounds=[(addr, "self_audit: the requester's own address exposure is the "
                              "deliverable")],
        )
        sa_scope = (selfaud / "scope.md").read_text(encoding="utf-8")
        assert f"[ ] {addr}  — in bounds: self_audit:" in sa_scope, sa_scope
        assert f"[x] {addr}" not in sa_scope
        # Every other standing exclusion stays ticked; unticking is per-line, never global.
        for still_on in (
            "[x] household members and minors in the household",
            "[x] minors, including any account that appears to belong to one",
            "[x] authentication, rate-limit, or CAPTCHA circumvention",
            "[x] non-public breach corpora and purchased credential dumps",
        ):
            assert still_on in sa_scope, f"--in-bounds unticked more than it was given: {still_on}"
        assert "in_bounds=[home address" in json.loads(
            (selfaud / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )["result"], "an unticked exclusion must be on the ledger row too"

        # A substring that matches nothing, and a blank reason, are both errors, and
        # neither leaves a directory behind.
        for bad_pair in (
            [("no such exclusion line", "because")],
            [(addr, "   ")],
            [("", "because")],
        ):
            try:
                init_case(root=root, **{**good, "slug": "in-bounds-reject"},
                          skeleton=real, in_bounds=bad_pair)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted --in-bounds {bad_pair!r}")
            assert not (root / "in-bounds-reject").exists(), "half-scaffolded case left behind"

        found = (live / "findings.md").read_text(encoding="utf-8")
        assert "example-one.test" not in found and "### f-1 —" not in found
        assert "## Blank block — copy this" in found

    # A security-branch locate on a person goes to identity, not infra; a domain
    # engagement is untouched.
    assert first_play("security", "person_name").startswith("/osint:osint-identity")
    assert first_play("security", "email").startswith("/osint:osint-identity")
    assert first_play("security", "domain") == FIRST_PLAY["security"]
    assert first_play("security", "") == FIRST_PLAY["security"]
    assert first_play("kyc", "person_name") == FIRST_PLAY["kyc"]

    # self_audit without the third-party exclusion is a usage error, not a quiet exit 0;
    # so is an --in-bounds with no matching --in-bounds-reason.
    print("--- the two argparse usage errors below are the expected output of the "
          "exit-code checks, not selfcheck failures ---", flush=True)
    base = ["--slug", "sa", "--purpose", "self_audit", "--target", "me@example.test",
            "--target-category", "self", "--question", "What is linkable?",
            "--authority", "own asset", "--jurisdiction", "unknown"]
    for argv in (base, base + ["--in-bounds", "home address"]):
        try:
            main(argv)
        except SystemExit as exc:
            assert exc.code == 2, (argv, exc.code)
        else:
            raise AssertionError(f"accepted {argv!r}")

    print("selfcheck ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
