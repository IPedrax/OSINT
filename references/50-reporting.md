*Load when: compiling a deliverable from a case directory, or the user asks for a report, memo, writeup, dossier, KYC file, or machine-readable export.*

## Inputs

Nothing is authored in the report that does not already exist upstream. If a sentence has no
upstream row, it is not a reporting problem, it is a collection gap.

| Case file | Supplies | Lands in `${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` |
|---|---|---|
| `scope.md` | header values, questions, out-of-bounds, authority, redaction default | 1, 3, handling note |
| `findings.md` | every graded claim, verbatim | 2, 5 |
| `entities.jsonl` | dossier rows, link-chart nodes | 6, 8 |
| `events.jsonl` | timeline rows with precision | 7 |
| `gaps.md` | negative results, open questions, next collection | 10 |
| `ledger.jsonl` | collection window, sequence, evidence hashes, mode counts | 4, 11 |
| `evidence/` | hash table, byte counts | 11 |

Compile order — the BLUF is written last, from the finished body:

1. Header from `scope.md`. Any mismatch means the report is wrong, not `scope.md`.
2. Section 3 verbatim, including the full out-of-bounds list.
3. Section 5: paste finding blocks. Do not rewrite claims into prose.
4. Sections 6, 7, 8 from the JSONL files.
5. Section 9 from the `alternatives` lines across all findings, deduplicated.
6. Section 10 from `gaps.md`.
7. Sections 11 and 12 from `ledger.jsonl` and the source grades in each finding.
8. Section 4: methodology, and what was deliberately not collected.
9. Section 2: BLUF.
10. Handling note, then the checklist.

## Audience tailoring

Same case files, four very different documents. The findings never change; the ordering, the
depth, and the default reading level do.

| Audience | Reader decides | Lead with | Deep sections | Thin sections | Register |
|---|---|---|---|---|---|
| Security / threat intel | block, hunt, escalate, notify | infrastructure relationships and timeline | 5, 7, 8, 11 | 6 dossiers on natural persons | technical, indicator-dense |
| Journalism / investigation | publish, keep reporting, drop | what can be stood up and what cannot | 5, 9, 12, handling note | 8 link chart | plain language, no jargon |
| KYC-AML due diligence | onboard, reject, escalate to EDD | identity resolution and adverse-media result | 3, 6, 10, 12 | 8 link chart, 7 timeline | procedural, audit-trail first |
| Self-audit | what to remove or lock down | exposure ranked by fixability | 6, 10 | 9, 12 | direct, action-oriented |

### Security / threat intel

- Lead the BLUF with the assessed relationship between infrastructure, then the confidence.
- Timeline is the spine. Infrastructure work is about sequence: registration before certificate
  before first resolution before first observed use.
- Indicators go in section 11 next to their hashes, so a reader can lift them into tooling
  without re-reading the prose. Mark each one `passive` or `active` — a defender needs to know
  whether looking at it already told the adversary something.
- Attribution to a named person is a separate, harder claim than clustering infrastructure. Keep
  them in different findings with different grades. Most security reports need only the cluster.
- Include a deception hypothesis (H4 in section 9). Adversary infrastructure is sometimes built
  to be found.

### Journalism / investigation

- The BLUF is what you can stand up in print, not what you believe. The BLUF states the estimative
  term the finding itself carries and the grade separately; a `C3` finding does not become more
  probable by being the strongest thing in the case.
- Section 12 matters more here than anywhere else: a source-reliability table is what survives a
  pre-publication legal read.
- Every finding about a private individual carries the public-interest reason it is in the report.
  The reason is the `public_interest` value recorded in `scope.md`; if that field is empty the
  finding comes out.
- Right of reply is a reporting step, not a collection step. Note in section 4 whether the subject
  was approached; if not, say so, because the absence is visible to readers.
- Name the single-source findings explicitly. "Sole support for" in section 12 is the list a legal
  reviewer will ask for first.

### KYC-AML due diligence

- Structure beats narrative. The file is read by a reviewer looking for a specific field, and re-read
  years later by an auditor reconstructing what was known on the decision date.
- Section 3 is the compliance record: mandate, jurisdictions, questions, screening scope.
- Section 6 dossiers are the deliverable. One per screened party, each stating whether identity was
  resolved, at what grade, and on which datapoint.
- Negative screening results are the product, not filler. "No match in `<list>` as at `<date>`,
  coverage `<yes>`" is exactly what the file exists to record. Name the list, the date, and the
  coverage every time.
- PII minimization is a control, so state it as one in section 4: what was not collected, and why
  that was the right call.
- Never present a sanctions or PEP screening hit as an identification. It is a name match at a
  stated grade until a second datapoint resolves it.

### Self-audit

- The requester is the subject, so redaction protects nobody; ask before including anything, and
  default to the same masking anyway if the file will be shared with an employer or a lawyer.
- Order section 6 by what the subject can actually remove, then by exposure severity. A leaked
  address on a broker site with a deletion form outranks an immutable archived post.
- Section 10 becomes an action list. Each row: what to change, where, and whether removal is
  reversible.
- Skip the adversarial framing. There is no hypothesis to reject; there is a footprint to reduce.

## BLUF discipline

Under 150 words. It answers the scope question. It is not a summary of the work.

| Rule | Failure it prevents |
|---|---|
| Write it last, from the finished body | A BLUF the body contradicts |
| One sentence per scope question, in question order | Burying the answer the requester paid for |
| Every sentence graded, or citing a graded finding id | Ungraded assertions with the most readers |
| Estimative wording only, from the seven ICD 203 phrases | Vague hedging that means nothing operationally |
| Grade the BLUF as a whole at the weakest link, not the average | Laundering a `C3` into a `B2` by volume |
| One line on what would change the assessment | A conclusion that looks unfalsifiable |
| No source names, no method, no URLs | A BLUF that reads as method rather than answer |

If the BLUF cannot be written, the case is not finished. That is a stop-condition signal, not a
writing problem.

Shape that works, in order: the answer, the confidence, the single most consequential
uncertainty, what would change it. Nothing else fits in 150 words.

## Write to the grade, not to the story

The pull toward narrative is the main failure mode of an OSINT report. A story wants a subject,
a motive, and a conclusion. The evidence usually supports a set of graded relationships. Write
those.

| Grade | How the sentence may be written |
|---|---|
| `A1` `B1` | Plain declarative, and only where two independent origins exist. "The company was struck from the register on 2024-03-11, recorded in the register and in the official gazette notice (A1, f-4)." |
| `A2` `B2` `C2` | Declarative for the record, estimative for anything inferred from it. |
| `C3` `D3` | Estimative phrase mandatory, and the single supporting source named in the sentence or the block. |
| digit `4` `5` | Present as a claim a source makes and this case doubts. Never in the reporting voice. |
| digit `6`, or rung `speculated` | Gaps only. Never in `findings.md`, never in the BLUF, never in a dossier. |

Tests to run on each sentence:

- **The "and" test.** Two claims joined by "and" hide the weaker grade behind the stronger. Split
  them.
- **The "so" test.** "so", "therefore", "which means" mark the point where the rung dropped from
  `observed` to `inferred`. Either the inference is its own graded finding or the clause comes out.
- **The adjective test.** "sophisticated", "shell company", "suspicious", "coordinated" are
  conclusions wearing adjective clothing. Replace with the observation, or grade the conclusion.
- **The motive test.** Motive is almost never observable in OSINT. If a sentence explains why a
  person did something, it is `inferred` at best and usually `speculated` — which means `gaps.md`,
  not the report.

Rewrites:

| Narrative | Written to the grade |
|---|---|
| "The attacker registered lookalike domains to phish employees." | "Four domains resembling the client brand were registered within 90 minutes on 2025-02-04 (A3, f-2). Their use for credential collection is `likely` given the login-form content on two of them (B3, f-3)." |
| "The company is a shell used to move funds." | "The company filed dormant accounts for three consecutive years (A3, f-6) and shares a registered address with 214 other entities (A3, f-7). Trading activity is `unlikely` (B3, f-8). No fund movement was observed; none was in scope." |
| "He clearly runs both accounts." | "Both accounts publish the same avatar file, sha256 matching (C3, f-9). Common control is `likely` (B3, f-10). Alternative: a shared graphic reused independently, not excluded." |

Every rewrite here that carries an estimative phrase is rung `inferred` and is capped at
credibility 3; a digit of 1 or 2 next to a probability word is a mis-grade.

Banned outright: "clearly", "obviously", "proves", "definitely", and "confirmed" unless the claim
digit is `1`. Banned by construction: a percentage where an ICD 203 phrase belongs, and a synonym
for one of the seven phrases.

## Redaction

Mandatory, applied to the delivered copy only. The case directory keeps full values under the
retention rule in `scope.md`.

| Situation | Default |
|---|---|
| Any natural person who is not the requester | partial: identifiers masked |
| `target_category: private-individual` | partial, plus no address, no coordinates, no movement |
| `target_category: public-figure` | partial for contact selectors, unredacted for official roles |
| `target_category: org` | unredacted for corporate records; partial for named officers |
| `purpose: kyc` | partial in the shared file; full values in the retained case dir |
| `purpose: journalism`, pre-publication | partial, and every unredacted value justified in writing |
| `purpose: self_audit` | ask; default partial if the file leaves the requester |
| Incidental third parties | remove entirely unless a finding depends on them |

What redaction looks like:

| Data | Delivered form |
|---|---|
| `email` | `j****@example.test` — local part masked, domain kept |
| `phone` | `+1 415 *** ##67` — country and area kept, subscriber masked |
| `address` | street and city kept, house or unit number removed |
| `coordinates` | reduced to a named locality; never rounded coordinates, which still locate |
| `person_name` | full name on first use only where justified; otherwise initials plus role |
| `username` | kept if the account is public and the finding is about the account |
| `document` | quote the operative line, do not attach the document |
| `photo` | describe the frame; do not embed images of people |

Never redacted:

- Entity ids. `e-7` stays `e-7` everywhere, so the report is internally traceable without values.
- Evidence hashes. A hash is not personal data and it is the integrity chain.
- Grades, rungs, and estimative wording.
- The out-of-bounds list.

Two-copy rule: one unredacted copy inside the case dir, one redacted deliverable. Never generate
a third. Record in the handling note where the unredacted copy lives, and never attach it.

Withheld findings still appear: id, grade, rung, `disconfirms`, and the claim replaced with
`[withheld — <reason>]`. Deleting the block hides that the finding exists.

## Presenting an unresolved identity

The identity-confusion guard exists so a report can say "these might be the same" without saying
"these are the same". Do not resolve it in prose that the data does not resolve.

Rules:

- Keep both entity ids in every sentence. Never introduce a single name that stands for both.
- State what they share, and state that it is what they share and nothing more.
- Name the datapoint that would resolve it, and the datapoint that would break it.
- Use an estimative phrase for the identity claim itself, graded separately from the underlying
  observations.
- Never merge in the link chart. Dashed edge, labelled `candidate group, unresolved`.

Sentence pattern:

`<e-7>` and `<e-8>` share `<the observed datapoint>` (`<grade>`, `<f-n>`). That they refer to the
same `<person | company | operator>` is `<estimative phrase>` (`<grade>`, `<f-n>`). Resolution
requires `<named datapoint>`; `<other observation>` would break the link.

What not to do:

| Anti-pattern | Why it fails |
|---|---|
| Referring to both as "the subject" | Silently merges them in the reader's head |
| Same-name-is-same-person | Name collision is common and jurisdiction-dependent |
| Same-username-is-same-person | Handle reuse across platforms is not evidence of identity |
| Merging because three weak signals "add up" | Three `C3` correlations are not a `B2`; state each one |
| Dropping the weaker candidate from the report | The reader cannot see that an alternative exists |

## Presenting negative results

A negative result is a result. Reports that hide them look thin and get re-run by the next
analyst, who spends the same hours.

- Give negatives their own table in section 10 with `coverage` on every row. Coverage is what makes
  a negative meaningful: a source that does not cover the jurisdiction, era, or language returning
  nothing tells you about the source.
- `coverage: yes` against an authoritative register supports a finding. Write it as one, graded on
  the register: "No company under that name is registered in `<jurisdiction>` as at `<date>` (A3)."
- `coverage: no` or `unknown` supports nothing. Say so in the row, not in a footnote.
- Count the negatives in section 4 so the reader sees the work: "31 sources queried, 19 returned
  nothing, coverage adequate on 12 of those."
- Frame by decision value, not by absence. "No adverse media in the covered jurisdictions" is an
  answer to a KYC question, and the file exists to record it.
- Never pad. A single-page report backed by 40 logged negatives is a good report. A ten-page report
  padded with method description is not.

| Weak framing | Strong framing |
|---|---|
| "We were unable to find any sanctions matches." | "No match on `<list>` as at `<date>`; list coverage includes `<jurisdictions>` (A3, n-4)." |
| "Nothing was found on social media." | "Four platforms checked by handle and by email; no account located. Coverage does not include closed platforms (n-7 to n-10)." |
| "No further information is available." | "The registry publishes officers only from 2016; the 2011 filing is not obtainable online. Structural gap, not a collection failure." |

## Machine-readable export

For pipelines, dashboards, and case-to-case reuse. Emit alongside the markdown, never instead of
it: the JSON has no instructions for a human reader and no redaction judgement.

`findings[]`, `entities[]` and `events[]` validate against
`${CLAUDE_PLUGIN_ROOT}/assets/entity-schema.json` (draft 2020-12): `findings[]` uses the `finding`
definition, `entities[]` and `events[]` are the JSONL lines unchanged. The enclosing envelope and
the remaining arrays are defined by this section and are not schema-validated. Field names in a
`finding` object differ from the `findings.md` block; the mapping is in the schema's top-level
`description`.

```json
{
  "case_id": "example-case",
  "generated": "2026-07-28T14:02:00Z",
  "report_version": 1,
  "purpose": "kyc",
  "classification": "internal only",
  "handling": "partial",
  "period_covered": "2019-01-01/2026-07-28",
  "collection_window": "2026-07-28T09:14:02Z/2026-07-28T13:40:11Z",
  "scope_questions": [
    {"id": "Q1", "question": "...", "status": "answered", "findings": ["f-1"]}
  ],
  "bluf": {"text": "...", "grade": "B2", "would_change": "..."},
  "findings": [],
  "entities": [],
  "events": [],
  "negative_results": [
    {"type": "company", "value": "...", "source": "...",
     "query": "...", "checked": "2026-07-28T11:00:00Z", "mode": "passive",
     "coverage": "yes", "informative": true}
  ],
  "hypotheses": [
    {"id": "H2", "hypothesis": "...", "status": "rejected", "basis": "...", "findings": ["f-3"]}
  ],
  "gaps": [
    {"scope_question": "Q3", "status": "unanswered", "missing": "..."}
  ],
  "next_collection": [
    {"id": "r-1", "action": "...", "closes": "Q3", "mode": "passive",
     "notifies_target": false, "cost": "free", "authority_needed": "none"}
  ],
  "evidence": [
    {"sha256": "...", "source_name": "...", "url": "...",
     "retrieved": "2026-07-28T09:14:02Z", "mode": "passive", "bytes": 18422,
     "cited_by": ["f-1"]}
  ],
  "source_reliability": [
    {"source_name": "...", "class": "corporate", "reliability": "A",
     "basis": "primary register", "findings": ["f-1"], "sole_support_for": []}
  ]
}
```

Generation rules:

- Apply the same redaction as the markdown. An export is a deliverable, not a debug dump.
- `handling` at the top level is the strictest handling of any included finding.
- Withheld findings appear with `"handling": "withheld"` and `claim` set to
  `"[withheld — <reason>]"`, the same string the markdown carries. Do not drop the object; its id
  is cited elsewhere.
- Sort `findings` by id, `events` by `ts`, `evidence` by `sha256`. Stable order makes diffs useful
  for change monitoring across report versions.
- `informative` on a negative result is `false` whenever `coverage` is `no` or `unknown`.
- Timestamps are UTC with `Z`. No local offsets anywhere.
- No key inside `findings[]`, `entities[]` or `events[]` without adding it to
  `${CLAUDE_PLUGIN_ROOT}/assets/entity-schema.json` first.

Rendering: the markdown report is the source of truth for humans. If the `make-pdf` skill is
installed, it renders the finished markdown; if the `diagram` skill is installed, it turns
section 8 into an editable chart. Neither is a dependency of this plugin — if either is absent,
ship the markdown and the mermaid source as they are. Neither step may change a claim, a grade,
or a redaction.

## Pre-delivery checklist

It ships inside the deliverable. Run the checklist at the end of
`${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` against the finished document, not from memory.

Mechanical checks worth running before the human pass:

| Check | How |
|---|---|
| Banned words | `grep -Einw 'clearly\|obviously\|proves\|definitely\|confirmed' report.md` |
| Ungraded findings | grep for `grade:` and count against the number of `### f-` headings |
| Orphan hashes | every 64-hex string in the report must exist as a filename stem in `evidence/` |
| Estimative drift | `grep -Ein 'probably\|possibly\|may \|could \|[0-9]+%' report.md` |
| Merged candidates | grep the report for every `cg-` id; each must appear with the word `unresolved` |
