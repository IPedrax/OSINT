---
name: osint-crypto
description: >
  Blockchain and on-chain investigation. Identifies the chain and asset from an address format, reads a
  transaction, maps the transaction graph, clusters addresses by common-input-ownership and change
  heuristics, attributes clusters to exchanges and services, and attempts off-chain linkage through naming
  services, marketplace profiles and addresses published on the open web. Covers cross-chain bridges,
  mixers and privacy coins, and sanctioned-address screening for KYC-AML. Accepts crypto_address, tx_hash,
  url, username. Passive throughout; sending anything on-chain is never part of the play.
when_to_use: >
  Use for "trace this bitcoin address", "who owns this wallet", crypto address tracing, wallet clustering,
  transaction graph, follow the funds, on-chain analysis, blockchain forensics, "where did the stolen funds
  go", ransomware payment address, scam or rug-pull address, pig butchering, exchange attribution, deposit
  address, "which exchange did this go to", ENS or .eth lookup, NFT holder, token holdings, cross-chain
  bridge, mixer, CoinJoin, Tornado Cash, Monero, sanctioned crypto address, OFAC digital currency address
  screening, crypto due diligence, source of funds. Not for: the person behind a handle once you have one
  (osint-identity), a company or its filings (osint-corporate), a scam site's hosting (osint-infra).
disable-model-invocation: true
---

# osint-crypto
Turn an address or transaction hash into a graded transaction graph, keeping what the ledger records strictly apart from what you inferred
about who controls it.

## 0. The rule this play exists to enforce
The ledger is a primary record of **what moved**. It is silent on **who moved it**. Two sentences, two rungs: "transaction `<hash>` moved
2.4 BTC from input set X to output set Y in block N" is rung `observed`, graded A-something once the artifact is verified (step 2);
"address Y is controlled by Alice" is rung `inferred`, capped at credibility 3 without a verified signature or a primary record, and written
with ICD-203 wording. Everything between them — clustering, change detection, exchange attribution, vendor labels — is heuristic with a
stated condition under which it is wrong. **Write the failure condition into the finding or do not write the finding.** A cluster is a
`candidate_group`, never a merge; the only Tier-1 datapoint for control of an address is a valid signature over a challenge message
(`10-pivot-matrix.md`), and an address in a post, an entity label or an ENS name is not.

## Preconditions
1. A case is open: `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` exists — if not, stop and run `/osint:osint-scope`. Read it for `question`
   (numbered `Q1..Qn`), `out_of_bounds[]` and `active_allowed`; the gate ran at intake, so do not re-ask it.
2. Record the seed in `entities.jsonl` as `crypto_address` or `tx_hash`. Copy it, never retype it: Base58, bech32 and EIP-55 are all
   case-bearing, and lowercasing an `0x` address destroys the checksum that would have caught a typo. A `url` or `username` seed is an
   off-chain entry point — start at step 9, then re-enter at step 1.
3. Record a **hop budget** in `scope.md` before the first hop. Graphs branch exponentially and an unstated limit turns a case into an
   unbounded crawl. Five hops from the seed is a working default; state whatever you choose.
4. Default `mode` is `passive`, and steps 1-9 are all passive. Step 10 is `active`: `active_allowed: true` **plus** a fresh confirmation
   naming the specific action. Intake does not cover it.
5. Every step appends a `ledger.jsonl` row whose `query` opens with the scope question id (`"Q1: ..."`) and copies the registry row's `mode`
   and `name` exactly. Grep `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` first; honour `fetchable=no` by opening a browser, not a tool call.

## The play

### 1. Chain and asset identification — `crypto_address` → `crypto_address` · passive
Format narrows the chain before any network call; the table is in `27-crypto.md`. The trap is EVM: `0x` plus 40 hex is simultaneously valid
on Ethereum, BNB Smart Chain and every other EVM chain, and one key controls it on all of them, so "an Ethereum address" is a guess until
activity is observed. **Blockchair** searches several chains at once; then read the detail on that chain's explorer — **Etherscan**,
**BscScan**, **Tronscan**, **Solscan**, **Blockstream.info** or **mempool.space**. Identify the *asset* too: on account chains the native
coin and each token are separate ledgers behind one address, and a USDT transfer on TRON is a contract call, not a TRX transfer. Read the
token-transfer list, not the balance.
- Ledger `mode=passive`, one row per explorer. Chain from format alone is rung `inferred` — say so if no explorer confirms it. "This address
  has activity on chain C from date D" is `B3` on one explorer; step 2 says what earns an A.
- An address with no activity anywhere is a `gaps.md` row, not a failure: it may be unused, or on a chain no registry explorer covers.

### 2. Read the transaction — `tx_hash` → `crypto_address` `tx_hash` · passive
Record for each transaction: block height and timestamp, every input address and amount, every output address and amount, the fee, and on
account chains the contract called and the decoded call. UTXO chains (Bitcoin) have input *sets*; account chains have exactly one sender,
which is why UTXO clustering logic does not transfer to them.
- **Grading escalation, and no step may be skipped to reach the next grade.** One mainstream explorer is `B3` — the explorer is a
  third-party indexer with a real history of display and decoding error. Two independent explorers agreeing is `B2`: that removes indexer
  error, but both read one ledger, so it is confirmation of the *rendering*, not independent corroboration of the event. Retrieve the raw
  transaction (**Blockstream.info** serves it) and check its hash equals the `tx_hash` you hold: the artifact is then self-authenticating
  and the ledger behind it is a class-A primary record — `A2`. Add your own validating node and it is `A1`.
- Ledger `mode=passive`, `result_sha256` over the archived explorer page or the raw transaction bytes.

### 3. Transaction graph — `crypto_address` `tx_hash` → `crypto_address` `tx_hash` · passive
Walk outputs forward and inputs backward, one hop at a time, against the budget from precondition 3. Record every hop as its own entity and
event; a hop you did not write down is a hop you will re-walk. Note the shapes: a **peel chain** (a large output repeatedly shedding small
payments) usually means one wallet paying out, and a **consolidation** (many inputs, one output) usually means a sweep — both are `inferred`
readings of structure, not facts.
- Ledger `mode=passive`, one row per hop, `query` naming the parent `tx_hash`. Grade each hop by step 2's escalation.
- Stop a branch when it reaches a service (step 6), a mixer (step 5), or the hop budget. Say which in `gaps.md`.

### 4. Clustering heuristics — `crypto_address` → `crypto_address` (cluster) · passive
Two heuristics, both UTXO-only, both wrong under named conditions. Read `27-crypto.md` before applying either.
- **Common-input-ownership**: inputs co-spent in one transaction are assumed to share a controller. Breaks on CoinJoin (many parties co-sign
  by design — visible in the structure), on **PayJoin, which is invisible in the structure and therefore breaks the heuristic silently**, on
  custodial batching (true, but the "entity" is an exchange holding thousands of unrelated users), and on Lightning, atomic swaps and
  collaborative funding. It does not apply at all on account chains.
- **Change detection**: identify which output returns to the sender. Name the distinguisher you used — script-type match, address novelty,
  non-round amount, position — and its failure condition. A reused change address, matching script types on both outputs, a self-transfer, a
  fiat-denominated payment, or a deliberately payment-shaped self-send each defeat it.
- **WalletExplorer** carries pre-built Bitcoin common-input clusters, `D` and years stale — a historical cross-check, never a current answer.
- Ledger `mode=passive`. The co-spend itself is `observed` (`B2`). "Therefore one controller" is `inferred`, `C3`, and it opens a
  `candidate_group` — it never merges two entities. A cluster with a mixed or unexamined structure is not a cluster; say so.

### 5. Mixers, CoinJoin and privacy coins — where steps 3 and 4 stop working · passive
Recognise these before spending hops on them. CoinJoin gives an anonymity set the size of that round's participants and hides nothing about
amounts or the fact of mixing; post-mix consolidation of outputs re-links them, and toxic change leaks. Fixed-denomination smart-contract
mixers are defeated by timing, unique amounts, a relayer funded from a linked address, and a thin denomination — not by hop-walking.
Centralised tumblers substitute trust in an operator who keeps logs. **Monero's graph is not readable from the chain**: the honest output is
a `gaps.md` row saying so, never a probability. Zcash leaks at the shielded/transparent boundary, which is where most of its volume sits.
- What none defeat is the **endpoints** — where funds entered (usually a KYC'd withdrawal) and left — nor operator error. Work those instead.
- Ledger `mode=passive`, recording the stop explicitly: "trail enters <tool> at `<tx_hash>`; anonymity set N; not traced further." A trail
  that dies in a mixer is a finding, and an important one for step 8.

### 6. Service attribution — `crypto_address` → `company` · passive
Two routes, graded differently.
- **Behavioural**: an address that forwards everything it receives into a single larger cluster is very likely a *deposit address* of that
  service. This is rung `inferred`, `C3`. What it supports: "funds reached an account at service E." What it does not support, ever: which
  customer. Payment processors and OTC desks behave identically.
- **Labels**: **Etherscan** address labels, **Arkham Intelligence** entity attribution, **Chainalysis** where licensed — proprietary,
  unpublished, not reproducible. Rung `reported`; Arkham is registry-graded `D`, so `D3`, or `C3` for a label that independently agrees with
  your own behavioural finding. A label is a Tier-3 datapoint (`10-pivot-matrix.md`) and Tier 3 does not accumulate.
- **Chainabuse** shows whether the address is already reported for ransomware, sextortion or pig-butchering, often with the lure text and
  contact channel. One report is an allegation (`D3`); a pattern of independent reports is `D2`.
- Ledger `mode=passive`. Filing a Chainabuse report or engaging an Arkham bounty is a public disclosing act — step 10.

### 7. Cross-chain bridges — `crypto_address` `tx_hash` → `crypto_address` `tx_hash` · passive
Value leaves chain A into a bridge contract and appears on chain B. The link is an inference from amount, timing and the bridge's own
emitted event or message id — fees change the amount, and a busy bridge batching similar amounts in one window collapses the correlation.
Read both sides on their own explorers; no free registry source automates this, and the paid platforms that do assert a vendor conclusion.
- The most common bridge is not a bridge: **deposit one asset to an exchange, withdraw another**. That link exists only in the exchange's
  books and is not recoverable on-chain. Record it as the end of the trail (step 6), not a gap in your method. Non-KYC instant swap services
  have the same property.
- Ledger `mode=passive`, one row per side. A crossing carried by a matching event id is `B2`; one carried by amount and timing alone is `C3`
  with the count of alternative matches in the window stated.

### 8. Sanctions and exposure screening — `crypto_address` → `document` `person_name` `company` · passive
Mandatory on every address in a KYC-AML case, fast, and usually empty. **OFAC Sanctions List Search** carries digital currency addresses
attached to designated persons; **OpenSanctions** mirrors them alongside other regimes. An exact hit is `A3` alone, `A2` where consistent
with other collected material — the list being authoritative does not corroborate the designation. Cite OFAC, never the mirror.
- Two traps. **Direct designation is not exposure**: "N hops from a sanctioned address" is a vendor risk score, not a legal status, and it
  belongs in the report as an `inferred` observation with the hop count and route stated. **A clean screen is not a clean file**: the 50
  Percent Rule has no on-chain analogue, so an unlisted address controlled by a designated person is still blocked property, and ownership
  analysis (`/osint:osint-corporate`) is the check that finds it.
- Interaction with a designated contract or address is itself a compliance event and belongs in the finding.

### 9. Off-chain linkage — `crypto_address` → `username` `url` `social_profile` `person_name` · passive
The highest-yield vector by a wide margin is **the address published on the open web by its own holder**. Search the exact address string in
**Google Search**, **Bing**, **Yandex**, **GitHub Code Search**, **grep.app**, **PublicWWW**, **Pastebin** and **Intelligence X**, then the
same query against **Wayback Machine (retrieval)** and **archive.today (retrieval)** for pages since edited. Donation and tip addresses on a
personal site, a forum signature, a README or a profile bio are the classic hit.
- **ENS** reverse resolution gives a primary name where the holder set one (most have not), and the text records on that name routinely
  carry a handle, a GitHub username, an email and a website. Forward resolution proves nothing — a name can point at an address its holder
  does not control. Names transfer and expire: date every observation.
- **OpenSea** profiles attach a chosen username, a bio and sometimes a linked account to an address; token and NFT holdings on **Etherscan**
  place it in a community or at an event. Holding is not choosing — anyone can send a token anywhere, and spam airdrops are constant.
- Grade the *publisher*, not the chain: an established organisation's own site is `B3`, a forum post `C3`, an anonymous paste `E3`. All of
  it is rung `reported`, and "therefore this person controls the address" stays `inferred` with estimative wording. Any recovered `username`
  or `person_name` goes to `/osint:osint-identity` under the same scope question — it is a selector, not permission to profile.
- **Exchange KYC is not an OSINT technique.** Identifying which exchange holds the account (step 6) is the deliverable; the account holder
  requires subpoena, MLAT or equivalent. Say so in the report, hand it to counsel; never write it as a next collection step.

### 10. Active steps — nothing here runs without `active_allowed: true` plus a fresh confirmation naming the action

| Action | Who learns what |
|---|---|
| Requesting a signed challenge message from the address holder | The holder knows they are being investigated. A verified signature is the only Tier-1 proof of control, and it attests control at signing time, not ownership |
| Filing a **Chainabuse** report | Public, permanent, and readable by the subject |
| Engaging an **Arkham Intelligence** deanonymisation bounty | Public request naming the address you care about |
| Contacting an exchange, service or the address holder | A third party is notified; may tip off the subject and prompt a sweep |
| Submitting evidence to **Wayback Machine Save Page Now** or **archive.today (submission)** | A public archive record dated to your interest |

- Ledger `mode=active`, one row per action, `query` naming the exact action and the confirmation text. A verified signature is `A1` — you
  performed the check and any reader can repeat it against the same key and message, which is independent verification under
  `41-confidence.md`, not an exemption from it.

## Reference index
| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/27-crypto.md` | Before steps 1, 4, 5 or 7. Address formats by chain, the heuristics with their failure conditions, what explorers do and do not show, mixers and privacy coins, bridge tracing, off-chain vectors, and the on-chain observation grading table |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting any source. Grep a filtered slice (`category=crypto`, or `accepts` contains `crypto_address`). Never load whole |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | **Before assigning any grade in this play.** One authoritative source alone is `A3`, or `A2` consistent with other material; certificate transparency is the only stated single-source `A1` exemption |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next pivot, or a hop came back empty. Sections `crypto_address`, `tx_hash`, chain C6, LINKING DATAPOINT STRENGTH, WEAK PIVOTS |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Judging whether a cluster may be merged, resolving a `candidate_group`, or two controllers plausibly fit one cluster |
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | The holder turns out to be a private individual, or the case is framed as fund recovery |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before any step 10 action, and when explorer queries themselves need to be unattributable |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md`; deciding which incidental counterparty addresses to redact |

## Stop conditions
- The scope question is answered at a stated confidence and every hop names its transaction and its grade.
- The trail reaches a custodial service or exchange deposit address. On-chain tracing ends there **by construction** — the next step is
  legal process, not more hops. Record the service, the deposit address and the date.
- The trail enters a mixer, CoinJoin or privacy coin and the anonymity set is larger than the case can carry.
- The hop budget is spent, or two consecutive hops add no new attributable counterparty.
- Every remaining attribution rests on a vendor label with no independent corroboration. Name it in `gaps.md`.
- The cluster turns out to belong to a service rather than the target. Stop, re-scope, do not silently widen.

Anti-rabbit-hole: name the `Q<n>` a hop advances before walking it. An unattributed address with no onward counterparty is inventory.

## Refusals — beyond the global gate in `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md`
- **No sending anything on-chain.** No dust, no test transaction, no token, no calldata message, to any address, for any reason: it is
  irreversible, permanently public, financially consequential, and dusting is the adversary's technique. Receiving dust is a signal about
  someone else; sending it is out of scope.
- **No naming a person as the controller of an address on cluster or label evidence.** Only a verified signature, an admission, or a primary
  record does that. State the cluster, state the grade, and stop.
- **No presenting a heuristic as a fact.** A cluster or change output asserted without its failure condition is a defect, not a shortcut.
- **No private keys, seed phrases, wallet files or key material** — not read, not requested, not stored, not tested.
- **No interaction with a sanctioned address or contract**, including to characterise it. Screening is a list lookup.
- **No fund-recovery or confrontation work.** "Trace who stole my crypto so I can reach them" is refused; the supported output is a graded
  trail plus the exchange and jurisdiction, handed to law enforcement or the exchange's own abuse channel.
- **No trading, buying, selling, swapping or moving any asset**, and no advice on doing so.
- **No dossier drift.** A handle or name recovered at step 9 is a selector for another department under the same scope question.
