*Load when: a claim, caption, quote, document or viral artifact has to be checked; tracing something to its origin; deciding whether several sources are actually one; assessing amplification; or writing a verification verdict. Mandatory before any status word is written.*

# Claim verification

The deliverable is a **status plus a grade plus, where an inference is involved, an ICD-203 term**.
Never a binary true/false. `unverified` is the honest and most common result, and delivering it
well is the skill.

Grading vocabulary is `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` and is not restated here.
Contested claims go through the ACH procedure in `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`,
also not restated: run it, do not paraphrase it.

## 1. Claim decomposition

A claim you cannot falsify cannot be verified either. Decompose before collecting anything.

### The test

A claim is checkable only if you can write one sentence beginning **"This would be false if..."**
naming an observation somebody could make. If that sentence cannot be written, the claim is not a
claim — it is a framing, an opinion, or a prediction, and it exits the play as `unverifiable` with
the reason recorded.

### Procedure

1. **Quote the assertion verbatim.** Archive it first (step 2 of the play). Paraphrasing at intake
   is how the checked claim drifts away from the claim that was made.
2. **Split into atomic claims.** One verifiable proposition each. A viral post routinely carries
   four: what the artifact shows, where, when, and why. They are checked separately and they
   routinely resolve to different statuses.
3. **Bind every vague term.** Who exactly, where exactly, when exactly, what counts as the thing.
   `many`, `linked to`, `sources say`, `reportedly`, `associated with` all bind to nothing.
4. **Separate the artifact claim from the context claim.** "This photo is real" and "this photo
   shows event E" are different claims with different evidence. The overwhelmingly common
   disinformation case is a genuine artifact with a false context.
5. **Name the falsifier for each atomic claim**, and whether the observation that would settle it
   is collectable now, `passive` or `active`, in or out of scope.
6. **Write each atomic claim into `gaps.md`** as an open question, id `C<n>`, mapped to the scope
   `Q<n>`. It migrates to `findings.md` only once graded.

### Worked decomposition

Raw: *"Shocking footage shows the massive explosion at the Port of Valmara last night — the third
attack this month, and the government is covering it up."*

| id | Atomic claim | Falsifier | Settled by |
|---|---|---|---|
| C1 | The video is an unaltered recording, not synthetic or spliced | An earlier copy with different content; a generative-provenance manifest; a splice boundary | Upstream trace + `/osint:osint-media` |
| C2 | The video depicts the Port of Valmara | Any identified feature inconsistent with that port | `/osint:osint-geoint` |
| C3 | The event occurred on the stated night | An earlier publication of the same footage | Upstream trace, archive timestamps |
| C4 | An explosion occurred at that port on that date | Absence from port authority, marine casualty and local media records with mandatory or near-complete coverage | Primary records |
| C5 | It was the third such event this month | Two prior events of the same class, dated | Primary records |
| C6 | It was an attack | A recorded accidental cause | Investigation record, usually not available for weeks |
| C7 | The government is concealing it | — no falsifier can be written as stated | **Not a claim.** `unverifiable`, recorded and dropped |

C1-C3 are artifact claims. C4-C5 are event claims that stand or fall independently of the video —
a fabricated video does not disprove the event, and a genuine video does not establish the cause.
C6 is an attribution claim and goes to ACH, never to a single-source verdict. Conflating these
seven into "is this true?" is the error the decomposition exists to prevent.

## 2. Upstream tracing — find the original, not the loudest copy

The first copy you were shown is almost never the first copy that existed. Everything downstream
depends on getting this right: provenance, chronology, source counting and status all read off the
earliest instance.

### By artifact type

| Artifact | Route to the earliest instance |
|---|---|
| `photo` | **TinEye** first — the only major engine that reliably sorts oldest-first, which is the entire question here. Then **Yandex Images** (strongest on crops, mirrors and faces), **Google Lens** (semantic and OCR of in-frame text), **Bing Visual Search** (region-of-interest crop), **Baidu Images** (the only practical route into Chinese-language sites). Run at least three: their indexes barely overlap |
| `video` | **InVID WeVerify Verification Plugin** to extract keyframes, then push each keyframe through the image route. Also read platform-side upload metadata where the plugin exposes it. **Ghostarchive** preserves the media itself rather than a page shell |
| Text claim | Verbatim-phrase search in quotes across **Google Search**, **Bing**, **Brave Search** (independent index, so a real second opinion), **Yandex** (post-Soviet coverage), **DuckDuckGo**, **SearXNG**. Use each engine's own date-restriction controls; do not trust a claimed publication date in the page body |
| Web page | **Wayback Machine (retrieval)** for capture history, **archive.today (retrieval)** for pages Wayback refuses, **Common Crawl** URL index for every path seen under the host, **Arquivo.pt** for full-text search across archived content when the URL itself is unknown |
| Social post | Archived copies first — deleted posts are the norm. **Wayback Machine (retrieval)**, **archive.today (retrieval)**, **Ghostarchive**. A quote-post or screenshot chain usually names the origin account; the origin account usually deleted |
| `document` | **Arquivo.pt** and **Common Crawl** on a distinctive phrase; **OCCRP Aleph** and **ICIJ Offshore Leaks Database** for leak corpora; the issuing body's own site and its archive captures |

### Technique

- Search a **distinctive fragment**, not the gist. A rare phrase, a filename, a visible sign, a
  serial number, an unusual spelling. Common phrasing returns the amplification, not the origin.
- **Crop before you reverse-search.** Engines match the dominant region; a watermark, a caption bar
  or an added border defeats matching. Search a distinctive sub-region separately.
- **Search the misspelling.** A copy chain preserves the origin's typos; that is what makes them
  useful.
- **Bound the search by date**, then widen. If the "new" image has hits before the claimed date,
  the context claim is dead and the artifact claim may still be alive.
- **Stop climbing when the chain terminates in an account or outlet that names no earlier source.**
  That is the earliest traceable instance. It is not necessarily the origin.

### What "earliest found" supports

The claim is **"the earliest instance located by sources S1..Sn as of TS is U, published at T"** —
a claim about your search, not about the world. Grade it `C3`. It rises to `B2` when two indexes
with genuinely different crawls return the same earliest item and neither returns anything earlier.
It never reaches credibility 1: absence of an earlier copy is a property of index coverage, and
every index under-covers closed platforms, messaging apps, non-Latin scripts and deleted content.
Write the coverage limit next to the finding.

## 3. Circular reporting

**The single most common corroboration error in verification work: N outlets carrying one wire
story is ONE source.** Volume is not corroboration. Ten thousand reposts of one photo is one photo.

### The counting method

Run this before writing any credibility 1 or 2. It is the operational form of the circular-reporting
check in `41-confidence.md`.

1. **List every supporting item with its earliest publication or capture timestamp**, not your
   retrieval order. Sort ascending. The top row is the candidate origin.
2. **Read each item's own attribution.** A wire credit (agency byline, "with reporting by",
   "according to"), a hyperlink, an embedded post, "sources told" — each names an upstream. Follow
   it. An item that names an upstream is not a source; it is a relay.
3. **Diff the wording.** Shared distinctive phrasing, a shared typo, a shared transposed digit, a
   shared unit error, an identically cropped image: copying, not agreement.
4. **Collapse the relays into their origin** and write the surviving count. If nine of ten items
   collapse, the finding says "one source, republished nine times", never "widely reported".
5. **Check citogenesis.** An unsourced sentence added to **Wikipedia**, picked up by an outlet, then
   cited back into the article as corroboration. The revision history timestamps the sentence;
   compare it against the outlet's publication date. The same loop runs through any user-editable
   corpus, aggregator, or LLM-written summary.
6. **Check yourself as the origin.** If anything in this case was published, submitted to a public
   archive, or run against a source that publishes queries, a later "independent" hit may be your
   own footprint returning. `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` §3.
7. **If the origin cannot be established, credibility is capped at 2** and the finding says so:
   "the earliest traceable publication is S at T; later items may derive from it."

### Cascades that look like many sources

| Cascade | What it actually is |
|---|---|
| Wire story + subscribers + aggregators + syndication partners | One newsroom |
| Press release + every article quoting it | One interested party |
| Government statement + the outlets reporting it | One statement. The claim is `reported`, not `observed` |
| One anonymous-source story + follow-ups citing "reports" | One unnamed source, whose existence you cannot check |
| A think-tank report + the coverage of it + the report's own sources | Check the report's footnotes: they often lead back to the outlets covering it |
| Translations of one item | One item. Two translations disagreeing is a translation finding, not a source conflict |
| Cross-platform reposts of one screenshot | One screenshot, and screenshots are trivially forged — find the live or archived post |
| An LLM-generated summary and the article it summarised | One article, plus an unattributable error surface |

**GDELT Project** is the fast way to see how far and in which languages a claim travelled, and
where the earliest datelines sit. It is graded `D` and aggregation is not corroboration: use it to
build the chronology, then read and cite the original articles.

## 4. Independence tests

Apply the four tests in `41-confidence.md` — counterfactual, upstream, origination, chain of
copying. Failing any one collapses two items to one source. Three further tests matter specifically
in verification:

| Test | Question | Failure means |
|---|---|---|
| Byline and agency | Do the items share a reporter, a stringer, a fixer, or an agency credit? | One field observation, several mastheads |
| Access | Did both outlets have their own access to the event, the document, or the person? | An outlet that was not there is reporting somebody who was |
| Naming | Does each item name **its own** on-record source, or do they both say "sources"? | Unnamed sources cannot be deconflicted; assume one until shown otherwise |

Stays independent in verification work specifically:

- Two journalists who each name a different on-record witness.
- A photograph and a separately produced video of the same scene from a different angle, where
  neither was published by the other's publisher.
- An eyewitness account and a physical record — a shipping manifest, a filing, a court exhibit —
  produced by unrelated processes.
- A satellite image and a ground photograph of the same place and date.
- The subject's own denial and a document contradicting them. The denial is a source; grade it as
  an interested party, and always seek it before publication.

## 5. Verification status vocabulary

A status is not a grade and never replaces one. Every status carries the Admiralty grade, the rung,
and an ICD-203 term wherever an inference is involved.

| Status | Applies when | Typical grade |
|---|---|---|
| `verified` | Original located, provenance established, and either two sources surviving all four independence tests, or the primary artifact itself observed and archived where the claim is about what that record says | credibility 1 or 2 |
| `partly verified` | Some atomic claims stand and others do not. Always name which, by `C<n>` | mixed, stated per claim |
| `unverified` | Sufficient corroboration was not found and no disconfirming evidence was found either. The default and most common outcome | credibility 3 |
| `unverifiable` | No available collection step could settle it: the record does not exist, is sealed, needs an unauthorised active step, or the claim has no falsifier as stated | credibility 6 |
| `misattributed` | The artifact is authentic but the stated context — place, date, event, speaker — is wrong. The most common form of visual disinformation by a wide margin | grade the disconfirming source |
| `manipulated` | The artifact was altered: edit, splice, selective cut, speed change, reframing, mistranslation. Name the specific alteration and how it was observed | grade the observation |
| `fabricated` | The artifact was created wholesale, including synthetically. Requires positive evidence, not a detector score | grade the evidence |
| `debunked` | A specific, sourced, graded observation contradicts the claim | credibility 4 or 5 for the claim |

Rules:

1. **`unverified` is not `false`.** It is a statement about the evidence available to this case at
   this time. Saying otherwise converts a collection limit into an accusation.
2. **One authoritative record alone does not make a claim about the world `verified` at
   credibility 1.** It is `A3` alone, `A2` where other collected material agrees; `A1` needs
   corroboration from a separately generated process. Reading a register does not corroborate what
   was filed in it. The one stated single-source exemption in `41-confidence.md` is certificate
   transparency, which is self-authenticating *and* independently mirrored — C2PA manifests,
   registry records and platform metadata are none of those things.
3. **`debunked` requires disconfirming evidence, not absence of confirming evidence.** Absence
   supports `unverified`, and only becomes evidence about the claim when the source has
   complete coverage and registration is mandatory — the authoritative-absence rule in
   `40-analysis.md`.
4. **A status attaches to an atomic claim, never to a post, an account, or a person.** "This account
   spreads disinformation" is not a verification output.
5. **`fabricated` and `manipulated` are the two most damaging statuses to get wrong.** Neither may
   rest on a synthetic-media detector score: **Hive AI-Generated Content Detection** and its
   equivalents are `D`-grade, error-prone in both directions, and direct where to look rather than
   deciding anything.
6. Re-state the status with its grade every time it is repeated. A status word in a summary without
   its grade is the laundering failure in `40-analysis.md`.

## 6. Disinformation patterns — what is diagnostic and what merely feels it

| Pattern | Actually diagnostic | Feels diagnostic, is not |
|---|---|---|
| Recycled imagery from an older event | An earlier dated copy of the same frame in an index | "It looks like an old photo"; low resolution; grainy |
| False caption on a genuine photo | Any in-frame feature contradicting the caption: signage language, plate format, vegetation season, vehicle model, architecture | Emotive caption wording; the poster's politics |
| Staged or re-enacted scene | Camera positioning impossible for a bystander; multiple takes of the same moment; an unpublished wider frame showing the crew | "It looks staged"; people behaving calmly |
| Forged document | Anachronistic template, font or logo; a registry field that contradicts the issuing register; internal date inconsistency; metadata authoring tool inconsistent with the claimed issuer | Bad grammar; poor scan quality; unfamiliar formatting |
| Fake screenshot of a post or headline | No archive capture at the claimed time; the URL never existed; layout inconsistent with the platform on that date | The account later deleting the post — real posts get deleted constantly |
| Outlet impersonation | Lookalike `domain`, registration date after the claimed article date, absent from the real outlet's own archive and sitemap. Hand the `domain` to `/osint:osint-infra` | An unfamiliar outlet name |
| Fabricated quote | Absent from the full transcript, video, or official record where one exists; the earliest instance is a commentary piece, not a primary record | The quote sounding out of character |
| Number laundering | The figure traces to a projection, a survey with an undisclosed method, or a rounding of a different figure | A number being large or precise |
| Selective edit | The unedited recording contains the omitted context; the cut points are audible or visible | Short clip length alone |
| Synthetic media | A C2PA generative manifest via **Content Credentials**; a physical impossibility that survives re-encoding; a matching prompt-output pair | Detector score; "uncanny" feel; hands; artifacting from compression |
| Rumour attributed to an institution | The institution's own record, register, or press page has nothing on that date | "No comment" from the institution |
| Prebunking inversion — accusing a real record of being fake | The primary record still exists at the issuing body | Loud denial |

Two rules that apply to the whole table:

- **Absence of a tell is not authenticity.** Every left-column check that comes back clean supports
  `unverified`, not `verified`.
- **A tell is a lead, not a verdict.** The finding is the observation ("plate format in frame is
  inconsistent with the claimed country, observed at TS in the archived copy, sha256 ..."), graded,
  with the falsifier named.

## 7. Coordinated inauthentic behaviour

**Every signal below is weak on its own, and most are worthless on their own.** A single account
exhibiting three of them is a person with unusual habits. The unit of analysis is the **network and
the timing**, never the account. Report CIB only as `inferred`, with ICD-203 wording, after ACH
against the mundane hypotheses: organic virality, a shared community, a fandom, a mailing list, a
scheduled-posting tool, a paid but disclosed campaign.

| Signal | What it can support | Why it fails alone |
|---|---|---|
| Identical or near-identical text across unrelated accounts | Copying — strong when the text carries a rare typo or an identical rare phrase | Copy-paste activism and template campaigns are ordinary and legitimate |
| Posting synchronised within seconds across accounts with no follow relationship | Coordination, when the window is tight and repeated across several distinct events | One breaking event makes strangers post simultaneously |
| Account creation clustered in a narrow window, all first posting on one topic | Coordination, when combined with the two rows above | Platforms see creation spikes after any news event or referral campaign |
| Avatar is a stock photo, a stolen photo, or a generated face | The persona is not who it claims — check with **Yandex Images**, **TinEye**, **Google Lens** | Privacy-conscious real people do this constantly |
| Handle pattern: name plus long random digit string | Weak. Default-suggested handles look exactly like this | Platform defaults produce it for real users |
| Dormant account reactivated to push one topic | Purchase or compromise of an aged account, when several show the same dormancy window | People return to old accounts |
| Follower graph overlaps almost completely across a set of accounts | A closed cluster — check on **Bluesky**, where the follow graph is retrievable unauthenticated | Communities overlap by definition |
| Cross-platform copies appearing in a fixed order with consistent lag | A distribution pipeline | Aggregators and reposters produce the same signature |
| Very high posting volume | Almost nothing | Heavy users exist; so do scheduling tools |
| Low follower count, new account, default avatar, few posts | Nothing at all | This describes most real accounts on any platform |

Reporting rules:

- **Never name an individual account as a bot, and never call a named person inauthentic.** The
  finding is about an observed pattern across a set, with the set described and its members
  referenced by entity id. Misidentifying a real person as a bot is the same category of harm as a
  wrong identity merge.
- State the observation window, the collection method, and what fraction of the set you actually
  examined. A sample is not the network.
- Platform-side data is partial and changes constantly. Deleted, suspended and locked accounts
  vanish; archive what you rely on at the moment you rely on it.
- Coordination is not falsity. A coordinated campaign can push a true claim, and an organic
  cascade can push a false one. Keep the two findings separate.

## 8. Quotes and documents against a primary record

**Quote:** find the complete primary record — full transcript, unedited recording, official
proceedings, the filing itself. Then: does the string appear verbatim; is it complete; is the
attribution right; what precedes and follows it. A quote that survives the string check but not the
context check is `manipulated`, not `verified`. For a translated quote, apply the machine-translation
row in `41-confidence.md`: quote the original string verbatim, cite the original, mark the rendering.
Where no primary record exists — a private remark, an off-record briefing — the claim is `reported`
at best and frequently `unverifiable`; say which.

**Document:** work outward from the artifact. Internal consistency (dates, references, sequence
numbers, signatories against their tenure); the template against a known-genuine document from the
same issuer and period; metadata via **ExifTool** and **Content Credentials**, remembering that
metadata is a claim by whoever last wrote the file; then every checkable field against the issuing
register — **UK Companies House**, **SEC EDGAR**, **The Gazette**, **CourtListener**,
**Find Case Law**, or the relevant register via `/osint:osint-corporate`. One field contradicting a primary
register is worth more than ten fields matching it. A document that survives every check is
`unverified` unless the issuer confirms it or a primary record contains it — surviving checks
establishes that it has not been shown false, which is a different statement.

## 9. Worked example, raw claim to graded verdict

**Raw:** a post carrying a photograph, captioned *"Fire at the Valmara chemical terminal this
morning, second incident this year."* 41,000 reposts.

1. **Decompose.** C1 the photograph is unaltered · C2 it depicts the Valmara chemical terminal ·
   C3 it was taken on the stated morning · C4 a fire occurred there that morning · C5 an earlier
   incident occurred this year. Falsifiers written for each.
2. **Freeze.** `archive.py` stores the post and the full-resolution image into `evidence/`; ledger
   `action=archive`, `mode=passive`, `result_sha256` recorded. The post is deleted six hours later;
   the case is unaffected.
3. **Trace upstream.** TinEye oldest-first returns a copy on a regional news site dated three years
   earlier. Yandex Images returns the same item plus two aggregator copies. Google Lens OCRs a sign
   in frame reading a company name that is not the terminal operator.
   - `f-1` — *observed*, `B2`: an identical image was published at U1 on 2023-04-11, retrieved TS,
     sha256 ... Earliest instance located as of TS; index coverage limits stated in `gaps.md`.
4. **Provenance.** The archived original carries EXIF stripped by the platform; the 2023 copy
   carries an IPTC credit naming a wire agency. Content Credentials: no manifest, which supports
   nothing either way.
5. **Count sources.** 41,000 reposts, 6 news items. Five carry the same agency credit and identical
   phrasing; one links to another. Surviving count: **one**, the 2023 agency item.
   - `f-2` — *correlated*, `B2`: six items collapse to one origin under the independence tests;
     shared credit and identical phrasing recorded.
6. **Disconfirm before grading.** Port authority notices, marine casualty listings and local outlets
   for the stated morning: nothing. Coverage judged near-complete for incidents of this class in
   this jurisdiction, so the absence is authoritative under `40-analysis.md`. **Google Fact Check
   Explorer** returns one prior adjudication; its underlying evidence — the same 2023 wire item —
   is read and cited directly, its verdict is not adopted.
7. **Verdict.**
   - C1 `unverified` (`C3`): no manipulation observed; absence of a tell is not authenticity.
   - C2 and C3 `misattributed` (`B2`, rung *observed*): the photograph was published three years
     before the stated date and the in-frame signage is inconsistent with the terminal.
   - C4 `unverified` trending to `debunked` (`C3` → the absence is authoritative, so `B4` for the
     claim): it is `unlikely` that a fire occurred at that terminal that morning. This assumption
     fails if the port authority does not publish incidents of this severity within 24 hours —
     checkable against its prior publication cadence.
   - C5 `unverifiable` on present access: the incident register is not public.
   - Overall: the post is `misattributed`. Nothing here establishes that the poster knew, and no
     finding is written about the poster's intent.

Note what did not happen: no verdict of "fake news", no claim about the poster, no accumulation of
41,000 reposts into corroboration, and no probability assigned to anything a retrieval settled.

## 10. Delivering `unverified`

Most verification work ends here, and a report that hides it is worse than one that says it.

- **Lead with the status and the grade.** "Unverified as of TS" is the BLUF, not a footnote.
- **Say what was checked and came back empty**, by source and query, so the reader can see the
  shape of the hole. Absence type per `40-analysis.md`: authoritative, subject-controlled, or
  non-authoritative.
- **Name what would settle it** — the specific observation, the source that holds it, whether it is
  `passive` or `active`, and why it was not obtained (out of scope, paid, sealed, not authorised).
- **Do not hedge the gap itself.** "The register returned no matching record on TS" is flat and
  factual; it takes no estimative term.
- **Do not fill the gap with the strongest available weak source.** A `D3` aggregator hit does not
  convert `unverified` into an answer; it converts a clean gap into a contaminated one.
- **Never convert `unverified` into an implication of falsity**, in the finding, the summary, or a
  headline. If the report will be read by a general audience, state explicitly that the claim was
  not established and was not disproved.
