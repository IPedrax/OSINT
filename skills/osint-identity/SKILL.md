---
name: osint-identity
description: >
  Identity collection play: usernames, email addresses, phone numbers, personal names, social
  profiles, breach exposure, and self-audit of an own footprint. Enumerates handles across
  platforms, infers corporate email patterns, validates phone numbers, reads breach-exposure
  metadata, pivots avatars, and holds identity confusion open with candidate groups and tiered
  linking datapoints. Passive by default; anything the target can observe is marked active.
when_to_use: >
  Invoked by the osint router for selector types email, username, person_name, phone,
  social_profile. Manual use: "find this person's accounts", "username across platforms", "what
  else uses this handle", "who owns this email address", email-to-name, corporate email format
  or address pattern for a domain, "is this phone number real", carrier or line-type lookup,
  reverse phone, "has this address been in a breach", exposure check, "am I exposed", self-doxx
  audit, footprint audit, opt-out work, KYC identity checks on a named individual, attributing a
  threat-actor handle, verifying a source's claimed identity before publication. Not for: domain,
  host or IP work (osint-infra); company registries, officers, UBO, sanctions or PEP screening
  (osint-corporate); EXIF, reverse image or synthetic-media checks (osint-media).
disable-model-invocation: true
argument-hint: "[email | username | phone | person_name | social_profile]"
---

# osint-identity

Turn an identity selector into graded, sourced findings without inventing a person.

## 0. Gate check

The router ran the case gate. This play re-checks two things, because it is the one a stalker wants.

1. **`target_category: private-individual` plus a requester who is not an institution with a documented mandate** (`authority`
   in `scope.md`): any step whose product is physical location, current or historical address, daily movements, routine, or a
   timezone-derived activity schedule is **refused outright** — not deferred, not redacted. That closes address lookups, voter
   and electoral registers, people-search aggregators, Find a Grave and Legacy.com relative graphs, and post-timestamp routine
   analysis. Wording: `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` §3.1 and §7. Log it, then stop.
2. Every other step on a private individual runs only where you can state, in one clause, which recorded `Q<n>` it answers.
   That clause goes in the ledger `query`. No clause, no step.

`purpose: self_audit` is the relaxed branch and the friendliest case this plugin has: the subject is the requester, every step
is authorized by definition, address and aggregator work is in scope because removing it is the deliverable, and the output is
a to-do list, not a dossier. Run steps 2-7 freely, skip the entropy hand-wringing on the user's own handles, finish with the
opt-out pass in step 8, and do not gate-nag someone auditing themselves. Public-figure, organizational and sanctioned CTF/lab
targets get the standard play.

## Preconditions

- A case exists: `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` and `ledger.jsonl`. If not, run `/osint:osint-scope` and stop —
  never collect first and scope later.
- `active_allowed` is known. If `false`, ACTIVE steps do not run; they go in `gaps.md` as unavailable-under-scope, which is
  not the same as a negative result.
- Source lookup is `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv`. Grep a slice (`accepts` contains the selector, `mode=passive`,
  `auth=none`, then widen to `free_key`); never load it whole. A `verified=no` row is a homepage to open by hand, not an API.

## The play

Each step: one `ledger.jsonl` row per action with the honest `mode`, `query` prefixed `Q<n>: `, archive what you read, grade
before it reaches `findings.md`. **A finding without a grade is not a finding.**

### 1. Normalize, then entropy-test — in: any · out: same type · passive

Split `email` into local-part (`username`) and domain (`domain`; hand the domain to `/osint:osint-infra` if the question
reaches infrastructure). Normalize `phone` to E.164 with **libphonenumber**, offline. Decompose `social_profile` into
`username`, the platform's immutable numeric id or DID, display `person_name`, and avatar `photo` — the id is the only Tier-1
part. Then measure entropy before spending anything: query the quoted handle or name in **Google Search** / **Brave Search**
and count distinct unrelated humans. A handle returning thousands of unrelated accounts carries zero linking weight; a name
shared by hundreds in the jurisdiction is Tier 3 and merges nothing. Record the count as a finding graded `C3` — the engine is
a `C` source and the count is uncorroborated, and it is a property of that index on that date, not a fact about the world.
Record it anyway: it decides how every later match is graded.

### 2. Username enumeration — in: `username` · out: `social_profile` `url`

Passive first. Read platforms that serve logged-out: **Bluesky** (DID and handle history, so renames stay traceable; a
custom-domain handle hard-links into a `domain`), **Reddit** (bot interstitial, browse manually), **Keybase** (signed proofs).
Then **Google Search**, **Yandex**, **Brave Search** on the quoted handle, and **Wayback Machine (retrieval)** /
**archive.today (retrieval)** for deleted profiles. A page you opened yourself grades `B3`, `B2` once a second independent
record agrees. ACTIVE, needing `active_allowed` and a fresh confirmation naming the tool: **WhatsMyName** (probes leave from
your own browser and IP), **Sherlock**, **Maigret** (parses hit pages for names, ids and emails, so it widens scope fast — cap
it against the question). **False positives are the whole story here.** These tools infer existence from HTTP status and body
strings: a site returning 200 for every path hits on every handle, a site blocking datacentre IPs misses every handle. An
unopened enumerator hit is **not a finding** — it is a ledger `collect` row, nothing more. Open each hit, compare avatar, bio,
creation date and post history against what you hold, then write it up.

### 3. Breach exposure, Gravatar, avatar — in: `email` · out: `breach_record` `photo` `url` · passive

**Have I Been Pwned** is the reference source: which named breaches an address appeared in, with date, record count and
exposed data classes (`B2` for "appears in breach X dated Y"). **Mozilla Monitor** has historically licensed HIBP data, so a
hit there restates one source and is not independent corroboration. **EmailRep.io** adds reputation and disposable-provider
flags on opaque sourcing (`C3` ceiling) but is ACTIVE, not passive: the provenance of its deliverability fields is
undocumented and may involve contacting the target's mail server, and uncertain means active. Exposure metadata only:
**never retrieve, buy, or reconstruct credential-dump
contents**, refused even inside an authorized engagement. Domain-wide HIBP search needs proof of control of the domain, so it
is a self-audit capability, not a way to enumerate someone else's staff. A null is a `gaps.md` row reading "not present in
HIBP as of `<ts>`", never "not breached". Then **Gravatar**: hash the lowercased trimmed address and fetch the avatar; nothing
reaches the target. A hit establishes that the address was registered (`B2`) and often exposes a public profile with a display
name, additional verified emails and linked accounts — Tier 2, the cheapest win on this play; grade those linked accounts `B3`
until each is opened, and absence tells you nothing. Any avatar from a confirmed profile becomes a `photo` for
`/osint:osint-media` (reverse image, synthetic-media check).

### 4. Account-existence and Google-side data — in: `email` · out: `social_profile` `person_name` · ACTIVE

Gate hard. **Holehe** and **Epieos** registration checks drive password-reset and registration endpoints; several modules send
verification or reset mail straight to the target's inbox, the fastest way to tip a target off on this play. Probing an
authentication flow for an account you do not own is arguably unauthorized access in several jurisdictions (US CFAA, UK
Computer Misuse Act) and must be named in scope in writing. **GHunt** returns what Google itself exposes for a Gmail address
or gaia id — display name, profile photo, public Maps reviews, calendar where left public — at `B2`, because it is Google's
own data; it needs your own authenticated session cookies, never a client's or an employer's account. **Epieos** is the hosted
equivalent: its Google-side output is the valuable half, its registration checks are Holehe-grade (`C3`) and stay ACTIVE
regardless of any no-logging claim. Under `self_audit` this is you checking your own inbox, no friction.

### 5. Corporate email pattern — in: `domain` `company` `person_name` · out: `email` · passive

**Hunter.io** Domain Search returns the observed format (`first.last@`, `flast@`) with a confidence score and a per-address
source URL — record that URL, it is what makes the result citable. **email-format.com** is a free first check; **Apollo.io**
and **RocketReach** go deeper on a named individual at a named employer. **GitHub Code Search**, **grep.app**, **GH Archive**
and **Software Heritage** surface commit-author addresses, which are self-published and far better sourced than any broker. An
address *derived* from a pattern is a hypothesis, not an entity: write it as inferred, name the pattern and its falsifier,
grade `C3`, never present it as the person's address. Brokers grade `D` — aggregation is not corroboration. **Deliverability
probing is a different act.** **Hunter.io Email Verifier** and **NeverBounce** open an SMTP conversation with the target's own
mail server; the connection lands in that server's logs and can alert a security team. ACTIVE, needs `active_allowed` plus
fresh confirmation, and only when deliverability is the recorded question. Catch-all domains return inconclusive.

### 6. Phone — in: `phone` · out: `phone` `company` `person_name`

Start offline with **libphonenumber**: numbering-plan validity, region, timezone, line type, E.164 form (`B2`). Note the
ceiling — it says what a number *can* be, never whether it is assigned, and ported numbers keep their original prefix, so
prefix-derived carrier is the *original* carrier (`C3` for the current one). **Twilio Lookup** resolves against carrier
databases and handles porting correctly (`B2`); its CNAM field gives a registered caller name on many US lines (`B3` —
registered, not verified). **PhoneInfoga** parses locally and pivots into search engines; confirm which scanners ran before
recording a negative. **Truecaller** is ACTIVE and notifies: its profile-view feature can surface you to the person you
searched, and installing the app uploads your own address book. Names in it are whatever other users saved the number as —
`D3`, never an identification alone. **Never add a number to a messenger contact list to test presence**; that is an
account-existence probe against the target's device. Aggregator reverse lookups (**ThatsThem**, **TruePeopleSearch**,
**Whitepages**, **Spokeo**, **192.com**, **Pipl**) are `D` leads, closed by §0 rule 1 once they yield an address.

### 7. person_name — in: `person_name` · out: `person_name` `company` `url` `address`

`person_name` is a Tier-3 link and merges nothing. Disambiguate before enriching: **ORCID** (institution-asserted entries
`B2`, self-asserted employment `C3`), **OpenAlex**, **PubMed** (`A2` on the biomedical record), **Google Scholar** for
affiliation and the co-author graph. Officers, filings and sanctions screening belong to `/osint:osint-corporate` — hand over
rather than half-do it here. Public records, all closed by §0 rule 1: **North Carolina Voter Registration Data** (`A2`, and
jurisdiction-specific — never assume another US state publishes on the same terms) and the **UK Register of Electors** (the
open/full register distinction is the point; full-register use outside a prescribed purpose is an offence). **FamilySearch**,
**Ancestry**, **Find a Grave** and **Legacy.com** are for deceased or historical subjects, and the living relatives they name
are out of scope unless the recorded question reaches them.

### 8. Resolve, grade, write up — in: everything held · out: graded findings

Identity confusion is resolved here or reported unresolved; never resolved by assumption. Two records that might be one person
get **two** `entities.jsonl` rows with distinct `id`s and a shared `candidate_group` (`cg-<n>`). Nothing is edited: a merge is
a new appended row naming the linking datapoint — selector type, literal value, source, retrieval timestamp, grade. "Multiple
weak signals" is not a name. Tier-3 matches do not accumulate; five of them remain a `candidate_group`. Any Tier-1
contradiction (two distinct platform ids, mutually exclusive locations at one timestamp) splits the group immediately. Tier 1
here: a platform-issued immutable id or DID on two profiles, a validating Keybase proof, a government identifier in a primary
record. Tier 2: an entropy-tested rare `username` reused across platforms, a commit `email` tying `username` to `person_name`,
a Gravatar profile linking an address to a named account. Tier 3: name match, avatar similarity, self-reported employer or
city, any aggregator assertion. Check **date overlap** too — handles transfer, numbers recycle, families share addresses; two
records must be contemporaneous to correlate. Then write `gaps.md` (every null, with where and when) and grade every finding
`A1`-`F6` in ICD-203 wording only. Under `self_audit`, close with the deliverable that matters — the opt-out list:
**Whitepages**, **TruePeopleSearch**, **Spokeo** and **ThatsThem** publish removal routes, **Mozilla Monitor** sells broker
removal, and **Gravatar** plus stale public profiles are the user's own to change.

## Reference index

| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | Any private-individual target; before applying §0 rule 1; PII-minimization or jurisdiction question; writing refusal text (§3, §7) |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next pivot; the obvious one came back empty; checking whether a pivot notifies (`PIVOTS THAT NOTIFY`, `WEAK PIVOTS`, `DEAD ENDS BY DESIGN`) |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Step 8, always — identity-confusion protocol, linking tiers, ACH when two people fit the evidence, pre-report checklist |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Any grade you are unsure of; choosing an ICD-203 word |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before any ACTIVE step (2, 4, 5 verifier, 6 Truecaller); before creating or using a research account |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md`; deciding redaction; the self-audit opt-out deliverable |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting a source. Grep a filtered slice, never load whole |
| `${CLAUDE_PLUGIN_ROOT}/assets/entity-schema.json` | Writing `entities.jsonl` and unsure of a field |

## Stop conditions

- The recorded `Q<n>` is answered at a stated confidence and the answer names its sources.
- Remaining pivots are logged in `gaps.md` and the residual uncertainty is written down.
- New collection returns only entities already held — saturation.
- The next step needs an ACTIVE source without `active_allowed`, or one in `out_of_bounds[]`.
- Every `candidate_group` is resolved with a named Tier-1 (or two Tier-2) datapoint, or reported unresolved with both
  candidates shown. Unresolved is a result, not a failure.
- You are collecting because a handle is interesting rather than because a `Q<n>` needs it.

## Refusals specific to this play

One line plus the nearest legitimate route. No lecture, no second paragraph. Log it, then stop.

- Location, address, movements, routine or activity schedule of a private individual for a non-institutional requester (§0
  rule 1). Nearest route: the platform's abuse or legal process, or law enforcement.
- Retrieving, buying or reconstructing credential-dump contents, combolists, or any non-public breach corpus. HIBP exposure
  metadata is the supported alternative; a password you already lawfully hold can be checked against **Pwned Passwords**,
  which is k-anonymous.
- Password-reset or account-recovery probing outside a scope that names it in writing, and any attempt to complete such a
  flow.
- Profiling a named individual beyond the recorded question, however cheap the extra pivot is. PII minimization is a
  collection rule, not a reporting rule.
- Enumerating a third party's staff by email; HIBP domain search and directory harvesting are self-audit and
  authorized-engagement capabilities only.
- Defeating a CAPTCHA, bot interstitial or rate limit on any platform in this play.
