*Load when: running the intake gate, judging whether a request is in bounds, screening a pivot for legal risk, or drafting a refusal.*

# Legal and ethics reference

Authorization and legality govern every case. The gate runs **once** at intake, is written to
`scope.md` and `ledger.jsonl`, and is referenced thereafter — not re-litigated at each step. A
tool that nags gets bypassed. This file is the source for the gate, the branches, the hard stops,
the jurisdiction rules, PII minimization, and refusal wording.

## 1. Intake gate fields

Recorded verbatim in scope. Field names are fixed; do not rename or add one. A field is not
"answered" until the answer is specific enough to act on.

| Field | Captures | Type |
|---|---|---|
| `purpose` | Declared branch: `security` / `journalism` / `kyc` / `self_audit` / `education` | enum |
| `target` | The selector(s) the case is about — a `domain`, `company`, `person_name`, `email`, etc. | string |
| `target_category` | `org` / `public-figure` / `self` / `private-individual` | enum |
| `authority` | Evidence the requester may run this collection (see §2) | string |
| `jurisdiction` | Where target, requester, and data subjects sit; drives §4 | string |
| `question` | The one question the case answers. Collection is scoped to this, not to the person | string |
| `out_of_bounds[]` | Named things the requester declares off-limits up front | list |
| `active_allowed` | Boolean. `false` by default. Gates every `active` step | bool |

`out_of_bounds[]` defaults to empty — an empty list is a complete answer. `jurisdiction` may be
recorded as `unspecified` when `target_category` is `org` and no §4 regime is engaged; it blocks
the gate only when the target or a data subject is a natural person. Only `purpose`, `target`,
`target_category`, `authority`, and `question` block the gate.

### What a satisfactory answer looks like, by audience

| Field | Security / threat-intel | Journalism | KYC-AML | Self-audit | Education / CTF |
|---|---|---|---|---|---|
| `target` | Asset, domain, or actor inside the engagement | Named subject or entity of the story | Client, counterparty, or beneficial owner | The requester's own selectors | A sanctioned lab target or CTF handle |
| `target_category` | `org` or actor infra; rarely `private-individual` | Often `public-figure` or `org`; `private-individual` only on public-interest test | `org` or `private-individual` as a business principal | `self` only | `org` (lab asset) or `self`; sanctioned targets only |
| `authority` | Engagement letter / scope doc / own-asset claim | Editorial assignment or commissioning outlet | Compliance mandate or client engagement | Self (trivially satisfied) | CTF scope doc or lab domain |
| `question` | "Which of these assets are exposed?" | "Did X do Y?" — a publishable claim | "Is this party who they claim, and are they sanctioned/PEP?" | "What of mine is exposed?" | "Solve the challenge / practise the pivot" |
| `active_allowed` | Sometimes true, per scope doc | Almost always false | False | False by default; true only if the user explicitly opts in for their own assets | False by default; true only if the user explicitly opts in for the sanctioned lab target |

A vague answer is a blocked gate. "A guy" is not a `target`. "Curiosity" is not a `question`.
"I just want to know everything about them" fails `question` and is a soft signal for §3.

## 2. Purpose branches — authority, scope, abuse pattern

Legitimate and explicitly supported: authorized pentest recon, threat intel, DFIR, brand
protection, journalism in the public interest, KYC/AML and corporate due diligence, sanctions
screening, missing-persons work by mandated parties, and self-audit.

When the declared purpose is on this list and authority is on the record, the gate passes — record
the fields and start collecting. Do not interrogate a request that has already answered the
question.

For each branch: the authority evidence that is normal in that field, what "in scope" ordinarily
means, and the characteristic abuse pattern to watch for behind a clean-looking request.

| Branch | Normal authority evidence | "In scope" usually means | Characteristic abuse pattern |
|---|---|---|---|
| **Security / threat-intel** | Signed engagement / statement of work; rules of engagement; own-asset ownership (registrant, ASN, account) | Assets and infrastructure named in the SoW; the actor attacking them; passive recon by default, active only where the SoW says so | "Pentest" framing pointed at a competitor's or ex-employer's estate the requester does not own; scope creep from the engaged domain to personal accounts of its staff |
| **Journalism** | Editorial assignment; a commissioning outlet; a public-interest rationale on the record | Entities and public figures where publication serves the public interest; private individuals only after a public-interest test that outweighs their privacy | Personal grievance dressed as a story; "exposing" a private individual with no public role; building a locate-able profile of a source's critic |
| **KYC-AML / due diligence** | Compliance mandate; client engagement; a regulatory obligation (onboarding, screening, EDD) | The counterparty as a business principal, its ownership chain, sanctions/PEP/adverse-media status; minimal PII, only what the risk question needs | Using regulated-purpose tooling to vet a tenant, employee, or date; harvesting family and lifestyle data beyond the risk question (see §4 FCRA) |
| **Self-audit** | Self. Trivially satisfied; still confirm the selectors are the requester's own | The requester's own footprint: their `email`, `username`, `domain`, exposed `breach_record`. No external-target plays | Someone routing a third-party target through the self-audit branch — check the selectors actually resolve to the requester |
| **Education / CTF** | CTF scope document; a lab/sandbox domain under the requester's or organizer's control | The sanctioned target only; teaching the pivot mechanics on data that was staged for it | A "for a class" or "for research" frame aimed at a live, non-consenting third party or their infrastructure |

Default plays per branch are in the router skill; this table is the authority test, not the play
list. When authority is weak but the request is otherwise clean, ask one specific question to firm
it up before collecting — do not refuse and do not proceed on a guess. That path never applies to
a §3 hard stop.

Mandated missing-persons or court-ordered locate has no branch of its own. Declare
`purpose: security`, `target_category: private-individual`, and record the mandate itself in
`authority` (court order, law-enforcement request, or instructing firm + matter reference). That
is the only route past §3.1. Absent the document, §3.1 refuses.

## 3. Hard stops

Refuse these outright. One line, plus the nearest legitimate alternative, no lecture (§7). These
are the global hard stops and must not be softened. Each is listed with why it is a stop,
the phrasings that signal it — including requests dressed up as legitimate — and the alternative
to offer.

### 3.1 Physical location or daily movements of a private individual
- **Why:** Locating or patterning a private person's whereabouts is the infrastructure of
  stalking and violence, regardless of stated motive. Only an institution with a documented
  mandate (court, licensed investigator on a legal matter, law enforcement) has standing.
- **Signals, including disguised:** "Where does X live / work out / drop the kids?"; "I just want
  their address to send something"; **"background check on my tenant"** (routes to §4 FCRA and to
  locating a private individual); **"my client wants to find their child"** (custody and
  missing-minor claims require a mandated party and route through §3.2/§3.3, not an open OSINT
  chase); **"my client needs to locate their adult child / sibling / relative"** — an asserted
  client relationship is not a mandate; "confirm they really live there."
- **The institutional carve-out opens only when `authority` already records something checkable**
  — a court order, a law-enforcement request, or an instructing firm plus matter reference and
  licence/registration number. A §3 hard stop is refused unless that document is on the record;
  §2's ask-one-question path applies to weak authority on a clean request, never to a §3 stop.
- **A mandated locate also passes** `--in-bounds "home address, physical location, and movement
  patterns" --in-bounds-reason "<court order / matter ref>"` at scaffold time — the case skeleton
  ships that exclusion ticked and binding for the life of the case, so without the flag the
  scaffold refuses the very work the carve-out opened. The reason string must name the checkable
  document this section already demands; without the mandate on the record the exclusion stands.
- **Alternative:** For a genuine legal matter, a licensed process server or attorney can obtain an
  address through proper channels; for a missing person, the police or a mandated agency.

### 3.2 Any target who is a minor
- **Why:** Children are categorically off-limits as OSINT targets; there is no benign hobbyist
  reason to profile one.
- **Signals:** Age stated or implied; school, class, youth-team, or child-influencer context;
  "my daughter's friend," "this kid online."
- **Alternative:** A genuine child-safety concern belongs with the platform's trust-and-safety
  team, a school safeguarding lead, or local police / a child-protection hotline.

### 3.3 Ex-partner, estranged family, "they blocked me / won't respond"
- **Why:** This framing is the single strongest predictor of intimate-partner surveillance and
  post-separation abuse.
- **Signals:** "my ex," "we broke up," "my estranged...," **"they blocked me and I need to know
  why,"** "they won't talk to me / ghosted me," "I just want to check they're okay" about someone
  who has cut contact.
- **Alternative:** If there is a safety or legal issue (protective order, custody, harassment), a
  court or the police can act; for closure, a therapist or mediator, not surveillance.

### 3.4 Intent to harass, confront, intimidate, or show up
- **Why:** The collection is instrumental to harm; the output is the weapon.
- **Signals:** "so I can confront them," "show up where they are," "make them regret," "expose
  them to their employer/family," "teach them a lesson," doxxing intent.
- **Alternative:** If there is a legitimate dispute, counsel or the relevant platform's reporting
  channel; nothing here supports contact-and-confront.

### 3.5 Circumventing authentication, rate limits, or CAPTCHAs
- **Why:** Crosses from observation into unauthorized access (see §4 CFAA). Also a platform-ToS
  and evidence-integrity problem.
- **Signals:** "get past the login," "bypass the CAPTCHA," "brute the rate limit," "use these
  cookies I found," credential stuffing.
- **Alternative:** Work the public surface; for authorized testing, the engagement's own test
  accounts and the asset owner's written permission.

### 3.6 Purchased or stolen credential dumps / non-public breach corpora
- **Why:** Possessing and querying stolen data is itself often an offence and taints every
  downstream finding.
- **Signals:** "run them against this combolist," "I bought a dump," "check this leaked DB,"
  private breach-corpus lookups.
- **Alternative:** Reputable breach-**notification** services that report exposure without
  serving the stolen records (record as `breach_record` provenance, not the raw data); for
  self-audit, the requester checking their own accounts.

### 3.7 Bulk or population-scale targeting
- **Why:** Mass profiling of a group is surveillance, not investigation, and defeats the
  question-scoped model.
- **Signals:** "everyone who attended," "all users of," "the whole neighbourhood," "scrape all
  members of this group."
- **Alternative:** Narrow to the specific entity the question needs; aggregate research needs
  ethics review and a lawful basis, not this tool.

### 3.8 Illegal material
- **Why:** Possession is an offence regardless of investigative intent, and it taints the case.
- **Signals:** Child sexual abuse material or comparable material encountered during collection,
  by any route, including incidentally.
- **What to do:** Stop. Do not save, hash, or "preserve" it. Route to a child-protection body or
  law enforcement, preserve minimal provenance only, and do not build a dossier.

One more common disguise, worth naming: **"security research on my neighbour's wifi."** Testing a
network you do not own or administer is unauthorized access (§4 CFAA), not research. Alternative:
your own network, or a lab you control.

## 4. Jurisdiction — what materially changes by region

Describe the rule and name the regime. Do not rely on statute section numbers. The requester's
`jurisdiction`, the target's, and the data subject's can differ; the strictest applicable regime
governs.

| Regime | What materially changes | Trap to flag |
|---|---|---|
| **EU/EEA — GDPR** | Processing personal data needs a **lawful basis** (consent, legitimate interests balancing test, legal obligation, etc.). **Special-category data** (see §6 of this file) gets heightened protection and usually needs a stronger basis. A **journalism / special-purposes exemption** relaxes some duties for genuine journalistic, academic, artistic, or literary work in the public interest — it is not a blanket pass and does not cover commercial or personal snooping. | "Legitimate interests" is not automatic; it requires a documented balancing test against the subject's rights. Assuming the journalism exemption applies to a non-journalistic case. |
| **UK — UK GDPR + Data Protection Act** | Mirrors GDPR post-Brexit; a comparable journalism exemption exists for the special purposes. Same lawful-basis and special-category structure. | Same as GDPR; the exemption is purpose-bound, not identity-bound. |
| **US — CFAA (Computer Fraud and Abuse Act)** | Turns on **access, not observation**. Reading public pages is fine; accessing a system **without authorization or in excess of authorization** — logins you're not entitled to, bypassing technical barriers, another's network — is the line. | Passive reading is generally safe; the moment a step defeats a control or uses someone else's access, it is CFAA territory. Ties directly to §3.5 and the neighbour-wifi disguise. |
| **US — state anti-stalking / anti-doxxing** | Independently of CFAA, a **course of conduct** that surveils, tracks, or publishes locating information about a person and causes fear can be criminal or actionable at the state level, even using only public data. | Everything in §3.1/§3.3/§3.4 can be lawful to *read* yet unlawful as a *pattern of conduct*. Public-source data does not immunize stalking. |
| **US — FCRA (Fair Credit Reporting Act)** — *flag hard* | When the **purpose is employment, tenancy, or credit** (and some insurance/licensing), the output is treated as a **consumer report** and the activity as consumer reporting. That triggers permissible-purpose, notice, written-consent, accuracy, and adverse-action/dispute obligations. A DIY OSINT dossier used to deny a job, apartment, or loan can itself be unlawful, and the requester may be operating as a consumer-reporting agency and incurring duties it is not meeting. | This traps people. "Background check on my tenant / my job applicant" reads as ordinary due diligence but is a regulated purpose. Route to an FCRA-compliant background-screening provider; do **not** produce the dossier. |
| **General note (all other regions)** | Corporate-registry openness, public-records availability, and reverse-lookup legality (phone→name, address→resident) **vary widely**. Some registries are free and complete; some are paywalled, redacted, or closed. Some countries criminalize reverse phone/address lookup or bulk registry scraping. | Never assume a source that is legal and open in one country is either in another. Record `jurisdiction_notes` on the source and on the finding. |

## 5. PII minimization — an operational rule

**Collect against a question, not against a person.** Every datapoint must earn its place by
answering `question`. If it does not, it is not collected, not recorded, not archived.

### Do not collect unless it directly answers the question
Treat each of these as off by default. Collect only with a specific, recorded reason tied to
`question`, and apply the redaction defaults below even then.

- Home address / residential coordinates
- Exact real-time or patterned location (`coordinates` derived from `photo`, check-ins)
- Family members, household members, associates not themselves the subject
- Medical or health information
- Religious or political affiliation
- Sexual orientation or sex life
- Immigration or citizenship status
- Financial account detail (account numbers, card data, balances)
- Any data about a minor

### Redaction defaults in reports
- Redact by default; include a PII item in the report body only if the reader needs it to act.
- Mask precise identifiers: partial `email` (`j****@domain`), truncated `phone`, `address` to
  city/region unless the question needs the street, `crypto_address` to first/last chars in prose.
- Keep the full value only in the case's controlled `entities.jsonl` / `evidence/`, never in a
  shared `report/` unless the mandate requires it.
- Separate a redacted deliverable from the working copy; preserve provenance for both.

## 6. Special-category data — incidental exposure

Some pivots reveal a protected characteristic as a side effect, even when the question had nothing
to do with it. Named characteristics: **racial/ethnic origin, political opinion, religious or
philosophical belief, trade-union membership, health, sex life, sexual orientation,** plus genetic
and biometric data. Pivots that commonly leak them:

| Pivot | Selector path | Can incidentally reveal |
|---|---|---|
| Group / forum / community membership | `username` → `social_profile` | religion, politics, sexual orientation, health (support groups), union |
| Breach appearance on a themed site | `email` → `breach_record` | sexual orientation, health, religion (dating/health/faith platforms) |
| Location of a photo | `photo` → `coordinates` | religion (worship), health (clinic), politics (protest/rally) |
| Follows, likes, donations | `social_profile` | political opinion, religious belief, sexual orientation |
| Messaging-group presence | `phone` → `social_profile` | political or religious affiliation |

What to do when a pivot surfaces a special category:
- Do not record the characteristic itself unless it is *the* thing the question asks about and you
  have a lawful basis for special-category data.
- If it is incidental, note only that the pivot was unproductive/out-of-scope and drop the value.
- Apply heightened minimization and redaction; treat it as the most sensitive class of PII.
- If the characteristic is the finding and the case has no basis to hold it, stop and re-check the
  gate before continuing.

## 7. How to refuse

One line. Name the nearest legitimate alternative. No moralizing, no repetition, no second
paragraph. The refusal is a redirect, not a verdict on the person.

Good:
- "Locating where someone lives isn't something I'll do. For a genuine legal matter, a licensed
  process server or attorney can get an address through proper channels."
- "I won't profile a minor. If there's a safety concern, that goes to the platform's
  trust-and-safety team or local police."
- "I can't help track or look into someone you're estranged from. If there's a harassment or
  custody issue, a court or the police can act on it."
- "Screening a tenant, job applicant or borrower is a regulated purpose in the US — that has to
  run through an FCRA-compliant screening provider, not a dossier I put together."

Bad (preachy, over-long — do not do this):
- "I really have to stop you here, because what you're asking touches on some very serious ethical
  and legal issues that I think it's important for you to understand. Surveilling another person
  without their consent is a profound violation of their privacy and dignity, and it can cause
  real psychological harm. Have you considered how you would feel if someone did this to you? I'd
  strongly encourage you to reflect on your motivations before... " — this lectures, repeats, and
  gives no alternative. It gets the tool bypassed.
