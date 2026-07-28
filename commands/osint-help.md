---
description: OSINT plugin router and help. Lists every osint command with its purpose, shows the currently open case, and reports which API keys are detected in this environment plus which sources work with no key at all. Use when the user asks "what OSINT commands do I have", "osint help", "which osint keys are set", "what can this plugin do", or is unsure where to start.
argument-hint: [blank | keys | case]
---

# OSINT plugin — commands, current case, key status

Passive by default: nothing touches target infrastructure unless the open case records
`active_allowed: true` and the specific action is confirmed at the moment it runs.
Provenance or it does not exist: source URL, retrieval timestamp, sha256 of an archived copy,
and an Admiralty source-reliability grade and a credibility grade (e.g. `B2`) on every finding, or
it stays out of `findings.md`.
Refusal boundary: no locating private individuals for non-institutional requesters, no minors,
no ex-partner or estranged-family framing, no harassment intent, no circumvention of
authentication, rate limits, or CAPTCHAs, no purchased or stolen credential dumps, no
population-scale targeting.

Entry point: **`/osint:osint-scope`**. It records purpose, target, the question, authority,
jurisdiction, out-of-bounds and the passive/active posture, then scaffolds the case. No other
command runs against an unscoped target.

If `$1` is `keys`, run only the API keys section. If `$1` is `case`, run only the Current case
section. Otherwise run the whole page.

## Commands

All of these ship. The `Phase` column records when each one was built, not whether it is present.
If a command still does not resolve in this build, say so rather than improvising it.

| Invocation | Purpose | Phase |
|---|---|---|
| `/osint:osint-scope` | Intake and authorization gate. Opens a case, freezes the answers, runs the refusal screen. | 0 |
| `/osint:osint-help` | This page: command list, open case, key status. | 0 |
| `/osint:osint` | Router skill. Picks the play for a selector and enforces case discipline. | 0 |
| `/osint:osint-infra` | DNS, WHOIS/RDAP, certificate transparency, subdomains, ASN and netblocks, passive DNS, search dorking. | 1 |
| `/osint:osint-identity` | `username`, `email`, `phone`, `person_name` — platform presence, email-pattern inference, public people records. | 1 |
| `/osint:osint-corporate` | Registries, filings, officers, UBO, sanctions and PEP screening, adverse media. | 1 |
| `/osint:osint-geoint` | Geolocation and chronolocation: scene features, imagery, sun and shadow, weather, transport tracking. | 2 |
| `/osint:osint-media` | Custody, EXIF and C2PA, reverse image search, earliest instance, manipulation and generative-origin checks. | 2 |
| `/osint:osint-image` | Single image or video, end to end: `/osint:osint-media` first, then `/osint:osint-geoint`. Takes a path or a URL. | 2 |
| `/osint:osint-crypto` | `crypto_address` and `tx_hash` — clustering, exchange attribution. | 2 |
| `/osint:osint-verify` | Claim verification and disinformation analysis. | 2 |
| `/osint:osint-graph` | Validates `entities.jsonl`, then renders it with `events.jsonl` as a link chart (mermaid, DOT or text). | 2 |
| `/osint:osint-report` | Compiles the case into a graded, redacted deliverable. Refuses on an ungraded finding or an unsourced claim. | 2 |
| `/osint:osint-monitor` | Recurring collection and footprint diffing. | 3 |

Support agents: `@osint:osint-collector` fans out one domain of collection into the case
directory; `@osint:osint-critic` reads the case back adversarially and reports what is unsourced,
assumed, or over-graded.

On a large case, `${CLAUDE_PLUGIN_ROOT}/references/60-graphify.md` documents an optional
third-party graph backend. Optional, not part of this plugin, and the wrong call below roughly
150 entities — say so if a user asks for it on a small case.

## Current case

Glob `${CLAUDE_PROJECT_DIR}/cases/*/scope.md`.

- **None:** say so in one line and point at `/osint:osint-scope`. Do not start collecting.
- **One:** read its `scope.md` and report slug, purpose, question, `target_category`,
  `active_allowed`, and the last `ts` in `ledger.jsonl`. Then report open items from `gaps.md`.
- **Several:** list slug, purpose and last ledger timestamp per case, and ask which one is live.
  Do not assume the most recent.

Never report a case as open on the basis of conversation history alone — `scope.md` on disk is
the only authority for what was authorized.

## API keys

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/check_keys.py"
```

`py -3` if `python` is not on PATH. The script reads each value only to test whether it is
non-empty. A key value is never printed, logged, or returned. It groups output into unlocked, missing (with what each would unlock and whether
the source has a free tier), and the zero-key baseline. Report the summary counts and the
unlocked list; do not paste the whole table unless the user asks for it.

Env var names the script marks `*` are conventional rather than vendor-documented, and `?` means
the name is unverified — if a key is set under a different name the scan will show it missing.
That is a naming gap, not a missing key.

## Zero-key baseline

A case can be fully worked with no API keys at all. Do not tell a user they need a key before
running these:

| Source | Gives | Mode |
|---|---|---|
| DNS (`nslookup`, `Resolve-DnsName`) | A/AAAA, MX, NS, TXT, SOA, SPF and DMARC records, mail-provider inference | passive |
| Certificate transparency search (`crt.sh`) | Subdomain inventory from issued certificates, historical hostnames | passive |
| Wayback Machine / Internet Archive (`web.archive.org`) | Historical page states, removed content, archive-on-read for evidence | passive |
| Public corporate registries (UK Companies House, US state secretaries of state, EU business registers) | Company records, officers, filings, addresses | passive |
| Search engines, plus Claude's own `WebSearch` and `WebFetch` | Dorking, adverse media, corroboration | passive |
| RDAP and system `whois` for registry-hosted records | Registration dates, registrar, nameservers, status codes | passive when queried against a registry rather than the target's own server |

Keys buy scale, history and convenience. They do not buy admissibility, and an unkeyed case is
not a lesser case.

## Rules that survive every command

1. Provenance on every finding, or it stays out of `findings.md`.
2. Archive on read — the source will change or vanish.
3. Grade the source and the claim separately (`B2`, `C3`), and use only the ICD-203 words:
   `almost no chance`, `very unlikely`, `unlikely`, `roughly even chance`, `likely`,
   `very likely`, `almost certain`.
4. Log negative results in `gaps.md`. Absence of evidence is a result.
5. Never merge two entities without a named linking datapoint — hold them in a
   `candidate_group` until one exists. `/osint:osint-graph` checks this mechanically and is a
   gate on `/osint:osint-report`.
6. Flag every collection step `passive` or `active` in the ledger.
7. Collect against the recorded question. Anything wider is a dossier, not an investigation.
