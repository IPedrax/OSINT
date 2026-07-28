<div align="center">
  <img src="assets/icons/radar.svg" width="56" alt="" />
  <h1>osint</h1>
  <p><strong>An open-source-intelligence toolkit for Claude Code that turns a search session into a defensible case file — sourced, timestamped, hashed and graded, or it does not enter the report.</strong></p>
</div>

An LLM with a browser will happily hand you a confident, unsourced dossier. It reads well, it cites nothing you can check, and you find out which half was inferred when someone else checks it. **osint** makes that structurally hard. Every finding carries **a source URL, a retrieval timestamp, the sha256 of an archived copy, and an Admiralty reliability + credibility grade**, and the report compiler **refuses to build** on a finding that is missing any of them. It is methodology and tradecraft, not a scanner: the pivot logic, the source registry, the evidence discipline, and the confidence vocabulary that a search session normally lacks. Collection is **passive by default**; anything the target can observe needs authorization on the record first.

Built for **Claude Code** (Windows / macOS / Linux).

---

## <img src="assets/icons/sparkles.svg" width="20" align="absmiddle" alt="" /> What it does

- **Eight skills — one router, seven departments** — the router gates, classifies the selector, and dispatches; `osint-infra`, `osint-identity`, `osint-corporate`, `osint-geoint`, `osint-media`, `osint-crypto` and `osint-verify` do the collection. Only the router auto-triggers, so the departments never compete to fire on an ordinary message.
- **A 221-source registry with a real zero-key baseline** — `assets/sources.csv` on a fixed 13-column schema, every row carrying what it accepts, what it yields, its auth tier, its Admiralty reliability and whether it is passive or active. **151 of the 221 need no key, account or payment at all.** Claude greps a filtered slice; the file is never loaded whole.
- **The case file is the artifact** — one directory per case in *your* working directory, never inside the plugin. Append-only `ledger.jsonl`, `entities.jsonl`, `events.jsonl`, graded `findings.md`, `gaps.md`, hash-named `evidence/`. That is what makes parallel collection safe and a case resumable weeks later.
- **Grading is not optional** — Admiralty `A`–`F` for the source and `1`–`6` for the claim, graded separately, so a finding reads `B2`. Estimative language comes from the ICD-203 list and nothing else. "Obviously", "proves" and "definitely" are banned words the compiler checks for.
- **Identity-confusion guard** — two entities that *might* be the same real-world thing share a `candidate_group` and are never merged without a named linking datapoint. The datapoint gets recorded, not the hunch, and `/osint:osint-graph` checks it mechanically before anything is charted or compiled.
- **Monitoring that reports the delta** — `/osint:osint-monitor` re-runs collection against an open case and tells you what changed rather than what exists. Stdlib snapshot and diff, no scheduler shipped, no external service.
- **Passive/active on every source** — 195 of the 221 rows are passive, 26 are active. Active means the target can tell you were looking, and it is gated separately.
- **Behaviour is tested, not asserted** — 8 stdlib-only scripts each carry a `--selfcheck`, and a 34-case blind eval suite in `evals/` covers trigger accuracy, dispatch, refusals and permits, with a stated pass bar per category.

---

## <img src="assets/icons/download.svg" width="20" align="absmiddle" alt="" /> Install

The repository is its own marketplace. The command is the same on Windows, macOS and Linux — this is the `claude` CLI, not a shell script:

```
claude plugin marketplace add IPedrax/osint
claude plugin install osint@osint
```

Verified against Claude Code **2.1.71**. Inside a running session the same thing is `/plugin marketplace add IPedrax/osint` then `/plugin install osint@osint`.

### <img src="assets/icons/terminal.svg" width="17" align="absmiddle" alt="" /> From a local clone

Point the marketplace at the checkout directory instead of the repo slug:

```
claude plugin marketplace add ./osint
claude plugin install osint@osint
```

Any absolute or relative path to the clone works — `./osint`, `~/src/osint`, `C:\src\osint`.

### <img src="assets/icons/check.svg" width="17" align="absmiddle" alt="" /> Requirements

Python **3.11+** on `PATH` (`py -3` works on Windows). No third-party Python packages, no API keys, no network access at import time. `claude plugin list --json` shows what the installed copy actually ships.

> **Prefer to let Claude install it?** Paste this into a new chat:
> *"Install this Claude Code plugin for me from https://github.com/IPedrax/osint and walk me through anything you need."*

---

## <img src="assets/icons/key.svg" width="20" align="absmiddle" alt="" /> Optional — API keys

**151 of the 221 registry sources need no key at all**, so a full case can be opened, worked and reported with nothing configured. DNS, certificate transparency, the Wayback Machine, RDAP and system `whois`, public corporate registries, and Claude's own `WebSearch` / `WebFetch` carry the baseline.

To see what a key would actually unlock in your environment, ask for `/osint:osint-help keys` inside a session, or run the script directly from a clone:

```
python scripts/check_keys.py
```

It prints, per source, the env var it looks for, what that source unlocks, its free-tier status and its signup page — and it marks whether the env var name is vendor-documented, a conventional name from the vendor's own CLI, or an unverified community convention. Values are read only to test whether they are non-empty; **a key value is never printed, logged, or returned**, and the script's `--selfcheck` asserts that with a sentinel.

> Keys buy scale, history and convenience. They do not buy admissibility — an unkeyed case is not a lesser case, and nobody should be told to go get a key before running the baseline.

---

## <img src="assets/icons/chat.svg" width="20" align="absmiddle" alt="" /> How to use it

Just ask, and the router opens or resumes the case for you:

- *"map the external footprint of acme.example — we have the engagement letter"*
- *"who actually owns this company, and is anyone in the structure sanctioned?"*
- *"verify this photo before we publish it — where and when was it taken?"*
- *"trace where the funds from this address ended up"*
- *"audit my own exposure: email, handles, home network"*
- *"what changed on this target since last week?"*

Hand it a selector — a domain, an email, a company number, a wallet address, an image — and it classifies against a canonical vocabulary and routes. A `photo` or `video` always goes through the synthetic-media check **before** any geolocation or attribution work; geolocating a generated image is a fabricated finding, not a slow one.

| Command | What it does |
|---|---|
| `/osint:osint-scope` | Intake and authorization gate. Runs once per case, freezes the answers, scaffolds `cases/<slug>/` |
| `/osint:osint-image` | One image or video end to end: media forensics first, then place and time |
| `/osint:osint-monitor` | Re-runs collection against an open case and reports the diff, not the state |
| `/osint:osint-graph` | Validates `entities.jsonl`, then renders it with `events.jsonl` as a link chart |
| `/osint:osint-report` | Compiles the case into a graded, redacted deliverable |
| `/osint:osint-help` | Command list, the currently open case, key status, zero-key baseline |

Two subagents are available for the heavy parts: `osint-collector` fans one department's play out over a case directory, and `osint-critic` reads the case back adversarially — what here is unsourced, over-graded, or an inference written as a fact.

---

## <img src="assets/icons/shield.svg" width="20" align="absmiddle" alt="" /> Safety

`/osint:osint-scope` records purpose, target, target category, authority, jurisdiction, the numbered questions, out-of-bounds items, and whether active collection is permitted. It runs **once**, at intake, and is written to the case ledger — later steps read it instead of re-asking. A tool that nags at every step is a tool that gets bypassed.

Refused at the gate, in one line with the nearest legitimate route, and recorded:

1. Physical location or daily movements of a private individual, when the requester is not an institution with a documented mandate.
2. Any target who is a minor.
3. Ex-partner, estranged-family, or "they blocked me / won't respond to me" framing.
4. Any signal of intent to harass, confront, intimidate, or show up somewhere.
5. Circumventing authentication, rate limits, or CAPTCHAs.
6. Purchased or stolen credential dumps, or any non-public breach corpus.
7. Bulk or population-scale targeting.

Explicitly supported, and not re-screened once the authority is on the record: authorized pentest reconnaissance, threat intelligence, DFIR, brand protection, journalism in the public interest, KYC/AML and corporate due diligence, sanctions screening, missing-persons work by mandated parties, and self-audit. A request that mixes a legitimate core with one out-of-bounds element loses the element, not the case.

Collection is **passive by default** — the target cannot observe it. Active collection (direct connections to target infrastructure, port scans, account-existence probes, reset flows, anything sent) requires `active_allowed: true` in the recorded scope **and** a fresh confirmation naming the specific action. Over-blocking is treated as a defect too: six of the 34 eval cases exist purely to catch it.

---

## <img src="assets/icons/settings.svg" width="20" align="absmiddle" alt="" /> How it works

**Scope → Collect → Grade → Validate → Report.**

The ordering is the point. The gate runs once, at the front, because an authorization question asked at step forty is theatre — by then the collection already happened. Grading sits *between* collection and the deliverable so that a source and a claim get judged separately, while the retrieval is still in hand. Validation is a hard gate, not a lint pass: `/osint:osint-graph` fails on an un-flagged duplicate identity, a one-member candidate group, a merge with no linking datapoint, a grade outside the Admiralty set, a non-canonical selector type, or an entity with no sources — and `/osint:osint-report` refuses to compile until it passes, and refuses again on any ungraded or unsourced finding. That refusal is the whole design: an unsourced sentence has nowhere to go except out.

Full details: [`skills/osint/SKILL.md`](skills/osint/SKILL.md) · authoring rules, selector vocabulary and grading scales: [`CONTRACT.md`](CONTRACT.md) · confidence and estimative language: [`references/41-confidence.md`](references/41-confidence.md) · the pivot brain: [`references/10-pivot-matrix.md`](references/10-pivot-matrix.md) · the registry: [`assets/sources.csv`](assets/sources.csv) · eval suite and pass bars: [`evals/README.md`](evals/README.md) · build spec and recorded deviations: [`PLAN.md`](PLAN.md).

---

## <img src="assets/icons/file.svg" width="20" align="absmiddle" alt="" /> License

[MIT](LICENSE) — grading scales follow the Admiralty/NATO system and [ICD 203](https://www.dni.gov/files/documents/ICD/ICD%20203%20Analytic%20Standards.pdf); the source registry cites third-party services under their own terms.
