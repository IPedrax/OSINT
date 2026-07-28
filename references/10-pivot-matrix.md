*Load when: you hold a selector and need to know what it can turn into, which named source does it, whether the step is observable by the target, and how often it actually works.*

# Pivot matrix

Every row is one pivot: a selector in, a selector out, through a source that exists in
`${CLAUDE_PLUGIN_ROOT}/assets/sources.csv`. Sources are cited by their exact registry name; grep the
registry for the row before calling anything, and honour `verified=no` by reaching the source through its
homepage rather than a constructed path.

Column legend, identical in every table. **Yields** is the canonical selector type produced (`CONTRACT.md` §4).
**How** names registry sources in the order to try them. **Mode** is `passive` / `active` copied from the
registry row; active needs `active_allowed` plus a fresh confirmation naming the action. **Yield** is an ICD-203
term for how often the pivot returns anything at all, not confidence in what it returns. **Cost** is `free` (no
auth) · `key` (free key or account) · `paid` · `slow`. **Notifies** is `no` · `yes` (target sees it) · `3p` (a
third party is notified, or a public record of your interest is created). **Rel** is the Admiralty reliability
of the typical result (`${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md`); it moves independently of Yield,
since TruePeopleSearch is high yield and grade D. Grade the claim separately from the source.

## email

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `username` | Local-part split, then username plays below. Nothing to call | passive | `very likely` | free | no | F |
| `domain` | Domain part, then domain plays below | passive | `almost certain` | free | no | F |
| `photo` `username` `url` | Gravatar — hash the lowercased trimmed address; a hit often carries a display name and linked accounts | passive | `unlikely` | free | no | B |
| `person_name` `photo` `url` | GHunt for a Google-hosted address; Epieos for a hosted equivalent | active | `likely` | key | 3p | B |
| `breach_record` | Have I Been Pwned, Mozilla Monitor. Exposure metadata only — never retrieve corpus content | passive | `roughly even chance` | free | no | B |
| `breach_record` `social_profile` | EmailRep.io reputation summary. Active because its deliverability fields have undocumented provenance and may be derived by contacting the target's mail server at query time — uncertain means active | active | `likely` | key | 3p | D |
| `email` (org pattern) | Hunter.io Domain Search returns the observed format with a per-address source URL. Hunter.io Email Verifier and NeverBounce are a different step: they open an SMTP conversation with the target's own mail server, and are separate `active` registry rows | passive | `likely` | key | no | C |
| `url` `username` `document` | GitHub Code Search on the address in commit metadata; grep.app; GH Archive for deleted history | passive | `unlikely` | key/slow | no | B |
| `document` `url` | OCCRP Aleph, Intelligence X, Pastebin, Google Search on the quoted address | passive | `unlikely` | key | no | D |
| `domain` `person_name` `company` `address` | Reverse WHOIS by registrant address: ViewDNS.info, DomainTools, WhoisXML API. Only these accept an `email` — RDAP.org and ICANN Lookup take a `domain`, so they come after the reverse lookup, not before it | passive | `unlikely` | free/paid | no | B |
| `social_profile` | Holehe, Epieos registration checks — these trip verification and reset mail | active | `roughly even chance` | free | yes | C |

## username

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `social_profile` `url` | WhatsMyName ruleset, Sherlock, Maigret. Triage only; open every hit yourself | active | `likely` | free | 3p | C |
| `social_profile` `url` | Direct read of platform pages that serve logged-out: Bluesky, Reddit, Keybase | passive | `likely` | free | no | B |
| `username` `social_profile` `url` | Keybase signed identity proofs — one of the few cryptographically hard cross-platform links | passive | `very unlikely` | free | no | B |
| `email` `person_name` | GitHub Code Search commit author fields; GH Archive push payloads; Software Heritage for deleted repos | passive | `roughly even chance` | key/slow | no | B |
| `photo` | Avatar from any confirmed profile, then the photo plays below | passive | `very likely` | free | no | C |
| `url` `document` | Google Search / Yandex / Brave Search on the quoted handle; Wayback Machine (retrieval) and archive.today (retrieval) for deleted profiles | passive | `likely` | free | no | C |
| `person_name` `email` | Maigret parses matched pages and extracts bios, ids and sometimes addresses | active | `roughly even chance` | free | 3p | C |

Entropy first. A handle that returns thousands of unrelated accounts contributes no linking weight; test rarity
before treating a match as a link.

## person_name

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `company` `company_number` `address` | UK Companies House officer search; Corporations Canada; ASIC Connect; ACRA BizFile+; Estonia e-Business Register; OpenCorporates to find which register | passive | `roughly even chance` | free | no | A |
| `document` `company` | SEC EDGAR full-text and DEF 14A; ProPublica Nonprofit Explorer Part VII; The Gazette; PACER and CourtListener | passive | `unlikely` | free | no | A |
| `person_name` `company` `document` | OFAC Sanctions List Search, UK OFSI Consolidated List, UN Security Council Consolidated List, EU Sanctions Map, OpenSanctions for a one-shot multi-regime screen | passive | `very unlikely` | free | no | A |
| `company` `url` | ORCID, OpenAlex, PubMed, Google Scholar for affiliation and to disambiguate a common name | passive | `unlikely` | free | no | B |
| `address` `phone` | North Carolina Voter Registration Data, UK Register of Electors, TruePeopleSearch, ThatsThem, Spokeo | passive | `likely` | free/paid | no | D |
| `person_name` `address` `document` | FamilySearch, Ancestry, Find a Grave, Legacy.com for family structure around a deceased subject | passive | `roughly even chance` | key | no | C |
| `company` `address` | WIPO Global Brand Database and Espacenet — filings often name the real owner years before a register does | passive | `very unlikely` | free | no | C |
| `url` `document` | GDELT Project to establish that coverage exists, then read the original articles | passive | `roughly even chance` | free | no | D |

`person_name` is Tier 3 as a link and never merges two entities. See
`${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`, identity-confusion protocol.

## phone

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `phone` (E.164) `company` | libphonenumber offline — region, line type, numbering-plan carrier | passive | `almost certain` | free | no | B |
| `company` | Twilio Lookup resolves against carrier databases and handles ported numbers; Numverify is a cheaper database lookup | passive | `very likely` | paid/key | no | B |
| `person_name` | Twilio Lookup CNAM for many US landline and mobile numbers | passive | `roughly even chance` | paid | no | B |
| `url` `company` | PhoneInfoga numbering-plan parse plus search-engine pivots. Local only; it never dials | passive | `likely` | free | no | C |
| `person_name` `address` `email` | ThatsThem, TruePeopleSearch, Spokeo, Whitepages, 192.com, Pipl | passive | `roughly even chance` | free/paid | no | D |
| `person_name` `company` | Truecaller — crowdsourced, strong in South Asia, Middle East, parts of Africa | active | `likely` | key | yes | D |
| `social_profile` `person_name` | Epieos phone lookup | active | `roughly even chance` | key | 3p | C |
| `document` `email` | Intelligence X selector search; Pastebin | passive | `unlikely` | key | no | D |

Never add a number to a messenger contact list to test presence. That is an account-existence probe against the
target's device.

## domain

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `subdomain` `ssl_cert` | crt.sh, SSLMate Cert Spotter, Censys Search, subfinder | passive | `very likely` | free/key | no | B |
| `ip` `subdomain` | DNSDB (DomainTools Farsight), CIRCL Passive DNS, SecurityTrails, Microsoft Defender Threat Intelligence (PassiveTotal) | passive | `likely` | paid/key | no | A |
| `ip` | dig (BIND DNS utilities), Google Public DNS, Cloudflare 1.1.1.1 DNS over HTTPS, MXToolbox — live resolution | active | `almost certain` | free | 3p | B |
| `company` (mail/host provider) | MX, SPF and DMARC records read out of passive DNS or an archived capture. SPF enumerates the third-party vendors an organisation authorised | passive | `very likely` | free/key | no | B |
| `company` (mail/host provider) | MXToolbox — live MX, SPF, DKIM, DMARC and blacklist lookups. Same reach into the target's nameservers as live DNS below, and the same gate | active | `almost certain` | free | 3p | C |
| `person_name` `email` `company` `address` | ICANN Lookup and RDAP.org for current registration; DomainTools, WhoisXML API, SecurityTrails for historical WHOIS | passive | `unlikely` | free/paid | no | A |
| `domain` (siblings) | PublicWWW and BuiltWith reverse lookup on an analytics ID, ad ID or tracking code; Shodan `http.favicon.hash` clustering | passive | `roughly even chance` | key/paid | no | C |
| `url` `subdomain` | Wayback Machine (retrieval), Common Crawl URL index, Arquivo.pt full-text, archive.today (retrieval) | passive | `very likely` | free/slow | no | B |
| `url` `ip` `ssl_cert` | urlscan.io (search public scans) — someone else's capture, including every host the page contacted | passive | `roughly even chance` | key | no | B |
| `document` `email` `url` | GitHub Code Search and grep.app for the domain in configs and source | passive | `roughly even chance` | key | no | B |
| `breach_record` | Have I Been Pwned domain search | passive | `roughly even chance` | free | no | B |
| `subdomain` `netblock` | Amass, DNSDumpster — resolve and brute-force candidate names | active | `likely` | free | yes | B |

## subdomain

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `ip` | CIRCL Passive DNS, DNSDB (DomainTools Farsight), SecurityTrails historical resolutions | passive | `likely` | key/paid | no | A |
| `ssl_cert` | crt.sh and Censys Search on the exact name; SANs on one cert often name the rest of the estate | passive | `very likely` | free/key | no | B |
| `url` `ip` `ssl_cert` | urlscan.io (search public scans) for an existing capture; Wayback Machine (retrieval) for what it served | passive | `roughly even chance` | free/key | no | B |
| `ip` `url` | Shodan, Censys Search, FOFA, LeakIX — banners and exposed services from their scans, not yours | passive | `likely` | key | no | B |
| `company` | Hostname convention itself (`jira-`, `vpn-`, `sap-`) plus BuiltWith for the stack | passive | `likely` | key | no | C |
| `ip` `url` | Nmap, Qualys SSL Labs Server Test, testssl.sh — direct connection | active | `almost certain` | free | yes | A |

Wildcard certificates hide the specific hostname and internal hosts that never received a public certificate
never appear in CT. CT absence is evidence about CT.

## ip

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `asn` `netblock` | Team Cymru IP-to-ASN Mapping, RIPEstat, Hurricane Electric BGP Toolkit | passive | `almost certain` | free | no | A |
| `company` `address` `email` `person_name` | RIPE Database, ARIN Whois-RWS, APNIC Whois via the IANA RDAP Bootstrap Registry | passive | `very likely` | free | no | A |
| `domain` `subdomain` (co-hosted) | DNSDB (DomainTools Farsight), CIRCL Passive DNS, SecurityTrails, ViewDNS.info reverse IP | passive | `likely` | paid/key | no | A |
| `domain` `url` `ssl_cert` | Shodan, Censys Search, FOFA, LeakIX — historical banners and certificates on that address | passive | `likely` | key | no | B |
| `coordinates` `address` `company` | MaxMind GeoLite2, IPinfo.io. Coordinates are frequently a regional centroid | passive | `almost certain` | key | no | C |
| `ip` (classification) | GreyNoise — is this opportunistic background noise or aimed at you | passive | `roughly even chance` | key | no | B |
| `person_name` `address` | ThatsThem accepts an IP as a selector | passive | `very unlikely` | free | no | D |
| `url` | Nmap, RIPE Atlas measurements | active | `very likely` | free/key | yes | A |

Never geolocate a person from an IP. Read `IPinfo.io` privacy flags before building any theory on an apparent
country: commercial VPN exits and carrier-grade NAT invalidate the whole line.

## asn

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `netblock` `ip` | Hurricane Electric BGP Toolkit, RIPEstat — every announced prefix | passive | `almost certain` | free | no | A |
| `company` `address` `email` | RIPE Database aut-num and abuse-c, ARIN Whois-RWS, APNIC Whois | passive | `very likely` | free | no | A |
| `company` `address` `asn` | PeeringDB — facilities, IXPs, NOC contacts. Self-published, so grade it C | passive | `likely` | key | no | C |
| `domain` `ip` | Censys Search and Shodan filtered to the ASN; Hurricane Electric's observed DNS names in a prefix | passive | `likely` | key | no | B |
| `asn` (relationships) | Hurricane Electric BGP Toolkit peers and upstreams | passive | `very likely` | free | no | B |

A shared ASN at a cloud or CDN provider is Tier 4 — no weight at all. See WEAK PIVOTS.

## company

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `company_number` `address` | The national register itself: UK Companies House, Delaware Division of Corporations, Germany Handelsregister, France Annuaire des Entreprises, Netherlands KVK Handelsregister, ACRA BizFile+, ASIC Connect. OpenCorporates and EU e-Justice Business Registers only to find which one | passive | `very likely` | free | no | A |
| `company_number` `address` | GLEIF Global LEI Index — legal name, registered address, local registry id, and Level 2 parent relationships where reported | passive | `roughly even chance` | free | no | A |
| `person_name` `document` | Officer, director and PSC entries on the register; SEC EDGAR DEF 14A; FINRA BrokerCheck | passive | `likely` | free | no | A |
| `company` `person_name` `address` | ICIJ Offshore Leaks Database; OCCRP Aleph. Presence is not wrongdoing | passive | `very unlikely` | key | no | B |
| `person_name` `document` | OFAC Sanctions List Search, US Consolidated Screening List, UK OFSI Consolidated List, World Bank Listing of Ineligible Firms and Individuals, OpenSanctions | passive | `very unlikely` | free | no | A |
| `document` `address` | USAspending.gov, TED Tenders Electronic Daily, UK Contracts Finder — counterparties, addresses, contract values | passive | `roughly even chance` | free | no | A |
| `document` `person_name` | PACER, CourtListener, Find Case Law, The Gazette | passive | `roughly even chance` | free/key | no | A |
| `domain` `url` | Hunter.io and Apollo.io map a company to its mail domain; deps.dev maps it to published packages and repos | passive | `likely` | key | no | B |
| `photo` `address` | WIPO Global Brand Database, Espacenet — applicant and representative addresses | passive | `unlikely` | free | no | C |
| `url` `document` | GDELT Project for adverse-media presence, then the original articles | passive | `likely` | free | no | D |

## company_number

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `document` | Filing history on the issuing register — accounts, charges, annual returns, officer appointments and terminations | passive | `almost certain` | free | no | A |
| `person_name` `address` | PSC / beneficial-ownership entries where the jurisdiction still publishes them; Ireland Register of Beneficial Ownership | passive | `roughly even chance` | free/key | no | A |
| `company` `company_number` | GLEIF Global LEI Index to cross the identifier into other jurisdictions | passive | `roughly even chance` | free | no | A |
| `company` `address` | ABN Lookup, IRS Tax Exempt Organization Search, Charity Commission Register of Charities for the sector-specific record | passive | `likely` | free | no | A |
| `document` | TED Tenders Electronic Daily — award notices carry the winner's national registration number, so the identifier searches directly | passive | `unlikely` | free | no | C |

`company_number` from a registry, present in two primary records, is Tier 1 — the strongest link this plugin can
produce. It is the reason to always carry the number, never just the name.

## photo

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `coordinates` `person_name` `email` | ExifTool locally — GPS, capture time with offset, camera make/model/serial, editing history, IPTC author. Run this first, before any upload | passive | `roughly even chance` | free | no | A |
| `person_name` `company` `url` | Content Credentials — a valid C2PA manifest is strong provenance, including generative-model disclosure | passive | `very unlikely` | free | no | B |
| `url` `photo` `social_profile` | Yandex Images first for faces and near-duplicate crops; Google Lens for objects, landmarks and OCR; Bing Visual Search; Baidu Images | passive | `roughly even chance` | free | no | B |
| `url` (first appearance) | TinEye — the only major engine that reliably sorts oldest first, which is what provenance questions actually need | passive | `roughly even chance` | free | no | B |
| `coordinates` | Google Lens OCR on signage, then GeoNames / OpenStreetMap tag search for the operator or brand read off the sign | passive | `roughly even chance` | free/key | no | C |
| `coordinates` | SunCalc and ShadeMap — shadow-to-object ratio narrows time of day; shadow bearing narrows azimuth | passive | `likely` | free | no | B |
| `coordinates` `photo` | Google Street View, Yandex Maps, Mapillary, Bing Maps for a ground-truth match on a candidate location | passive | `roughly even chance` | free/key | no | B |
| `photo` (manipulation) | Hive AI-Generated Content Detection, InVID WeVerify Verification Plugin | passive | `likely` | key | no | D |
| `coordinates` | FotoForensics quantisation tables — but free-tier uploads join a public gallery | active | `roughly even chance` | free | 3p | B |
| `url` `photo` | PimEyes face search. Not against private individuals; record the authority for every query | passive | `roughly even chance` | paid | no | C |

Synthetic-media and manipulation checks run before any geolocation effort, not after. Metadata is a claim by
whoever last wrote the file, not an observation.

## crypto_address

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `tx_hash` `crypto_address` | mempool.space for Bitcoin; Etherscan, BscScan, Tronscan, Solscan for the respective chain | passive | `almost certain` | free/key | no | B |
| `domain` `username` `email` `url` `social_profile` | ENS reverse resolution then the text records on the name — handle, GitHub username, email, avatar, website | passive | `unlikely` | free | no | B |
| `company` `person_name` | Arkham Intelligence and Chainalysis entity labels; Etherscan's own address labels. Uncorroborated third-party attribution — grade C at best | passive | `roughly even chance` | key/paid | no | D |
| `crypto_address` (cluster) | WalletExplorer common-input-ownership clusters. Stale — historical cases only | passive | `roughly even chance` | free | no | D |
| `crypto_address` `document` | OFAC Sanctions List Search carries designated addresses; OpenSanctions mirrors them | passive | `very unlikely` | free | no | A |
| `url` `domain` | Chainabuse user-submitted abuse reports; PublicWWW full-text search for the address string in page source | passive | `roughly even chance` | free/key | no | D |
| `url` `document` | Google Search, Intelligence X and Pastebin on the quoted address | passive | `roughly even chance` | key | no | D |

Only a valid signature demonstrates key control. An address appearing in a post is not ownership.

## ssl_cert

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `subdomain` `domain` | crt.sh and SSLMate Cert Spotter — SANs on one certificate enumerate the estate it was issued for | passive | `very likely` | free/key | no | B |
| `ip` `domain` | Censys Search and Shodan certificate-field pivots: identical key fingerprint, subject organisation, or an unusual issuer | passive | `likely` | key | no | B |
| `company` | The subject organisation field, but only on OV or EV certificates — the CA checked it against a register. DV certificates assert nothing about identity | passive | `unlikely` | free | no | A |
| `url` `ip` | urlscan.io (search public scans) and FOFA for hosts observed presenting the certificate | passive | `roughly even chance` | key | no | B |
| `ssl_cert` | Take the hostname off the certificate, then Qualys SSL Labs Server Test or testssl.sh against it — what that host presents right now | active | `almost certain` | free | yes | A |
| `subdomain` (ongoing) | SSLMate Cert Spotter monitoring — new issuance alerts across an engagement | passive | `likely` | key | no | B |

An identical certificate key fingerprint across two domains is Tier 2. A shared CA, a shared issuance date, or a
shared wildcard at a hosting provider is Tier 4.

## social_profile

No registry source accepts `social_profile` as an input. You pivot by decomposing the profile into selectors
that do have sources, then feeding those.

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `username` `photo` `url` `person_name` | Read the public page logged-out, or the archived copy: Wayback Machine (retrieval), archive.today (retrieval), Ghostarchive | passive | `very likely` | free | no | C |
| `username` (immutable id) | The platform's numeric or DID account identifier, not the display name. Bluesky exposes DID and handle history unauthenticated | passive | `roughly even chance` | free | no | B |
| `username` `url` | Keybase proofs attached to the account | passive | `very unlikely` | free | no | B |
| `url` `document` | Google Search, Bing, Yandex on the quoted handle and on distinctive bio strings | passive | `likely` | free | no | C |
| `photo` → `url` | Avatar into Yandex Images and TinEye | passive | `roughly even chance` | free | no | B |
| `social_profile` `person_name` | LinkedIn viewed while signed in | active | `very likely` | key | yes | C |

A platform-issued immutable account identifier appearing on two records is Tier 1. A display name, a bio, or a
profile photo is Tier 3 or 4 — any of them can be copied by an impersonator.

## url

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `url` `document` `photo` `video` | Wayback Machine (retrieval), archive.today (retrieval), Ghostarchive, Arquivo.pt. Always before a live fetch | passive | `likely` | free | no | B |
| `domain` `ip` `ssl_cert` | urlscan.io (search public scans) — DOM, screenshot, and every host the page contacted | passive | `roughly even chance` | key | no | B |
| `domain` `url` | PublicWWW and BuiltWith on an identifier lifted from the page source; grep.app and GitHub Code Search on a distinctive string | passive | `roughly even chance` | key | no | C |
| `company` `url` | BuiltWith technology profile; deps.dev if the URL is a repository | passive | `likely` | key | no | B |
| `url` `subdomain` | Common Crawl URL index for every path and hostname seen under the host | passive | `likely` | free/slow | no | B |
| `url` `document` | Wayback Machine Save Page Now, archive.today (submission) — creates your evidence copy, and fetches the page | active | `very likely` | free | yes | B |
| `ip` `ssl_cert` | urlscan.io (submit new scan). Default visibility is public and searchable by the target | active | `almost certain` | key | yes/3p | B |
| `email` `url` | TruffleHog against a repository URL — it verifies discovered credentials against live services | active | `roughly even chance` | free | yes | B |

## file_hash

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `ip` `domain` `url` | Shodan `http.favicon.hash` — every other host serving an identical favicon. The strongest infrastructure-clustering pivot in the registry | passive | `likely` | key | no | B |
| `breach_record` | Pwned Passwords, for a password hash held in an authorized investigation | passive | `roughly even chance` | free | no | B |
| `file_hash` (identity) | An identical hash across two artifacts is Tier 1 — same bytes, no interpretation needed | passive | `almost certain` | free | no | A |

The registry currently carries **no malware-sample or file-reputation repository**. Sample-hash enrichment is a
gap, not a pivot; record it in `gaps.md` rather than improvising an endpoint.

## coordinates

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `photo` | Google Earth Pro historical imagery, Google Street View time slider, Mapillary, Bing Maps, Yandex Maps | passive | `likely` | free/key | no | B |
| `address` `company` | OpenStreetMap object tags — operator, brand, phone, website, opening hours, plus the public edit history | passive | `likely` | free | no | C |
| `photo` `coordinates` | Copernicus Data Space Ecosystem, USGS EarthExplorer, NASA Worldview, Planet for dated overhead imagery | passive | `very likely` | key/paid | no | A |
| `coordinates` (time) | SunCalc and ShadeMap to test whether a claimed time is consistent with shadows | passive | `almost certain` | free | no | B |
| `coordinates` | NASA FIRMS thermal anomalies; National Collection of Aerial Photography for historical aerial coverage | passive | `roughly even chance` | free/key | no | A |
| `address` `coordinates` | GeoNames, Google Maps, OpenRailwayMap for named-feature and infrastructure context | passive | `very likely` | key | no | C |
| `aircraft` `vessel` | Flightradar24, ADS-B Exchange, OpenSky Network, MarineTraffic filtered to a bounding box and time window | passive | `roughly even chance` | free/key | no | B |

## document

| Yields | How | Mode | Yield | Cost | Notifies | Rel |
|---|---|---|---|---|---|---|
| `person_name` `email` `coordinates` | ExifTool on the file locally — author, company, creation and edit timestamps, producing application | passive | `likely` | free | no | A |
| `person_name` `company` `url` | Content Credentials manifest where present | passive | `very unlikely` | free | no | B |
| `url` (other copies) | Google Search / Bing / Yandex on a verbatim distinctive sentence; Arquivo.pt full-text over archived pages | passive | `roughly even chance` | free | no | C |
| `company` `person_name` `address` | OCCRP Aleph and ICIJ Offshore Leaks Database for the entities named inside it | passive | `roughly even chance` | key | no | D |
| `url` `domain` | Embedded links and remote-resource references inside the file — inspect statically, never open | passive | `roughly even chance` | free | no | B |
| `document` (filing chain) | SEC EDGAR, PACER, CourtListener, The Gazette for the exhibit or docket the document belongs to | passive | `roughly even chance` | free/key | no | A |

No registry source accepts a `document` as input, so every row here feeds a string, name or identifier lifted
out of the file, not the file itself. Documents call home: remote images, beacons and canary tokens fire on
open, so sandbox offline with remote content disabled. Opening one is `active`.

## Remaining selector types

| Selector | Best pivots | Mode | Cost | Notifies |
|---|---|---|---|---|
| `netblock` | Team Cymru IP-to-ASN Mapping, RIPEstat, RIPE Database / ARIN Whois-RWS / APNIC Whois for holder; Censys Search and Shodan for hosts; Hurricane Electric BGP Toolkit for the announcing ASN | passive | free/key | no |
| `address` | UK Companies House and Florida Sunbiz address search for entity clusters; OpenStreetMap tags; Google Street View; TruePeopleSearch and North Carolina Voter Registration Data for occupancy history | passive | free | no |
| `video` | InVID WeVerify Verification Plugin for keyframes into Yandex Images; ExifTool; Ghostarchive for a deleted copy; Content Credentials | passive | free | no |
| `tx_hash` | mempool.space, Etherscan, BscScan, Tronscan, Solscan for inputs, outputs and internal calls; WalletExplorer for the historical cluster | passive | free/key | no |
| `vehicle_plate` | UK MOT History — make, colour, mileage series and advisory text. No legitimate route turns a plate into a keeper identity | passive | free | no |
| `vessel` | Equasis for registered owner, ISM manager and beneficial owner where declared; MarineTraffic for port-call history; UK OFSI Consolidated List and OFAC Sanctions List Search carry IMO numbers | passive | key | no |
| `aircraft` | FAA Aircraft Registry for the registered owner — usually a trust or SPV, so pivot that name into corporate work; ADS-B Exchange for aircraft other trackers hide; OpenSky Network for deep history; Planespotters | passive | free/key | no |
| `breach_record` | Metadata only: Have I Been Pwned breach date, record count and data classes. Do not retrieve, quote or store corpus content | passive | free | no |

## HIGH-YIELD CHAINS

Drop-off is what to expect, not what you are owed. Each chain names where it usually dies.

| # | Chain | Where it dies, and what to do about it |
|---|---|---|
| C1 | Estate discovery → sibling business. `domain` -crt.sh-> `subdomain` -CIRCL Passive DNS / DNSDB-> `ip` -Shodan / ViewDNS.info-> co-hosted `domain` -UK Companies House / Delaware Division of Corporations-> `company` | The co-hosting hop, on shared or CDN infrastructure. CT returns dozens and passive DNS resolves most of them, but one address usually hosts unrelated tenants. Only a dedicated address makes the `ip` link survive — count the neighbours before spending anything on it |
| C2 | Tracking identifier → operator network. `url` -page source-> analytics / ad / tag ID -PublicWWW, BuiltWith reverse-> sibling `domain` -ICANN Lookup, crt.sh-> `company` | Agency-managed sites, where the shared ID belongs to the agency and not the operator. Extraction is reliable; the reverse lookup is the paid part and the free tier truncates. Confirm the ID is account-scoped, not container-scoped, before treating it as a link |
| C3 | Alias → real name via code. `username` -GitHub Code Search commits-> `email` -Gravatar, Have I Been Pwned-> `person_name` -UK Companies House officer search-> `company` | Privacy-email settings, and name-to-officer when the name is common. Commit email is present far more often than people expect; `noreply` addresses kill it. Recover deleted history from GH Archive and Software Heritage before closing the branch |
| C4 | Corporate shell unwinding. `company` -register-> `company_number` -officer entries-> `person_name` -officer search-> other appointments -shared `address`-> the cluster | The nominee layer. Officers are usually present; the address hop collapses on formation agents and virtual offices, which is Tier 3 and never a merge. Escape through filings and litigation — SEC EDGAR, PACER, CourtListener, The Gazette — which name real controllers when a register does not |
| C5 | Image → account → identity. `photo` -ExifTool, Content Credentials-> provenance -TinEye oldest-first-> first appearance `url` -page-> `social_profile` -> `username` -> C3 | Cropped or re-encoded reposts no engine matches. Platforms strip EXIF, so intact metadata is itself a finding about origin, and TinEye's oldest-first ordering is what makes the provenance claim defensible. Yandex Images is the second pass worth running; a third engine rarely adds anything |
| C6 | Wallet → social identity. `crypto_address` -ENS reverse-> name -text records-> `username` / `url` -> C3, with Arkham Intelligence and Chainabuse only as leads | Exchange deposit addresses, which belong to the exchange. Most addresses have no ENS name; those that do frequently carry a handle. Attribution labels are proprietary and uncorroborated — grade C, never merge on one |
| C7 | ASN → forgotten infrastructure. `asn` -Hurricane Electric BGP Toolkit-> `netblock` -Censys Search / Shodan-> hosts -certificate subject / SAN-> `domain` -> `subdomain` | Organisations with no ASN of their own, which is most of them. Prefixes are complete; host coverage is a scan snapshot, so a hit means *was*, not *is*. Only worth running when the target announces its own space |
| C8 | Historical resolution → predecessor host. `domain` -SecurityTrails / DNSDB historical-> prior `ip` -reverse-> what else lived there then -Wayback Machine (retrieval)-> what it served | The date window. Historical DNS is the paid or key-gated part and free tiers cap it hard. Two records must overlap in time to correlate: an IP shared in 2019 and again in 2024 with a gap between is not a link |
| C9 | Person → jurisdiction hop. `person_name` -OpenSanctions multi-regime screen-> hit or nothing -GLEIF Global LEI Index-> the group's entities in other jurisdictions -local register-> `document` | Jurisdictions with no public register. Screening is fast and usually empty; GLEIF Level 2 parents exist only where reported. A closed jurisdiction is a `gaps.md` entry naming the source that would resolve it, not a conclusion |
| C10 | Email pattern → org roster. `domain` -Hunter.io Domain Search-> `email` pattern -apply to `person_name` from SEC EDGAR or Companies House-> candidate `email` -Gravatar, Have I Been Pwned-> corroboration | Verification. The pattern is usually recoverable; per-person confirmation is where it collapses. Do not verify with an SMTP or reset probe — a constructed address stays `inferred` with its assumption stated, or it is dropped |

## PIVOTS THAT NOTIFY

**Every row below is observable by the target or creates a third-party record of your interest.
None of them run without `active_allowed: true` in scope and a fresh confirmation naming the specific action.**
This is the operational form of `CONTRACT.md` §9.

| Pivot | Who learns, and what they learn |
|---|---|
| Holehe, Epieos registration checks | The target's own inbox receives verification or reset mail. Direct tip-off |
| Sherlock, WhatsMyName, Maigret | Requests to every platform on the list from one address in seconds. Platforms log it; some rate-limit or ban |
| LinkedIn profile view while signed in | The owner sees who viewed. The single most common way a corporate target learns it is being looked at |
| Truecaller lookup | Premium users see who searched them |
| Live DNS against the target's authoritative nameservers (dig, MXToolbox, DNSDumpster) | A query in the target's DNS logs with your resolver and timing |
| Amass default mode, DNSDumpster record view | Resolution and brute-force traffic hitting target infrastructure |
| Nmap, RIPE Atlas measurements | Packets from your host in the target's logs with your source address |
| Qualys SSL Labs Server Test, testssl.sh | A direct TLS connection; SSL Labs additionally publishes results by default |
| urlscan.io (submit new scan) | The target sees the fetch, and a default-visibility scan becomes publicly searchable — including by the target |
| Wayback Machine Save Page Now, archive.today (submission) | The page is fetched, and a public archive record dated to your interest is created |
| FotoForensics free tier | The uploaded image joins a publicly browsable gallery |
| TruffleHog default mode | Discovered credentials are verified against the live service, which logs the attempt |
| Hunter.io Email Verifier, NeverBounce | An SMTP conversation with the target's own mail server |
| Any direct fetch of a target-controlled page | Your IP, user-agent, referrer and timing in their logs and analytics |
| Opening a document, shortened link, or shared file the target controls | A callback with your IP and open time — often a deliberate tripwire |
| Requesting a TLS certificate for recon infrastructure named after the target | Your certificate appears in public CT logs, where brand monitoring finds it |

Rule, restating `CONTRACT.md` §9: a step is `active` if the target can observe it, if a third party is notified
or a public record of your interest is created, or if it changes state anywhere. Reading a dataset a third party
already collected is not active. Uncertain means active. Passive substitutes are in
`${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` §1.

## WEAK PIVOTS

These feel productive. Most are not. Each row names what would make it strong.

| Weak pivot | Why it is weak | What makes it strong |
|---|---|---|
| Shared IP on common hosting | One address at a shared host serves hundreds of unrelated tenants. Co-hosting is a property of the host | A dedicated address with a small, stable neighbour set, plus overlapping date windows in passive DNS |
| Shared nameservers at a large provider | Everyone using that registrar or DNS host shares them. It identifies the provider, not the operator | Self-hosted or rare nameservers, especially ones named after the operator, present on both domains at the same time |
| Shared ASN at a cloud or CDN provider | Tier 4. Millions of unrelated tenants share it | An ASN registered to the organisation itself, with the prefix confirmed in the RIR record |
| Common `person_name` match | Tier 3 at best, Tier 4 for common names. This is the mechanism by which an uninvolved person acquires someone else's history | Name plus a registry-issued identifier in a primary record, or name plus address in a primary record |
| Shared generic favicon | Default framework, CMS or template icons collide across unrelated sites | A custom or accidentally distinctive favicon, with the neighbour set small enough to enumerate and check individually |
| CDN or WAF IP | The address belongs to Cloudflare, Fastly or Akamai. It says nothing about the origin | An origin address recovered from historical passive DNS predating CDN adoption, or from a certificate on the origin host |
| Same registrar or hosting provider | Tier 3. Market concentration means most domains share a handful of providers | A registrar-assigned account reference appearing across both registry records |
| Shared `address` at a formation agent or virtual office | Thousands of entities share it by design | The address appearing as an operating address in a filing, or with a phone or officer that is not the agent's |
| Data-broker "possible relatives" | Tier 4. Algorithmic, unsourced, and wrong often enough to be dangerous | A primary record — voter file, probate filing, registry entry — naming the relationship |
| Aggregator agreement | OpenCorporates, OpenSanctions, ViewDNS.info, Intelligence X, Pipl repackage others' collection. Two aggregators carrying one fact is one source | Following each aggregator's link back to the issuing register or primary source and citing that |
| Similar writing style or posting hours | Tier 3, unfalsifiable at this scale | Nothing. Do not use it as a link; use it to prioritise which hard check to run next |
| Profile photo similarity | Photos are reused, stolen and stock. Tier 3 | The same image with intact matching EXIF, or a Tier-1 platform account identifier on both profiles |

## LINKING DATAPOINT STRENGTH

Which pivot *outputs* carry merge authority. Tier definitions and merge rules live in
`${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`; this table only maps pivots onto them.

| Tier | Pivot outputs that land here |
|---|---|
| 1 | `company_number` from an issuing register in two primary records · a platform-issued numeric id or DID (Bluesky) on two `social_profile` · a valid signature demonstrating control of a `crypto_address` · identical `file_hash` · a validating Keybase proof · a government identifier in a primary record |
| 2 | A rare `username` reused across platforms, entropy-tested · a commit `email` from GitHub Code Search or GH Archive tying `username` to `person_name` · the same `email` as contact on two independent records · identical `ssl_cert` key fingerprint on two `domain` · `address` plus `person_name` in a primary record · a Gravatar profile linking an `email` to a named account |
| 3 | `person_name` match · shared `ip` or `netblock` on shared hosting · shared registrar, nameserver or hosting provider · shared `address` at a formation agent · `photo` similarity · an Arkham Intelligence or Etherscan address label · any aggregator assertion · a self-reported employer or city |
| 4 | Any name collision · shared `asn` at a cloud or CDN provider · shared generic favicon · CDN IP · broker "possible relatives" |

Two properties decide the tier and are easy to skip: **date overlap** — two records must be contemporaneous to
correlate, since domains resell, phones recycle and usernames transfer — and **entropy**, because a selector
shared by thousands links nobody. Record both as findings before the link. Tier 3 does not accumulate: five
Tier-3 matches remain a `candidate_group`.

## DEAD ENDS BY DESIGN

Pivots that used to work and no longer do. Practitioners lose hours here.

| Dead pivot | What changed | Do instead |
|---|---|---|
| WHOIS registrant name, email, address | GDPR and the 2018 ICANN Temporary Specification redacted contact data on most gTLDs; many ccTLDs redacted natural persons long before | ICANN Lookup and RDAP.org for registrar, EPP status codes, nameservers and dates, which are usually more evidentially useful anyway. Historical WHOIS predating 2018 via DomainTools, WhoisXML API or SecurityTrails |
| Free reverse-WHOIS by registrant email or name | Withdrawn to paid tiers alongside redaction | DomainTools or WhoisXML API if budgeted; otherwise crt.sh, PublicWWW and analytics-ID pivots reach the same estates |
| EU beneficial-ownership registers | The CJEU's November 2022 ruling struck down general public access; most member states closed or restricted theirs | Ireland Register of Beneficial Ownership and UK Companies House PSC entries, which remain accessible; otherwise the filing history, and record the rest as a gap |
| `cache:` operator and Google's cached pages | Retired in 2024 | Wayback Machine (retrieval), archive.today (retrieval), Common Crawl, Arquivo.pt |
| `link:` and `info:` search operators | Long since non-functional; `link:` returns nothing meaningful | PublicWWW full-text source search; Common Crawl link graphs; `site:` and verbatim-phrase queries |
| Facebook Graph Search and its URL-parameter successors | Retired in 2019; the parameterised workarounds were closed after it | Public page and group content only, via general search engines and archives. Do not reconstruct removed query paths |
| Free X/Twitter API and open logged-out browsing | Free API tier withdrawn in 2023; logged-out access repeatedly restricted since | Archived copies via Wayback Machine (retrieval) and archive.today (retrieval), which captures social pages Wayback will not |
| Pushshift-style open Reddit history | Public access ended with the 2023 API pricing change | Reddit's own public pages for live content; archives for deleted posts |
| Venmo public transaction feed | The global public feed was removed and per-account defaults tightened | Nothing equivalent. Record as a gap |
| Instagram and Facebook public data endpoints | Progressively closed after 2018 | Public web pages logged-out and archived copies only |
| Google+ profile enumeration | The service shut down in 2019 | Wayback Machine (retrieval) for archived profiles |
| WalletExplorer for recent activity | The clustering dataset has not been meaningfully maintained for years | mempool.space to read the graph by hand; Arkham Intelligence or Chainalysis for labels, graded as uncorroborated |
| Scriptable Have I Been Pwned web lookup | The free web form now sits behind a bot challenge | Manual browser check, or the paid API key. Do not attempt to defeat the challenge |
| Free-tier Censys and SecurityTrails at scale | Free access progressively reduced; both also serve bot interstitials to automated requests | crt.sh and subfinder for CT and passive enumeration; confirm current quotas in a browser before planning a case around either |
| UK national online electoral roll search | No national lookup exists; the open register is reached through local authorities or commercial resellers | UK Companies House officer and address search, and the sources listed under `person_name` |
| Turning a UK plate into a keeper identity | Never publicly available, and correctly so | UK MOT History for vehicle facts only |
