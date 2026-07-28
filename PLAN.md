# OSINT Plugin — Build Spec

**Decisions locked 2026-07-27:** ship as a Claude Code *plugin* · serve all four audiences
with a purpose-branching intake gate · prose-first with minimal stdlib Python.

---

## 1. Repo layout

```
osint/                              # repo root, also a self-hosted marketplace
  .claude-plugin/
    plugin.json                     # name, description, version, author
    marketplace.json                # so `/plugin marketplace add <repo>` works
  README.md
  commands/
    osint-help.md                   # router / help. NOT osint.md — see note below
    osint-scope.md                  # intake + authorization gate
    osint-image.md
    osint-monitor.md
    osint-graph.md
    osint-report.md
  references/                       # PLUGIN ROOT — shared by all skills
    00-legal-ethics.md
    01-tradecraft-opsec.md
    10-pivot-matrix.md              # the brain
    25-geoint.md                    # scene reading, sun/shadow, imagery sources
    26-media-forensics.md           # metadata, C2PA, reverse image, manipulation
    27-crypto.md                    # chains, clustering heuristics, bridges
    28-verification.md              # claim tracing, origin, amplification
    30-dorking.md                   # search-operator cheatsheets
    40-analysis.md                  # ACH, bias checklist, stop conditions
    41-confidence.md                # Admiralty + ICD-203
    50-reporting.md
    60-graphify.md                  # optional third-party graph backend
  assets/                           # PLUGIN ROOT
    sources.csv                     # the moat
    entity-schema.json
    report-template.md
    case-skeleton/
  scripts/                          # PLUGIN ROOT
    case_init.py
    selectors.py
    archive.py
    graph.py
    check_keys.py
    monitor.py                      # footprint snapshot + diff
    report.py                       # case dir -> markdown / HTML / JSON, with a refusal gate
    case_status.py                  # SessionStart hook payload, read-only
  skills/
    osint/                          # ROUTER skill — the only one that auto-triggers broadly
      SKILL.md                      # <400 lines: gate → play selection → case discipline
    osint-infra/SKILL.md            # DNS, WHOIS, CT logs, ASN, passive DNS, dorking
    osint-identity/SKILL.md         # username, email, phone, people records
    osint-corporate/SKILL.md        # registries, filings, UBO, sanctions/PEP, adverse media
    osint-geoint/SKILL.md           # imagery, chronolocation, terrain, transport
    osint-media/SKILL.md            # EXIF, reverse image, AI-generated detection
    osint-crypto/SKILL.md           # address clustering, exchange attribution
    osint-verify/SKILL.md           # claim verification / disinfo
  agents/
    osint-collector.md              # fan-out worker: one domain, writes to case dir
    osint-critic.md                 # adversarial: "what here is unsourced or assumed"
  hooks/
    hooks.json                      # optional: block writes outside cases/ during a case
```

**Verified during Phase 0** against the live docs and by running `claude plugin validate` on the
installed Claude Code 2.1.71. Findings that changed this layout, recorded so they are not
relitigated (full detail in `FORMAT.md`):

- `references/`, `assets/`, `scripts/` sit at the **plugin root**, not under `skills/osint/`.
  Eight skills share them. Skills address them via `${CLAUDE_PLUGIN_ROOT}`, never
  `${CLAUDE_SKILL_DIR}` — the latter resolves to the individual skill's own folder.
- **`commands/osint.md` is forbidden.** It collides with `skills/osint/SKILL.md`; both resolve to
  `/osint:osint` and the skill silently shadows the command. Help lives at `commands/osint-help.md`.
  The same collision rules out `commands/osint-infra.md`, `osint-identity.md`, `osint-corporate.md`
  and `osint-verify.md` — each shadows the skill directory of the same name. Those departments are
  skills only; `commands/` keeps `osint-help`, `osint-scope`, `osint-image`, `osint-monitor`,
  `osint-graph`, `osint-report`.
- `$schema` in `plugin.json` is a hard validation error on 2.1.71.
- `marketplace.json` needs `metadata.description`; top-level `description` alone warns.
- `description` + `when_to_use` are truncated at 1,536 chars in the skill listing.
- Department skills need `disable-model-invocation: true` so only the router auto-triggers.

---

## 2. Intake gate — branches by declared purpose

`/osint scope` runs once per case, writes answers to `ledger.jsonl`, and is referenced
thereafter instead of re-asked.

| Purpose declared | Default plays | Authority expected | Gate strictness |
|---|---|---|---|
| **Security / threat intel** | infra → media → crypto | Engagement letter, scope doc, or own-asset claim | Active steps need scope confirmation |
| **Journalism / investigation** | verify → geoint → corporate → identity | Editorial assignment / publication | Public-interest test on private individuals |
| **Due diligence / KYC-AML** | corporate → identity → adverse media | Compliance mandate, client engagement | PII minimization enforced hard |
| **Self-audit** | identity → infra → media | Self (trivially satisfied) | Relaxed; no external-target plays |
| **Education / CTF** | any, against sanctioned targets only | CTF scope or lab domain | Refuse live third-party targets |

Recorded fields: `purpose`, `target`, `target_category` (org / public-figure / self /
private-individual), `authority`, `jurisdiction`, `question`, `out_of_bounds[]`,
`active_allowed` (bool).

### Hard stops (refuse, one line + nearest alternative, no lecture)
- Physical location of a private individual for a non-institutional requester
- Minors as targets
- Ex-partner / "they blocked me" / "they won't talk to me" framing
- Harassment, intimidation, or confrontation signals
- Auth or CAPTCHA circumvention; purchased credential dumps
- Bulk/mass targeting of a population

### Always on
PII minimization · no dossier broader than the stated question · redact by default in
reports · passive-only unless `active_allowed`.

---

## 3. Case file format

```
cases/<slug>/
  scope.md          # frozen intake answers, human-readable
  ledger.jsonl      # append-only: {ts, actor, action, source, query, result, result_sha256, mode}
  entities.jsonl    # {id, type, value, first_seen, grade, sources[], candidate_group, notes}
  events.jsonl      # {ts, actor_entity, description, grade, sources[], precision}
  findings.md       # graded prose; nothing enters without source + ts + hash
  gaps.md           # negative results + unanswered questions + next collection
  evidence/         # archived copies, named <sha256>.<ext>
  report/           # rendered outputs
```

Append-only ledger is what makes parallel subagents safe and the case resumable.

---

## 4. Non-negotiables (Phase 0, not later)

1. **Provenance or it doesn't exist.** Source URL + retrieval timestamp + sha256 of an
   archived copy, or it stays out of `findings.md`.
2. **Archive on read.** Wayback Save Page Now + local snapshot. OSINT evidence rots.
3. **Confidence grading on every finding.** Admiralty A–F / 1–6 plus ICD-203 wording.
   Without this the plugin is a fast bullshit generator.
4. **Negative results logged.** Prevents re-work; makes absence-of-evidence explicit.
5. **Identity-confusion guard.** Never merge two entities without a named linking
   datapoint. Hold `candidate_group` until resolved.
6. **Passive/active flag on every source.** Active tells the target you're looking.

---

## 5. sources.csv schema

```
name,category,accepts,yields,endpoint,auth,rate_limit,mode,verified,fetchable,jurisdiction_notes,reliability,notes
```
- `fetchable` was added in Phase 1 and is the 13th column: an endpoint can be perfectly correct
  and still unfetchable (SEC EDGAR, crt.sh, Wayback all are), and conflating that with `verified`
  wasted tool calls in both directions.
- Column rules, including `verified` and `notes`, are in `CONTRACT.md` §5. `accepts` / `yields`
  are pipe-delimited types from `CONTRACT.md` §4 — exact strings, no synonyms, no plurals.

Claude greps a filtered slice ("accepts contains email, auth=none") instead of loading an
encyclopedia. Scales to 300+ sources at near-zero context cost; extendable by editing a CSV.

---

## 6. Pivot matrix (references/10-pivot-matrix.md)

```
email      → username(local-part) · domain · breach records · gravatar hash
             · org email-pattern inference · [ACTIVE: reset-flow probing]
username   → other platforms · real name · avatar→reverse-image · archived posts
             · git commit emails
domain     → subdomains(CT logs) · IPs · ASN · MX/SPF→mail provider
             · sibling domains via analytics ID / favicon hash · historical WHOIS
phone      → carrier · region · messenger presence · leak corpora
photo      → EXIF/GPS · device model · reverse image · landmarks→geoloc
             · sun angle→time-of-day · synthetic-media check FIRST
company    → officers→people · addresses · filings · trademarks · subsidiaries · UBO
ip         → ASN · rDNS · co-hosted domains · historical resolutions · [ACTIVE: ports]
crypto_address → tx graph · exchange deposit clusters · ENS · social mentions
```

Each entry carries: yield confidence, cost, mode, and whether it notifies the target.

---

## 7. Scripts (stdlib-first, ~5 files)

| Script | Deps | Job |
|---|---|---|
| `case_init.py` | stdlib | scaffold case dir, seed ledger with scope answers |
| `selectors.py` | stdlib | classify/normalize a selector, emit ranked pivots from sources.csv |
| `archive.py` | stdlib `urllib` | snapshot URL → Wayback SPN + local file + sha256 → ledger row |
| `graph.py` | stdlib | entities.jsonl + events.jsonl → mermaid link chart |
| `check_keys.py` | stdlib | env scan → which sources unlock |

Anything needing `requests`/`dnspython`/`Pillow` was deferred and, in the end, never needed:
all eight shipped scripts are standard library only, including the Phase 3 additions. The core
loop runs with a bare Python and Claude's own WebSearch/WebFetch/Bash.

Shipped: the five above plus `monitor.py` (footprint snapshot and diff), `report.py` (compiles a
case directory to markdown, HTML or JSON and refuses on an ungraded finding, an unsourced
finding, a banned certainty word, or an open `candidate_group` written as resolved), and
`case_status.py` (SessionStart hook payload, read-only).

---

## 8. Phases

- **Phase 0 — done.** Plugin manifest · router SKILL.md · `00-legal-ethics` · `41-confidence` ·
  `/osint:osint-scope` · case skeleton · `case_init.py` · report template. *Usable immediately.*
- **Phase 1 — done.** `sources.csv` · pivot matrix · `osint-infra` · `osint-identity` ·
  `osint-corporate` · `selectors.py` · `archive.py`.
- **Phase 2 — done.** `osint-geoint` · `osint-media` · `osint-crypto` · `osint-verify` ·
  `graph.py` · dorking cheatsheets · `/osint:osint-image` · `/osint:osint-graph` ·
  `/osint:osint-report`.
- **Phase 3 — done.** Monitoring and footprint diffing · collector + critic subagents ·
  graphify evaluated and documented · final documentation pass · version 0.3.0.
- **Evals — not built.** No eval suite ships. The `--selfcheck` in each script covers the
  mechanical logic; nothing covers trigger accuracy or the refusal set. This is the largest
  outstanding gap and is stated here rather than quietly dropped.

### Deviations from the plan as written

Recorded so the plan stays a record rather than an aspiration.

| Planned | Shipped | Why |
|---|---|---|
| `sources.csv` target 120 rows | 221 rows, all `verified=yes` | The registry is the moat; the ceiling was the supply of endpoints that could be stated with certainty, not the target |
| 12-column source schema | 13 columns — `fetchable` added | See §5. `verified` is a claim about the URL; `fetchable` is a claim about retrieval, and merging them cost tool calls |
| Monitoring via the `schedule` / `loop` skills | `scripts/monitor.py` (stdlib snapshot + diff) driven by `/osint:osint-monitor`; scheduling left to the user's own scheduler | A hard dependency on a third-party skill would make the core loop unrunnable without it |
| graphify as the backend for `entities.jsonl` | Documented as an **optional** third-party lens in `references/60-graphify.md`, with a deterministic conversion and an explicit "do not bother" threshold | graphify has no concept of an Admiralty grade or an unresolved identity, and its LLM extraction path would invent edges into an evidence graph. `graph.py` remains the authority |
| HTML artifact reports | Not built. `/osint:osint-report` emits markdown; the `make-pdf` and `diagram` skills are named as optional renderers and are not dependencies | Markdown is the archivable form; an artifact adds a rendering surface, not evidence |
| Third-party Python permitted in Phase 3 | Not used. All seven scripts are standard library only | Nothing needed it |
| `hooks/hooks.json` "optional: block writes outside `cases/` during a case" | A read-only `SessionStart` hook that surfaces an open case and blocks nothing | A hook that blocks writes breaks unrelated work in the same session; surfacing the frozen scope solves the actual problem |

---

## 9. Integrations available on the build machine

None of these is a dependency. The plugin runs with a bare Python and Claude's own tools; each
entry below is a convenience if it happens to be installed.

| Integration | Status |
|---|---|
| **graphify** | Evaluated and documented in `references/60-graphify.md` as optional. Interface verified against `graphifyy` 0.9.8 by reading its source and building a fixture graph. Optional, third-party, and wrong on a small case |
| **make-pdf** | Named in `/osint:osint-report` as an optional renderer of the finished markdown |
| **diagram** | Named in `/osint:osint-graph` as an optional route from DOT to an editable chart |
| **firecrawl MCP** | Not wired. `monitor.py` does the diffing with the standard library, so change detection has no external dependency |
| **playwright / chrome-devtools MCP** | Not wired. `sources.csv` marks a row `fetchable=no` when it needs a real browser; the investigator opens it by hand |
| **schedule / loop skills** | Not wired. `/osint:osint-monitor` runs a pass on demand; recurrence is the user's scheduler |
