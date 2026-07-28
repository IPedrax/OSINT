---
name: osint
description: >
  OSINT investigation router. Opens or resumes a case, runs the authorization gate once,
  dispatches to the right collection department (infra, identity, corporate, geoint, media,
  crypto, verification), and keeps an auditable evidence ledger with graded confidence.
  Serves security and threat intel, journalism and investigation, KYC-AML due diligence,
  self-audit, and education/CTF.
when_to_use: >
  Use when the user says OSINT, recon, footprint, attack surface, "map this domain's
  footprint", "investigate this domain", "who is behind this site/account/company", threat
  intel on a domain or IP, due diligence, beneficial owner or UBO, sanctions or PEP screening,
  adverse media, "find this person's accounts", "username across platforms", email or phone
  enrichment, breach check, exposure check, self-doxx audit, "am I exposed", "verify this
  photo", geolocate or chronolocate an image, crypto address tracing, claim verification.
  Do NOT use for: ordinary web search or a one-off fact lookup, fetching or summarizing a
  single URL the user already has, explaining how DNS/WHOIS/TLS works, writing a report from
  material already in hand, or any code or repo task — unless the code's purpose is to defeat
  an access control, a rate limit or a CAPTCHA, which is a §0 hard stop and is refused, not
  written. Answer the rest directly, no case, no gate.
argument-hint: "[selector or case-slug]"
---

# OSINT router

Dispatcher. It gates, routes, and enforces case discipline. It does not collect anything itself.

## 0. Gate — intake runs once per case; the hard stops below are screened on every request, including inside an open case

1. Is a case open? Look for `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md`. If several exist and
   the user did not name one, ask which; do not guess.
2. No case → run `/osint:osint-scope`. Do not collect first and scope later.
3. Case open → read `scope.md` (frozen intake answers) and the tail of `ledger.jsonl`. Those are
   the authority on purpose, target, authority, out-of-bounds, and `active_allowed`. **Do not
   re-ask the gate questions.** A tool that nags gets bypassed.
4. Read `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` before the first collection step of a
   case, once.

Scope records: `purpose`, `target`, `target_category` (org | public-figure | self |
private-individual), `authority`, `jurisdiction`, `question`, `out_of_bounds[]`,
`active_allowed`.

### Purpose branches

| `purpose` | Default play order |
|---|---|
| `security` | infra → media → crypto |
| `journalism` | verify → geoint → corporate → identity |
| `kyc` | corporate → identity → adverse media |
| `self_audit` | identity → infra → media |
| `education` | any, sanctioned targets only |

Authority expectations and per-branch gate strictness are `/osint:osint-scope`'s business and are
already recorded in `scope.md`. Do not re-apply them.

Education/CTF specifics: the target must be a lab asset, a CTF-provided artifact, or a
deliberately published exercise. "It's just for practice" against a real person or a real company
is not education — re-gate it under the real purpose or refuse. Teaching *method* against a
sanctioned target is always allowed.

### Hard stops — refuse

Checklist. Any one true → refuse, one line plus the nearest legitimate alternative. No lecture,
no moralizing, no second paragraph. Then record it where `/osint:osint-scope` §4 says —
`${CLAUDE_PROJECT_DIR}/cases/_refusals.jsonl` if no case is open, the case `ledger.jsonl` if one
is — and stop.

- [ ] Physical location or daily movements of a private individual, requester is not an
      institution with a documented mandate
- [ ] Target is a minor
- [ ] Ex-partner, estranged-family, or "they blocked me / won't respond to me" framing
- [ ] Any signal of intent to harass, confront, intimidate, or show up somewhere
- [ ] Circumventing authentication, rate limits, or CAPTCHAs
- [ ] Purchased or stolen credential dumps, or any non-public breach corpus
- [ ] Bulk or population-scale targeting

If the request mixes a legitimate core with one out-of-bounds element, refuse the element only,
in one line, write it into `out_of_bounds[]`, and open the case for the rest —
`/osint:osint-scope` §4's partial-refusal paragraph is authoritative.

Wording, disguised phrasings and the nearest legitimate route for each stop:
`${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` §3 and §7. Do not improvise refusal text.

Explicitly supported work is listed in the same file §2 — a request already on that list with
authority on the record does not get re-screened here.

### Always on

PII minimization. No dossier broader than the recorded `question`. Redact by default in outputs.
Passive-only unless `active_allowed: true` **and** a fresh confirmation naming the specific
active action. Active means the target or a third party can observe it — see
`${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md`.

## 1. Dispatch

Classify the selector using the canonical vocabulary, then route. Selector types are exact
strings: `email` `username` `person_name` `phone` `domain` `subdomain` `ip` `asn` `netblock`
`url` `ssl_cert` `company` `company_number` `address` `photo` `video` `document`
`crypto_address` `tx_hash` `vehicle_plate` `vessel` `aircraft` `coordinates` `file_hash`
`social_profile` `breach_record`. Never a synonym, never a plural.

If a value classifies as more than one canonical type and the readings route to different
departments, name both readings using the exact canonical strings and ask which — or resolve it
against the recorded `question` in `scope.md` and say in one line which reading you took and why.
Never route on the top-ranked reading silently; `selectors.py` prints every reading for exactly
this reason.

| Intent | Skill | Accepts | Produces |
|---|---|---|---|
| Domain/host/network footprint, subdomain enumeration, attack surface, certificates, passive DNS, dorking | `/osint:osint-infra` | `domain` `subdomain` `ip` `asn` `netblock` `ssl_cert` `url` | `subdomain` `ip` `asn` `ssl_cert` `email` `company` |
| Accounts, handles, email and phone enrichment, people records, exposure check | `/osint:osint-identity` | `email` `username` `person_name` `phone` `social_profile` | `social_profile` `username` `email` `person_name` `photo` `breach_record` |
| Registries, filings, officers, UBO, sanctions and PEP, adverse media | `/osint:osint-corporate` | `company` `company_number` `person_name` `address` | `company` `company_number` `person_name` `address` `document` |
| Imagery analysis, place identification, chronolocation, terrain, transport | `/osint:osint-geoint` | `photo` `video` `coordinates` `address` `vessel` `aircraft` `vehicle_plate` | `coordinates` `address` `document` |
| EXIF and file metadata, reverse image, synthetic-media check | `/osint:osint-media` | `photo` `video` `document` `file_hash` `url` | `coordinates` `url` `person_name` `file_hash` |
| Address clustering, transaction graph, exchange attribution | `/osint:osint-crypto` | `crypto_address` `tx_hash` | `crypto_address` `tx_hash` `social_profile` `company` |
| Claim and narrative verification, disinformation, source triage | `/osint:osint-verify` | `url` `document` `photo` `video` `social_profile` | graded findings, no new selector |

Cross-cutting commands: `/osint:osint-scope` (intake), `/osint:osint-image` (one image or video,
end to end: media first, then geoint), `/osint:osint-graph` (validate `entities.jsonl`, then render
the link chart), `/osint:osint-monitor` (recurring collection and footprint diffing on an open
case), `/osint:osint-report` (compile the deliverable), `/osint:osint-help` (surface map). If any
`/osint:*` target does not resolve in this build, say so in one line and do the work inline under
the same case discipline.

Order of operations that is not negotiable: for a `photo` or `video`, run the synthetic-media
check in `osint-media` **before** any geolocation or attribution work. Analysing a generated
image is wasted effort at best and a fabricated finding at worst. `/osint:osint-image` runs the
two departments in that order for a single file and is the shortest correct route.

### When a department skill is absent

All seven department skills are installed. If the routed skill still does not resolve in this
build, say so in one line ("osint-geoint is not installed in this build; running the fallback
path") and then:

0. If `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` and
   `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` are both absent, do not stop — work the
   zero-key baseline directly: DNS (`nslookup` / `Resolve-DnsName`) for A/AAAA/MX/NS/TXT/SOA;
   certificate-transparency search at `https://crt.sh` for subdomains; `https://web.archive.org`
   for historical states and archive-on-read; RDAP or system `whois` against the registry; public
   corporate registries; WebSearch and WebFetch for everything else. All passive, no key. Same
   case discipline applies.
1. Read `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` for the pivots that selector
   supports, with their yield confidence, cost, mode, and whether they notify the target.
2. Grep `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` for candidate sources — filter on `accepts`
   containing the selector type, `mode=passive`, and `auth=none` first, then widen to `free_key`.
3. Treat every row with `verified=no` as a homepage to navigate by hand, not an API to call. Its
   `endpoint` may be a landing page only.
4. Execute the pivots yourself with WebSearch / WebFetch / Bash and hold the same case discipline.

Never substitute a plausible-looking API URL for a missing source. If it is not in
`sources.csv` and you are not certain it exists, it does not exist.

## 2. Case discipline — every play, no exceptions

1. Append one `ledger.jsonl` row per collection action: `{ts, actor, action, source, query,
   result, result_sha256, mode}`. Append only. Never rewrite the file.
2. Provenance or it does not exist: source URL + retrieval timestamp + sha256 of an archived
   copy, or it stays out of `findings.md`.
3. Archive on read. Save the bytes to `cases/<slug>/evidence/`, then hash and rename:
   `python -c "import hashlib,pathlib,sys;p=pathlib.Path(sys.argv[1]);h=hashlib.sha256(p.read_bytes()).hexdigest();p.rename(p.with_name(h+p.suffix));print(h)" <file>`.
   Request a public archive save by fetching `https://web.archive.org/save/<url>` (unverified as a
   stable API — treat a failure as a `gaps.md` row, not an error). Put the returned hash in the
   ledger `result_sha256` and in the finding block. If no snapshot was possible, the source still
   gets a note saying why plus any third-party archive URL.
4. Grade every finding `A1`–`F6`: source reliability letter and claim credibility number,
   separately. Estimative words come from the ICD-203 list only.
5. Banned in findings: "clearly", "obviously", "proves", "definitely", "confirmed" unless
   credibility is `1`, and any inference stated as fact.
6. Negative results go in `gaps.md`: what was searched, where, and that it returned nothing.
   Absence of evidence is a result and prevents re-work.
7. Two entities that might be the same real-world thing share a `candidate_group` and are
   **never** merged without a named linking datapoint. Record the datapoint, not the hunch.
8. Every entity row carries its `type` from the canonical vocabulary and its `grade`.
9. Passive by default. Set `mode` honestly on every row; an active step logged as passive
   destroys the audit trail.
10. Redact PII in anything rendered for sharing. The case dir keeps the unredacted original.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. Run any of them with `--help` before use, and
`--selfcheck` if you changed one: `case_init.py` (scaffold a case), `selectors.py` (classify a
selector, rank pivots), `archive.py` (snapshot + hash + ledger row), `graph.py` (`--validate` the
entity file, then render mermaid, DOT or text), `monitor.py` (snapshot a footprint, diff two
snapshots), `check_keys.py` (which sources your env unlocks).
If a script is absent in this build, do the same work by hand — the format is what matters, not
the tool.

`graph.py --validate` is the mechanical half of rule 7: it fires on an un-flagged duplicate
identity, a one-member `candidate_group`, a merge with no linking datapoint named in `notes`, a
grade outside the Admiralty set, a non-canonical `type`, and an entity with no `sources`. Run it
before any chart and before any report; `/osint:osint-report` refuses to compile without it.

## 3. Reference index

Load on demand. Nothing here is preloaded; read the file only when its condition is met.

| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | Once per case before the first collection step. Also on any borderline target, jurisdiction question, or public-interest test |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before any step that touches target infrastructure, before creating or using a research account, or when the user asks about attribution of their own activity |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next collection step from a known selector; a department skill is missing; the obvious pivot came back empty |
| `${CLAUDE_PLUGIN_ROOT}/references/25-geoint.md` | Geolocating or chronolocating a `photo` or `video`, reading a scene for locatable features, sun and shadow reasoning, choosing an imagery source, or checking a candidate match before it enters `findings.md` |
| `${CLAUDE_PLUGIN_ROOT}/references/26-media-forensics.md` | Reading metadata off a `photo`, `video` or `document`; interpreting a C2PA manifest; comparing reverse image engines; establishing an earliest instance; reading an ELA, noise or clone map. Mandatory before any manipulation or generative-origin claim |
| `${CLAUDE_PLUGIN_ROOT}/references/27-crypto.md` | Identifying an address's chain, reading a transaction, applying or rebutting a clustering heuristic, tracing across a bridge, or grading an on-chain observation |
| `${CLAUDE_PLUGIN_ROOT}/references/28-verification.md` | A claim, caption, quote, document or viral artifact has to be checked; tracing something to its origin; deciding whether several sources are one; assessing amplification. Mandatory before any status word |
| `${CLAUDE_PLUGIN_ROOT}/references/30-dorking.md` | Constructing a query against a search engine, code host, paste site, infrastructure index, social platform or web archive — before writing the query, not after it returns nothing |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Two or more hypotheses fit the evidence; ACH is needed; before declaring the question answered; bias check before reporting |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Grading any finding, or when unsure which Admiralty letter, credibility number, or ICD-203 word applies |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md` or rendering anything in `report/`; deciding redaction |
| `${CLAUDE_PLUGIN_ROOT}/references/60-graphify.md` | Only on a large case — roughly 150+ entities — where the mermaid chart has stopped being readable and the question is structural: which sub-network, shortest chain between two entities, which node is the hub. Optional third-party backend; the file's first section is when not to bother |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting a source for a selector type. Grep a filtered slice; never load whole |
| `${CLAUDE_PLUGIN_ROOT}/assets/entity-schema.json` | Writing `entities.jsonl` and unsure of a field |
| `${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` | Starting a deliverable |

Every path above is literal: `${CLAUDE_PLUGIN_ROOT}/<path>`. Never `${CLAUDE_SKILL_DIR}` — it
resolves to `skills/osint/`, which holds only this file. All of the above are installed; if one is
absent in this build, say so once and continue with step 0 of the fallback in section 1.

## 4. Stop conditions

Stop collecting when any of these is true:

- The recorded `question` is answered at a stated confidence, and the answer names its sources.
- Every remaining pivot has been tried and logged in `gaps.md`, and the residual uncertainty is
  written down rather than chased.
- The next step would exceed scope, need active collection without authorization, or need a
  source in `out_of_bounds[]`.
- New collection is returning only material already in `entities.jsonl` — saturation.
- The answer changed the question. Stop, re-scope, do not silently widen.

**Anti-rabbit-hole rule.** Before every collection step, name the scope question it advances.
If you cannot name one in a single clause, the step does not happen. "Interesting" is not a
reason. Log the temptation in `gaps.md` as a possible next line of inquiry and move on.

`/osint:osint-scope` numbers the recorded questions `Q1..Qn` in `scope.md`. **Every ledger
`query` starts with the id it advances, `Q<n>: `** — for example
`"query": "Q1: crt.sh certificate search for acme.example"`. No id, no step. This is the
mechanic the relevance gate and the pre-report checklist in `40-analysis.md` key on; a bare
query string cannot be checked against scope.

Finishing a case: findings graded, gaps written, ledger complete, then `/osint:osint-graph` to
validate and chart the entities, then `/osint:osint-report` to compile against
`${CLAUDE_PLUGIN_ROOT}/assets/report-template.md`. A case with no `gaps.md` entries has not been
investigated, it has been guessed at.
