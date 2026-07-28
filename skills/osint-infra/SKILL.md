---
name: osint-infra
description: >
  Infrastructure and attack-surface footprint mapping from a domain, subdomain, IP, ASN,
  netblock, TLS certificate or URL. Enumerates subdomains from certificate transparency, reads
  RDAP/WHOIS registration, authoritative DNS, passive DNS and historical resolutions, ASN and
  netblock ownership, mail configuration as a provider tell, sibling sites via analytics IDs and
  favicon hashes, and archived content. Runs end to end with no API keys; key-gated sources are
  optional enrichment. Passive by default; every step touching target infrastructure is marked
  active and separately gated.
when_to_use: >
  Dispatched by the /osint router. Use for "map this domain's footprint", "attack surface",
  "subdomain enumeration", "what subdomains does X have", "certificate transparency", "crt.sh",
  "who owns this IP", "what ASN is this", "reverse IP", "co-hosted domains", "passive DNS",
  "DNS records for", "MX SPF DMARC", "which mail provider", "WHOIS this domain", "RDAP",
  "when was this domain registered", "historical DNS", "what did this site used to be",
  "sibling sites", "same operator infrastructure", "shadow IT", "exposure of my own domain",
  "phishing infrastructure", "pivot on this threat infrastructure". Not for: people, usernames,
  email or phone (osint-identity); registries, filings or UBO (osint-corporate); explaining DNS.
disable-model-invocation: true
---

# osint-infra
Turn one infrastructure selector into the estate around it, sourced and graded.

## Preconditions
1. A case is open: `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` exists. If not, stop and run `/osint:osint-scope`. Do
   not collect first and scope afterwards.
2. Read `scope.md` for `question` (numbered `Q1..Qn`), `out_of_bounds[]`, `active_allowed`. The gate ran at intake; do
   not re-ask it.
3. Record the seed in `entities.jsonl` with its canonical type — `domain` `subdomain` `ip` `asn` `netblock` `ssl_cert`
   `url`. Normalize first: strip scheme and path, lowercase, IDN to punycode, reduce to the registrable domain before
   enumerating.
4. Default `mode` is `passive`. Steps 6, 7b and 10 are `active`: each needs `active_allowed: true` **plus** a fresh
   confirmation naming the specific hosts or records. Intake does not cover them.
5. Every step appends a `ledger.jsonl` row whose `query` opens with the scope question id (`"Q1: ..."`) and copies the
   registry row's `mode` and `name` exactly. Grep `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` first; honour `verified=no`
   by using the homepage.

## The play — steps 1-5 need no key and touch nothing the target controls; run them first, always

### 1. Certificate transparency — `domain` `company` → `subdomain` `ssl_cert` · passive
The primary subdomain source, and free. **crt.sh** on the registrable domain and its wildcard form, then **SSLMate Cert
Spotter**, whose monitoring alerts on new issuance across a long engagement. Read every SAN list — one certificate
routinely enumerates the estate. Pivot the subject organisation field only on OV or EV certificates; DV asserts nothing
about identity.
- Ledger `mode=passive`, one row per query. Grade `A1` that the name was certified at that date — a CT entry is
  self-authenticating and mirrored, the one single-source `A1` in `41-confidence.md`. That the host resolves now is a
  *different* claim: do not grade it, resolve it at step 6, 8 or 10. `gaps.md`: wildcards hide the hostname and hosts
  without a public certificate never appear.

### 2. Registration record — `domain` → `company` `person_name` `email` `address` · passive
Find the registry via the **IANA RDAP Bootstrap Registry** (`dns.json` for TLDs, `ipv4.json` / `ipv6.json` / `asn.json`
for number resources), or let **RDAP.org** redirect for you. **ICANN Lookup** is authoritative but is a JavaScript
application, so use RDAP for machine-readable output. Post-GDPR the contact block is redacted on most gTLDs — expected,
not a dead end. Registrar, dates, EPP status codes and nameservers survive, and are usually more evidential anyway.
- Ledger `mode=passive`. Grade registry output `A3` — authoritative source, single uncorroborated record; `A2` only
  where other collected material agrees. A reseller carrying the same field (**WhoisXML API**, **ViewDNS.info**) is `D3`
  — the registry repackaged, never corroboration of it. Pre-2018 registrant identity survives only in historical WHOIS
  (**DomainTools**, **WhoisXML API**, **SecurityTrails**, all paid or key-gated); no access is a `gaps.md` row, not a
  guess. A registrant name goes to `/osint:osint-identity` or `/osint:osint-corporate`, same scope question.

### 3. Archived content — `domain` `url` → `subdomain` `url` `document` · passive
Read what the estate was before touching what it is. **Wayback Machine (retrieval)** for deleted pages and superseded
contact listings. **Common Crawl** URL index enumerates every path and hostname seen under the domain without sending it
a request. **archive.today (retrieval)** captures pages Wayback will not; **Arquivo.pt** alone offers full-text search
over archived content. **GitHub Code Search** finds the domain in configs and source, where internal hostnames appear
that DNS never has.
- Ledger `mode=passive` — retrieval never notifies; **submission** does and belongs to step 10. Grade `B2` for an
  Internet Archive capture with its timestamp, `C3` for archive.today (anonymous operator). Takedowns and robots
  exclusions silently remove captures: a gap is not proof of absence.

### 4. Network layer — `ip` `netblock` → `asn` `netblock` `company` `address` · passive
Once an address is in hand: **Team Cymru IP-to-ASN Mapping** for bulk attribution (read its own current documentation
for the query interface; do not reconstruct it from memory), **RIPEstat** for announced prefixes, routing history and
abuse contacts, **Hurricane Electric BGP Toolkit** for prefix-to-origin, peers, upstreams and DNS names observed in a
prefix. Then the holder record at the responsible RIR — **RIPE Database**, **ARIN Whois-RWS**, **APNIC Whois** — via the
bootstrap registry from step 2. **PeeringDB** gives facilities and NOC contacts, all self-published.
- Ledger `mode=passive`. Grade RIR output `A3` (`A2` where a second process agrees), PeeringDB `C3`, and "this
  organisation operates this host" `C3` — registered holder is not operator. The more specific object names the real
  user: ARIN customer records for reassigned sub-blocks often name the tenant; APNIC refers to NIRs.
- Read **IPinfo.io** privacy flags before any country theory — a VPN exit or CGNAT invalidates the line, **MaxMind
  GeoLite2** coordinates are often a regional centroid, and a CDN or WAF address is Tier 4: it says nothing about the
  origin.

### 5. Passive subdomain enumeration — `domain` → `subdomain` · passive
**subfinder** in default mode queries third-party datasets and CT and sends the target nothing; its opt-in resolution
mode makes this a step 10 action needing the same authorization. **Amass** is the reverse — active by default, with a
passive-only mode you must select deliberately. **DNSDumpster** is graded active: its record view is current and nothing
public establishes it is stored.
- Log `mode=passive` only if you can name the mode you selected; uncertain means active. Grade `B3` — an aggregated list
  is a lead set, not a confirmed estate. Deduplicate against step 1, keeping CT-sourced names apart. Yield tracks
  provider keys: with none, say so in `gaps.md`.

### 6. Authoritative DNS — `domain` `subdomain` → `ip` `subdomain` · ACTIVE
**Reaches the target's authoritative nameservers and lands in their DNS logs.** Needs `active_allowed: true` plus a
fresh confirmation naming the records and hosts. **dig (BIND DNS utilities)** — `Resolve-DnsName` or `nslookup` on
Windows — for A, AAAA, MX, NS, TXT, SOA, CAA. Querying the target's own nameservers directly is the most detectable
form; **Google Public DNS** and **Cloudflare 1.1.1.1 DNS over HTTPS** put a public resolver's address in the log instead
of yours, but the lookup still arrives. Query both: geo-steered and split-horizon zones answer differently, and the
difference is itself a finding.
- Ledger `mode=active`, `query` naming the record types, the exact names, and the confirmation received. Grade `A2` —
  direct observation of the live zone, one observation. `A1` only where two independent resolvers return the same
  answer, which is why you query both.
- Refused or ungated: substitute passive DNS (8), CT (1), archives (3), scan indexes (9). None gives the current zone;
  all give a defensible approximation. Record it in `gaps.md`.

### 7. Mail configuration as a provider tell — `domain` → `company` · passive or active
MX, SPF, DMARC and DKIM name the vendors an organisation trusts. SPF enumerates authorized third parties — CRM,
marketing, ticketing, payroll — that appear nowhere else in the footprint, and DMARC reporting addresses often expose an
internal mailbox or a security vendor.
- **7a passive:** TXT and MX history from passive DNS (8) or an archived capture. `mode=passive`, grade `B2` — a
  historical record may have been superseded.
- **7b active:** **MXToolbox** performs live lookups, as does step 6 tooling. `mode=active`, same gate as step 6, grade
  `A2`. Each vendor found is a `company` selector for `/osint:osint-corporate`.

### 8. Passive DNS and historical resolution — `domain` `ip` → `ip` `domain` · passive · key
Optional enrichment; the case must stand without it. This answers the two questions no zero-key source answers: what a
name resolved to years ago, and every name that ever pointed at an address. **CIRCL Passive DNS** (credentials issued to
vetted CSIRTs and researchers, strong EU coverage), **DNSDB (DomainTools Farsight)** (the reference commercial dataset —
Farsight was absorbed into DomainTools in 2021, so pre-2021 links and tooling may not behave as older guides describe),
**SecurityTrails** (reverse lookup by nameserver or MX; `verified=no`, so use a browser). **Microsoft Defender Threat
Intelligence (PassiveTotal)** is licence-only.
- Ledger `mode=passive`. Grade DNSDB `A2`, CIRCL `B2`, SecurityTrails `B3`, **ViewDNS.info** `D3`. Date overlap decides
  whether two records correlate at all — two domains on one address in non-overlapping windows are not linked. Record
  the windows before asserting a link.

### 9. Scan indexes and siblings — `ip` `asn` `domain` `url` → `ip` `url` `ssl_cert` `domain` · passive · key
You read the operator's stored snapshot; the target sees nothing. **Shodan** (banners, TLS certificates, exposed
services, and `http.favicon.hash` clustering — the strongest infrastructure-clustering technique in the registry),
**Censys Search** (the strongest certificate index; `verified=no`, bot interstitial on automated requests, so use a
browser), **FOFA** (far better Chinese and Asian coverage, operated from China — weigh what the query discloses),
**LeakIX** (exposed services, metadata only), **urlscan.io (search public scans)** (someone else's capture, including
every host the page contacted — check it before contemplating a scan of your own). Siblings by shared identifier:
**PublicWWW** full-text source search on an analytics ID, ad-network ID, tracking code or distinctive path;
**BuiltWith** reverse lookup on the same (paid).
- Ledger `mode=passive`. Grade scan hits `B2` **at the capture date** — snapshots run weeks stale, so a hit means *was*,
  not *is*, and a present-tense claim is `C3` until step 6 or 10 confirms it.
- Grade sibling hits `C3`: a shared analytics or ad ID is Tier 3 and opens a `candidate_group`, never a merge; a shared
  *generic* favicon (default CMS, framework, template) is Tier 4 and links nobody; a custom favicon with a small
  neighbour set is worth checking host by host. Tier 3 never accumulates.

### 10. Active surface confirmation — last, optional, and no row runs without `active_allowed: true` plus a fresh confirmation naming the host set

| Action | Source | Who learns what |
|---|---|---|
| Port and service enumeration | **Nmap** | Your source address in their logs |
| TLS inspection | **testssl.sh** (local), **Qualys SSL Labs Server Test** (connects from Qualys and publishes to a public board unless you opt out) | A direct TLS connection. The SAN list is an overlooked subdomain source |
| Live DNS and mail records | step 6 tooling, **MXToolbox**, **DNSDumpster** | A query in the target's DNS logs |
| Active subdomain resolution | **Amass** default mode, **subfinder** active mode | Resolution and brute-force traffic on target infrastructure |
| New page capture | **urlscan.io (submit new scan)** | The target sees the fetch; default visibility is public and searchable by the target |
| Evidence snapshot | **Wayback Machine Save Page Now**, **archive.today (submission)** | A public archive record dated to your interest; archive.today captures cannot be withdrawn |
| Path and latency measurement | **RIPE Atlas** | Real packets, and the measurement definition is publicly visible on Atlas |

- Ledger `mode=active`, one row per action, `query` naming the exact hosts and the confirmation text. Grade `A2` —
  direct observation is the most reliable evidence there is, which is why it is gated, not banned; `A1` needs the
  observation independently repeated. Snapshot last: an early Save Page Now dates your interest for a watchful target.

## Reference index
| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting any source. Grep a filtered slice (`accepts` contains the selector, `mode=passive`, `auth=none` first). Never load whole |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next pivot, or the obvious one came back empty. Sections `domain` `subdomain` `ip` `asn` `ssl_cert` `url`, plus WEAK PIVOTS and DEAD ENDS BY DESIGN |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before any step 6, 7b or 10 action; using a research account; the user asks how exposed their own collection is |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Grading a finding and unsure of the Admiralty letter, credibility number, or ICD-203 word |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | Two operators plausibly fit one estate; merging a `candidate_group`; judging a linking datapoint's tier |
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | Scanning-jurisdiction questions, or the registrant turns out to be a private individual |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md` or rendering; deciding what to redact |

## Stop conditions
- The scope question is answered at a stated confidence and every asserted host names its source.
- Enumeration returns only names already in `entities.jsonl`. Two consecutive empty passes end it.
- Every remaining pivot is key-gated and no key exists. Name the missing capability in `gaps.md` ("historical resolution
  pre-2022 needs DNSDB or SecurityTrails") and stop.
- A CDN or WAF wall is reached and no historical origin is recoverable — itself a finding.
- The next step needs active collection without `active_allowed`, or a host outside written scope.
- The estate turned out to belong to someone else. Stop, re-scope, do not silently widen.

Anti-rabbit-hole: name the `Q<n>` a step advances before running it. An unresolved subdomain serving nothing is
inventory, not a finding.

## Refusals — beyond the global gate in `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md`
- **No active probing outside a written scope.** Unauthorized port scanning is a criminal offence in several
  jurisdictions. Nmap, testssl.sh, SSL Labs and active resolution run only against hosts named in an engagement letter,
  scope document, or own-asset claim.
- **A shared-hosting neighbour is not in scope.** Cover for one tenant does not extend to the other domains on that
  address. Enumerate them as context; do not touch them.
- **No circumventing bot protection, rate limits or CAPTCHAs.** Censys, SecurityTrails, Software Heritage and grep.app
  serve interstitials to automated requests — use a browser or record a gap.
- **No retrieving exposed content.** LeakIX and Intelligence X index exposed databases and breach-derived material. Read
  metadata to establish exposure; retrieving, quoting or storing it is outside passive collection and outside nearly
  every engagement scope.
- **No IP-to-person geolocation.** GeoIP resolves to an allocation, not a residence. Decline the inference; offer the
  RIR holder record instead.
- **No recon certificates named after the target.** A TLS certificate for infrastructure bearing the target's name
  publishes your interest into the CT logs, where brand monitoring finds it.
- **No dossier drift.** A registrant name, abuse contact or NOC contact is a selector to hand to another department
  under the same scope question — not permission to profile a person.
