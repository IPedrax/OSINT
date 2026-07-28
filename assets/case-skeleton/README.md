# Case directory format

This directory is a case. It was copied from the plugin's `assets/case-skeleton/`. Delete this
README once you know the format, or keep it — nothing reads it programmatically.

```
cases/<slug>/
  README.md        this file
  scope.md         frozen intake answers. Written once, never edited. Amendments appended.
  ledger.jsonl     append-only action log. Every query, every negative, every refusal.
  entities.jsonl   one line per selector value observed.
  events.jsonl     one line per dated event.
  findings.md      graded prose. Nothing enters without url + timestamp + sha256.
  gaps.md          negative results, open questions, recommended next collection.
  evidence/        archived copies, named <sha256>.<ext>. Immutable.
  report/          rendered deliverables.
```

The three `.jsonl` files ship **empty**, deliberately: a comment line is not valid JSON and any
parser reading the directory would choke on it. Field order and types are documented here and
enforced by the plugin's `assets/entity-schema.json` (JSON Schema draft 2020-12).

## JSONL rules

- One JSON object per line. No pretty-printing, no trailing commas, no blank lines.
- UTF-8, LF newlines, no BOM.
- **Append only.** Never rewrite a line, never reorder, never delete. A wrong line is corrected
  by appending a new line and a note, not by editing history. This is what makes parallel
  collectors safe and the case resumable.
- Write the line at the moment the action happens, not in a batch at the end.
- Keys in the order given below. JSON does not care; humans reading `tail -f` do.

## ledger.jsonl

Field order: `ts` `actor` `action` `source` `query` `result` `result_sha256` `mode`

```json
{"ts":"2026-07-28T09:14:02Z","actor":"main","action":"collect","source":"Example Registry WHOIS export","query":"https://example.test/whois/example-one.test","result":"registrar and creation date retrieved","result_sha256":"3f786850e387550fdab836ed7e6dc881de23001b3ffa10c46f88b3d20b9f6b1a","mode":"passive"}
{"ts":"2026-07-28T09:20:11Z","actor":"osint-collector","action":"collect","source":"Example Certificate Log Search","query":"example.test subdomains","result":"none","result_sha256":null,"mode":"passive"}
{"ts":"2026-07-28T09:31:00Z","actor":"main","action":"refusal","source":"n/a","query":"home address of e-7","result":"refused: physical location of a private individual, non-institutional requester","result_sha256":null,"mode":"passive"}
```

| Field | Type | Notes |
|---|---|---|
| `ts` | ISO8601 UTC, `Z` | When the action completed |
| `actor` | string | `main`, or the subagent name, or an analyst |
| `action` | enum | `scope` `collect` `pivot` `archive` `finding` `refusal` |
| `source` | string | `sources.csv` name verbatim, or tool name, or `n/a` |
| `query` | string | Exactly what was asked. Someone must be able to re-run it from this field |
| `result` | string | One-line summary, or the literal `none` for a negative result |
| `result_sha256` | hex64 or null | Hash of the archived copy; `null` when nothing was archived |
| `mode` | enum | `passive` `active` |

Negative results are mandatory. A collection that found nothing still gets a row with
`"result":"none"`, and a matching row in `gaps.md` section 1.

A row with `"action":"finding"` starts its `result` with the finding id and a colon —
`"f-3: shared registrar account across two domains"`. That is the only link between this file
and `findings.md`.

## entities.jsonl

Field order: `id` `type` `value` `first_seen` `grade` `inference_rung` `sources`
`candidate_group` `notes`

```json
{"id":"e-3","type":"domain","value":"example-one.test","first_seen":"2026-07-28T09:14:02Z","grade":"B3","inference_rung":"observed","sources":["2026-07-28T09:14:02Z"],"candidate_group":null,"notes":""}
{"id":"e-7","type":"username","value":"examplehandle","first_seen":"2026-07-28T10:02:11Z","grade":"C3","inference_rung":"observed","sources":["https://platform-a.test/examplehandle"],"candidate_group":"cg-1","notes":"string identity with e-8 only; resolves if avatar file hashes match"}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `e-<n>` | Stable, never reused, never renumbered |
| `type` | enum | Canonical selector vocabulary, CONTRACT.md section 4. Exact string, singular |
| `value` | string | Normalized: lowercase domain/email/username, E.164 phone, decimal-degree coordinates. Raw form goes in `notes` if normalization lost anything |
| `first_seen` | ISO8601 UTC | When **this case** first recorded it, not when it came into existence |
| `grade` | Admiralty | Letter grades the source, digit grades the claim that the value exists as stated. The letter is the class letter from the source-class table in the plugin's `references/41-confidence.md`, and the digit may not beat that class's max credibility alone |
| `inference_rung` | enum | `observed` `reported` `correlated` `inferred` `speculated`. Optional: CONTRACT.md section 7 does not require it, but fill it |
| `sources` | array, min 1 | Ledger `ts` values or URLs. An entity with no provenance does not exist |
| `candidate_group` | `cg-<n>` or null | Identity-confusion guard |
| `notes` | string | May be empty. For a `cg-` member, name the datapoint that would resolve the link |

Optional: `attributed_to` (`e-<n>` or null). Setting it is an attribution claim and requires a
matching block in `findings.md`.

An entity records a thing observed. Who it belongs to is a finding, not an entity field.

### candidate_group

Two entities that **might** be the same real-world thing share a `cg-` id and are **never
merged** without a named linking datapoint. A datapoint is sufficient only per the tier table in
the plugin's `references/40-analysis.md`: one Tier-1 datapoint (identical `file_hash`, a
registry-issued `company_number` in two primary records, a platform-issued immutable account id,
demonstrated key control) or two independent Tier-2 datapoints. Same name and same username
string are Tier 3 and never sufficient at any quantity. Name the datapoint in `notes` when you
merge, and keep both ids: the superseded entity stays in the file with a note pointing at the
survivor.

## events.jsonl

Field order: `ts` `actor_entity` `description` `grade` `inference_rung` `sources` `precision`

```json
{"ts":"2024-11-30","actor_entity":"e-3","description":"Domain registered.","grade":"B3","inference_rung":"observed","sources":["2026-07-28T09:14:02Z"],"precision":"day"}
{"ts":"2025-03/2025-06","actor_entity":"e-7","description":"Profile activity ceased.","grade":"C3","inference_rung":"inferred","sources":["https://platform-a.test/examplehandle"],"precision":"approx"}
```

| Field | Type | Notes |
|---|---|---|
| `ts` | ISO8601 date, instant, or `a/b` interval | At the precision actually known. Do not pad with fake zeros |
| `actor_entity` | `e-<n>` | The entity the event is about |
| `description` | string | One sentence, past tense, no interpretation |
| `grade` | Admiralty | The letter is the class letter from the source-class table in the plugin's `references/41-confidence.md`, and the digit may not beat that class's max credibility alone |
| `inference_rung` | enum | `observed` `reported` `correlated` `inferred` `speculated`. Optional, as for entities |
| `sources` | array, min 1 | |
| `precision` | enum | `exact` `day` `month` `year` `approx` |

Optional: `timezone_note` — where the source's clock came from and what was assumed when
converting to UTC. Fill it whenever a conversion happened.

`precision: approx` values (sun angle, foliage, sequence position) must never be rendered as a
precise time in a report.

## evidence/

Named `<sha256>.<ext>` where the hash is of the exact bytes stored. Never renamed, never edited.
The hash in a `findings.md` block, a `ledger.jsonl` row, and the filename are the same string —
that is the whole integrity chain.

If a snapshot could not be taken, the source still needs a note saying why, and any third-party
archive URL that does exist.

Save the bytes first, then hash and rename in one step:

```
python -c "import hashlib,pathlib,sys;p=pathlib.Path(sys.argv[1]);h=hashlib.sha256(p.read_bytes()).hexdigest();p.rename(p.with_name(h+p.suffix));print(h)" evidence/<file>
```

Request a public archive save by fetching `https://web.archive.org/save/<url>`. That URL form is
unverified as a stable API — a failure is a `gaps.md` row, not an error.

## report/

Rendered deliverables. Generated from `findings.md` + `entities.jsonl` + `events.jsonl` +
`gaps.md` using the plugin's `assets/report-template.md`. Nothing is authored here by hand that
does not exist upstream in the case files.

## Integrity check

Stdlib only, run from the case directory. Checks that every line parses and that every hash
referenced by the ledger exists in `evidence/`.

Every line parses (raises and exits non-zero on the first bad line):

```
python -c "import json,pathlib;[json.loads(l) for p in ('ledger.jsonl','entities.jsonl','events.jsonl') for l in pathlib.Path(p).read_text('utf-8').splitlines() if l.strip()]"
```

Every hash the ledger references is present in `evidence/`:

```
python -c "import json,pathlib;h={json.loads(l).get('result_sha256') for l in pathlib.Path('ledger.jsonl').read_text('utf-8').splitlines() if l.strip()}-{None};have={p.stem for p in pathlib.Path('evidence').iterdir()};print('missing evidence:',sorted(h-have) or 'none')"
```

To validate against the schema you need a JSON Schema library, which the plugin does not depend
on. If `jsonschema` happens to be installed, point it at the plugin's `assets/entity-schema.json`
and validate each line against the top-level `oneOf`. Otherwise the tables above are the
contract.
