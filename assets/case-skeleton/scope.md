# Scope — case `<slug>`

**This file is frozen once the case opens.** It is written once, at intake, before any
collection. After the first row is appended to `ledger.jsonl`, do not edit it. If the scope
must change, close this case and open a new one, or append an `amendment` block at the bottom
with its own timestamp and signature — never overwrite an answer. Every later step is checked
against this file instead of re-asking the analyst, so an edited scope silently rewrites the
authority under which work already happened.

Fill every field. `unknown` is an acceptable answer; blank is not.

`case_init.py` fills what the intake gate collects: case_id, opened, branch, target, target_type,
target_category, authority, jurisdiction, the numbered questions, the decision line, out-of-bounds,
active_allowed, and the §9 gate-result block. The remaining slots — `requester`, `analyst`,
`period_covered`, `classification`, `authority_ref`, `legal_review`, §7's technique checklist and
signature block, and §8 handling and retention — are the analyst's to complete, and they ship as
visible `<placeholders>` on purpose so an unfilled one is obvious rather than silently absent.
An unsigned §7 means `active_allowed: no` no matter what §7 says.

---

## 1. Purpose branch

Select exactly one. The branch sets default plays, expected authority, and gate strictness.

```
[ ] security         Security / threat intel, pentest recon, DFIR, brand protection
[ ] journalism       Journalism / investigation, public-interest reporting
[ ] kyc              Due diligence, KYC-AML, sanctions screening, counterparty checks
[ ] self_audit       Self-audit of the requester's own footprint or own assets
[ ] education        Education / CTF against sanctioned lab targets only
```

| Branch | Default play order | Authority expected | Gate strictness |
|---|---|---|---|
| `security` | infra -> media -> crypto | Engagement letter, scope document, or own-asset claim | Active steps need per-action confirmation |
| `journalism` | verify -> geoint -> corporate -> identity | Editorial assignment or publication | Public-interest test required on any private individual |
| `kyc` | corporate -> identity -> adverse media | Compliance mandate or client engagement | PII minimization enforced hard |
| `self_audit` | identity -> infra -> media | Self, trivially satisfied | Relaxed; no external-target plays |
| `education` | any, sanctioned targets only | CTF scope document or lab domain | Live third-party targets refused outright |

Selected branch: `<security|journalism|kyc|self_audit|education>`

---

## 2. Case identity

| Field | Value |
|---|---|
| `case_id` | `<slug, kebab-case, no personal names>` |
| `opened` | `<ISO8601Z>` |
| `requester` | `<name or role, and organization>` |
| `analyst` | `<name or handle of whoever runs this case>` |
| `period_covered` | `<earliest>..<latest>, or "no time bound"` |
| `classification` | `<handling label your organization uses, or "internal only">` |

`case_id` appears in every deliverable. Do not name it after a target individual.

---

## 3. Target

| Field | Value |
|---|---|
| `target` | `<the selector or name the case starts from>` |
| `target_type` | `<canonical selector type: domain, company, username, email, person_name, ...>` |
| `target_category` | `<org \| public-figure \| self \| private-individual>` |

`target_category` drives the gate more than `purpose` does.

- `private-individual` plus a non-institutional requester: refuse location, movement, and
  daily-pattern work. Everything else needs a stated reason it is necessary.
- Any target who is a minor: refuse the case. Do not open it, do not scaffold it.
- `self`: the requester must be the subject. Take the claim, record it here, move on.

Additional in-scope selectors known at intake (one per line, canonical types only):

```
<type>: <value>
<type>: <value>
```

---

## 4. Authority

| Field | Value |
|---|---|
| `authority` | `<what permits this work: engagement letter, assignment, mandate, self>` |
| `authority_ref` | `<document name, ticket, contract number, or "verbal, recorded here">` |
| `jurisdiction` | `<requester jurisdiction>` / `<target jurisdiction(s)>` |
| `legal_review` | `<yes, by whom \| no \| not required, why>` |

Jurisdiction is recorded because it changes what is legal to collect, not for the header.
Registry access, company data, and personal-data handling differ per country; note anything
already known to be restricted in `out_of_bounds`.

---

## 5. Question

The case answers questions, not a person. One line each, numbered, answerable, falsifiable.
Findings are later mapped back to these numbers, and a finding that answers none of them is
scope creep.

```
Q1. <question>
Q2. <question>
Q3. <question>
```

Decision this feeds: `<what the requester will do differently depending on the answer>`

If that line cannot be filled, stop. A case with no decision attached has no stop condition
and will collect until someone gets bored.

---

## 6. Out of bounds

Explicit exclusions. Anything listed here is refused for the life of the case even if the
requester later asks for it in passing. Add the branch-specific defaults, then case specifics.

```
[x] household members and minors in the household
[ ] associated parties, officers and shareholders
[x] minors, including any account that appears to belong to one
[x] home address, physical location, and movement patterns
[ ] employer or colleagues not named in the question
[x] health, religion, sexual orientation, political affiliation, union membership
[x] non-public breach corpora and purchased credential dumps
[x] authentication, rate-limit, or CAPTCHA circumvention
[x] any contact with the target or with people around the target
[ ] <case-specific exclusion>
[ ] <case-specific exclusion>
```

Branch dependency, stated once so it is not carried in the reader's head: `associated parties,
officers and shareholders` and `employer or colleagues not named in the question` default **off**
for `kyc` — UBO tracing, connected-party and PEP relationship screening are that branch's subject
matter — and default **on** for every other branch. `case_init.py` ticks them for you outside
`kyc`.

The seven standing exclusions ship checked. Unchecking one requires a one-line reason on the same
line naming what in the recorded question needs it.

Not collected by design (state this in the report, do not hide it):

```
<data class deliberately not gathered> — <why>
```

---

## 7. Active collection

`passive` means the target cannot observe the collection. `active` means the target or a third
party can observe it, or state changes somewhere: direct connections to target infrastructure,
port scans, live WHOIS against target-controlled name servers, account-existence probes,
password-reset flows, profile views on platforms that notify, joining anything, sending
anything.

Every play defaults to passive. Active steps require both `active_allowed: yes` below and a
fresh confirmation naming the specific action at the moment it is run.

```
active_allowed: <yes | no>
```

If `yes`, list the specific active techniques authorized. An unlisted technique is not
authorized by this line.

```
[ ] live DNS / WHOIS queries against target-controlled infrastructure
[ ] TCP port and service enumeration of in-scope hosts
[ ] HTTP retrieval directly from target-owned hosts (not via cache or archive)
[ ] account-existence checks on platforms that do not notify the account holder
[ ] <other, named precisely>
```

In-scope network ranges and hostnames for active work, verbatim from the engagement document:

```
<host, CIDR, or domain>
```

Blackout windows, rate ceilings, and abort contact:

```
window:  <when active work may run>
ceiling: <requests per second or per hour agreed>
abort:   <who to call, how, to stop immediately>
```

### Authorization signature

Signed by the person with authority to permit active collection against these targets.

```
name:      ____________________________________
role:      ____________________________________
signed:    ____________________________________   date: ______________
```

Unsigned means `active_allowed: no`, regardless of what is written above. An analyst may not
sign their own authorization unless `purpose = self_audit` and the assets are their own.

---

## 8. Handling and retention

| Field | Value |
|---|---|
| `deliverable` | `<report format and audience>` |
| `redaction_default` | `<full \| partial \| identifiers-withheld>` (default: partial) |
| `share_with` | `<who receives the report>` |
| `retention` | `<how long the case dir is kept, and who deletes it>` |
| `evidence_handling` | `<where evidence/ lives, whether it may leave this machine>` |

Reports redact by default. `redaction_default: full` needs a reason on the next line.

---

## 9. Intake gate result

Filled by whoever ran the gate, then frozen.

| Field | Value |
|---|---|
| `gate_run_by` | `<main session \| analyst name>` |
| `gate_ts` | `<ISO8601Z>` |
| `gate_result` | `<accepted \| accepted-with-limits \| refused>` |
| `limits_imposed` | `<what was narrowed and why, or "none">` |
| `refusal_reason` | `<one line, if refused>` |

A refused intake is recorded in `cases/_refusals.jsonl`, not here — no case directory is created
for a refused request. `/osint:osint-scope` §4 is authoritative on that.

---

## Amendments

Append only. Never edit the sections above.

```
amendment 1
ts:        <ISO8601Z>
changes:   <field> from <old> to <new>
reason:    <why>
authority: <who authorized the change>
signed:    ____________________________________
```
