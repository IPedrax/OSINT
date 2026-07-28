---
description: Compile the case into a graded deliverable with scripts/report.py, in markdown, HTML or JSON, from scope.md, findings.md, entities.jsonl, events.jsonl, gaps.md, ledger.jsonl and evidence/. Runs the entity-graph validator and the pre-report checklist first, applies the redaction default, and refuses to compile if a finding is ungraded or unsourced, if an unresolved candidate group is treated as resolved, or if a banned certainty word appears in a finding. Use when the user says "write the report", "compile the case", "produce the deliverable", "write it up", "draft the memo", "KYC file", "export the case", or "we're done, write it up".
argument-hint: [case-slug | blank for the open case]
---

# Compile the case

Nothing is authored here. Every sentence in the deliverable already exists in a case file; if it
does not, that is a collection gap, not a writing problem. Reporting method, audience tailoring,
BLUF discipline, redaction, negative-result framing and the machine-readable export are all in
`${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md`. Read it before section 3 below and do not
restate it from memory.

`${CLAUDE_PLUGIN_ROOT}/scripts/report.py` does the assembly. Run it; do not hand-copy the
template section by section unless the script is absent from this build.

## 0. Find the case

Glob `${CLAUDE_PROJECT_DIR}/cases/*/scope.md`. None → nothing to compile. Several and no `$1` →
ask; do not assume the most recent.

`scope.md` is the authority on the header, the numbered questions, `out_of_bounds[]`,
`target_category`, `active_allowed` and `redaction_default`. Where a draft and `scope.md`
disagree, the draft is wrong. The compiler reads all of it — you do not need to transcribe it.

## 1. Gate — both checks, before anything is compiled

### 1a. Entity graph

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/graph.py" "<CASE_DIR>" --validate
```

Exit `1` → stop and report the violations. A report over unvalidated entities can merge two
people into one dossier; `/osint:osint-graph` §1 explains each rule and its fix. `report.py`
embeds the chart into section 8 from the same code, so a graph that does not validate produces
a chart that should not ship.

### 1b. Pre-report checklist

Run all sixteen items of the pre-report checklist in
`${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`, each as a pass/fail against the case files,
not as a reminder. Report the failures as a list with the finding id against each. These are the
judgement calls; section 2's are the mechanical ones, and passing one is not passing the other.

## 2. Write the BLUF, then compile

The compiler does not author claims, so it does not write the BLUF. Write it last, from the
finished body, under the discipline in `50-reporting.md`, and save it as
`cases/<slug>/report/bluf.md`:

```
grade: <Admiralty grade of the weakest link, not an average>
would_change: <the single observation most likely to overturn it>

<BLUF text, under 150 words, estimative wording only, every sentence graded or citing a
graded finding id.>
```

No `bluf.md` → section 2 ships a visible "not written" marker, which is a defect, not a style.
If the BLUF cannot be written, the case is not finished; that is a stop-condition signal.

Then compile:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" "<CASE_DIR>" --out "<CASE_DIR>/report/report.md"
python "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" "<CASE_DIR>" --format html --out "<CASE_DIR>/report/report.html"
python "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" "<CASE_DIR>" --format json --out "<CASE_DIR>/report/report.json"
```

| Flag | Use |
|---|---|
| `--format markdown\|html\|json` | markdown is the source of truth for humans; HTML is one self-contained file with no external request; JSON is the export envelope in `50-reporting.md` |
| `--redact partial\|full\|none` | defaults to `redaction_default` in `scope.md`, else `partial`. `identifiers-withheld` in `scope.md` is that file's name for `full`. Redaction is visible: a removed value becomes `[redacted: <class>]` |
| `--report-version N` | header only, for a re-issue |
| `--force` | see below |

Emit the JSON alongside the markdown, never instead of it.

## 3. When it refuses

Exit `1`, every blocking item named by id. Report them and fix the case files; do not argue with
the gate and do not hand-write the report to get around it.

| Check | Fires on |
|---|---|
| `ungraded` | a finding with no grade, or a grade outside `A1`–`F6` |
| `unsourced` | a finding with no source block |
| `merged` | a finding naming two members of an open `candidate_group` with no estimative phrase and no phrase holding the identity open |
| `banned` | `clearly`, `obviously`, `proves`, `definitely`, or `confirmed` below credibility `1`, inside a finding |

`--force` compiles anyway and stamps an unsuppressible override banner into the deliverable
listing every failed check by id. It is for a document that must exist while a fix is in flight,
never for shipping. A forced report is not deliverable.

Other stop signals the script will not catch for you, from `50-reporting.md` and section 1b: an
empty `gaps.md` (the case was guessed at, not investigated), a `journalism` case against a
`private-individual` with an empty `public_interest`, an `active` ledger row in a case whose
scope records `active_allowed: false`, and any `speculated` item in `findings.md`.

## 4. Read what came out, then deliver

The compiler fills every section of `${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` and ticks
the mechanical half of the pre-delivery checklist at the end of the document. Three things are
still yours:

- **The boxes marked `ANALYST`** in that checklist. Tick them against the finished document.
- **Audience emphasis.** The findings never change with `purpose`, only ordering and depth.
  Re-order section 5 and say so; the tailoring table is in `50-reporting.md`.
- **Anything the report prints as `unrecorded` or `not recorded`.** Each one is a real hole in
  `scope.md` or `gaps.md`, not a formatting artifact.

Two copies only: the unredacted case directory, and the redacted deliverable. Never a third.
Optional and neither a dependency: `make-pdf` renders the finished markdown, `diagram` turns the
section 8 mermaid source into an editable chart. **No rendering step may change a claim, a grade,
or a redaction.**

If `report.py` is absent from this build, say so in one line, copy
`${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` into `cases/<slug>/report/` and fill it in the
order `50-reporting.md` prescribes — BLUF last — holding the same four refusals by hand.
