*Load when: planning collection that could touch target-controlled infrastructure, standing up a research identity, or handling collected evidence.*

# Tradecraft and OPSEC reference

This is about protecting the investigator and the integrity of the investigation — not the
target. Two failure modes drive it: **intent leakage** (the target learns they are being looked
at, changes behaviour, lawyers up, or retaliates) and **contamination** (your own activity
pollutes the findings or the evidence). Everything below defaults to `passive` — the target cannot
observe it; `active` steps need `active_allowed: true` and a fresh, named confirmation.

**Boundary — deliberate and stated.** This file is separation and hygiene only. It does **not**
cover fabricating identities or personas, evading platform bot-detection, defeating CAPTCHAs, or
circumventing terms of service. CAPTCHA defeat and authentication circumvention are hard stops
(`00-legal-ethics.md` §3.5); identity fabrication and ToS circumvention are out of scope for this
plugin by design, not hard stops. A research account is a real, ToS-compliant account used for
work and kept apart from your personal life — not a sock puppet built to deceive a platform.

## 1. Intent leakage — what notifies or reveals the target

Each row: the action, what leaks, its mode, and the passive alternative that answers the same
question without tipping the target. Prefer the alternative unless scope explicitly permits the
active step.

| Action | What leaks to the target / a third party | Mode | Passive alternative |
|---|---|---|---|
| Viewing a profile on a network that notifies (e.g. professional networks showing "who viewed you") | Your identity or research account, and the fact of interest | active | Read the public/cached copy signed-out; view archived versions; use the platform's private-browse mode where it exists |
| Following / connecting / friending | A notification, plus a standing edge in the social graph | active | Read public posts only; pull archived posts; never connect to observe |
| Viewing a story / ephemeral post | Major platforms show the owner an exact viewer list | active | Do not view while identified; rely on reposts, archives, or third-party captures already public |
| Live DNS resolution against the target's own authoritative nameservers | A query in the target's DNS logs tied to your resolver/IP and timing | active | Passive DNS datasets; `ssl_cert` history via certificate-transparency search; historical resolutions from third parties |
| WHOIS / RDAP lookup | Goes to the registry/registrar, not the target. Some registries log queries, and some paid WHOIS products notify the registrant — treat those specific products as `active` | passive | Use standard registry/RDAP queries; prefer historical WHOIS snapshots for `domain` history |
| Direct fetch of the target's web server | Your IP, user-agent, referrer, and timing in their access logs, analytics, and any referrer chain | active | Search-engine cache and web archives first; third-party scan datasets; live fetch last, with a research identity, only if unavoidable |
| Opening a shortened or tracked link the target controls | Your IP/UA/time to the shortener and the destination; confirms you clicked | active | Expand the short URL with a preview/expander that resolves without loading the final page; inspect before any fetch |
| Opening a document that "calls home" (remote images, beacons, canary tokens in Office/PDF) | A callback to the target with your IP and open time — a deliberate tripwire | active | Open offline in a sandboxed viewer with network disabled and remote content off; inspect embedded `url`s in the file first |
| Requesting a TLS certificate for a recon domain named after the target | The certificate appears in public Certificate Transparency logs; a target monitoring CT for their brand sees it | active | Do not name recon infrastructure after the target; avoid standing up a named HTTPS service; use generic, unrelated domains |
| Opening a shared Google Doc / accepting a Calendar invite while signed in | Your account/avatar shown to owner and co-viewers; RSVP and presence artifacts | active | View signed-out or with a research account; request a static export; never open shared docs under a personal identity |
| Email tracking pixel / read receipt (MDN) | Sender learns you opened, when, your IP, and client | active | Read with remote images disabled; use plain-text view; never auto-send read receipts |
| Password-reset / account-existence probe | Reveals whether an `email`/`username` has an account, and can send the real owner a "someone tried to reset" alert | active | Infer account presence from public `social_profile` pages only; do not run reset or signup flows (also §3.5 of legal-ethics) |
| Joining a group / community to read it | Admins and members get a join notice; you appear on the roster | active | Read publicly visible or archived threads; use cached copies; do not join to observe |
| Live fetch when a cache exists | Touches the target directly (see direct-fetch row) | active | Search-engine cache and web archive serve a copy without touching the target — try them before any live request |

Rule of thumb: if a step changes state on the target's side or produces a record a third party
controls, it is `active`. When unsure, treat it as active and check scope.

## 2. Research-account hygiene

Separate the research identity from the personal identity. Three reasons, all about protecting
the investigator and the work:

- **Contamination of results** — a personal account carries your history; personalization and
  recommenders bend what you see and make findings non-reproducible (§3).
- **Personal risk** — a target who detects observation can retaliate against a real name; a
  personal `email`, `phone`, or home IP in the loop is an exposure.
- **Tainted evidence** — if collection runs through your personal account, the evidence is
  entangled with your private life and harder to stand behind.

Separation practices (hygiene, not disguise):

| Layer | Practice |
|---|---|
| Identity | A dedicated, genuine work account kept distinct from personal accounts. Real and terms-compliant, used only for research |
| Browser / session | A separate browser profile or browser; isolated cookies, cache, and history so personalization does not bleed between personal and research use |
| Device / OS | A separate OS user, VM, or dedicated machine for sensitive work; keep the research environment out of your personal login |
| Network egress | Egress that does not expose your home/office IP to targets — so live steps do not tie the work to you personally |
| Credentials | A distinct secrets store for research logins, never shared with personal accounts |

## 3. Contamination control

Your own activity can pollute both the findings and the target's view of you.

| Vector | How it contaminates | Control |
|---|---|---|
| Autocomplete / search history | Repeated queries feed your own suggestions and history, nudging later searches and making sessions non-clean | Work in a clean research profile; clear or isolate history between cases |
| Recommender feedback | Viewing/following trains "suggested" graphs on both sides; your feed fills with the target's orbit and biases you | Read without engaging; never follow/like to observe; keep the research profile cold |
| Personalized search | Signed-in, personalized results differ per user and per history — findings are not reproducible and may be skewed | Query signed-out; record that results were personalized-off; note engine and date |
| Appearing in the target's "people you may know" / "viewed by" | Platform graph inference (contact overlap, profile views, shared network) can surface *you* to the target | Do not view identified; isolate network and contacts; avoid uploading contact lists on research accounts |

Reproducibility note: record which engine, which account state (signed-out), and the date/time
for every search-derived finding, so another analyst can re-run it and get the same result.

## 4. Evidence integrity

A finding exists only with provenance: source `url` + retrieval timestamp + `file_hash` of an
archived copy. Handle the evidence so it holds up.

- **Hash on collect.** Compute the `file_hash` (sha256) at capture time — save the bytes, then
  `python -c "import hashlib,pathlib,sys;p=pathlib.Path(sys.argv[1]);print(hashlib.sha256(p.read_bytes()).hexdigest())" <file>` — and write it to the
  ledger row; store the archive named by its hash (`evidence/<sha256>.<ext>`). The hash proves the
  stored file matches what was logged.
- **A screenshot alone is weak.** It is trivially editable and carries no headers, URL, or
  server-side provenance. Capture the *source* — the original HTML/`document`/file, the response
  headers, the full `url` — and hash that. Keep the screenshot as an aid, not as the evidence.
- **Timestamp in UTC; record the source's timezone.** Log retrieval time as ISO8601 `Z`.
  Separately record the timezone or relative time the source itself displays (a "2h ago", a local
  clock), so the real event time can be reconstructed. Precision goes in `events.jsonl.precision`.
- **Preserve originals unmodified.** The master copy is never edited. Redaction happens on a
  *copy*; keep the original and the redacted version side by side, each with its own hash and
  provenance. Redacted deliverables ship; masters stay in the case.
- **Chain of custody is an append-only ledger.** `ledger.jsonl` is append-only — never rewrite it.
  Every collect / pivot / archive / finding / refusal is one row. The append-only property plus
  per-file hashes is what lets parallel subagents work safely and what makes the evidence
  defensible later.

## 5. Investigator bias and safety

The analyst is part of the instrument. Guard against skew and against harm to yourself.

- **Cognitive bias.** Confirmation bias and anchoring corrupt findings as surely as bad sources.
  Run competing hypotheses and grade evidence against all of them, not just the favoured one — see
  `40-analysis.md` (ACH, bias checklist). Never state an inference as a fact.
- **Vicarious trauma / burnout.** Distressing material (violence, abuse, extremist content) has a
  cumulative cost. Limit exposure, turn media/thumbnails off when not needed, take breaks, do not
  dwell, and seek support. Sustained exposure degrades judgement as well as wellbeing.
- **Never download or store illegal material.** Encountering child sexual abuse material or
  similar means you stop — do not save, hash-collect, or "preserve" it yourself. Possession is a
  crime and is out of bounds (`00-legal-ethics.md` §3.8).
- **When to hand off, not continue.** Stop investigating and route to the proper channel when you
  find: CSAM (a child-protection body / law enforcement), a credible threat to life or imminent
  harm (law enforcement), an ongoing crime, or a missing/endangered person (mandated agency; also
  a hard stop for private-party requesters). Preserve minimal provenance, report it, and do not
  build a dossier. A platform's trust-and-safety channel is the route for on-platform abuse that
  is not a police matter.
