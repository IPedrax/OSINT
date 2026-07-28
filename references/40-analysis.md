*Load when: more than one explanation fits the evidence, identity is in doubt, a branch is producing diminishing returns, or before compiling any report. Also load when the requester has supplied a theory to confirm.*

# Structured analysis

A model doing OSINT fails in a specific direction: it builds one coherent story fast, then spends
the rest of the run decorating it. Everything below exists to interrupt that.

## Analysis of Competing Hypotheses

Run ACH whenever attribution, control, identity, intent, or a causal claim is at stake. Do not run
it on questions of fact that a collection step settles.

### Procedure

1. **Enumerate hypotheses before re-reading the evidence.** Minimum three. Mandatory inclusions:
   the mundane explanation (coincidence, shared infrastructure, common name, ordinary commercial
   relationship); the null hypothesis "the evidence is insufficient to distinguish"; and, whenever
   identity is in question, "the selectors belong to two different real-world entities". Hypotheses
   must be mutually exclusive as written — if two can both be true, split or merge them. The null
   is exempt: it is a claim about the evidence, not a state of the world, so it is never scored as
   a row and is reported as an output state instead.
2. **List every datapoint as a row**, by finding id, with its grade and rung. Include arguments,
   assumptions, and **absences** (a negative result is a row). Include datapoints that came from
   the requester.
3. **Score each cell against each hypothesis** using the notation below. Score the cell by asking
   "if this hypothesis were true, would I expect to see this?" — never "does this fit my
   favourite?".
4. **Delete non-diagnostic rows.** Any row scoring identically across all hypotheses discriminates
   nothing and must be struck from the matrix. These are usually the rows that feel most
   convincing, because they are consistent with the favoured hypothesis — and with every other one.
5. **Rank by disconfirmation, not by fit.** The surviving hypothesis is the one with the fewest and
   weakest inconsistencies. A hypothesis with ten `+` and one `--` from an `A1` source is in worse
   shape than one with two `+` and no inconsistency.
6. **Weight by grade.** A `--` from `A1` outweighs any number of `+` from `C3`. Never total the
   symbols as if they were equal.
7. **Report all hypotheses with their status**, not just the leader. A report that names one answer
   and hides the others is not an ACH output.
8. **Name falsifiers and milestones.** For each surviving hypothesis, the specific observation that
   would kill it, and whether that observation is collectable now, `passive` or `active`.

### Notation

| Symbol | Meaning |
|---|---|
| `++` | Strongly consistent — expected if this hypothesis holds and hard to explain otherwise |
| `+` | Consistent |
| `N` | Neutral — no bearing |
| `-` | Inconsistent |
| `--` | Strongly inconsistent — near-fatal to this hypothesis |
| `?` | Cannot be scored; states why in the notes column |

### Worked matrix

Question: who operates `domain` `acme-billing.example`?

- H1: operated by ACME Ltd itself.
- H2: operated by a managed-service provider on ACME Ltd's behalf.
- H3: unrelated party, lookalike domain.
- H4: insufficient evidence to distinguish.

H4 is not a column: the null is an output state, not a row-scored hypothesis.

| # | Datapoint | Grade | Rung | H1 | H2 | H3 | Note |
|---|---|---|---|---|---|---|---|
| f-1 | `ssl_cert` in CT log carries ACME Ltd in the organization field, OV-validated | A1 | observed | `++` | `+` | `--` | OV validation requires the CA to check the org against a registry |
| f-2 | MX records point to a shared multi-tenant provider | B2 | observed | `+` | `+` | `+` | Non-diagnostic — strike |
| f-3 | Registrant fields privacy-proxied | B3 | observed | `+` | `+` | `+` | Non-diagnostic — strike |
| f-4 | Site footer names ACME Ltd | C3 | reported | `+` | `+` | `+` | A lookalike copies the footer. Feels strong, discriminates nothing — strike |
| f-5 | Nothing on ACME Ltd's primary `domain` links to this one | B2 | observed | `-` | `-` | `+` | Subject-controlled complete absence — weak; companies routinely do not link their own properties |
| f-6 | Hosting `netblock` differs from ACME Ltd's other properties | B2 | correlated | `-` | `++` | `+` | |

After striking f-2, f-3, f-4 the matrix is f-1, f-5, f-6. H3 dies on f-1 (`--` from `A1`). H1
carries two inconsistencies. H2 carries one inconsistency and one `++`. Output: H2 is `likely`,
H1 is `unlikely`, H3 is `very unlikely`, and H4 is not supported — three surviving rows do
discriminate between the three. The falsifier for H2 is named: a `company` relationship between
ACME Ltd and the MSP, checkable in filings or the MSP's own client list, `passive`.

Note that the intuitive answer, H1, is the one the footer supported, and the footer was struck.

## Key Assumptions Check

Run before the first pivot and again before compiling. List every assumption the current line of
analysis rests on, including the ones inherited from the requester's framing.

Columns, one row per assumption:

| Assumption | Why held | Confidence | Falsifier | Impact if wrong |
|---|---|---|---|---|
| ADDRESS is an operating address, not a formation agent's premises | It is the registered office on the filing and nothing yet says otherwise | `roughly even chance` | The agent's own client list, or a count of other companies registered at ADDRESS | Every `correlated` finding resting on the shared `address` drops to a Tier-3 coincidence |

Prompts that surface hidden assumptions:

- What must be true for this conclusion to hold that nobody has checked?
- Which assumption came from the requester rather than from a source?
- Which assumption was true at some earlier date and is being carried forward? Company officers,
  DNS records, employment, and infrastructure all change; the record's date is not today.
- Would this assumption hold in this jurisdiction, or is it imported from another one? Registry
  coverage, name conventions, address formats, and privacy defaults are all jurisdiction-specific.
- If this assumption is wrong, which findings collapse? Any assumption whose failure kills three or
  more findings is a single point of failure and gets its own collection step.
- Is the assumption doing work that a five-minute passive check would remove?

## Quality of Information Check

Per source in the case, before it supports anything:

| Check | Fail condition |
|---|---|
| Provenance | Cannot name who produced the record and how |
| Primary or derived | Derived, and the primary was reachable but not fetched |
| Content date vs retrieval date | Only the retrieval date is recorded |
| Coverage | Source's population and sampling are undisclosed, yet an absence is being read from it |
| Single-sourced | Every supporting source collapses to one under the independence tests in `41-confidence.md` |
| Translation | Quoted text is machine-translated and the original string was not preserved |
| Manipulability | Source is subject-controlled or open-submission, and this is not stated |
| Persistence | Not archived; no sha256 in `evidence/` |
| Mode | `passive`/`active` not recorded |

Any fail either downgrades the grade or turns the item into a `gaps.md` entry. It does not get
written to `findings.md` unbadged.

## Failure modes of an LLM doing OSINT

Each countermeasure is a check to run, not an intention to hold.

- **Name collision treated as identity.** Two records share a `person_name`, and subsequent
  reasoning silently treats them as one person.
  Countermeasure: before any `person_name` is used as a link, run the entropy test — count
  distinct individuals returned for that name in that jurisdiction. Record the count as a finding.
  If it is above a handful, `person_name` contributes zero linking weight and the entities stay in
  a `candidate_group`.

- **Plausible-but-unverified detail asserted as fact.** A registration number, incorporation date,
  job title, or middle initial appears in the output with no source, because it fit the pattern.
  Countermeasure: every proper noun, number, and date in `findings.md` must trace to a ledger row
  with a `result_sha256`. Before compiling, grep the draft for digits and capitalised tokens and
  confirm each has a citation. Anything unsourced is deleted, not softened.

- **Inference laundered into a finding across a summarisation step.** An `inferred` claim written
  with a hedge in step 4 reappears as flat fact in the step-9 summary.
  Countermeasure: summaries are re-derived from `findings.md` and `ledger.jsonl`, never from your
  own earlier prose. Every summary line carries the grade and rung of the finding it compresses. A
  summary line without a grade is a defect.

- **Over-weighting whatever was found first.** The first coherent source sets the frame and later
  contradictory evidence is read as noise.
  Countermeasure: in the ACH matrix, score rows in reverse discovery order. Separately, ask of the
  earliest source: if this had arrived last, would it change anything? If no, it was anchoring.

- **Stopping at the first coherent story.** One explanation accounts for the evidence, so
  collection stops and the alternatives are never enumerated.
  Countermeasure: no conclusion is written until at least two alternatives have been named and
  scored, one of them mundane. Coherence is not evidence — a single narrative is what a model
  produces by default, whether or not it is true.

- **Confusing "no results" with "does not exist".** An empty response becomes "the person has no
  corporate footprint".
  Countermeasure: every negative result is written as "source S, query Q, at TS, returned none",
  plus a coverage judgement. Authoritative absence requires a complete-coverage source where
  registration is mandatory. Otherwise the finding is about the source, not the target.

- **Inventing an endpoint or a record.** A plausible API path, query parameter, or record layout is
  produced from pattern, then reasoned over as if it returned data.
  Countermeasure: only endpoints marked `verified=yes` in `sources.csv` are called directly;
  everything else is reached through its homepage, and a `fetchable=no` row needs a browser rather
  than a burnt HTTP call. If `sources.csv` is absent from a build, no endpoint is verified — reach
  every source through its homepage. A tool call that failed is a `gaps.md`
  entry, never a summarised result. Never describe a record you did not retrieve.

- **Treating a machine translation as the source text.** A translated phrase is quoted as if it
  were what the document says, and a term of art shifts meaning.
  Countermeasure: apply the Machine translation row in `41-confidence.md`'s source-class table.
  Legal, financial, and status terms (liquidation vs dissolution, beneficial vs registered owner)
  are re-checked against the jurisdiction's own vocabulary.

- **Accepting a data broker's aggregation as corroboration.** The broker already merged records
  from several places, so its output looks like multiple agreeing sources.
  Countermeasure: apply the aggregator row and the two class-level overrides in
  `41-confidence.md`'s source-class table. An aggregator is one source, capped at credibility 3,
  never a merge basis.

- **Adopting the requester's hypothesis.** The intake framing names a suspect or a conclusion, and
  collection becomes a search for supporting material.
  Countermeasure: the requester's theory enters the ACH matrix as one hypothesis among the
  minimum three, and its datapoints are graded as `reported` from an interested party. State
  explicitly in the report which findings originated with the requester.

- **Silent scope drift.** Each pivot is individually reasonable; the aggregate is a dossier nobody
  asked for.
  Countermeasure: every ledger `query` starts with the scope question id it advances. A step with
  no id is not run. Before compiling, list the scope questions and check every finding maps to one;
  findings that map to none are deleted from the report, not filed away.

## Identity-confusion protocol

### How `candidate_group` works

- Every entity row is append-only. Two records that *might* be the same real-world thing get
  **two** rows with distinct `id`s and a shared `candidate_group` value `cg-<n>`.
- Nothing is ever edited or overwritten. A merge is a new appended row that names the linking
  datapoint, its source, and its grade; a split is a new appended row that names the contradiction.
- While a `candidate_group` is unresolved, no finding may attribute an attribute of one member to
  another, and no report may render the group as one person or one `company`.
- A `candidate_group` with an unresolved status at report time is reported as unresolved. This is a
  result, not an omission.

### Linking datapoint strength

| Tier | Datapoints | Merge authority |
|---|---|---|
| 1 | `company_number` issued by a registry and present in two primary records · a platform-issued immutable account identifier appearing on two `social_profile` records (numeric id, not display name) · demonstrated key control over a `crypto_address` (valid signature) · identical `file_hash` · a government-issued identifier in a primary record | One is sufficient, if the carrying source is grade A or B |
| 2 | Rare `username` reused across platforms (entropy-tested) · `email` appearing as the contact on two independent records · `phone` in two independent records · identical `ssl_cert` key fingerprint across two `domain` · a commit `email` tying a `username` to a `person_name` · `address` plus `person_name` in a primary record · a shared registrar-assigned account reference across two registry records | Two independent Tier-2 datapoints, from sources that pass the independence tests |
| 3 | `person_name` match, however unusual · self-reported employer, city, or school · `photo` similarity · writing style · temporal co-occurrence of posts · shared `ip` or `netblock` on shared hosting · an aggregator asserting the link · shared registrar or hosting provider · shared `address` at a formation agent, virtual office, or shared premises | Corroborative only. Never a merge basis, at any quantity |
| 4 | Any name collision · shared common surname · shared `asn` at a cloud or CDN provider · broker "possible relatives" · a subjective sense that it is the same person | No weight. Not recorded as a link at all |

Rules:

- A merge needs a **named** datapoint: its type from the canonical vocabulary, its literal value,
  its source, its retrieval timestamp, and its grade. "Multiple weak signals" is not a name.
- Tier-3 datapoints do not add up. Five Tier-3 matches remain a `candidate_group`.
- Any Tier-1 contradiction splits the group immediately — two different dates of birth in two
  primary records, mutually exclusive locations at one timestamp, two distinct platform account ids.
- Selector reuse is not identity: shared infrastructure, recycled `phone`, resold `domain`,
  transferred `username`, and family members sharing an `address` all produce true matches with
  false implications. Date every datapoint and check the windows overlap.

### When two candidates cannot be separated

Do not pick. Write it as a finding:

> **Unresolved identity — `cg-4`.**
> grade `C3` · rung `correlated`
> Two candidates match the selectors collected: `e-12` (`person_name` N, ADDRESS-1, source S1,
> retrieved TS) and `e-19` (`person_name` N, ADDRESS-2, source S2, retrieved TS). The shared
> datapoints are `person_name` (Tier 3; the name returns 40+ distinct individuals in this
> jurisdiction, f-13) and city of residence (Tier 3). No Tier-1 or Tier-2 datapoint separates or
> joins them. No identity claim is made here. Findings f-20 and f-21 apply to `cg-4` as a whole
> and to neither candidate individually. Resolvable by: `company_number` on the filing at S3
> (`passive`, available); platform account id (`active`, not authorized).

Then: report both candidates, attribute nothing to either, and name the check that would resolve
it. A wrong merge is the most damaging error this plugin can make — it is the mechanism by which
an uninvolved person acquires someone else's history.

## Stop conditions and the anti-rabbit-hole rule

Every collection step names the scope question it advances, in the ledger `query` field, prefixed
`Q<n>:`. If naming the question takes more than one sentence, the step is not justified.

| Test | Rule |
|---|---|
| Relevance | No scope question id, no step |
| Depth | Three pivots from the seed selector. Deeper requires a Tier-1 or Tier-2 link at the boundary, recorded |
| Breadth | The question selects which pivots run. `10-pivot-matrix.md` enumerates them; take the ones the question needs and name each explicitly. Never enumerate all of them |
| Diminishing returns | Three consecutive steps on one branch producing no new entity or event at `C3` or better closes the branch |
| Sufficiency | If the scope question can be answered now at the grade the purpose requires, stop. Available is not the same as needed |
| Cost of noticing | Never take an `active` step to improve a probability word that a `passive` step already settles |
| Minimization | A step that would collect PII beyond the question is not run, whatever it might yield |

Declare a gap instead of continuing when: the answer needs a non-public source; a paid source that
is not available; an `active` step that scope does not authorize; a jurisdiction whose records are
not reachable; or a category the global gate refuses. A named gap is a deliverable. An unbounded
search is not.

## Deconfliction and negative results

"Checked X, found nothing" is a finding. It bounds the search, stops the next run repeating the
query, and is sometimes evidence about the target: absence from a registry where registration is
mandatory means something, absence from a dataset of undisclosed coverage means nothing.

| Absence type | Requirement | Reads as |
|---|---|---|
| Authoritative | Complete-coverage source, mandatory registration, current index | Evidence about the target |
| Subject-controlled | A source the subject controls and which is complete for its own contents (a company's own site for its own links) | Weak evidence about the target — subjects routinely omit their own properties. Never carries a conclusion alone |
| Non-authoritative | Partial, sampled, or undisclosed coverage | Evidence about the source only |

Write every negative result to `gaps.md` with: gap id, the scope question id, the selector type and
value queried, source name and endpoint, the query string verbatim, retrieval timestamp, `none` as
the result, the absence type, whether a re-check is worthwhile and on what trigger, and what
observation would change the answer. Append the matching `ledger.jsonl` row with `"result":"none"`
and `"result_sha256":null`.

Before collecting anything, grep `gaps.md` and `ledger.jsonl` for the selector value. A repeated
query is wasted budget, and against an `active` source it is a second notification to the target.

## Pre-report checklist

Run before compiling anything. Every item is a check with a pass/fail, not a reminder.

1. Every finding carries a grade, a rung, at least one source, a retrieval timestamp, a
   `result_sha256`, and `passive`/`active`.
2. No banned word appears: "clearly", "obviously", "proves", "definitely", "confirmed" outside a
   credibility-1 finding.
3. No sentence contains both an estimative term and a numeric percentage.
4. No estimative term is attached to an `observed` or `reported` rung.
5. No probability is assigned to a claim a listed `passive` step would settle.
6. Every credibility 1 or 2 survived the four independence tests and the circular-reporting check.
7. Every `inferred` finding states its assumption and its falsifier.
8. No `speculated` item appears in `findings.md`.
9. Every proper noun, number, and date traces to a ledger row.
10. Every `candidate_group` is either resolved with a named Tier-1 or two Tier-2 datapoints, or
    reported as unresolved with both candidates shown.
11. At least two alternative hypotheses were named and scored for every attribution or identity
    conclusion, and their status is reported.
12. Findings that originated with the requester are labelled as such.
13. Every finding maps to a recorded scope question; the rest are dropped.
14. Every negative result is in `gaps.md` with its absence type.
15. Every `active` step in the ledger has `active_allowed: true` in scope and a recorded
    confirmation naming that action.
16. PII in the report is the minimum the question needs, and redacted by default.
