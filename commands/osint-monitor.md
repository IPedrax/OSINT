---
description: Recurring collection and footprint change detection for an open case. Snapshots a target's observable footprint and diffs two snapshots so you read what changed instead of re-reading everything. Defaults to sources that never touch the target; active polling needs active_allowed plus a fresh confirmation, and repeated polling is more detectable than a single fetch. Use when the user says "monitor this domain", "watch this target", "alert me if this changes", "track changes", "what changed since last week", "recurring collection", "attack surface drift", "brand protection monitoring", "watch for new subdomains", "keep an eye on this company", "re-run the collection", or asks to schedule an investigation.
argument-hint: [case-slug | blank for the open case] [target | blank for the case's primary target]
---

# Footprint monitoring

One script, two jobs: `${CLAUDE_PLUGIN_ROOT}/scripts/monitor.py`. `snapshot` records state,
`diff` says what moved. The diff is the product; snapshots are only the raw material.

`$1` is a case slug, blank means the open case. `$2` is a target, blank means the case's primary
target from `scope.md`.

## 0. Preconditions

1. **A case must be open.** Glob `${CLAUDE_PROJECT_DIR}/cases/*/scope.md`. None → run
   `/osint:osint-scope` first. Several and no slug given → list them and ask. `CASE_DIR` below is
   `${CLAUDE_PROJECT_DIR}/cases/<slug>`.
2. **The target must already be in the case** — the `target` recorded in `scope.md`, or a value
   already in `entities.jsonl`. Monitoring a name the case never collected is a new investigation
   wearing a monitor's clothes; re-scope it instead.
3. Read `scope.md` for `active_allowed`. It decides everything in section 2.

## 1. What monitoring is for

Name the audience before choosing signals — it changes which drift matters and which is noise.

| Purpose | What you are watching for | Signals that carry it |
|---|---|---|
| `security` | Attack-surface drift and brand protection: a new host, a certificate for a name nobody authorised, a mail or DNS provider swap, a status change on something that should be dark | CT logs, passive DNS, `dns`, `tls` |
| `journalism` | A story developing: a page edited or pulled, a staff listing changed, a site moving hosts, a claim quietly rewritten | archives, `http` status and content hash |
| `kyc` | Adverse-media and sanctions-list changes after onboarding: a new designation, a new filing, coverage appearing in a language you did not search | OpenSanctions, issuing-authority lists, GDELT |
| `self_audit` | Exposure appearing over time: a subdomain someone stood up, an address surfacing in a new breach corpus, a profile you forgot | CT logs, `entities`, breach-notification services |

Monitoring answers a *recorded* question repeatedly. If the answer to `Q<n>` in `scope.md` would
not change when the signal changes, do not watch that signal.

## 2. Passive by default — this is the real opsec point

Monitoring polls. Polling the target's own infrastructure is **active**, and a *schedule* is more
detectable than a single fetch: one lookup is background noise, the same lookup every Monday at
09:00 from the same address is a pattern in the target's logs that identifies your interest and
roughly when you started. CONTRACT.md section 9 applies with extra force here.

| Signal | Mode | Who sees it |
|---|---|---|
| Certificate transparency (crt.sh, SSLMate Cert Spotter) | passive | Nobody. Logs are third-party, append-only and public |
| Passive DNS (SecurityTrails, CIRCL, DNSDB) | passive | Nobody. You read a vendor's sensor history, not the zone |
| Web archives (Wayback retrieval, Common Crawl, Arquivo.pt) | passive | Nobody. Reading existing captures is invisible to the target |
| Sanctions and adverse media (OpenSanctions, issuing lists, GDELT) | passive | Nobody |
| `monitor.py --signals entities` | passive | Nobody. Reads the case's own `entities.jsonl` |
| `monitor.py --signals dns` | **active** | The target's authoritative nameservers see a query — from a Google or Cloudflare resolver IP, not yours |
| `monitor.py --signals tls` | **active** | The target sees a TLS handshake from your address |
| `monitor.py --signals http` | **active** | The target's access log gets a row with your address and user agent |
| Wayback Save Page Now (`archive.py --wayback`) | **active** | The target sees an archive.org crawler hit, and the capture is public immediately |

**Default to the passive column.** For most engagements the passive route answers the question:
CT logs surface a new hostname before it resolves, passive DNS shows the provider swap, and an
archive shows the page edit. Reach for `--active` when the passive sources are silent and the
question genuinely needs live state.

`--active` requires **both**: `active_allowed: true` in `scope.md`, **and** a fresh confirmation
naming the specific action and the cadence — "resolve and fetch `acme.example` once a week for the
next four weeks", not "monitoring is fine". Record the confirmation in the ledger. If
`active_allowed` is false, run the passive signals and say plainly which questions stay open.
A diff is always passive: it compares two files already on disk.

## 3. Running it

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/monitor.py" snapshot --case "<CASE_DIR>" \
    --target acme.example --query "Q2: weekly footprint snapshot"
python "${CLAUDE_PLUGIN_ROOT}/scripts/monitor.py" snapshot --case "<CASE_DIR>" \
    --target acme.example --active --query "Q2: weekly footprint snapshot"
python "${CLAUDE_PLUGIN_ROOT}/scripts/monitor.py" diff --case "<CASE_DIR>" \
    --target acme.example --query "Q2: weekly footprint diff"
python "${CLAUDE_PLUGIN_ROOT}/scripts/monitor.py" list --case "<CASE_DIR>"
```

`py -3` if `python` is not on PATH. `--help` for the full flag set. Without `--active` the three
network signals are skipped and recorded as skipped, and only the passive `entities` signal is
collected — that is the safe default, not a failure.

Every ledger `query` starts with the scope question id it advances, `Q<n>: `. No id, no step.

Snapshots land in `<CASE_DIR>/monitor/<ISO8601Z>.json`, basic format
(`20260728T145501Z.json`) because a colon is not a legal Windows filename character.

Exit codes: `0` ok, including "nothing changed"; `1` only with `--exit-changed`, when a diff found
changes; `2` usage; `3` the case directory or a named snapshot is missing.

## 4. Reading a diff

**Silence is the expected result and it is a PASS.** A run that reports no change is evidence the
footprint held steady, and it costs nothing to read. Do not treat it as an error, do not re-run it
to "get something", and do not widen the signal set to manufacture a result.

Three outcomes, all clean:

| Output | Meaning |
|---|---|
| `PASS - nothing to compare yet` | First run. One snapshot is a baseline, not a diff. Nothing was written |
| `PASS - no change` | The compared signals held. Nothing was written |
| `N change(s)` | Grouped by signal, each line in plain language, added / removed / changed |

A `[not compared]` block means a signal was collected in one snapshot and not the other — most
often because one run had `--active` and the other did not. **That is not a disappearance.**
Never report an uncollected signal as something that went away.

When a diff finds changes the script appends, without being asked:

- **One ledger row** — action `monitor`, mode `passive`, `result_sha256` of the newer snapshot.
- **Entity rows for selectors the change introduced**, graded. A new subdomain appearing is a
  finding and enters the case like any other finding; it does not sit in a side file.
  New IPs and new MX/NS/CNAME hostnames from live DNS grade `B3`. New subjectAltNames on the
  served certificate grade `A3` — an authoritative primary artifact, uncorroborated. The single
  source `A1` exemption in `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` belongs to
  **certificate transparency log entries**, and a leaf certificate read off one TLS connection is
  not one. Do not raise either grade when writing the change into `findings.md` unless a second,
  independently generated observation carries it — a CT log entry alongside a passive DNS
  resolution is the usual pair. Re-read `41-confidence.md` before writing any grade.

Then work it like any other collection: does the change answer `Q<n>`, or is it noise? A rotated
certificate serial and a changed page content hash are usually routine — a CDN redeploy moves
both weekly. A new SAN, a new nameserver, a new mail provider, or a status flipping to 200 on a
host that was dark are the ones worth a finding.

## 5. Scheduling

**This plugin does not implement a scheduler and does not ship one.** Nothing here starts a
daemon, registers a job, or wakes itself up.

What it gives you is a job that is trivial to schedule, because the whole interface is one command
line with no interactive state:

```
snapshot --case <CASE_DIR> --target <target> [--active] --query "Q<n>: ..."
diff     --case <CASE_DIR> --target <target>            --query "Q<n>: ..."  --exit-changed
```

Run the pair on a cadence — daily for a live incident, weekly for attack-surface drift, monthly
for post-onboarding KYC. `--exit-changed` makes `diff` exit `1` when something moved, which is the
hook most schedulers use to fire an alert; without it the exit is `0` either way.

Wire that to **your own scheduling tooling**. Claude Code has its own mechanisms for recurring
work, and installations differ in which are present — check the tooling's own help or docs for the
exact name and invocation rather than taking one from this file. At the operating-system level,
Task Scheduler on Windows and cron or a systemd timer elsewhere all run a command on a cadence and
are entirely sufficient. Whatever you use, the three things it needs are: the command line above,
an interval, and somewhere for the output to go.

Two constraints the scheduler does not know about and you must enforce:

- **A schedule is an active-collection decision with a duration.** Confirm the cadence and an end
  date when you confirm `--active`, put both in the ledger, and stop when the case closes. An
  unattended job still polling a target after an engagement ended is unauthorised collection.
- **Re-read scope before acting on what a run returns.** An automated run cannot apply the
  relevance gate. A scheduled job may collect; only a session with `scope.md` in front of it
  decides what is a finding.

## 6. Refusals

- **No monitoring without a case and a recorded question.** A standing collection job with no
  question is a surveillance feed, which is what the intake gate exists to prevent.
- **No monitoring of a private individual's accounts, presence, or movements.** Recurring
  collection against a person is the shape of stalking regardless of the requester's stated
  intent; global gate items 1, 3 and 4 in
  `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` apply, and the cadence makes it worse, not
  better. Organisations, infrastructure, and the user's own exposure are the legitimate targets.
- **No `--active` without `active_allowed` and a fresh confirmation naming the action and the
  cadence.** Passing the flag on the user's behalf because it "would be more complete" is exactly
  the failure CONTRACT.md section 9 is written against.
- **No polling faster than the signal changes.** Certificates last months; CT logs update in
  minutes but a domain's estate does not. Hourly polling of a target's own site produces no extra
  information and a much louder trace.
- **No inventing a change.** If a signal was not collected in both snapshots, it was not compared.
  Say so; do not report it as a disappearance.
