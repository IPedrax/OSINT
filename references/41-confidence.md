*Load when: grading any finding, resolving how much weight two sources jointly carry, or choosing estimative wording. Mandatory before anything is written to `findings.md`.*

# Confidence grading

Two independent axes, always both. Source reliability is a letter, information credibility is a
number, and the grade is the pair: `B2`, `C3`, `E1`. Never a letter alone, never a number alone.

## Source reliability (Admiralty / NATO)

| Grade | Meaning |
|---|---|
| A | Completely reliable — authoritative primary record |
| B | Usually reliable — established source, minor history of error |
| C | Fairly reliable — generally sound, some doubt |
| D | Not usually reliable — significant doubt |
| E | Unreliable — history of error |
| F | Cannot be judged — no basis to assess |

## Information credibility

| Grade | Meaning |
|---|---|
| 1 | Confirmed by independent sources |
| 2 | Probably true — consistent with other information |
| 3 | Possibly true — reasonable but uncorroborated |
| 4 | Doubtful — contradicted by other information |
| 5 | Improbable |
| 6 | Cannot be judged |

## The distinction that gets confused

Reliability grades the **source**. Credibility grades the **claim**. They move independently.

- `A3` is normal and correct: a national registry (A) carrying a single filing that nothing else
  corroborates (3). The registry being authoritative does not corroborate the filing's contents.
- `E1` is normal and correct: an anonymous poster (E) making a claim that a separately obtained
  document confirms (1). `E` is a judgement about the *class* — anonymous open-submission posts
  have a documented history of error — not about this poster's own track record. Where even the
  class cannot be assessed, the letter is `F`. The poster stays untrusted; this one claim is
  confirmed.
- `A1` requires two things: an authoritative source **and** independent corroboration. One
  authoritative source alone is `A3`, or `A2` if it is consistent with other collected material —
  unless the artifact is self-authenticating and independently mirrored, which is the one stated
  exemption: see the Certificate transparency row in the class table below.
- `F6` is the honest grade for an artifact of unknown provenance making an uncheckable claim. It
  is not a failure to grade. It is a grade, and it tells the reader to spend nothing on it.

Grading the source twice is the most common error: reading "authoritative registry" and writing
`A1` because the registry is trustworthy. Ask separately: who says this, and what else says it.

A finding also carries, alongside the grade: its rung on the inference ladder, the source URL,
retrieval timestamp, the sha256 of the archived copy, and `passive` or `active`. Rendering is
`50-reporting.md`'s business; the fields are non-optional here.

## Five worked examples

### 1. National corporate registry filing

Registry record states a person was appointed director of a company on a date, with a service
address.

| Element | Value |
|---|---|
| Source | National registry, primary record of a statutory filing |
| Reliability | A |
| Claim as stated | "The registry records X as appointed director of `company_number` NNNN on DATE" |
| Credibility | 3 if this is the only source; 1 only if a source with a different origination process repeats it — a court record, a regulator's decision, or a filing by a different party. A second filing by the same filer is the same source |
| Grade | `A3` |

The trap: "X is a director" and "X controls the company" are different claims. Nominee and
professional directors exist in every jurisdiction. The registry attests the filing, not the
truth of it — most registries do not verify what is filed. A claim about **control** is rung
`inferred`, needs a stated assumption, and cannot inherit the `A`.

### 2. Certificate transparency log entry

A CT log holds a certificate whose SAN list includes `vpn.example.com`, logged at a timestamp.

| Element | Value |
|---|---|
| Source | CT log — append-only, cryptographically verifiable, tamper-evident |
| Reliability | A |
| Claim as stated | "A certificate covering `vpn.example.com` was logged at TS" |
| Credibility | 1 — the log entry is self-authenticating and mirrored across logs |
| Grade | `A1` |

The trap: CT says a name was **certified**, not that a host exists, resolves, or ever served
traffic. "`vpn.example.com` is live" is a different claim, rung `inferred`, and it is *checkable*
— resolve it (passive DNS first) instead of assigning it a probability.

### 3. Self-reported LinkedIn employment claim

A profile states the person is Head of Engineering at a named company since a given year.

| Element | Value |
|---|---|
| Source | The **subject**, transmitted by the platform. Grade the originator, not the transmitter |
| Reliability | C — self-report, unverified, with an incentive to inflate; `D` if other self-reports by the same person already conflict |
| Claim as stated | "The profile asserts employment as TITLE at COMPANY since YEAR" |
| Credibility | 3 uncorroborated |
| Grade | `C3` |

The trap: corroborating with the same person's CV, personal site, or conference bio does not
raise this. Those are the same source — the subject — restated. Independent corroboration is the
employer's own staff page, a filing naming them as an officer, or a press release from the
company. When that arrives, the finding is carried by the new source at `B2` or `A2` and stays on
rung `reported` — you still have not seen the employment, only a second assertion of it — and the
profile is demoted to a consistent secondary.

### 4. Anonymous forum post matching a leaked document

An anonymous post names an individual as the operator of a piece of infrastructure. A document
obtained independently records the same attribution.

| Element | Value |
|---|---|
| Source | Anonymous open-submission post; unknown motive |
| Reliability | E — anonymous open-submission posts as a class have a documented history of error. `F` if even the class cannot be assessed |
| Credibility | 1 — an independently obtained document carries the same claim |
| Grade | `E1` |

Two conditions or it is not `1`:
- The document must not be sourced from that forum, that thread, or a mirror of it. If the post
  is the only route to the document, this is one source and the grade is `E3`.
- The document must be lawfully available. A non-public breach corpus or purchased credential
  dump is refused outright (global gate item 6) — it does not corroborate anything, because it
  cannot be used at all.

### 5. Data broker aggregator record

An aggregator returns a record tying a `phone` and an `address` to a `person_name`.

| Element | Value |
|---|---|
| Source | Aggregator. No per-field provenance, no retrieval date per field, records merged by fuzzy name matching, stale entries retained indefinitely |
| Reliability | C at best, commonly D |
| Credibility | 3 |
| Grade | `C3` / `D3` |

The traps, all three of which occur constantly:
- Two brokers agreeing is **not** corroboration when both license the same upstream feed. Assume
  a shared upstream unless the vendor documents otherwise.
- Broker records merge distinct people who share a name. A broker record is a *hypothesis about
  an identity*, not an identity. It never satisfies the named-linking-datapoint test.
- "Possible relatives" and "associated persons" fields are algorithmic co-occurrence, not
  relationships. They are never a finding.

## Grading rules by source class

`Attests` is what the class can actually support. A claim outside that column does not inherit
the class's letter — it is a new claim at a new rung.

| Source class | Reliability | Attests | Max credibility alone | Notes |
|---|---|---|---|---|
| Primary government / court record | A | That the record exists and says what it says | 3 | Contents may be unverified by the issuer. Sealed, amended, and appealed records exist. Date the record, not the retrieval only |
| Registry / registrar data (company, land, vessel, aircraft) | A–B | The filed value as of the filing date | 3 | Self-filed in most jurisdictions. Nominees and agents are normal, not suspicious |
| WHOIS / RDAP | B–C | Registrar-held fields at retrieval time | 3 | Privacy-proxied by default for most `domain`. Registrant fields are self-supplied. Historical WHOIS is a vendor's snapshot — grade the vendor |
| Certificate transparency | A | A name was included in a logged certificate at a time | 1 | Self-authenticating. Says nothing about resolution, ownership, or liveness |
| Passive DNS | B–C | That a vendor's sensors observed a resolution in a window | 2 | Sensor coverage is partial and undisclosed. Absence is not non-existence. Two vendors sharing a sensor network is one source |
| Self-reported profile data | C–D | That the subject asserted it | 3 | Grade the subject, never the platform. All of one subject's self-reports are one source |
| Data broker aggregator | C–D | That the broker's index contains this tuple | 3 | No provenance, no field dates, fuzzy merges. Never a merge basis |
| Breach corpora | Refused unless public and lawfully obtained | — | — | Global gate item 6. Where a corpus is lawfully usable, treat as D–F: unverified, salted, and merged with prior dumps |
| Archived snapshot (web archive, local capture) | B | That the capture shows this content at the capture time | 2 | Grade the *underlying* source for the claim; the archive attests only the capture. Partial captures, blocked assets, and retroactive exclusions are common |
| Machine translation | Not a source | Nothing | — | Cannot raise credibility and cannot be the cited source. Quote the original string verbatim, cite the original, mark the rendering as machine-translated. Legal and financial terms of art are where MT fails silently |
| Analyst inference | Not a source | Nothing | — | There is no source to grade. Carry the grade of the evidence it rests on, mark the rung `inferred`, state the assumption, and use estimative language for the leap. Never write a letter grade as if the inference were sourced |

Two class-level rules that override any individual judgement:

- Any claim whose only support is a self-report by the subject is capped at credibility 3, no
  matter how many places the subject repeated it.
- Any claim whose only support is an aggregator is capped at credibility 3 and can never justify
  merging two entities.

## Estimative language (ICD 203)

Use these words, no others.

| Term | Range |
|---|---|
| `almost no chance` | 01–05% |
| `very unlikely` | 05–20% |
| `unlikely` | 20–45% |
| `roughly even chance` | 45–55% |
| `likely` | 55–80% |
| `very likely` | 80–95% |
| `almost certain` | 95–99% |

Banned in findings: "clearly", "obviously", "confirmed" (unless credibility is 1), "proves",
"definitely", and any bare assertion of an inference as a fact.

Rules on top of the table:

1. **Never mix a probability word with a numeric percentage in the same sentence.** Write "it is
   likely that", not "it is likely (about 70%) that". The word carries the range; the number
   invents a precision the evidence does not have, and readers anchor on it.
2. **Never assign a probability to something you could simply go and check.** "It is likely the
   domain resolves to that host" is a failure to run a lookup. Estimative language is for claims
   about the world that no available collection step settles — attribution, intent, control,
   relationship. Apply the checkability test before every probability word: is there a passive
   step in `10-pivot-matrix.md` that would answer this? If yes, take the step. If
   `10-pivot-matrix.md` is absent from a build, apply the test against the zero-key baseline in the
   router's absent-skill fallback — a DNS lookup, a CT search or an archive fetch settles most of
   these.
3. **Never apply estimative language to an observed artifact.** You read the filing; it is not
   "very likely" that the filing says what it says. Estimative language belongs to rungs
   `inferred` and above, never to `observed` or `reported`.
4. One estimative term per claim. A sentence with two probability words is two claims.
5. Do not hedge a refusal or a gap. "No result was returned" is flat and factual.

## Corroboration: what counts as independent

Independence means two **separately generated observations of the world**, not two presentations
of one observation. Apply all four tests; failing any one collapses them to a single source.

| Test | Question |
|---|---|
| Counterfactual | Would source B still carry this if source A had never published? |
| Upstream | Do they share a feed, sensor network, licensing deal, or original document? |
| Origination | Do both trace to one self-report by the subject, or one filing, or one press release? |
| Chain of copying | Is there a plausible copy path — later timestamp, identical phrasing, identical typo, identical error in a number? |

Collapses to one source:

- Two outlets republishing one wire story. Also: an outlet, its syndication partners, and the
  aggregators that scraped it.
- A data broker and its upstream feed. Also two brokers licensing the same feed.
- Two subdomain enumeration tools that both read the same CT logs.
- Two passive DNS vendors sharing a sensor network.
- A subject's LinkedIn, CV, personal site, conference bio, and podcast introduction.
- A company's press release and every article that quotes it.
- A Wikipedia article and any source that cites it, in either direction — check publication dates.
- Two translations of one document.
- A registry's own API, its web UI, and a third-party reseller of its bulk data.

Stays independent:

- A registry filing and a court docket recording the same fact from different processes.
- A CT log entry and a passive DNS resolution for the same `subdomain`.
- A company staff page and a filing naming the same person as an officer.
- Two journalists who each name their own distinct on-record source.

### Circular reporting detection

Run this before writing any credibility 1 or 2:

1. Order every supporting source by earliest publication or capture timestamp, not by retrieval
   order. The earliest is the candidate origin.
2. Diff the wording of the shared claim. Shared distinctive phrasing, a shared typo, or a shared
   transposed digit means copying, not agreement.
3. Read each source's own citations. If they cite each other, or all cite one document, count one.
4. Check whether the "independent" source could have been seeded by the first — including by your
   own earlier collection, if anything in this case was published or queried publicly.
5. If the origin cannot be established, credibility is capped at 2 and the finding says so:
   "the earliest traceable publication of this claim is SOURCE at TS; later sources may derive
   from it."

## The inference ladder

Every finding declares exactly one rung. The rung is mechanical, not a judgement call: it is
determined by what you touched, not by how confident you feel. Use these sentence patterns
verbatim — if the finding will not fit the pattern for the rung you claimed, it is on a lower rung.

| Rung | You have | Max credibility | Where it may be written |
|---|---|---|---|
| `observed` | The artifact itself, archived, hashed | 1 | `findings.md` |
| `reported` | A source asserting it; you did not see the underlying thing | 2 | `findings.md` |
| `correlated` | Two or more observed datapoints sharing a value | 2 | `findings.md` |
| `inferred` | A conclusion drawn from lower rungs plus a stated assumption | 3 | `findings.md`, marked, with estimative language |
| `speculated` | A hypothesis with no evidentiary weight | 6 | `gaps.md` only. Never `findings.md` |

Sentence patterns:

- **observed** — "`<artifact>` retrieved from `<url>` at `<ts>` (sha256 `<hash>`) shows
  `<verbatim field or quoted string>`."
- **reported** — "`<source name>` states `<claim>` (`<url>`, retrieved `<ts>`, sha256 `<hash>`).
  The underlying record was not obtained."
- **correlated** — "`<selector A value>` and `<selector B value>` share `<linking datapoint
  type>` = `<value>`, observed in `<source 1>` at `<ts>` and `<source 2>` at `<ts>`. No
  identity claim is made here."
- **inferred** — "Assuming `<assumption stated as a testable proposition>`, it is `<estimative
  term>` that `<conclusion>`. Basis: `<the specific observed/reported/correlated findings, by
  id>`. This assumption fails if `<falsifier>`."
- **speculated** — "Hypothesis, untested: `<statement>`. Would be supported by `<specific
  collection step>`; would be falsified by `<specific collection step>`. Not carried into
  findings."

Two rules that stop rung inflation:

- A summarisation step cannot raise a rung. If a finding was `inferred` when written, it is
  `inferred` in the executive summary, in the report, and in the next session. Re-derive from the
  ledger, never from your own prose.
- A finding that cites another finding rather than a source inherits the **lowest** rung and the
  **weakest** grade in its chain.

## One finding, written badly and correctly

Badly:

> The company is clearly a front controlled by Jan Novak. The registered address matches the one
> on his LinkedIn, and the domain was obviously registered by the same person since the WHOIS
> email uses his name. Confirmed.

What is wrong: "clearly", "obviously", "Confirmed" are banned. No source, no timestamp, no hash.
An address match is `correlated` and is asserted as control, which is `inferred` — two rungs
laundered in one sentence. A shared `address` at a company formation agent's premises is a
Tier-3 datapoint, not a link. The self-reported profile is treated as authoritative. "WHOIS email
uses his name" is a `person_name` string match — the weakest datapoint class there is. The
identity is merged with no named linking datapoint.

Correctly:

> **f-14 — Registered address of COMPANY matches an address on a self-reported profile.**
> grade `C3` · rung `correlated` · passive
> Registry record for `company_number` NNNNNN retrieved 2026-07-27T09:14:00Z (sha256 `a1b2…`)
> gives the registered office as ADDRESS. A `social_profile` for `person_name` "Jan Novak"
> retrieved 2026-07-27T09:31:00Z (sha256 `c3d4…`) lists the same ADDRESS. The two records share
> `address` = ADDRESS. No identity claim is made here.
> disconfirms: a registry filing or agent client list showing ADDRESS is a formation agent's
> premises shared by unrelated companies, which would make the shared value a Tier-3 coincidence
> rather than a link.
>
> **f-15 — Control of COMPANY by the profile holder is not supported on present evidence.**
> grade `C3` · rung `inferred` · passive
> Assuming the registry's named director (f-12, `A3`) is not a nominee, it is `unlikely` that the
> profile holder controls COMPANY: the directorship sits elsewhere, and `person_name` "Jan Novak"
> returns 40+ distinct individuals in this jurisdiction (f-13). This assumption fails if the
> named director is a nominee — checkable against the agent's own client list and against the
> count of directorships held by that person. `e-12` and `e-19` remain in `candidate_group`
> `cg-3`.
> disconfirms: a signed instrument, a shareholder register, or a filing naming the profile holder
> as a person with significant control.
> Not resolved; see `gaps.md` G-1.

Note what changed: the grade dropped, the rung is declared, the estimative term points *away*
from the initial guess because the disconfirming evidence was scored, the assumption is stated
with its falsifier, the unresolved identity stays in a `candidate_group`, and the next concrete
check is named rather than guessed at.
