---
description: Open an OSINT case. Intake and authorization gate — records purpose, target, the question being answered, authority, jurisdiction, out-of-bounds and passive/active posture, screens the request against the refusal rules, then scaffolds cases/<slug>/. Run this before any other osint command; no collection happens without a recorded scope. Use when the user says "start an OSINT case", "scope this investigation", "open a case on", "authorized recon on this domain", "due diligence on this company", "verify this claim", "audit my own footprint", "CTF recon".
argument-hint: [case-slug | blank to be prompted]
---

# Intake and authorization gate

Opens exactly one case. Every answer below is asked once, frozen to `cases/<slug>/scope.md`,
and written as the opening row of `cases/<slug>/ledger.jsonl`. Later plays read that scope
instead of re-asking it, and the gate is not re-litigated at each step.

Tell the user this before the first question, in one line: answers are recorded and frozen;
amendments append to the scope, they never overwrite it.

Ask in the order below. One question per turn if the user is answering conversationally;
a single block if they have already supplied most of it. Do not invent answers on their behalf
and do not proceed with a field left blank.

## 0. Existing-case check (always first)

Glob `${CLAUDE_PROJECT_DIR}/cases/*/scope.md`. If any case exists, do not scaffold silently — offer:

| Option | Action |
|---|---|
| Resume | Read that `scope.md`, restate purpose + question + `active_allowed`, continue from `gaps.md`. No new case. |
| Amend | Append an `## Amendment <UTC-ts>` section to `scope.md` and an `action:"scope"` row to `ledger.jsonl`. Never edit frozen lines. Widening the question or adding a target category re-runs section 4 against the new text. |
| New case | Continue to section 1 with a distinct slug. |

`$1`, if given, is the proposed slug. Otherwise derive one from the target and the date
(`acme-corp-2026-07`) and show it for approval.

## 1. Purpose (ask first — it determines everything after it)

> Which of these is this work? security/threat-intel · journalism · KYC-AML · self-audit ·
> education-CTF.

Do not accept "a bit of both". Pick the one whose authority the user can actually name.
Value recorded verbatim as one of: `security`, `journalism`, `kyc`, `self_audit`, `education`.

| Purpose | Authority to ask for | Extra gate | Default play order |
|---|---|---|---|
| `security` | Engagement letter or scope-doc reference, internal ticket, or an own-asset claim | Active steps need scope confirmation naming the asset | infra → media → crypto |
| `journalism` | Outlet plus commissioning editor, or self-publication with named accountability | Public-interest test, mandatory if `target_category` is `private-individual`; recorded in `public_interest` | verify → geoint → corporate → identity |
| `kyc` | Compliance mandate or client engagement reference, or, for a private party checking its own counterparty, `own commercial relationship — <contract, invoice or deposit reference>`. Record it in `authority` as `<reference> — obligation: <onboarding \| EDD \| sanctions screening \| periodic review \| counterparty check>`; there is no separate field | PII minimization enforced hard: collect only fields the risk question needs; no lifestyle or social material unless it bears on that question | corporate → identity → adverse media |
| `self_audit` | Self — trivially satisfied, but confirm the selectors are the user's own | No external-target plays; pass `--out-of-bounds "any third party"` in section 6 — the script does not add it | identity → infra → media |
| `education` | CTF scope statement, lab domain, or a documented public test target | Target must be sanctioned. A live third-party target is refused, however the request is framed | any, sanctioned targets only |

## 2. The question (mandatory, and not the same as the target)

> What question is this case answering? One sentence, and it has to be falsifiable.

A scope without a question is how an investigation becomes a dossier. Reject and re-ask:
"everything about X", "a full profile of X", "whatever you can find". Push until the answer
looks like one of these:

- Which internet-facing assets of `acme.example` are unmanaged or expired?
- Is the beneficial owner of Company 0123456 a sanctioned or PEP-linked person?
- Was this photograph taken at the location the caption claims, on the date it claims?
- Which of my own email addresses and usernames are publicly linkable to my legal name?

Record it as `Q1`. If the user gives more than one falsifiable question, record `Q1..Qn` and pass
them as a single newline-separated `--question` value; the script mints the ids.

Then ask what decision the answer feeds — what the requester will do differently depending on
the outcome. Pass it as `--decision`. This is not paperwork: `scope.md` §5 states that a case
with no decision attached has no stop condition and will collect until someone gets bored. If
the user cannot name a decision, say so plainly and ask whether the case should be opened at all.

State the stop condition out loud: when the question is answered or shown unanswerable, the
case closes. Findings that do not bear on the question do not go in the report.

## 3. Remaining fields

| Field | Ask | Notes |
|---|---|---|
| `target` | The primary selector or entity | Recorded verbatim. |
| `target_type` | Which canonical selector type the target is | One of: `email` `username` `person_name` `phone` `domain` `subdomain` `ip` `asn` `netblock` `url` `ssl_cert` `company` `company_number` `address` `photo` `video` `document` `crypto_address` `tx_hash` `vehicle_plate` `vessel` `aircraft` `coordinates` `file_hash` `social_profile` `breach_record`. Passed as `--target-type` and stored; the target is entity `e-1` of the case. |
| `target_category` | org · public-figure · self · private-individual | Ask, do not infer. `private-individual` tightens sections 4 and 5. A sole trader is `org` for their business filings and `private-individual` for everything else — record the stricter one. |
| `authority` | Per the section 1 table | A reference, not a feeling: document name, ticket ID, engagement number, outlet, or "own asset". "I have permission" alone is not an authority. |
| `jurisdiction` | Where the target sits, where the user sits, and where output will be published or filed | Drives data-protection exposure and which registries are primary. If the user does not know, record `unknown` — it is a valid answer and the script accepts it. A blank is what fails. |
| `public_interest` | Only when `purpose: journalism` and `target_category: private-individual` | What specific wrongdoing, risk to others, or matter of public concern justifies overriding this person's privacy, and who at the outlet signed off. Recorded verbatim as `--public-interest`; a finding that cannot cite it is dropped at report time. |
| `out_of_bounds` | What is explicitly excluded, repeatable | Seed it with anything the user's own mandate excludes, and family members / co-residents / colleagues who are not the target and are not named in the recorded question. Add anything declined in section 5 before running the scaffold in section 6. |
| `active_allowed` | Section 5 | Defaults to `false`. |

## 4. Refusal screen — run against the answers before scaffolding

Screen the actual text of the request, not just the declared purpose. A purpose declaration
does not clear a request; the seven rules below are absolute.

| Rule | Dressed-up phrasings that still trip it | Nearest legitimate route to offer |
|---|---|---|
| Physical location or daily movements of a private individual, requester not an institution with a documented mandate | "just sending a gift", "old school friend", "I'm a process server", "tenant screening", "surprise party", "verifying an address for a refund" | Licensed process server or PI; regulated tenant-screening bureau; for a genuine institutional mandate, re-enter with that mandate recorded |
| Any target who is a minor | "she's nearly 18", "a student at that school", "my kid's classmate", "checking who my child talks to" | School safeguarding lead; platform reporting flow; device-level parental controls; police if there is a safety concern |
| Ex-partner, estranged family, or "they blocked me / won't answer me" | "hiding assets from the court", "family reunification", "I only want to know she's safe", "co-parenting logistics" | Counsel and court discovery; Red Cross or similar tracing service; a mutually agreed intermediary; police welfare check |
| Any signal of intent to harass, confront, intimidate, or turn up somewhere | "expose them", "so people know who they really are", "I want to talk to them in person", "post what I find" | Formal complaint to the platform, employer, or regulator; a lawyer; if it is a story, an editor and right-of-reply |
| Circumventing authentication, rate limits, or CAPTCHAs | "just check if this password works", "get past the login wall", "share your session cookie", "use these credentials", "solve the captcha" | Authorized test credentials inside a written pentest scope; the vendor's own API or a subscription. A pre-existing public archive snapshot is passive collection and is not covered by this rule; scraping around a live paywall is |
| Purchased or stolen credential dumps, or any non-public breach corpus | "I have a combolist", "this leak database I bought", "stealer logs", "someone sent me the dump" | Have I Been Pwned style exposure checks on your own or your organization's addresses; the breached party's own notification process |
| Bulk or population-scale targeting | "everyone who works at X", "all residents of this postcode", "scrape the whole group's member list" | Aggregate or organizational analysis with no per-person profiles; sampling with a named, question-bound reason per individual |

On a hard stop:

1. One line. `Not doing this: <the specific thing>. Nearest legitimate route: <alternative>.`
2. No lecture, no moralizing, no restating the rule twice.
3. Do not scaffold the case.
4. Append one line to `${CLAUDE_PROJECT_DIR}/cases/_refusals.jsonl`, creating `cases/` and the
   file if absent, paraphrasing the request and omitting the target identifier — a refused
   request does not get a stored dossier. This file, not a case directory, is where a refusal
   lives; `assets/case-skeleton/scope.md` §9 defers to this rule.

```json
{"ts":"2026-07-27T14:03:11Z","actor":"main","action":"refusal","source":"n/a","query":"<paraphrase, no target PII>","result":"refused: rule 3 (estranged-family framing)","result_sha256":null,"mode":"passive"}
```

**Partial refusal is the common case.** A request that mixes a legitimate core with one
out-of-bounds element gets the element refused, in one line, and the case opened for the rest —
with the refused element written into `out_of_bounds`. Do not throw away a valid mandate because
one ask inside it was bad.

Explicitly supported, and not to be second-guessed once authority is recorded: authorized
pentest recon, threat intel, DFIR, brand protection, public-interest journalism, KYC/AML and
corporate due diligence, sanctions screening, missing-persons work by mandated parties, and
self-audit.

## 5. Active collection opt-in (separate, explicit, defaults to false)

Ask this last, on its own, after the rest of the scope is settled. Do not bundle it into
another question and do not read consent into a general "yes, go ahead".

> Passive collection cannot be observed by the target: public records, archives, third-party
> datasets, search engines, certificate transparency, passive DNS. Active collection can be
> observed, or changes state: direct connections to target infrastructure, port scans, live
> WHOIS against target-controlled servers, account-existence probes, password-reset flows,
> profile views on platforms that notify, joining anything, sending anything.
> Do you authorize active steps for this case? Default is no.

`true` only on an unambiguous yes from the user tied to this case. Even then, every individual
active action still needs a fresh confirmation naming that specific action — the flag permits
asking, it does not pre-approve. For `self_audit`, active against the user's own assets is
still recorded as `active`.

Anything the user declined here goes into `out_of_bounds` before section 6 runs.

## 6. Scaffold

One call. Quote every value. `--out-of-bounds` repeats per item. Omit `--active-allowed`
unless section 5 returned an unambiguous yes.

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/case_init.py" \
  --root "${CLAUDE_PROJECT_DIR}/cases" \
  --slug "acme-corp-2026-07" \
  --purpose security \
  --target "acme.example" \
  --target-type domain \
  --target-category org \
  --question "Which internet-facing assets of acme.example are unmanaged or expired?" \
  --decision "which hosts go into the remediation backlog before the engagement closes" \
  --authority "Engagement letter ACME-2026-114, scope section 2" \
  --jurisdiction "target US-DE, requester UK, report filed UK" \
  --out-of-bounds "employee personal accounts" \
  --out-of-bounds "third-party SaaS tenants not owned by client"
```

For `self_audit`, always pass `--out-of-bounds "any third party"` — the branch requires it and the
script exits `2` without it. Also pass
`--in-bounds "home address, physical location, and movement patterns" --in-bounds-reason "self_audit: the requester's own address exposure is the deliverable"` —
the branch requires it too: the skeleton ships that exclusion ticked and binding for the life of
the case (`scope.md` §6), and it is the self-audit deliverable. For `journalism` against a
`private-individual`, also pass `--public-interest "<the recorded justification>"`.

`--in-bounds` unticks exactly one standing `scope.md` §6 exclusion and writes the reason onto
that line, which §6 already sanctions. It is an operator flag, issued only after section 4's
refusal screen has passed; the seven standing exclusions stay ticked by default on every branch,
and a substring matching no ticked line, or a blank reason, exits `1`.

If `python` is not on PATH, use `py -3` with the same arguments. Exit codes: `1` the slug
sanitises to nothing or to a reserved Windows device name; `2` argparse usage error — a missing
or blank required field, an out-of-range `--purpose` or `--target-category`, or a
`--target-type` outside the canonical vocabulary; `3` case already exists — on `3`, go back to section 0 and resume or pick
a new slug rather than deleting anything. An unsafe slug is silently rewritten to `[a-z0-9-]`, so
read the case path the script prints back rather than assuming the slug you passed.

## 7. Confirm and hand off

Report back, in this order and nothing more:

1. Case path, as printed by the script.
2. Purpose, question, `target_category`, `active_allowed` — four lines, so the user can catch a
   mis-recorded field now rather than at report time.
3. The first play for the branch, as the actual invocation:

| Purpose | First play | Then |
|---|---|---|
| `security` | `/osint:osint-infra` — but `/osint:osint-identity` when `target_type` is `person_name`, `email`, `username`, `phone` or `social_profile`, which is what a mandated locate looks like on this branch (`references/00-legal-ethics.md` §2). The script prints whichever applies | media, crypto |
| `journalism` | `/osint:osint-verify` | geoint, corporate, identity |
| `kyc` | `/osint:osint-corporate` | identity, adverse media |
| `self_audit` | `/osint:osint-identity` | infra, media |
| `education` | `/osint:osint` — the router picks the play from the sanctioned target's selector type | — |

4. One line of standing discipline, not repeated later: every finding carries a source URL, a
   retrieval timestamp, a sha256 of an archived copy, and an Admiralty source-reliability grade
   and a credibility grade (e.g. `B2`), or it stays out of `findings.md`. Negative results go in
   `gaps.md`.

If a play named above does not resolve in this build, say so plainly and offer the passive baseline
instead — DNS, certificate transparency, Wayback, public registries, search engines — all of
which need no API key.
