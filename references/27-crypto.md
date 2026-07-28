*Load when: identifying which chain an address belongs to, reading a transaction, applying or rebutting a clustering heuristic, deciding what a mixer or privacy coin actually defeats, tracing across a bridge, or grading an on-chain observation.*

# On-chain investigation

The ledger records **what moved**. It does not record **who moved it**. Every technique below either reads the
ledger (rung `observed`) or guesses at a controller from its shape (rung `inferred`, credibility 3 or worse).
Keep the two apart in every sentence you write.

## Address formats by chain

The table narrows the candidate set. It does not identify the chain — confirm by finding activity on an explorer.

| Prefix / shape | Chain and script type | Notes |
|---|---|---|
| `1` + Base58, 26-34 chars | Bitcoin P2PKH (legacy) | Case-sensitive. Base58 omits `0` `O` `I` `l`. Identical in form to a Bitcoin Cash legacy address |
| `3` + Base58 | Bitcoin P2SH — multisig, wrapped SegWit | Also matches legacy Litecoin P2SH, which is why Litecoin moved to `M` |
| `bc1q` + 39 or 59 chars, all lowercase | Bitcoin SegWit v0, bech32 (P2WPKH / P2WSH) | Mixed case is invalid, not a variant. Never "normalise" case here |
| `bc1p`, all lowercase | Bitcoin Taproot (SegWit v1), bech32m | |
| `m` `n` `2` `tb1` | Bitcoin testnet | A testnet address in a live case is usually a copy-paste error or a test transaction |
| `0x` + 40 hex | Every EVM chain at once | See below. Mixed case is the EIP-55 checksum — lowercasing destroys it |
| `L` or `M` + Base58, `ltc1` | Litecoin | |
| `bitcoincash:q…`, or legacy `1`/`3` | Bitcoin Cash (CashAddr or legacy) | A BCH legacy address is a syntactically valid Bitcoin address. Check both chains |
| `D` + Base58 | Dogecoin | |
| `T` + Base58, 34 chars | TRON | Where most low-value USDT moves. Token transfers are contract calls, not native transfers |
| Base58, 32-44 chars, no prefix | Solana | An owner holds a separate token account per mint, so one party presents as several addresses |
| `4` or `8` + 95 chars | Monero (standard / subaddress); 106 chars for an integrated address | There is no reusable on-chain address: outputs use one-time keys |
| `t1` `t3` | Zcash transparent | Behaves like Bitcoin. Fully traceable |
| `zs1`, `u1` | Zcash shielded (Sapling), unified | Contents not readable from the chain |
| `r` + Base58, 25-35 chars | XRP Ledger | Exchanges share one address across all customers and separate them by **destination tag** |
| `G` + base32, 56 chars | Stellar | Same shared-address-plus-**memo** pattern as XRP |
| `addr1` + bech32 | Cardano (Shelley) | |
| `cosmos1`, `osmo1`, other bech32 HRPs | Cosmos-SDK chains | The same key renders under each chain's own prefix |
| `1` or `5` + Base58, SS58 | Polkadot / generic Substrate | One public key renders differently per network prefix; two "different" addresses can be one key |
| `name.eth` | ENS name, not an address | Resolve it; the resolution can change and can point anywhere |
| `lnbc…` | Lightning invoice | Not an address. Single-use, and the payment does not appear on-chain |

**The EVM trap.** `0x` plus 40 hex is simultaneously a valid address on Ethereum, BNB Smart Chain, Polygon,
Arbitrum, Optimism, Avalanche C-Chain, Base and every other EVM chain, and one private key controls it on all of
them. A single-chain explorer returning nothing establishes nothing. Search cross-chain (**Blockchair**) or check
each chain's own explorer before writing "no activity".

**The contract trap.** A contract address and an externally-owned account are indistinguishable by shape. Only the
presence of deployed code separates them, and every explorer shows it. A contract has no private key: nobody can
sign for it, its behaviour is its code, and "who controls it" means whoever holds its admin or owner role — which
is a different address, and often a multisig of several.

## What a block explorer does and does not show

| Shows | Does not show |
|---|---|
| Confirmed transactions, blocks, timestamps, fees | Who controls any address |
| Inputs, outputs, amounts, script types | Why a transfer happened, or any off-chain agreement behind it |
| Token transfers decoded from event logs | Which customer of a custodial service a deposit belongs to |
| Contract bytecode, and source where verified | Activity on any other chain |
| Internal transactions (EVM) | The contents of shielded or ring-signature transactions |
| Curated address labels | Anything the indexer has not indexed, including unusual events and new contracts |

Caveats that bite:

- **The indexer is a third party.** Display and decoding errors are real, reorgs briefly show transactions that
  later vanish, and indexing lags the chain. This is why a single explorer read is `B3`, not `A`-anything.
- **"Internal transactions" are a reconstruction** from execution traces. They are not consensus objects and
  different tracers disagree at the margins.
- **Token balances are read from contract state.** A hostile token contract can report whatever it likes, including
  a fake balance or a fake transfer event. Spam tokens and fake "airdrops" designed to look like a known asset are
  routine — check the contract address, not the ticker.
- **NFT metadata usually lives off-chain** on IPFS or a web server and can be changed after the sale. What is on
  the chain is a token id and a pointer.
- **"Verified source" means the source compiles to the deployed bytecode.** It is not an audit and says nothing
  about safety or intent.
- Querying an explorer discloses your interest to the explorer's operator, not to the target. Where that matters,
  self-host (**mempool.space** supports this) or use a Tor-reachable instance.

## Reading a transaction

Record, per transaction: block height, timestamp, all inputs with amounts, all outputs with amounts, the fee, and
on account chains the contract called plus the decoded call.

- **UTXO chains** (Bitcoin and its forks): a transaction spends a *set* of prior outputs and creates new ones.
  There is no "sender field". Everything about who sent it is inferred from the input set.
- **Account chains** (Ethereum and EVM, TRON, Solana): exactly one signing account per transaction. UTXO
  clustering logic does not apply — applying it is a category error, not a weaker inference.
- **Shapes worth naming, all of them `inferred` readings of structure**: a **peel chain** (one large output
  repeatedly shedding small payments while the remainder moves on) usually indicates a single wallet paying out;
  a **consolidation** (many inputs, one output) usually a sweep; a **batch** (one input set, many unrelated
  outputs) usually a service paying many customers at once.

**Verification, which is what upgrades the grade.** Retrieve the raw transaction (**Blockstream.info** serves it)
and confirm its hash equals the `tx_hash` you hold. The artifact then authenticates itself against a class-A
ledger. Without that step you are trusting an indexer's rendering.

## Clustering heuristics and their failure conditions

Every row is a heuristic. State the failure condition in the finding, or do not write the finding.

| Heuristic | Claim | Applies to | Fails when |
|---|---|---|---|
| Common-input-ownership | Inputs co-spent in one transaction share a controller | UTXO chains only | CoinJoin (many parties co-sign deliberately; visible in the structure) · **PayJoin, which looks exactly like an ordinary payment and so breaks it silently** · custodial batching (the "entity" is an exchange holding thousands of unrelated users) · Lightning channel opens and closes · atomic swaps · collaborative funding |
| Change by address novelty | The output going to a never-before-seen address is change | UTXO chains | The sender reuses a change address · the payee address is also new · a consolidation, where every output is change |
| Change by script type | Change matches the input script type; the payment does not | UTXO chains | Both outputs share a script type · the wallet deliberately varies it · the payee happens to use the same type |
| Change by round amount | The round-numbered output is the payment; the remainder is change | UTXO chains | The payment is fiat-denominated, so neither amount is round · both are round · a deliberately payment-shaped self-send |
| Change by output position | Change sits in a fixed position | Weak everywhere | Most modern wallets randomise change position. Treat a position match as a tiebreaker, never a distinguisher |
| Unnecessary-input | A transaction that included more inputs than the payment needed reveals which output is change | UTXO chains | Fee optimisation, dust consolidation, and coin-control choices produce the same shape |
| Wallet fingerprinting | Transaction version, locktime, nSequence, input ordering (BIP-69), fee-rate rounding and change position identify the wallet software | UTXO chains | It identifies **software**, not a person. Two users of the same wallet fingerprint identically; one user changing wallets breaks the group |
| Exchange deposit-address clustering | An address that forwards its full balance into one larger cluster is a deposit address of that service | All chains | Payment processors, OTC desks, custodial wallets and bridge contracts behave identically · some services reassign deposit addresses · on XRP, Stellar and similar chains all customers share one address and are separated by a tag or memo the chain shows but the mapping for which only the exchange holds |

Two rules that survive all of the above:

- A cluster is a **`candidate_group`**, not a merge. `40-analysis.md` governs when a group may be resolved, and a
  Tier-3 datapoint — which is what a cluster, a label or a name match is — does not accumulate into a Tier-1 one.
- **Dust in an input set voids common-input-ownership for that transaction.** A dusting attack sends tiny amounts
  to many addresses precisely so that a careless consolidation links them. If the subject spent attacker-supplied
  dust, the resulting "cluster" contains the attacker. Check input provenance before clustering.

## Mixers and privacy tools, realistically

| Tool | What it defeats | What it does not defeat |
|---|---|---|
| Equal-output CoinJoin (Wasabi, JoinMarket and similar) | Common-input-ownership for that transaction. Anonymity set = the number of equal-value outputs in the round | It hides neither the amounts nor the fact that you mixed — the structure is obvious. Consolidating two post-mix outputs re-links them. Spending a mixed output alongside unmixed change ("toxic change") re-links it. Repeated small rounds by one user are correlatable |
| Fixed-denomination smart-contract mixers | The direct on-chain link between deposit and withdrawal | Timing correlation, a non-standard amount, a thin denomination pool, a relayer or gas paid from a linked address, and withdrawal to an address already funded by the same source. Sanctions status has changed more than once since 2022 following litigation — check the current OFAC list rather than any guide, including this one |
| Centralised tumblers | Nothing durable | You are trusting an operator who keeps records. Several have been seized and their records used in prosecutions |
| Monero | The transaction graph itself: ring signatures hide which input was spent, stealth addresses mean there is no reusable address on chain, RingCT hides amounts | Nothing on-chain replaces it. Known weaknesses are historical (pre-RingCT visible amounts, early small ring sizes, decoy-selection and chain-reaction analysis) or off-chain (exchange records, network-level observation). **The honest output for a Monero leg is a `gaps.md` row saying the trail is not traceable on-chain — never a probability** |
| Zcash shielded pool | Contents of shielded transactions | The transparent side. Most value has historically moved through t-addresses or t→z→t patterns where amount and timing leak at the boundary |
| Dash PrivateSend, Litecoin MWEB and similar optional layers | Some linkage, weakly | The base chain stays transparent, adoption is thin so the anonymity set is small, and the entry and exit are visible |

What **none** of them defeat, and where the case is usually won:

- **The entry point** — where the funds came from. Very often a withdrawal from a KYC'd exchange account.
- **The exit point** — where they went. A deposit at another exchange, a purchase, an OTC desk.
- **Operator error** — a reused address, an address posted publicly, an amount that matches something else exactly,
  a distinctive time-of-day pattern, a wallet fingerprint change that dates a migration.

Coordinator shutdowns and enforcement actions since 2024 mean the population using any given privacy tool changed
substantially. A CoinJoin dated 2021 and one dated last month imply different things; date the observation.

## Cross-chain bridge tracing

Three designs, three strengths of link:

1. **Lock-and-mint / burn-and-release (canonical bridges).** Value is locked in a contract on chain A and a wrapped
   asset is minted on chain B, or the reverse. Most emit an event carrying a message id, nonce or destination
   address. **That identifier, present on both sides, is the strong link** — grade `B2`.
2. **Liquidity-network bridges.** A pool on chain B pays out; nothing is minted. The link rests on amount and
   timing, and the payout amount differs from the deposit by fees and slippage. `C3`, and the finding must state
   how many other crossings in the same window would also match.
3. **The exchange, which is the most common bridge of all.** Deposit BTC, withdraw ETH. The link exists only in
   the exchange's books and **is not recoverable on-chain**. This is the end of the trail, not a gap in method.
   Non-KYC instant-swap services have the same property, minus the records.

Procedure: read the deposit transaction on chain A on its own explorer, pull the bridge contract's event log for
the identifier and the stated destination, then search chain B's explorer around that identifier and time window.
No free registry source automates this; the commercial platforms that do are asserting a vendor conclusion, which
is rung `reported` and unreproducible.

Failure modes: aggregated relayers that batch many users into one settlement, fee-adjusted amounts that break
exact matching, and a destination address freshly created for that crossing and used once.

## Off-chain linkage vectors that actually work

Ranked by yield in practice.

| Vector | How | Grade of the result |
|---|---|---|
| The holder published the address themselves | Search the exact address string in **Google Search**, **Bing**, **Yandex**, **PublicWWW**, **GitHub Code Search**, **grep.app**, **Pastebin** and **Intelligence X**; then the same string against **Wayback Machine (retrieval)** and **archive.today (retrieval)** for pages since edited | Grade the publisher: an organisation's own site `B3`, a forum post `C3`, an anonymous paste `E3`. Rung `reported` |
| Court filings, indictments and regulator actions naming addresses | **CourtListener**, **PACER**, **SEC EDGAR**. Chronically underused, and the strongest attribution documents that exist outside a vendor | `A3` alone, `A2` where other collected material agrees — a primary record attributing an address, on rung `reported` unless you also read the exhibit |
| Sanctions designations naming addresses | **OFAC Sanctions List Search**, mirrored by **OpenSanctions** | `A3` alone, `A2` where consistent with other collected material, at the issuing authority. Cite OFAC, never the mirror |
| Naming services | **ENS** reverse resolution gives a primary name only where the holder set one; the text records on that name routinely carry a handle, a GitHub username, an email, an avatar and a website | The record is `B2` `observed`; its contents are self-report, `C3` `reported`. Forward resolution proves nothing — a name can point at an address its holder does not control, and names transfer and expire, so date every observation |
| Marketplace and community profiles | **OpenSea** profiles carry a chosen username, a bio and sometimes a linked account. Token and NFT holdings on **Etherscan** place an address in a community, a DAO or at an event | `C3`. Holding is not choosing: anyone can send a token to any address, and spam airdrops are constant. A profile can be set by an impersonator holding a lookalike name |
| Abuse reports | **Chainabuse** often carries the lure text, the contact channel, a domain or an email — which pivot to `/osint:osint-infra` and `/osint:osint-identity` | One report is an allegation, `D3`; a pattern of independently filed reports, `D2` |
| Donation and tip addresses | A published donation address links the address to the *publisher of that page*, which is the cleanest passive link available. Check the page's own history: swapping a donation address is a standard website compromise | Grade the publisher. Rung `reported` |
| On-chain messages | OP_RETURN data, EVM calldata text, XRP and Stellar memo fields. People write ransom notes, contact details and threats there | `observed` that the message exists; its contents are unauthenticated claims by whoever sent it |
| Timing of transactions | Timestamps clustering in one timezone's waking hours | Tier 4. Use it to prioritise which hard check to run next. Never as a link |

**Exchange KYC is not an OSINT technique.** Identifying which exchange holds the receiving account is the OSINT
deliverable. Obtaining the account holder's identity requires a subpoena, an MLAT request, a court order or a
regulator's own powers. Write that in the report and hand it to counsel or law enforcement; do not list it as a
next collection step, and do not imply the identity is a few clicks away.

**Sending dust is not an OSINT technique either.** Dusting is what an adversary does to pollute someone else's
cluster. As an investigator you never send anything on-chain: it is irreversible, permanently public, financially
consequential, and it tips off the subject. Dust *arriving* at a subject's address is a finding about a third
party and a warning that the next clustering step may be poisoned.

## KYC-AML: screening and what an exchange attribution is worth

- **Screen every address in scope** against **OFAC Sanctions List Search** and **OpenSanctions**. It is fast and
  usually empty. An exact address match is `A3` alone, `A2` where consistent with other collected material, cited to
  the issuing authority — the list being authoritative does not corroborate the designation.
- **Direct designation is not exposure.** "Three hops from a designated address" is a vendor risk score, not a
  legal status. If it goes in the report at all it goes in as `inferred`, with the hop count, the route and the
  intermediate services stated.
- **A clean screen is not a clean file.** The OFAC 50 Percent Rule has no on-chain analogue: an address controlled
  by a designated person is blocked property whether or not it appears on any list. The check that finds it is
  ownership analysis of the counterparty (`/osint:osint-corporate`), not more hops.
- **Exchange attribution is a lead, not proof.** The defensible sentence is: "Funds reached an address whose
  behaviour indicates a deposit address of service E (`C3`, rung `inferred`, failure condition: payment processors
  and OTC desks behave identically). E may hold customer records for that account; obtaining them requires legal
  process." The sentence that is a defect is: "The funds went to E's customer, X."
- Interaction with a designated address or contract is itself a reportable compliance event, independent of who
  the counterparty turns out to be.
- PII minimisation applies here as everywhere: a transaction graph sweeps up dozens of uninvolved counterparties.
  Only those that answer the scope question belong in `entities.jsonl`.

## Grading table — on-chain observations to defensible grades

Read `41-confidence.md` first. Reliability grades the source; credibility grades the claim; one authoritative
source alone is `A3`, or `A2` where consistent with other collected material. Certificate transparency is the only
stated single-source `A1` exemption, and the blockchain is not a second one.

| Observation | Rung | Grade | Why |
|---|---|---|---|
| Transaction exists with these inputs, outputs, amounts and block — read on one mainstream explorer | `observed` | `B3` | The explorer is a third-party indexer with a real history of display and decoding error, and nothing corroborates it |
| Same, agreed by two independent explorers | `observed` | `B2` | Removes indexer error. Both still read one ledger, so this confirms the *rendering*, not the event independently |
| Same, with the raw transaction retrieved and its hash checked against the `tx_hash` | `observed` | `A2` | The artifact authenticates itself against a class-A primary ledger; still a single line of verification |
| Same, plus confirmation from your own validating node | `observed` | `A1` | Authoritative record plus independent verification |
| Address X sent to address Y at time T | `observed` | as above | The claim is about addresses. It says nothing about people |
| Address holds token or NFT N at block B | `observed` | as above | Holding is not choosing. Anyone can send anything to any address |
| Two addresses appear as inputs to one transaction | `observed` | `B2` | The co-spend is on the chain |
| …therefore one entity controls both (common-input-ownership) | `inferred` | `C3` | Heuristic. State the failure condition and whether the structure is a CoinJoin. Never on an account chain |
| Output Z is the change output | `inferred` | `C3` | Heuristic. Name the distinguisher used and what would defeat it |
| Address is a deposit address of exchange E (behavioural) | `inferred` | `C3` | Supports "funds reached an account at E". Never names a customer |
| Vendor entity label (**Arkham Intelligence**, **Etherscan**, **Chainalysis**) | `reported` | `D3`, or `C3` where it independently agrees with your own behavioural finding | Proprietary, unpublished, not reproducible. Tier 3, and Tier 3 does not accumulate |
| **Chainabuse** reports naming the address | `reported` | `D3`; `D2` for a pattern of independently filed reports | Unverified user submissions |
| Address appears on the OFAC SDN list | `reported` | `A3` alone, `A2` where consistent with other collected material | Primary designation record; the list being authoritative does not corroborate the designation. `A1` where a second issuing authority designates it through its own process |
| ENS name resolved to this address at time T | `observed` | `B3` on one indexer, `B2` on two independent ones, `A2` with the hash check | An on-chain record read through an indexer — the same escalation as a transaction read |
| ENS text record gives handle `@x` | `reported` | `C3` | Self-report by whoever controls the name |
| …therefore `@x` controls the address | `inferred` | `C3`, ICD-203 wording mandatory | The name holder and the address holder are separate facts |
| Address published as a donation address on site S | `reported` | grade of the publisher | Check the page's edit history for a swapped address |
| Court filing or indictment attributes the address to a named person | `reported` | `A3` alone, `A2` where other collected material agrees | A primary record of an allegation or a finding — read which it is. `A1` where a second process records it |
| A signature over a challenge message verifies against the address | `observed` | `A1` | You performed the check and any reader can repeat it against the same key and message. That is independent verification under `41-confidence.md`, not an exemption from it. It attests **control at signing time**, not ownership, and requesting one is an `active` step |
| Monero transaction linkage | — | `F6`, and it belongs in `gaps.md` | Not readable from the chain |

Three rules that stop grade inflation across a chain of hops:

1. A finding that cites another finding inherits the **lowest rung** and the **weakest grade** in its chain. A
   `C3` cluster feeding a `C3` attribution feeding a `C3` identification is `C3` at rung `inferred` — it does not
   become stronger because the first hop was an `A2` transaction.
2. Date every attribution. Exchange hot wallets are rotated, deposit addresses are reassigned, ENS names expire
   and vendor labels are not versioned. A label read today may describe 2019.
3. One address is not one person. A custodial address represents thousands of users; a multisig or smart-contract
   wallet represents a threshold of separate keys; one person routinely holds hundreds of addresses.

## The six errors this discipline keeps making

1. Reporting an exchange's cluster as the target's wallet, because the trail led there.
2. Repeating a vendor label as an identification. It is an unreproducible third-party assertion.
3. Laundering a heuristic into a fact by dropping the failure condition somewhere between `findings.md` and the
   executive summary.
4. Applying UTXO clustering to an account chain, or reading a Solana owner's several token accounts as several
   parties.
5. Treating "the funds passed through this address" as "this person controls this address".
6. Grading the ledger instead of the source you actually read. You read an explorer, not the chain.
