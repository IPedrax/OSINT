# Gaps — case `<slug>`

Three sections, in this order. Negative results are logged as they happen, not reconstructed at
the end. This file is as load-bearing as `findings.md`: it is what prevents re-work, what makes
absence of evidence reportable, and what a second analyst reads before touching the case.

An empty section is a claim. If nothing was checked and found empty, say so explicitly rather
than leaving the table blank.

---

## 1. Negative results — checked, found nothing

One row per check that returned nothing. A negative result needs the same provenance as a
finding: what was queried, where, when, and whether the absence is meaningful.

`coverage` is the honest bit. A source that does not cover the target's jurisdiction, era, or
language returning nothing tells you about the source, not the target.

| # | selector checked | value | source | query | when (ISO8601Z) | mode | result | coverage | meaning of absence |
|---|---|---|---|---|---|---|---|---|---|
| n-1 | `<type>` | `<value, redacted if needed>` | `<sources.csv name>` | `<exact query>` | | `passive` | none | `<covers target? yes/partial/no/unknown>` | `<informative \| uninformative>` |

### Notes on specific negatives

```
n-1: <why this absence does or does not support a finding. If it supports one, the finding goes
      in findings.md with the negative result as its source and an explicit estimative phrase.>
```

Rules:

- A negative result with `coverage: no` or `coverage: unknown` may never be cited as evidence
  that something does not exist. It is a gap, not a finding.
- A negative result with `coverage: yes` against an authoritative register can support a finding
  ("no company by that name is registered in `<jurisdiction>`", graded on the register).
- Every row here must also exist as a `ledger.jsonl` row with `result: "none"`. This table is
  the human-readable view; the ledger is the record.

---

## 2. Open questions — mapped to scope

Every scope question gets a row, answered or not. A question with no findings against it is the
most important line in the deliverable.

| scope Q | question (short) | status | findings so far | what is missing |
|---|---|---|---|---|
| Q1 | | `answered \| partial \| unanswered \| unanswerable` | `f-1, f-3` | `<the specific datapoint that would close it>` |
| Q2 | | | | |
| Q3 | | | | |

`unanswerable` needs a reason on its own line below, and the reason must be structural (record
does not exist, jurisdiction does not publish it, the artifact is gone) rather than "ran out of
time" — that is `unanswered`.

```
Q<n> unanswerable: <structural reason>
```

### Questions raised by the work, not in scope

Questions the collection surfaced that `scope.md` does not authorize. Record them; do not
answer them. This list is the input to a scope amendment or a follow-on case.

```
- <question> — would require <what>, currently out of bounds per scope.md section 6
```

### Unresolved identities

Candidate groups still open. Never merged without a named linking datapoint. Each open item in
this file carries a `G-<n>` id so findings can cite it.

| id | candidate_group | member entities | what they share | named datapoint that would resolve it | what would break the link |
|---|---|---|---|---|---|
| G-1 | cg-1 | e-7, e-8 | | | |

---

## 3. Recommended next collection

Ranked. Highest information-per-cost first. Each row must name the scope question it closes, or
it does not belong on the list.

| # | action | selector in | selector out | closes | mode | notifies target | cost | auth needed | expected yield |
|---|---|---|---|---|---|---|---|---|---|
| r-1 | `<what to do, specifically>` | `<type>` | `<type>` | Q2 | `passive` | no | `free \| free_key \| paid: <amount> \| analyst hours: <n>` | `<none \| account \| scope amendment \| legal review>` | `<high \| medium \| low>` |

Cost vocabulary, use these words:

| Cost | Means |
|---|---|
| `free` | Public, no account, no money |
| `free_key` | Free API key or free account required |
| `paid: <amount+currency>` | Money, stated |
| `analyst hours: <n>` | Human time, stated |
| `blocked` | Cannot be done under current scope or authority |

Anything `mode: active` also needs `active_allowed: yes` in `scope.md` and a fresh confirmation
naming the action. Anything `notifies target: yes` needs an explicit decision from the requester
that the target learning of the inquiry is acceptable.

### Not recommended

Actions deliberately not proposed, so nobody proposes them later assuming they were overlooked.

```
- <action> — not recommended because <out of bounds \| notifies target \| poor yield \| illegal in jurisdiction>
```

---

## Stop condition check

Fill this before compiling a report. If both answers are yes, the case stops.

```
Every scope question is answered, partial, or unanswerable:   <yes | no>
The next-collection list contains no free, passive, high-yield row:  <yes | no>
```

If the second is `no`, run those rows before delivering. Cheap passive collection left on the
table is not a gap, it is unfinished work.
