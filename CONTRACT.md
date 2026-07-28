# OSINT Plugin — Authoring Contract

Every file in this repo is written against this contract. Read it before writing anything.
`PLAN.md` says *what* to build; this says *how*, exactly. Where they conflict, this wins.

---

## 0. Hard rule: never invent an endpoint

**Do not write an API URL, endpoint path, query parameter, or CLI flag you are not certain
exists.** A hallucinated endpoint in `sources.csv` is worse than a missing row — it sends an
investigator down a dead path and destroys trust in the whole registry.

When unsure, record the **human-facing homepage URL** and set the `verified` column to `no`.
A row marked `verified=no` is honest and useful. A confidently wrong row is a defect.

Same rule for tool names, Python library APIs, and platform-specific URL patterns.

---

## 1. Repo root and the path base

The repository root is the plugin root. Layout is fixed by `PLAN.md` §1.
Create parent directories as needed. Do not add files outside that layout without saying so.

**Shared directories live at the plugin root, not inside a skill.** `references/`, `assets/`,
`scripts/`, `commands/`, `agents/`, `hooks/` are all siblings of `skills/`. Eight skills share
one reference set and one `sources.csv`; burying them inside `skills/osint/` would force every
sibling skill to reach across into another skill's directory.

**Therefore every path a skill writes MUST be based on `${CLAUDE_PLUGIN_ROOT}`, never
`${CLAUDE_SKILL_DIR}`.** `${CLAUDE_SKILL_DIR}` resolves to the individual skill's own
subdirectory (`skills/osint/`, `skills/osint-infra/`, ...), which contains only `SKILL.md`.
Writing `${CLAUDE_SKILL_DIR}/references/...` produces a path that does not exist and silently
breaks progressive disclosure. This was a real Phase 0 defect; do not reintroduce it.

Correct: `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md`,
`${CLAUDE_PLUGIN_ROOT}/assets/sources.csv`, `${CLAUDE_PLUGIN_ROOT}/scripts/case_init.py`.

Case output is the exception: cases are written to the user's working directory
(`cases/<slug>/`), never inside the plugin.

---

## 2. Skill file format

`FORMAT.md` is the authority on file formats; it was established by reading the live docs and
by running `claude plugin validate` against the installed Claude Code (2.1.71). Where this
section and `FORMAT.md` disagree, `FORMAT.md` wins. Rules below are conventions this repo
enforces on top of it.

Every `skills/<name>/SKILL.md` opens with:

```
---
name: <kebab-case, MUST equal the directory name>
description: <what it does AND when to use it, third person, trigger vocabulary first>
when_to_use: <additional trigger phrasings>          # optional, same char budget
disable-model-invocation: true                        # REQUIRED on department skills
---
```

- Every frontmatter key is technically optional — nothing fails validation if omitted. These are
  repo conventions, not schema enforcement. Do not expect an error when they are violated.
- `name` **must** equal the directory name. In a plugin skill `name` sets the last segment of
  the command, so a mismatch changes the invocation path.
- **`description` + `when_to_use` are truncated at 1,536 characters** in the skill listing.
  Put the primary use case and the strongest trigger phrases FIRST; anything past the cap is
  discarded. Write to be *matched*, but write short.
- `disable-model-invocation: true` on all seven department skills. The router
  (`skills/osint/SKILL.md`) is the only skill that may auto-trigger. Without this key every
  department skill competes to fire on every message.
- Other keys are permitted only if `FORMAT.md` documents them as valid on this Claude Code build.

### Command files

`commands/<file>.md` — the FILE NAME is the command name; do not set `name` in frontmatter.

**A command and a skill cannot share a name.** Within one plugin, `commands/osint.md` and
`skills/osint/SKILL.md` both resolve to `/osint:osint`, and the skill silently shadows the
command — no error, no warning. The router help command is therefore `commands/osint-help.md`.
Check every new command name against the skill directory names before creating it.

### Body structure — every SKILL.md

1. **One-line purpose.**
2. **Preconditions** — what must already be true (usually: a case is open, scope is recorded).
3. **The play** — numbered steps, each naming the selector consumed and produced.
4. **Reference index** — a table of `references/*.md` with a "load when" column. Never
   inline what belongs in a reference.
5. **Stop conditions** — how to know the play is done.
6. **Refusals** — what this play must not do, if anything beyond the global gate.

Router skill (`skills/osint/SKILL.md`) is the exception: it is a dispatcher. Hard ceiling
400 lines. Department skills: hard ceiling 200 lines. Reference files: 400 lines.

---

## 3. Reference file format

Every `references/*.md` opens with a single italic line: *Load when: <condition>.*
Then content. Prefer tables and dense bullets over paragraphs. No preamble, no summary
section at the end — Claude is reading this for facts, not narrative.

---

## 4. Canonical selector vocabulary

Use these exact strings everywhere (`sources.csv`, pivot matrix, `entities.jsonl`, scripts).
Never a synonym, never a plural.

```
email  username  person_name  phone  domain  subdomain  ip  asn  netblock
url  ssl_cert  company  company_number  address  photo  video  document
crypto_address  tx_hash  vehicle_plate  vessel  aircraft  coordinates
file_hash  social_profile  breach_record
```

Adding a type requires adding it here first.

---

## 5. sources.csv contract

Header, exactly:

```csv
name,category,accepts,yields,endpoint,auth,rate_limit,mode,verified,fetchable,jurisdiction_notes,reliability,notes
```

| Column | Rule |
|---|---|
| `name` | Human name of the source. Unique. |
| `category` | One of: `infra` `identity` `corporate` `geoint` `media` `crypto` `code` `transport` `search` `archive` `breach` `sanctions` |
| `accepts` | Pipe-delimited selector types from §4. What you feed it. |
| `yields` | Pipe-delimited selector types from §4. What you get back. |
| `endpoint` | Homepage or documented API URL. See §0. No invented paths. |
| `auth` | `none` \| `free_key` \| `paid` \| `account` |
| `rate_limit` | Free-text, or `unknown`. Do not guess a number — write `unknown`. |
| `mode` | `passive` \| `active`. Active = the target can detect it, or a third party is notified. |
| `verified` | `yes` only if you are certain the endpoint is correct **as written**. Else `no`. This is a claim about the URL, not about your ability to retrieve it. |
| `fetchable` | Can an agent retrieve this programmatically? `yes` = plain HTTP works. `no` = bot challenge, WAF, or JS-gated; open it in a browser and do not burn a tool call. `api` = fetchable only via a documented API, not the human URL. `unknown` = untested. Split out from `verified` in Phase 1: an endpoint can be perfectly correct and still unfetchable (SEC EDGAR, crt.sh, Wayback all are), and conflating the two produced wasted calls in both directions. |
| `jurisdiction_notes` | Legal/regional caveats, or empty. |
| `reliability` | Admiralty letter A–F (see §6). `F` if genuinely unjudgeable. |
| `notes` | Gotchas, coverage limits, what it is actually good for. |

Quote any field containing a comma. No trailing commas. UTF-8, LF newlines.

---

## 6. Confidence vocabulary — mandatory on every finding

### Source reliability (Admiralty / NATO)
| Grade | Meaning |
|---|---|
| A | Completely reliable — authoritative primary record |
| B | Usually reliable — established source, minor history of error |
| C | Fairly reliable — generally sound, some doubt |
| D | Not usually reliable — significant doubt |
| E | Unreliable — history of error |
| F | Cannot be judged — no basis to assess |

### Information credibility
| Grade | Meaning |
|---|---|
| 1 | Confirmed by independent sources |
| 2 | Probably true — consistent with other information |
| 3 | Possibly true — reasonable but uncorroborated |
| 4 | Doubtful — contradicted by other information |
| 5 | Improbable |
| 6 | Cannot be judged |

A finding is graded `B2`, `C3`, etc. Grade the **source** and the **claim** separately.

### Estimative language (ICD 203) — use these words, no others
`almost no chance` (01–05%) · `very unlikely` (05–20%) · `unlikely` (20–45%) ·
`roughly even chance` (45–55%) · `likely` (55–80%) · `very likely` (80–95%) ·
`almost certain` (95–99%)

Banned in findings: "clearly", "obviously", "confirmed" (unless credibility=1),
"proves", "definitely", and any bare assertion of an inference as a fact.

---

## 7. Case file field names

`ledger.jsonl` — append-only, one JSON object per line:
```json
{"ts":"ISO8601Z","actor":"main|agent-name","action":"scope|collect|pivot|archive|finding|refusal",
 "source":"sources.csv name or tool","query":"what was asked","result":"summary|none",
 "result_sha256":"hex or null","mode":"passive|active"}
```

`entities.jsonl`:
```json
{"id":"e-<n>","type":"<§4 selector type>","value":"...","first_seen":"ISO8601Z",
 "grade":"B2","sources":["ledger ts or url"],"candidate_group":"cg-<n>|null","notes":"..."}
```

`events.jsonl`:
```json
{"ts":"ISO8601Z or range","actor_entity":"e-<n>","description":"...",
 "grade":"C3","sources":["..."],"precision":"exact|day|month|year|approx"}
```

`candidate_group` is the identity-confusion guard: two entities that *might* be the same
real-world thing share a group and are never merged without a named linking datapoint.

---

## 8. Global refusals — reproduce these semantics, do not soften

Refuse, with one line plus the nearest legitimate alternative, no lecture, no moralizing:

1. Determining the physical location or daily movements of a private individual, when the
   requester is not an institution with a documented mandate.
2. Any target who is a minor.
3. Ex-partner, estranged-family, or "they blocked me / won't respond to me" framing.
4. Any signal of intent to harass, confront, intimidate, or show up somewhere.
5. Circumventing authentication, rate limits, or CAPTCHAs.
6. Using purchased or stolen credential dumps, or any non-public breach corpus.
7. Bulk or population-scale targeting.

Legitimate and explicitly supported: authorized pentest recon, threat intel, DFIR, brand
protection, journalism in the public interest, KYC/AML and corporate due diligence,
sanctions screening, missing-persons work by mandated parties, and self-audit.

The gate runs **once** at intake and is recorded. Do not re-litigate it at every step —
a tool that nags is a tool that gets bypassed.

---

## 9. Passive vs active

`passive` — the target cannot observe it. Public records, archives, third-party datasets,
search engines, certificate transparency, passive DNS.

`active` — the target or a third party can observe it, or state changes. Direct connections
to target infrastructure, port scans, live WHOIS against target-controlled servers,
account-existence probes, password-reset flows, profile views on platforms that notify,
joining a group, sending anything.

Active steps require `active_allowed: true` in scope **and** a fresh confirmation naming the
specific action. Default every play to passive.

---

## 10. Script rules

- Python 3.11+, standard library only in Phases 0–2. If a script would need a third-party
  package, it belongs in Phase 3 and must degrade to a clear "install X to enable" message.
- No network calls at import time. No global mutable state.
- Every script: `--help` via `argparse`, exit non-zero on error, and a `demo()` invoked under
  `if __name__ == "__main__"` when run with `--selfcheck`, containing `assert`-based checks of
  the non-trivial logic. No test framework.
- Scripts write to the case dir via append only. Never rewrite `ledger.jsonl`.
- Windows-safe paths (`pathlib`, no hardcoded `/`).

---

## 11. Prose style

Terminal-readable GitHub-flavored markdown. No emoji. No horizontal-rule spam. Tables where
data is tabular. Sentences short. Do not explain what a domain name is — the reader is a
practitioner. Do not add "Conclusion" or "Summary" sections to reference files.

Never write marketing copy about the plugin inside the plugin.
