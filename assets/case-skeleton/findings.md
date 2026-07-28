# Findings — case `<slug>`

Graded prose. Nothing enters this file without a source URL, a retrieval timestamp, and the
sha256 of an archived copy in `evidence/`. Ungraded sentences do not belong here at all, not in
an intro, not in a transition, not in a caveat.

Every finding is one block in the format below. Copy the blank template, fill every field,
append. Do not reorder or renumber blocks: `f-` ids are cited in `ledger.jsonl`, in the report,
and in other findings.

`f-` ids are lowercase and unpadded: `f-1`, `f-14`. `F-014` is not a valid id — the plugin's
`assets/entity-schema.json` rejects it. A `ledger.jsonl` row with `action: "finding"` puts the id
first in `result`: `f-3: <one-line summary>`. That is the only link between the ledger and this
file.

---

## Block format

### f-<n> — <short label, 6 words or fewer>

```
claim:      <one sentence, one claim, no conjunction hiding a second claim>
grade:      <Admiralty letter+digit, e.g. B2>
rung:       <observed | reported | correlated | inferred>
estimative: <ICD 203 phrase, or "none" if the claim is not probabilistic — exports as JSON null>
answers:    <Q<n> from scope.md, or "none — see gaps.md">
entities:   <e-<n>, e-<n>>
mode:       <passive | active>
handling:   <none | partial | withheld>

sources:
  1. <source name from sources.csv, or tool name>
     url:       <exact URL retrieved>
     retrieved: <ISO8601Z>
     sha256:    <64 hex chars of evidence/<sha256>.<ext>>
     source_grade: <A-F>
  2. ...

reasoning:  <two or three sentences at most. How the sources get you to the claim. Name the
             linking datapoint if this is an identity or attribution claim.>

alternatives:
  - <competing explanation> — rejected because <reason>

disconfirms: <the observation that would make this claim wrong, concrete enough to go look for>
```

### Field rules

| Field | Rule |
|---|---|
| `claim` | One sentence. If it needs "and", it is two findings. Present tense for state, past tense for events. |
| `grade` | Letter grades the source, digit grades the claim. Graded separately. Weakest source letter wins unless independent corroboration is argued in `reasoning`. |
| `rung` | How far the claim sits from something retrieved. See the ladder below. |
| `estimative` | Required whenever the claim is probabilistic. One of the seven ICD 203 phrases, no synonyms, no percentages. `none` only when a record was literally retrieved. |
| `answers` | The scope question this serves. A finding answering nothing is scope creep; move it to `gaps.md`. |
| `mode` | Whether the collection behind it was observable by the target. |
| `handling` | Redaction state as delivered. `withheld` findings are still cited by id. |
| `sources` | At least one, each with url + retrieved + sha256 + source grade. No sha256 means it is not a finding yet. |
| `disconfirms` | Mandatory. If nothing could disconfirm it, it is not a finding, it is a belief. |

### Inference rung ladder

Strongest to weakest. State the rung honestly; a report reader can discount a low rung, but
cannot detect a mislabelled high one.

| Rung | Means |
|---|---|
| `observed` | The value appears verbatim in an artifact archived in `evidence/`. |
| `reported` | A source asserts it; the underlying artifact was not retrieved. |
| `correlated` | Two or more independently retrieved artifacts agree on a named linking datapoint. Name it. |
| `inferred` | No source states it; it follows from pattern, structure, timing, or absence, **plus one stated assumption with its falsifier**. See the `inferred` sentence pattern in the plugin's `references/41-confidence.md`. |

`speculated` exists on the ladder but may never be written in this file; it belongs in `gaps.md`.

### Grade reference

Source: `A` completely reliable - `B` usually reliable - `C` fairly reliable -
`D` not usually reliable - `E` unreliable - `F` cannot be judged.

Claim: `1` confirmed by independent sources - `2` probably true - `3` possibly true -
`4` doubtful - `5` improbable - `6` cannot be judged.

`1` requires genuinely independent sources. Two outlets syndicating one wire story are one
source. Three sites scraping the same registry are one source.

### Estimative language

`almost no chance` 01-05 - `very unlikely` 05-20 - `unlikely` 20-45 -
`roughly even chance` 45-55 - `likely` 55-80 - `very likely` 80-95 -
`almost certain` 95-99.

Banned anywhere in this file: "clearly", "obviously", "proves", "definitely", and "confirmed"
unless the claim digit is `1`.

---

## Worked example — delete before use

### f-1 — Shared registrant across two domains

```
claim:      example-one.test and example-two.test were registered through the same registrar
            account within a four-minute window.
grade:      B2
rung:       correlated
estimative: none
answers:    Q1
entities:   e-3, e-4
mode:       passive
handling:   none

sources:
  1. Example Registry WHOIS export
     url:       https://example.test/whois/example-one.test
     retrieved: 2026-07-28T09:14:02Z
     sha256:    3f786850e387550fdab836ed7e6dc881de23001b3ffa10c46f88b3d20b9f6b1a
     source_grade: B
  2. Example Registry WHOIS export
     url:       https://example.test/whois/example-two.test
     retrieved: 2026-07-28T09:14:41Z
     sha256:    89e6c98d92887913cadf06b2adb97f26cde4849b3b9ff0e0f0e8e0b7b3b6a1c2
     source_grade: B

reasoning:  Both records carry identical creation timestamps to the minute and the same
            registrar identifier. The linking datapoint is the registrar-assigned account
            reference field, present in both records and not derivable from either alone.

alternatives:
  - Coincidental bulk registration by unrelated customers of the same registrar — rejected
    because the account reference field matches, not merely the registrar.
  - Registrar-side data artifact — not excluded; would require a second registry view to rule
    out, recorded in gaps.md.

disconfirms: A registrar statement, or a second independent registry view, showing the account
             reference field is shared across all customers rather than per-account.
```

### f-2 — Attribution held open

```
claim:      The examplehandle accounts on Platform A and Platform B belong to the same person:
            roughly even chance.
grade:      C3
rung:       inferred
estimative: roughly even chance
answers:    Q2
entities:   e-7, e-8
mode:       passive
handling:   partial

sources:
  1. Platform A public profile
     url:       https://platform-a.test/examplehandle
     retrieved: 2026-07-28T10:02:11Z
     sha256:    a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90
     source_grade: C
  2. Platform B public profile
     url:       https://platform-b.test/examplehandle
     retrieved: 2026-07-28T10:03:50Z
     sha256:    b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1
     source_grade: C

reasoning:  Assuming the handle is not a common dictionary word reused independently, it is
            roughly even chance that e-7 and e-8 are the same person. Basis: string identity
            only — no shared avatar hash, no cross-link, no overlapping contact selector. The
            assumption fails if the handle appears on more than a handful of unrelated
            platforms. e-7 and e-8 remain in candidate_group cg-1 and are not merged.

alternatives:
  - Two unrelated users who picked the same common handle — not excluded and not unlikely for
    a short dictionary-word handle.

disconfirms: Either profile linking to a different, non-overlapping identity; or a registration
             date on one account predating the other's stated first use in a way the same
             person could not produce.
```

---

## Blank block — copy this

### f-<n> — <label>

```
claim:
grade:
rung:
estimative:
answers:
entities:
mode:
handling:

sources:
  1. <source name>
     url:
     retrieved:
     sha256:
     source_grade:

reasoning:

alternatives:
  -

disconfirms:
```

---

## Findings index

Keep this table in sync. It is what the report compiler reads first.

| id | claim (short) | grade | rung | answers | handling |
|---|---|---|---|---|---|
| f-1 | | | | | |
