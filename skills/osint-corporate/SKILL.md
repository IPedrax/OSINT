---
name: osint-corporate
description: >
  Corporate and due-diligence collection: company registries and filings, officer and shareholder
  extraction, beneficial ownership (UBO) tracing through layered and nominee structures, sanctions and
  PEP screening, adverse media, litigation and insolvency records. Accepts company, company_number,
  person_name, address. Home play for KYC-AML; corporate tracing arm for journalism.
when_to_use: >
  Use for "who owns this company", "who is behind this business", beneficial owner, UBO, KYC, AML, EDD,
  onboarding a counterparty, due diligence on a vendor, client, investor or acquisition target, "is this
  entity sanctioned", OFAC, OFSI, EU or UN sanctions screening, PEP check, adverse media check, "pull the
  filings", annual return, company number lookup, registered address or agent, director or officer search,
  shell company, offshore structure, nominee director, formation agent, group structure, parents and
  subsidiaries, corporate litigation, judgments, insolvency history. Do NOT use for domains and network
  assets (osint-infra), a person as an individual rather than as an officer or owner (osint-identity), or
  a one-off lookup with no case open.
disable-model-invocation: true
---

# osint-corporate

Registry, ownership, screening and adverse-information collection on `company`, `company_number`, `person_name`, `address`.

## 0. The rule this play exists to enforce

**A registry filing is usually a SELF-REPORT.** The register authoritatively records *that the filing was made and says what
it says*; most registers do not verify the content. "The register records X as appointed director of `company_number` NNNN
on DATE" is `observed`, `A3` alone; "X owns it" is `inferred` — it cannot inherit the `A` and needs a stated assumption plus
a named disconfirmer. Nominee directors, secretaries, resident agents and formation agents are lawful and normal everywhere:
one sitting on dozens of unrelated entities is a service provider, a routing signal, never a finding about control.

## 1. Preconditions

1. A case is open — `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` records `purpose`, `target`, `authority`, `jurisdiction`,
   `Q1..Qn`, `out_of_bounds[]`, `active_allowed`. **If not, stop and run `/osint:osint-scope`.** Do not collect first and
   scope afterwards.
2. `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` read once this case. You have a jurisdiction, or step 1 establishes
   one — "in Europe" is not a jurisdiction.
3. Endpoints come from `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` (grep a slice: `category` of `corporate` or `sanctions`,
   `accepts` containing the selector, `mode=passive`, `auth=none` first). `verified=no` rows are homepages to open by hand,
   not APIs. Never invent a URL for a source you lack.

Every step appends one `ledger.jsonl` row `{ts, actor, action, source, query, result, result_sha256, mode}` whose `query`
starts with the scope question id (`"Q2: ..."`). No id, no step. Archive on read: bytes to `cases/<slug>/evidence/`, sha256,
rename to the hash.

## 2. Registry map

| Where | Sources (exact `sources.csv` names — read each row's `notes` before use) |
|---|---|
| Routing only — cite the national register, never these | GLEIF Global LEI Index (LEI, registered address, local registry id, Level 2 direct and ultimate parent where reported) · EU e-Justice Business Registers · OpenCorporates |
| Europe | UK Companies House (free and deepest: accounts, charges, appointments, PSC, reverse officer and address search) · The Gazette · Find Case Law · Charity Commission Register of Charities · Ireland Companies Registration Office CORE (per-item paid) · Ireland Register of Beneficial Ownership (restricted) · Germany Handelsregister (free extracts plus the Gesellschafterliste shareholder list — real direct ownership, updated on every transfer) · France Annuaire des Entreprises · Netherlands KVK Handelsregister (directors only on the paid extract) · Denmark CVR and Estonia e-Business Register (free company, person and address search, free annual reports) |
| US | Delaware Division of Corporations and Wyoming Secretary of State business search (existence, status, agent, nothing on control) · Florida Sunbiz and California bizfile Online (officer, agent and address search, free filing images) · New York Department of State business entity database · SEC EDGAR (DEF 14A officer biographies and compensation, SC 13D/13G stakes, Forms 3/4/5) · FINRA BrokerCheck · IRS Tax Exempt Organization Search · ProPublica Nonprofit Explorer (Form 990 Part VII officers, Schedule I grant graph) |
| Commonwealth, Asia, Gulf, offshore | Corporations Canada (federal CBCA directors and the individuals-with-significant-control register) · SEDAR+ · ASIC Connect and ACRA BizFile+ (paid extracts carry directors and members with shareholdings) · ABN Lookup · Hong Kong Companies Registry (annual returns name shareholders; residential addresses and full ID numbers withheld under the phased inspection regime) · ADGM Public Register and DIFC Public Register (the only meaningfully searchable UAE registers) · BVI Financial Services Commission and Cayman Islands General Registry (nothing beyond licensees and enforcement notices) · Jersey Financial Services Commission Registry · Panama Registro Publico (directors, dignatarios, resident agent — usually nominees) |
| Litigation, procurement, media, leaks | CourtListener · PACER · USAspending.gov · TED Tenders Electronic Daily · UK Contracts Finder · GDELT Project · ICIJ Offshore Leaks Database · OCCRP Aleph · WIPO Global Brand Database · Espacenet |

## 3. The play

### Step 1 — Resolve to a jurisdiction and an identifier
in `company` `address` `person_name` → out `company_number` `address` · passive

- Name-only searching is the largest source of wrong-entity findings; the registry-issued number is the only Tier-1
  corporate link. Routing row, then the national register. Name traps: suffix variants, transliteration, non-Latin
  originals, same-name reincorporations, trading names.
- Ledger `action=collect`, `source=<register>`, result = number and status; an empty search is a `gaps.md` row naming
  register, variants tried, date. Grade an identifier from the issuing register `A3` — one authoritative source alone is
  never `A1` (`41-confidence.md`), and `A2` needs other collected material agreeing. From an aggregator it caps at `3` and
  never merges.

### Step 2 — Pull the primary filings and read them
in `company_number` → out `document` `person_name` `address` · passive

- Pull the filing, not a summary; issuers, regulated firms and nonprofits disclose more than any register. Date every fact
  to the **filing date**, not retrieval — returns are annual or biennial, so an officer list can be two years stale and
  still be current. Ledger one row per document with sha256 and filing date.
- Grade `A3` for what the filing states; accounts audited by a named firm reach `A2` on the numbers.

### Step 3 — Extract officers, secretaries and shareholders
in `document` `company_number` → out `person_name` `address` `company` · passive

- Keep three roles apart: **officer** (management, on the register), **legal shareholder** (title, on a filed shareholder
  list), **beneficial owner** (economic interest, usually filed nowhere).
- Reverse-officer search turns one `person_name` into every appointment held; only UK Companies House, Florida Sunbiz,
  Denmark CVR, Estonia e-Business Register, Corporations Canada, ACRA BizFile+ and ASIC Connect offer it. Run it before
  assuming an entity is standalone.
- Same name is two entities until a named linking datapoint says otherwise: `person_name` alone is Tier 3, a partial date of
  birth plus a shared appointment is Tier 2, so hold both in one `candidate_group`. Ledger every search including the empty
  ones. Grade an appointment `A3`; a service address is not a residence.

### Step 4 — Trace beneficial ownership and chain across jurisdictions
in `company_number` `person_name` → out `person_name` `company` `company_number` · passive

| Problem | Handling |
|---|---|
| Where UBO is published | UK Companies House PSC (over 25% of shares or votes, self-declared and historically unverified — a *claim*, `A3`, never `A1`) · Corporations Canada significant control (federal CBCA only, so a provincial company is invisible to it) · Germany Handelsregister shareholder list |
| Where it is not | The November 2022 CJEU ruling in joined cases C-37/20 and C-601/20 struck down public access to EU beneficial-ownership registers, so assume EU UBO is closed unless a member state demonstrably says otherwise. BVI and Cayman have none; ACRA controllers are filed but non-public |
| Layered structures | Ownership walks upward: entity → shareholder entity → its shareholder. Record each hop as its own entity with its own `company_number` and grade, and state the hop count and the jurisdiction that stopped you. A chain ending at a BVI or Cayman layer is *truncated*, not traced: the finding is "the chain terminates at an opaque layer", never "unknown, therefore X" |
| Nominee directors | They read identically to principals. Discriminators: appointment count across unrelated entities, the person sitting at the agent's own address, identical registration dates across the cluster, the agent openly marketing nominee services. When the layer holds, escape through filings by a listed parent that consolidates the entity, litigation (step 7), procurement, and the leak databases for historical intermediaries — leak-dated, `B3` at best, presence is not wrongdoing |
| Crossing a border | Bridges that work: GLEIF Level 2 parent data; a foreign qualification filing where the company actually trades (California and Florida carry out-of-state entities); an Irish or Dutch holding layer on a director list; a Hong Kong annual return naming the BVI or Samoa parent. Carry the identifier, never the name: a name match across two registers is Tier 3, the same `company_number` in two primary records is Tier 1, a group structure claimed in marketing is `C3` |

Ledger each hop with the register that supplied it. Grade a significant-control declaration `A3`; an inferred controller is
`inferred` — state the assumption, use one ICD-203 term, name the disconfirmer.

### Step 5 — Cluster on shared address and formation agent
in `address` `person_name` → out `company` · passive

**A shared service address is a weak pivot. Tier 3, never a merge basis.** Formation agents, registered-agent services and
virtual offices host thousands of unrelated entities by design — that is the product, and Tier 3 does not accumulate: five
matches remain a `candidate_group`. Search Florida Sunbiz, UK Companies House, Denmark CVR, Estonia e-Business Register.
What upgrades it: the address as an *operating* address in a filing, award or licence; the address plus a `person_name` in a
primary record (Tier 2); a phone or officer that is not the agent's; a neighbour set small enough to enumerate. Same-day
formation through one agent is a signal about the client, not proof of control. Ledger the search and the neighbour count —
count before treating a cluster as meaningful. Grade co-location `C3`, rung `correlated`: write "share an address", never
"are linked".

### Step 6 — Screen sanctions and PEP status
in `person_name` `company` → out `document` · passive

| Rule | Handling |
|---|---|
| Screen the issuing authorities, not one aggregator | OFAC Sanctions List Search · US Consolidated Screening List (adds Commerce Entity List and State debarments a financial screen misses) · UK OFSI Consolidated List (diverged from the EU after Brexit; assuming equivalence is a standard error) · EU Sanctions Map (the binding text is the Official Journal regulation) · UN Security Council Consolidated List (a baseline, not a programme) · World Bank Listing of Ineligible Firms and Individuals (adjudicated debarment, far stronger than adverse media). OpenSanctions is derived — confirm hits at the issuing list; LSEG World-Check is licensed and its entries are allegations |
| A name match is not a hit | False positives dominate. Discriminate on date and place of birth, nationality, passport or national ID, and the entity identifier; then state which discriminators you had and which you did not |
| Transliteration multiplies the error both ways | Arabic, Cyrillic, Chinese and Persian names have many valid romanisations and lists carry some, never all. Screen the variants and the native script where you have it; a clean screen of one spelling is not a clean screen |
| A clean list result is not a clean file | The OFAC 50 Percent Rule blocks an entity owned 50% or more in aggregate by designated persons *without it appearing on any list*; UK ownership and control rules are worded differently and need not agree. Step 4 is mandatory before writing "no match" |

Ledger every screen: list, exact query string, spelling variants, date, and the result including "no match" — a negative
screen is a finding, not silence. Grade a designation `A3` on the list entry alone, `A1` once the designating instrument is
also retrieved (Federal Register notice, Official Journal regulation, UN narrative summary) — that is a second,
independently generated record, not the same one restated. "Not sanctioned" is at best `A3` and is bounded by the lists
screened, spellings run and ownership work done, so state all three. A PEP classification from a compiled database is `D3`.

### Step 7 — Litigation, insolvency and adverse media
in `company` `person_name` → out `document` `url` `person_name` · passive

| Source | Handling |
|---|---|
| Courts and official notices, run first | CourtListener before PACER (RECAP mirrors much of it; PACER charges per page) · Find Case Law · The Gazette for UK insolvency and striking-off, often weeks ahead of the company record · SEC EDGAR and SEDAR+ for related-party transactions · Charity Commission for statutory inquiries. Jersey, DIFC and Cayman judgments frequently name beneficial owners no register discloses. **Absence of a judgment is not absence of litigation** — settled, withdrawn and struck-out cases leave none, and RECAP holds only what someone bought. Log the coverage limit as a negative result |
| Media, second | GDELT Project to establish that coverage exists, in which outlets and languages, then read and cite the original articles, never a tone score or extracted entity. Non-English coverage is where most cross-border reputational risk surfaces. OCCRP Aleph mixes registers with leaked material; reliance depends on the authority in `scope.md`, and the citation belongs to the originating filing |

Ledger each search with date range and outlets covered. Grade a judgment or regulatory decision `A2`, a single news report
`C3`; two outlets running one wire or press release is **one** source — apply the independence test in `41-confidence.md`.
An allegation stays an allegation: "OUTLET reported on DATE that …", never the bare fact.

## 4. Active steps in this play

Every step above is `passive`. These are `active` and need `active_allowed: true` in `scope.md` **plus** a fresh
confirmation naming the action: ordering a paid extract, certificate or filing image (ASIC Connect, ACRA BizFile+, Hong Kong
Companies Registry, Cayman Islands General Registry, KVK, CORE, PACER), which leaves a transaction record at the registrar
tied to your account; contacting a registered agent, formation agent, insolvency practitioner, officer or the counterparty;
creating a register account. Uncertain means active. A licensed platform (LSEG World-Check, Thomson Reuters CLEAR,
LexisNexis Accurint) is `passive` — nothing reaches the subject — but every search is logged by the vendor and those logs
are discoverable, so record the permissible purpose you relied on alongside the query.

## 5. Reference index

| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | Once per case before the first collection step; any jurisdiction, GDPR, consumer-report-purpose or public-interest question |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before any §4 step, or before creating a research account on a register |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next pivot from `company`, `company_number`, `address` or `person_name`; the obvious pivot came back empty; checking whether a pivot notifies |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Two ownership hypotheses fit the filings; merge and `candidate_group` decisions; bias check before reporting |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Grading any finding; the filing-versus-truth distinction; the source-independence test on adverse media |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md` or a due-diligence deliverable; redaction decisions |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting a register or screening list. Grep a filtered slice, never load whole |
| `${CLAUDE_PLUGIN_ROOT}/assets/entity-schema.json` | Writing `entities.jsonl` or `events.jsonl` and unsure of a field |

## 6. Stop conditions

Write up as you go: one finding block per claim with statement, grade, rung, mode, source, retrieval timestamp, sha256 and
disconfirmer. Ownership claims carry the hop chain and the layer that stopped it, screening claims the lists, spellings and
date. `gaps.md` takes every empty search, unbought document and restricted register. Under `purpose: kyc`, minimise PII to
the counterparty's role as a business principal. Stop when any is true:

- The scope question is answered at a stated grade, naming register, filing date and hash.
- The chain reaches a natural person in a primary record, **or** a jurisdiction that does not publish — write the
  truncation, do not guess past it.
- Screening is complete for the lists in scope, with spellings, ownership analysis and negative results.
- Every remaining pivot is in `gaps.md`, or needs a paid document, an unauthorized §4 action, or an `out_of_bounds[]`
  source. Saturation: new filings return only entities already in `entities.jsonl`.

Before each step name the `Q<n>` it advances in one clause. If you cannot, the step does not happen — log the temptation in
`gaps.md` and move on.

## 7. Refusals specific to this play

Global refusals in `00-legal-ethics.md` §3 apply unchanged. In addition, refuse with one line plus the nearest legitimate
route, no lecture:

- Profiling a private individual who is not a business principal in the matter — a tenant, employee, date or neighbour. Same
  answer for an employment, tenancy, credit or insurance decision: a consumer report, with its own statutory process.
- Home addresses, family members or movements of an officer or beneficial owner. The register's service address is the
  extent of it; a residential address needs a documented institutional mandate naming it.
- Circumventing a register's paywall, rate limit, bot challenge or CAPTCHA. `verified=no` rows are reachable in a browser —
  open them by hand, or record the block in `gaps.md`.
- Stating a sanctions or PEP hit on name match alone, or writing "no adverse findings" without naming the lists, spellings
  and databases screened. Both are defects, not shortcuts.
