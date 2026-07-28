#!/usr/bin/env python3
"""Report open OSINT cases found under <root>/cases/.

Payload for the SessionStart hook in hooks/hooks.json: a resumed session must see the
frozen scope before it collects anything. Prints nothing when no case is open — a hook
that talks when it has nothing to say gets disabled.

Read-only. No network. Nothing in the case directory is written or locked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RE_QUESTION = re.compile(r"^(Q\d+)\.\s+(.+?)\s*$")
MAX_Q = 3
MAX_Q_CHARS = 110


def _table_value(text: str, key: str) -> str:
    """Value cell of a `| key | value |` row, backticks stripped. '' if absent."""
    pattern = re.compile(r"^\|\s*`?" + re.escape(key) + r"`?\s*\|\s*(.*?)\s*\|\s*$", re.M)
    m = pattern.search(text)
    return m.group(1).strip("` ") if m else ""


def find_cases(root: Path) -> list[Path]:
    """Case directories under root/cases/ that hold a scope.md, sorted by name."""
    cases_dir = root / "cases"
    if not cases_dir.is_dir():
        return []
    return sorted(d for d in cases_dir.iterdir() if (d / "scope.md").is_file())


def summarize(case_dir: Path) -> dict:
    """One case, reduced to what a resuming session must not proceed without."""
    try:
        scope = (case_dir / "scope.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        scope = ""
    questions = []
    for line in scope.splitlines():
        m = RE_QUESTION.match(line)
        if m and not m.group(2).startswith("<"):
            q = m.group(2)
            questions.append(f"{m.group(1)}. {q[:MAX_Q_CHARS]}")
    rows, last_ts = 0, ""
    ledger = case_dir / "ledger.jsonl"
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            rows += 1
            try:
                last_ts = json.loads(line).get("ts", last_ts)
            except (ValueError, AttributeError):
                pass
    return {
        "slug": _table_value(scope, "case_id") or case_dir.name,
        "opened": _table_value(scope, "opened"),
        "active_allowed": _table_value(scope, "active_allowed") or "unknown",
        "questions": questions,
        "rows": rows,
        "last_ts": last_ts,
        "path": case_dir,
    }


def render(cases: list[dict], root: Path) -> str:
    if not cases:
        return ""
    head = (
        f"OSINT: {len(cases)} open case(s) under {root / 'cases'}. "
        "Read the case scope.md before collecting anything; it is frozen and it is the "
        "authority on purpose, out-of-bounds and active_allowed. Do not re-run the intake gate."
    )
    lines = [head, ""]
    for c in cases:
        opened = f" opened {c['opened']}" if c["opened"] else ""
        seen = f", last {c['last_ts']}" if c["last_ts"] else ""
        lines.append(
            f"  {c['slug']}{opened}  active_allowed={c['active_allowed']}  "
            f"ledger {c['rows']} row(s){seen}"
        )
        for q in c["questions"][:MAX_Q]:
            lines.append(f"    {q}")
        extra = len(c["questions"]) - MAX_Q
        if extra > 0:
            lines.append(f"    (+{extra} more in {c['path'] / 'scope.md'})")
    return "\n".join(lines)


def demo() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert find_cases(root) == [], "no cases/ dir must yield no cases"
        assert render([], root) == "", "silence when nothing is open"

        case = root / "cases" / "acme-2026-07"
        case.mkdir(parents=True)
        (case / "scope.md").write_text(
            "| `case_id` | `acme-2026-07` |\n"
            "| opened | 2026-07-28T09:00:00Z |\n"
            "| active_allowed | false |\n"
            "Q1. Who operates acme-billing.example\n"
            "Q2. <question>\n",
            encoding="utf-8",
        )
        (case / "ledger.jsonl").write_text(
            '{"ts":"2026-07-28T09:00:00Z","actor":"main","action":"scope"}\n'
            "not json\n",
            encoding="utf-8",
        )
        found = find_cases(root)
        assert found == [case], f"scope.md must mark a case dir, got {found}"

        s = summarize(case)
        assert s["slug"] == "acme-2026-07", s["slug"]
        assert s["opened"] == "2026-07-28T09:00:00Z", s["opened"]
        assert s["active_allowed"] == "false", s["active_allowed"]
        assert s["questions"] == ["Q1. Who operates acme-billing.example"], s["questions"]
        assert s["rows"] == 2 and s["last_ts"] == "2026-07-28T09:00:00Z", s
        # An unfilled template placeholder is not a question.
        assert all("<question>" not in q for q in s["questions"])

        out = render([s], root)
        assert "acme-2026-07" in out and "active_allowed=false" in out, out
        assert "Q1. Who operates" in out, out

        # A case dir with no scope.md is not an open case.
        (root / "cases" / "half-made").mkdir()
        assert find_cases(root) == [case], "scope.md is the marker, not the directory"

    print("case_status.py: all checks passed")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Report open OSINT cases under <root>/cases/. Prints nothing if none.",
        epilog="Read-only. Payload for the SessionStart hook; also useful by hand.",
    )
    p.add_argument("--root", default=".", help="directory holding cases/ (default: cwd)")
    p.add_argument("--max", type=int, default=5, help="cases to print (default: 5)")
    p.add_argument("--selfcheck", action="store_true", help="run assert-based checks and exit")
    args = p.parse_args(argv)

    if args.selfcheck:
        demo()
        return 0

    root = Path(args.root).resolve()
    cases = find_cases(root)
    text = render([summarize(c) for c in cases[: max(args.max, 0)]], root)
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a hook must never break the session it greets
        print(f"case_status.py: {exc}", file=sys.stderr)
        sys.exit(0)
