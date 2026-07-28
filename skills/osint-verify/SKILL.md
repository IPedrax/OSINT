---
name: osint-verify
description: >
  Claim verification and disinformation analysis on a url, document, photo, video, social profile
  or named source. Reduces a vague assertion to falsifiable atomic claims, traces each upstream to
  its earliest instance rather than its loudest repost, establishes provenance and chronology,
  counts independent sources rather than citations, tests amplification for coordinated inauthentic
  behaviour, checks quotes and documents against the primary record, and searches for disconfirming
  evidence before grading. Delivers a graded verdict in ICD-203 estimative language, never a binary
  true or false; unverified is a legitimate outcome and the most common one.
when_to_use: >
  Invoked by the osint router on the journalism branch and for source triage on any branch.
  Manual use: "is this true", "verify this claim", "fact check this", "debunk this", "is this photo
  real", "is this video authentic", "who posted this first", "find the original", "is this a
  repost", "where did this claim come from", "how many sources actually have this", "are these
  outlets independent", "circular reporting", "wire story", "is this account a bot", "coordinated
  inauthentic behaviour", "is this quote real", "did they actually say this", "is this document
  genuine", pre-publication source check, influence-operation triage. Not for: EXIF, reverse image
  or synthetic-media scoring (osint-media); geolocating a scene (osint-geoint); registries and
  filings (osint-corporate); accounts and handles (osint-identity).
disable-model-invocation: true
argument-hint: "[url | document | photo | video | social_profile | person_name]"
---

# osint-verify

Turn a circulating claim into a graded verdict, or into an honest `unverified`.

## Preconditions

- A case exists: `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` and `ledger.jsonl`. If not, run `/osint:osint-scope` and
  stop. Never check first and scope afterwards — the claim as first stated is evidence, and the case is where it is frozen.
- Read `scope.md` for `question` (`Q1..Qn`), `active_allowed`, `out_of_bounds[]`, and — on the journalism branch — the
  `public_interest` value. The gate ran at intake; do not re-run it.
- The seed enters `entities.jsonl` under its canonical type: `url` `document` `photo` `video` `social_profile`
  `person_name`. This play produces **graded findings**, not new selector types; selectors it extracts go to another
  department under the same `Q<n>`.
- Everything is `passive` except step 2's archive submission and any direct fetch of a page the subject controls — that
  fetch is `active` even though it looks like reading: your IP, referrer and timing land in their log.
- Sources come from `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv`; grep a slice (`accepts` contains the selector,
  `mode=passive`, `auth=none` first), or run `${CLAUDE_PLUGIN_ROOT}/scripts/selectors.py <value> --passive-only`. A
  `verified=no` row is a homepage to open by hand; a `fetchable=no` row needs a browser, not a burnt HTTP call.

## The play

Every step appends a `ledger.jsonl` row whose `query` begins with the scope question id (`"Q1: ..."`), carries the honest
`mode`, and names the registry source exactly as `sources.csv` spells it. **Steps 1-6 run before any verdict is drafted.**
A model doing this work fails in one direction — it finds a coherent account early and spends the rest of the run
decorating it — so step 6 runs whether or not the answer already feels settled.

### 1. Isolate the falsifiable claim — in: any seed · out: atomic claims `C1..Cn` · passive

Quote the assertion verbatim, then split it into atomic claims, one checkable proposition each. Bind every vague term
(`many`, `linked to`, `sources say`, `reportedly`). Separate the **artifact** claim ("this photo is unaltered") from the
**context** claim ("this photo shows event E") — a genuine artifact with a false context is the most common case in this
play by a wide margin. For each, write the sentence "this would be false if...", naming an observation somebody could
make; a claim for which that sentence cannot be written is not a claim and exits as `unverifiable`. Procedure and a
worked decomposition: `${CLAUDE_PLUGIN_ROOT}/references/28-verification.md` §1.
- Ledger `action=finding`, `source=analyst decomposition`, `mode=passive`, `result_sha256=null`. Each `C<n>` goes to
  `gaps.md` as an open question mapped to its `Q<n>`, migrating to `findings.md` only once graded. Nothing is graded here.

### 2. Freeze the artifact before it moves — in: `url` `document` `photo` `video` `social_profile` · out: `file_hash` · passive, submission ACTIVE

Viral posts get deleted, edited silently, and locked. Snapshot now: `${CLAUDE_PLUGIN_ROOT}/scripts/archive.py <url> --case
<dir>` writes the bytes into `evidence/<sha256>` and appends the ledger row. Capture the full-resolution media, not the
page thumbnail, and the surrounding thread — the reply naming the origin disappears with it. Existing captures:
**Wayback Machine (retrieval)**, **archive.today (retrieval)**, **Ghostarchive**.
- Ledger `action=archive`, `mode=passive`, `result_sha256` mandatory. A capture grades `B2` **for what the page showed at
  the capture time** and nothing more; the claim inside it is graded separately, by its own source.
- **Wayback Machine Save Page Now** and **archive.today (submission)** are `active`: they fetch the target and create a
  public dated record of your interest, and an archive.today capture cannot be withdrawn. Needs `active_allowed: true`
  plus a fresh confirmation naming the URL, and on a live case it tells the operator their material is being examined.

### 3. Trace upstream to the earliest instance — in: `photo` `video` `url` `document` · out: `url` `social_profile` · passive

The first copy you were shown is almost never the first that existed. For a `photo`: **TinEye** first, the only major
engine that reliably sorts oldest-first, then **Yandex Images**, **Google Lens**, **Bing Visual Search**, **Baidu Images**
— their indexes barely overlap, so one engine is not a search. For a `video`: **InVID WeVerify Verification Plugin** to
pull keyframes, then run each through the image route; **Ghostarchive** keeps the media rather than an empty shell. For
text: verbatim-phrase search across **Google Search**, **Bing**, **Brave Search** (independent index), **Yandex**,
**SearXNG**, plus **Arquivo.pt** for full-text search of archived pages and **Common Crawl** for every path seen under a
host. Search a distinctive fragment and the misspelling, and crop before reverse-searching. Technique per artifact type:
`28-verification.md` §2.
- Ledger `mode=passive`, one row per engine including the empty ones. Grade the earliest item `C3` — the claim is "the
  earliest instance located by these indexes as of TS", a statement about your search. `B2` where two genuinely different
  crawls return the same earliest item and neither returns anything earlier. **Never credibility 1**: absence of an
  earlier copy is a property of index coverage, which under-covers closed platforms, messaging apps, non-Latin scripts
  and deleted content — write that limit into `gaps.md` beside the finding.

### 4. Provenance and chronology of the artifact — in: `photo` `video` `document` `url` · out: chronology, `person_name` `company` · passive

**ExifTool** locally, disclosing nothing: capture timestamp with offset, camera, editing software, IPTC credit. Grade the
*content* `C3` — it is a claim by whoever last wrote the file, and platforms strip it on upload, so intact EXIF means the
file probably did not come from a public post, which is itself a finding. **Content Credentials** reads a C2PA manifest;
a valid one is `B2` and states what the signer asserts, including generative provenance. C2PA is self-authenticating but
**not independently mirrored, so it does not inherit the certificate-transparency exemption** in
`${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md`; absence of a manifest supports nothing either way. Build the
chronology only from things carrying real timestamps: archive captures, HTTP headers, platform-side upload metadata,
dated mentions. Synthetic-media scoring and file forensics belong to `/osint:osint-media`, place and time-of-day from the
scene to `/osint:osint-geoint` — hand over the selector rather than half-doing it here.

### 5. Count sources, not citations — in: the supporting `url` set · out: an origin chronology · passive

**N outlets republishing one wire story is ONE source.** This is the single most common corroboration error in
verification work, and volume is its disguise: ten thousand reposts of one photo is one photo. Sort every supporting item
by earliest publication timestamp, read each item's own attribution (agency credit, hyperlink, embedded post, "sources
told"), and collapse relays into their origin. Diff the wording: shared distinctive phrasing, a shared typo or a shared
transposed digit is copying, not agreement. Check citogenesis through the **Wikipedia** revision history — an unsourced
sentence added there, picked up by an outlet, then cited back as corroboration — comparing the revision timestamp against
the outlet's publication date. **GDELT Project** shows how far and in which languages the claim travelled and where the
earliest datelines sit; it is `D`, so build the chronology with it and cite the original articles. Then apply the four
independence tests in `41-confidence.md` plus the byline, access and naming tests in `28-verification.md` §4.
- Ledger `mode=passive`. Report the **surviving** count: "one source, republished nine times", never "widely reported". A
  finding carried by the origin inherits the origin's grade, not the aggregate of its copies. If the origin cannot be
  established, credibility caps at 2 and the finding names the earliest traceable publication.

### 6. Look for what would disconfirm it — before drafting any verdict · passive

Take each atomic claim's falsifier from step 1 and collect it. Check the claim against the **primary record**, not
against commentary: the full transcript or unedited recording for a quote, the issuing register for a document —
**UK Companies House**, **SEC EDGAR**, **The Gazette**, **Find Case Law**, or the right register via
`/osint:osint-corporate`; **CourtListener** is a mirror, so cite the issuing court, not the mirror. One field
contradicting a primary register outweighs ten fields matching it. A primary record
that directly attests the claim is `A3` alone, `A2` where other collected material agrees, and `A1` only with
corroboration from a separately generated process. **Google Fact Check Explorer** shows whether the claim was already
adjudicated: read the fact-checker's evidence and cite the record it rests on — adopting their verdict is the same
circular-reporting error as counting a wire story's republishers. The mundane explanation — coincidence, an old photo
reused innocently, an ordinary commercial relationship — enters the ACH matrix as a hypothesis; for any contested claim
run the ACH procedure in `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`, scoring rows in reverse discovery order.
- Every empty check is a `gaps.md` row with its absence type. Absence is evidence about the *claim* only where the source
  has complete coverage and recording is mandatory; otherwise it is evidence about the source.

### 7. Amplification and coordinated inauthentic behaviour — in: `social_profile` `url` · out: `inferred` findings only · passive

Optional, and only where a recorded `Q<n>` asks who pushed the claim. **Every signal here is weak alone and most are
worthless alone**: low follower count, a new account, a default avatar, high volume and an odd posting schedule describe
most real accounts on any platform. What can carry weight is the *network and the timing* together — identical text
carrying an identical rare typo, posting synchronised within seconds across accounts with no follow relationship and
repeated across distinct events, creation clustered in a narrow window, a near-total follow-graph overlap (**Bluesky**
exposes the graph unauthenticated), an avatar **Yandex Images** or **TinEye** shows is stock or stolen. What each signal
fails to support alone: `28-verification.md` §7.
- Grade `C3` at best, written as `inferred` with an ICD-203 term, after ACH against organic virality, a shared community
  and scheduled-posting tools. **Never name an individual account as a bot and never call a named person inauthentic** —
  the finding describes a pattern across a set, members referenced by entity id, with the observation window and the
  fraction actually examined stated. Coordination is not falsity: a coordinated campaign can push a true claim, so the
  two findings stay separate.

### 8. Grade and deliver the verdict — out: `findings.md` · passive

One status per atomic claim, never one verdict for the whole post: `verified` · `partly verified` · `unverified` ·
`unverifiable` · `misattributed` · `manipulated` · `fabricated` · `debunked`. Definitions and the conditions each needs:
`28-verification.md` §5. A status is not a grade — every one carries its Admiralty grade, its rung, and an ICD-203 term
wherever an inference is involved. **`unverified` is not `false`**; `debunked` requires a specific sourced disconfirming
observation, not the absence of confirming evidence. `fabricated` and `manipulated` are the two most damaging statuses to
get wrong and neither may rest on a synthetic-media detector score — **Hive AI-Generated Content Detection** and its
equivalents are `D` and direct where to look, deciding nothing. If the outcome is `unverified`, lead with it: what was
checked, what came back empty, what would settle it, why that was not obtained. Pattern: `28-verification.md` §10.

## Reference index

| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/28-verification.md` | Steps 1, 3, 5, 7, 8 — decomposition, upstream tracing, circular reporting, status vocabulary, CIB signals, the worked example, delivering `unverified` |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Before any grade. The four independence tests, the circular-reporting check, the inference ladder, ICD-203 wording |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Step 6, always — ACH for any contested claim; key assumptions check; quality-of-information check; absence types; pre-report checklist |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md`; the journalism branch's `public_interest`, right-of-reply and single-source rules; redaction |
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | The subject turns out to be a private individual or a minor; PII minimization; writing refusal text (§3, §7) |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before step 2 submission or any fetch of subject-controlled infrastructure; §3 when checking whether a "corroborating" hit is your own footprint |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing a pivot from `url` `photo` `video` `social_profile` `document`; `PIVOTS THAT NOTIFY` before anything active |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting a source. Grep a filtered slice, never load whole |

## Stop conditions

- Every atomic claim carries a status, a grade, a rung and its sources. That includes the ones that ended `unverified` —
  a claim without a status is unfinished work, not a silent pass.
- The upstream trace terminates: the earliest instance names no earlier source, or two consecutive engines return only
  items already held.
- The surviving independent source count stops changing as new items are added. More copies is not more evidence.
- The next step needs an `active` action without `active_allowed`, a paid or sealed record, or a source in
  `out_of_bounds[]`. Name the capability in `gaps.md` and stop.
- The remaining uncertainty is about intent, motive or who benefits — not collectable here. State it as an open question.
- You are still collecting because the story is interesting rather than because a `C<n>` is open.

## Refusals specific to this play

One line plus the nearest legitimate route. Log it, then stop.

- **No verdict of "true" or "false".** Statuses and grades only. A binary verdict is refused even when the requester asks
  for one; give the status, the grade, and the specific observation behind it.
- **No calling a named account or person a bot, a troll, or inauthentic.** The supported finding is a pattern across a
  described set, graded `inferred`. Misidentifying a real person is the same class of harm as a wrong identity merge.
- **No unmasking an anonymous source, whistleblower or pseudonymous account** to test their credibility. Assess the
  claim, the artifact and the record instead — deanonymisation endangers the person and is not a verification step.
- **No investigating the requester's opponent under cover of checking a claim.** The scope is the claim. A claim about a
  private individual needs the recorded `public_interest` value; if that field is empty, the check does not run.
- **No retrieving, quoting or storing non-public breach corpora or purchased dumps** to authenticate a leaked document,
  even inside an authorized engagement. Verify against the issuing register, or record it `unverifiable`.
- **No defeating a bot interstitial, paywall, rate limit or CAPTCHA** to reach a source page. Browser, or record the gap.
- **No verdict on a `photo` or `video` before `/osint:osint-media` has run the synthetic-media check.** Analysing a
  generated artifact is wasted effort at best and a fabricated finding at worst.
