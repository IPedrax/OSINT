*Load when: constructing a query against a search engine, code host, paste site, infrastructure index, social platform or web archive — before writing the query, not after it returns nothing.*

# Search operators by surface

A retired operator does not throw an error. It degrades into an ordinary keyword, the query still
returns plausible-looking results, and you never learn it failed. That is why every table here
carries a status column.

| Status | Meaning |
|---|---|
| works | Currently supported and behaves as described |
| undocumented | Not in the vendor's own operator list but observed to work; can vanish without notice |
| retired | Removed. The query degrades to plain keywords — this is the trap |
| uncertain | Current support could not be confirmed here. Test it in the engine before a case depends on it |

**A search result is not a finding.** The engine attests only that its index held a match at query
time. Grade the page the result points at, per `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md`,
and grade it as one source: an authoritative page reached by a dork is `A3` alone, `A2` if
consistent with other collected material. The one single-source `A1` exemption is a certificate
transparency entry, because it is self-authenticating and independently mirrored. Nothing else on
this page qualifies.

Record the exact query string, engine, account state and date for every hit — dorking results are not otherwise reproducible (`01-tradecraft-opsec.md` §3).

## 1. General web engines

### 1.1 Google Search — works

| Operator | Status | Notes |
|---|---|---|
| `site:` | works | Domain, subdomain, or path prefix. `site:*.acme.com` reaches subdomains |
| `-site:` | works | Drop one host from an otherwise broad query |
| `filetype:` | works | One extension per operator; alternatives need `OR` |
| `ext:` | undocumented | Behaves as `filetype:`; absent from Google's own operator list |
| `intitle:` `allintitle:` | works | `allintitle:` must not be mixed with other operators |
| `inurl:` `allinurl:` | works | Same mixing restriction |
| `intext:` `allintext:` | works | Forces a term into the body, not title/URL/anchor |
| `"phrase"` | works | Also suppresses stemming and synonym expansion inside the quotes |
| `-term` | works | Binds to one term or one operator expression |
| `OR` `|` | works | `OR` must be uppercase; lowercase `or` is a stopword |
| `*` | works | Single-term placeholder inside a phrase |
| `before:` `after:` | works | `YYYY-MM-DD`, also `YYYY` and `YYYY-MM`. Filters Google's *estimate* of page date, which is often wrong |
| `..` | works, degraded | Numeric range. Results are inconsistent; verify by eye |
| `AROUND(n)` | undocumented | Proximity. Works often enough to try, never guaranteed |
| `inanchor:` `allinanchor:` | undocumented | Never officially documented; behaviour inconsistent |
| `imagesize:` | uncertain | Reported to work in Google Images. Confirm before relying on it |

### 1.2 Google Search — retired, and what practitioners still waste hours on

| Operator | Status | Replacement |
|---|---|---|
| `cache:` | retired | Removed in 2024. Use `Wayback Machine (retrieval)` for a dead URL |
| `link:` | retired | Deprecated 2017, never restored. Backlink data now needs a commercial index |
| `info:` | retired | Removed. Nothing replaced it |
| `related:` | retired / unreliable | Widely reported non-functional. Do not build a query on it |
| `+term` | retired | Repurposed in 2011. Use `"term"` for forced inclusion |
| `~term` | retired | Synonym expansion is now implicit and cannot be requested |
| `phonebook:` `rphonebook:` `bphonebook:` | retired | Removed 2010. No successor |
| `daterange:` | retired / unreliable | Julian-date filter. Use `before:` / `after:` |
| `numrange:` | uncertain | `..` is the surviving form |
| `blogurl:` | retired | Blog Search is gone |
| `location:` `source:` | not web operators | Google News surface only |

Google is personalised and country-filtered, including right-to-be-forgotten delistings in the EU
(registry `Google Search`). Two analysts get different result sets. Query signed out and archive
every hit.

### 1.3 Bing

Different crawl and different ranking from Google — it routinely surfaces pages Google has dropped
(registry `Bing`). It is also the index behind `DuckDuckGo`, so agreement between the two is one
source seen twice, not corroboration.

| Operator | Status | Notes |
|---|---|---|
| `site:` `domain:` | works | |
| `filetype:` `ext:` | works | |
| `intitle:` | works | |
| `inbody:` | works | Bing's equivalent of Google's `intext:` |
| `url:` | works | Tests whether a specific URL is in the index |
| `contains:` | works | Pages linking to a file of that type, e.g. `contains:pdf` — no Google equivalent |
| `feed:` `hasfeed:` | works | Locates syndication feeds on a site |
| `loc:` `language:` `prefer:` | works | Country, language, and soft-ranking preference |
| `( )` grouping | works | Genuine boolean grouping. Google does not document this and behaves inconsistently |
| `NOT` `-` `OR` `|` | works | |
| `ip:` | uncertain | Documented Bing operator for co-hosted sites; results have degraded badly. Use `Shodan` or `SecurityTrails` instead |
| `inanchor:` | uncertain | Historically supported, now inconsistent |
| `intext:` | uncertain | Use `inbody:` |
| `linkfromdomain:` | uncertain / likely retired | Do not plan around it |

### 1.4 DuckDuckGo, Brave Search, Yandex, SearXNG

| Engine | Supported | Absent or different |
|---|---|---|
| `DuckDuckGo` | `site:` `filetype:` `intitle:` `inurl:` `-` `""` `OR`, and `!bang` syntax jumping straight into a site's own search | No `before:`/`after:` — use the UI time filter. No `AROUND()`. No `allin*`. `intext:` uncertain |
| `Brave Search` | `site:` `filetype:` `intitle:` `inurl:` `-` `""` `OR`. Genuinely independent index, so a real second opinion (registry) | `before:`/`after:` and `intext:` uncertain. Goggles — user-defined re-ranking rulesets — are a second axis no other engine offers |
| `Yandex` | `site:` `host:` `rhost:` `domain:` `url:` `mime:` (its `filetype:`) `lang:` `title:` `inurl:` `date:`; `!` forces exact word form, `+` requires, `-` excludes, `""` phrases | `/n` proximity, `&` same-sentence and `&&` same-document are documented but drift — verify in Yandex's own operator help. Best coverage of Russian-language content; the query itself is disclosed to a Russian-jurisdiction operator (registry) |
| `SearXNG` | Whatever the selected upstream engine supports, plus `!bang` engine and category selection | Nothing of its own. A public instance operator sees every query — self-host for sensitive work (registry). A relayed hit must be re-checked at the engine that produced it before citation |

### 1.5 Combining operators

- Adjacent terms are implicitly `AND` on every engine here. Writing `AND` is harmless on Google
  and meaningful on Bing.
- `OR` must be uppercase on Google. Lowercase is discarded as a stopword and the query silently
  becomes an `AND` — a common cause of a "narrow" result set that should have been wide.
- Negation binds to one token: `-site:acme.com` drops the host, `-"exact phrase"` drops the phrase,
  `-a -b` needs both minuses.
- `allintitle:`, `allinurl:` and `allintext:` are whole-query modes on Google. Mixing them with
  `site:` or `filetype:` produces undefined behaviour — use the singular forms instead.
- Grouping with parentheses is reliable on Bing and not on Google. On Google, express alternatives
  as separate queries and merge the results yourself.
- Very long queries are silently truncated — shorten before assuming an operator broke. And
  `filetype:` takes one extension: `filetype:pdf OR filetype:docx` works, `filetype:pdf,docx` does not.

### 1.6 Worked patterns — general engines

| Objective | Query | Caveat |
|---|---|---|
| Exposed directory listings on a target estate | `site:acme.com intitle:"index of"` | Fetching what you find is a direct hit on the target and is `active` (`01-tradecraft-opsec.md` §1) |
| Credentials or config referencing a company, anywhere | `"acme.com" (ext:env OR ext:yml OR ext:ini)` on Bing, where grouping works | Run the un-grouped alternatives separately on Google |
| A person across the public web, minus the noisy platforms | `"Jane Roe" "Acme" -site:linkedin.com -site:facebook.com` | Then run the platforms deliberately, signed out, in §6 |
| Content Google dropped | Same query on `Bing`, then `Yandex`, then `Brave Search` | Only Brave is a genuinely independent index; a Bing/DuckDuckGo pair is one source |
| A page you remember a phrase from but not the URL | `"exact sentence from the page"` then feed any hit to §8 archives | If it is gone from the live web, go straight to `Arquivo.pt` full-text or `Common Crawl` |

## 2. Code hosts

### 2.1 GitHub Code Search

Requires a signed-in account (registry `GitHub Code Search`). Searching notifies nobody; starring,
forking, following or opening an issue does.

| Qualifier | Status | Notes |
|---|---|---|
| `repo:owner/name` `org:` `user:` | works | Scope first — unscoped queries drown in forks |
| `path:` | works | Glob-capable: `path:*.env`, `path:.github/workflows/` |
| `language:` | works | |
| `symbol:` | works | Matches definitions rather than every mention |
| `content:` | works | Restricts the match to file content |
| `/regex/` | works | Real regular expressions between slashes — the reason this index beats keyword search for key shapes |
| `AND` `OR` `NOT` | works | Explicit boolean, unlike the old index |
| `"exact string"` | works | |
| `is:archived` `is:fork` | works | |
| `extension:` `filename:` `size:` `in:file` `in:path` `fork:` | retired / unreliable | Qualifiers of the pre-2023 code index. Pre-2023 dork lists fail here, and fail silently as keywords. Rewrite `extension:env` as `path:*.env` and `filename:.npmrc` as `path:.npmrc` |

Commit search is a **separate index with its own qualifiers**: `author-email:`, `committer-email:`,
`author-name:`, `committer-name:`, `author-date:`, `committer-date:`, `hash:`, `merge:true`,
combined with `repo:` and `org:`. This is where an organisation's email domain surfaces in commit
metadata, and where personal addresses that never appear on a profile show up (registry).

### 2.2 The rest of the code surface

| Source | Query surface | Constraints |
|---|---|---|
| `grep.app` | Literal and regex search over a crawl of public GitHub repos; language, repo and path filters are UI controls, not query operators | A third-party crawl subset — a miss here does not mean the string is absent from GitHub. Browser only; a security checkpoint blocks scripted fetches (registry `fetchable=no`) |
| `Software Heritage` | Search by **origin URL**, not by content. Objects are addressed by SWHID of the form `swh:1:<type>:<hash>` with types `cnt` `dir` `rev` `rel` `snp` | No general full-text code grep. The right place when a repository was deleted from its origin. Archive host is browser-only (registry) |
| `GH Archive` | No operator language: hourly JSON event dumps, or SQL over the BigQuery copy | The route to deleted repos, force-pushed commits, edited issue text and pre-rename usernames. Volume defeats ad-hoc grep — plan for a query engine (registry) |
| `deps.dev` | Browse by ecosystem and package name; no dork syntax | Package → repository → maintainer account pivot, and typosquat detection by declared-vs-real repository mismatch (registry) |
| `TruffleHog` | CLI over a cloned repo and its full history | **`active` by default** — it verifies discovered credentials against the issuing service. Disable verification to stay passive; verification without written authorisation is likely unauthorised access (registry) |

### 2.3 Worked patterns — code

| Objective | Query | Caveat |
|---|---|---|
| Committed environment files in a target's own repos | `org:acme path:*.env` | Then `path:*.pem`, `path:id_rsa`, `path:.npmrc`, `path:*.tfstate` |
| Cloud key shapes across a target's code | `org:acme /AKIA[0-9A-Z]{16}/` | Never test a discovered key. Testing is the `TruffleHog` verification problem and is out of scope without written authorisation |
| An internal hostname leaked anywhere on GitHub | `"vpn.acme.internal"` then the same literal on `grep.app` | Two indexes, two different crawls; run both before recording a negative |
| Every email address that ever authored in a repo | Clone, then `git log --all --format='%ae%n%an' \| sort -u` | Local and passive once cloned. Reaches force-pushed history the web UI hides |
| A repository that has been deleted | `Software Heritage` by origin URL; failing that, `GH Archive` push events for the org | Absence in Software Heritage means harvesting missed it, not that the repo never existed |

## 3. Paste and dump sites

Paste content is anonymous or near-anonymous user submission with no provenance. It is a lead, not
a finding: `D3` at best from `Pastebin`, and the claim needs a source with a different origination
process before it moves.

| Source | Query surface | Constraints |
|---|---|---|
| `Pastebin` | Its own search is weak. `site:pastebin.com <selector>` on `Google Search` or `Bing` works better | Unlisted pastes are never indexed, so coverage is partial by design and absence proves nothing. The scraping API needs a paid Pro account (registry) |
| `GitHub Gist` | `site:gist.github.com <selector>` on a general engine, or the site's own search | **Gists are a separate corpus from the repository code index — a `GitHub Code Search` query never reaches them.** Secret gists are unlisted rather than private and are not indexed. Every gist binds to an account, so the author is an immediate pivot |
| `Intelligence X` | Selector search across pastes, leak collections and historical web data | Free tier shows truncated previews only. Treat a hit as evidence that a selector *appears in circulating data* — an exposure finding. Do not retrieve, quote or store breach-derived content (global gate item 6). Graded `D`: an aggregator of third-party corpora, and the same dump indexed twice is one artefact |
| `Wayback Machine (retrieval)`, `archive.today (retrieval)` | Deleted pastes by URL | The usual route once a paste is removed |

| Objective | Query |
|---|---|
| Company identifiers dumped in a paste | `site:pastebin.com "acme.com"`, repeated on `Bing` for the different crawl |
| Key-shaped strings in pastes | `site:pastebin.com "AKIA"` — high recall, low precision, expect to discard most of it |
| Configuration leaked in a gist | `site:gist.github.com "acme" (password OR secret OR api_key)` on `Bing`, where grouping is reliable |
| Establish exposure without retrieving anything | `Intelligence X` selector search on the domain; record that the selector appears and where, not the contents |

## 4. Infrastructure search engines

`Shodan`, `Censys Search`, `FOFA` and the rest are read against a vendor's stored scan snapshot, so
the target observes nothing — and a hit means **was**, not **is** (registry `Shodan`).

### 4.1 Shodan

| Filter | Status | Notes |
|---|---|---|
| `port:` `hostname:` `net:` `asn:` `org:` | works | `net:` takes CIDR |
| `country:` `city:` | works | Geolocation is vendor-inferred; treat as `C` |
| `product:` `os:` | works | Banner-derived, frequently wrong on rebranded software |
| `ssl:` `ssl.cert.subject.cn:` `ssl.cert.issuer.cn:` | works | Certificate-field pivots |
| `http.title:` `http.html:` `http.status:` | works | |
| `http.favicon.hash:` | works | Registry-confirmed. Every host serving an identical favicon — one of the strongest infrastructure-clustering techniques available. Compute the hash from the favicon; never guess a value |
| `has_screenshot:` | works | |
| `vuln:` | gated | Paid/academic plans only |
| `before:` `after:` | works | The accepted date format is **not** ISO — read Shodan's own filter reference rather than assuming |
| `OR` | uncertain / unreliable | Run separate queries and merge. `-` negation does work |

Free accounts are heavily limited (registry). Shodan also sells on-demand scanning, which is
`active` and is not what this section describes.

### 4.2 Censys Search

Field-path syntax: `services.port:`, `dns.names:`, `autonomous_system.asn:`, `location.country:`,
with `and` / `or` / `not` and a `same_service(...)` scoping function that constrains several
conditions to the same service rather than the same host.

**Retired:** the v1 port-prefixed syntax (`80.http.get.title:`, `protocols:`) and the separate
`ipv4` / `websites` / `certificates` indexes. Queries copied from pre-2021 material will not run.
The schema is versioned and has changed more than once — read the current field reference rather
than trusting a deep field path from a blog post. Both search hosts answer automated requests with
a bot-protection interstitial (registry `fetchable=no`); confirm the entry point in a browser.

### 4.3 FOFA, urlscan.io, and the rest

| Source | Syntax | Notes |
|---|---|---|
| `FOFA` | `field="value"` with quoted values, combined with `&&` and `||`, negated with `!=`. Core fields: `domain=` `host=` `ip=` `port=` `title=` `body=` `cert=` `icon_hash=` `org=` `asn=` `country=` | Markedly better coverage of Chinese and other Asian infrastructure than Shodan or Censys. Operated from China — weigh what the query itself discloses before submitting a sensitive selector (registry) |
| `urlscan.io (search public scans)` | Lucene-style `field:value` with `AND` / `OR` / `NOT` and wildcards: `page.domain:` `page.url:` `page.ip:` `page.asn:` `page.server:` `domain:` `ip:` `hash:` `filename:` | Purely passive: you read someone else's capture, with screenshot, DOM and every domain and IP the page contacted. Always check here before submitting your own |
| `urlscan.io (submit new scan)` | Same platform, different mode | **`active`.** The target sees the request, and a scan left on default public visibility becomes searchable *by the target*. Public scans of a target submitted by others are themselves a signal someone else is looking (registry) |
| `crt.sh` | A name with `%` as the SQL wildcard: `%.acme.com` | Browser only (registry `fetchable=no`); large-estate queries time out. Wildcard certificates hide the specific hostname and hosts that never got a public certificate never appear — structural blind spots, not gaps you can query around |
| `SSLMate Cert Spotter` | Certificate transparency search plus **monitoring** on newly issued certificates | The difference from crt.sh: you watch an estate across an engagement instead of taking one snapshot |
| `LeakIX` | Search over hosts with exposed services and open databases. **Query syntax is not asserted here** — read it off the site | Read the metadata, not the exposed contents. Pulling exposed data is outside passive collection and outside almost every engagement scope (registry) |
| `GreyNoise` | GNQL `field:value`: `classification:` (`malicious` / `benign` / `unknown`), `cve:`, `tags:`, plus metadata fields | Answers one question: opportunistic background noise, or aimed at you. It will not tell you who owns the host — pivot to an RIR |
| `PublicWWW` | Literal string search over page HTML, JavaScript and CSS. Filter syntax not asserted here | The sibling-site pivot: query an analytics or ad identifier, a distinctive favicon path, a wallet address or a unique code comment. Free tier truncates results severely (registry) |
| `SecurityTrails` | UI and API reverse lookup by nameserver, MX record and WHOIS field | The practical answer to "what did this domain resolve to two years ago". Browser-first (registry `fetchable=no`); free quota has been repeatedly cut |
| `BuiltWith` | Technology profile, plus reverse lookup by analytics or ad-network identifier | That reverse lookup is the pivot that matters and it is a paid feature. Crawl-based, so dead technologies linger (registry) |
| `Hurricane Electric BGP Toolkit` | No query language — navigate by ASN, prefix, IP or DNS name | ASN → announced prefixes, prefix → origin ASN, peers and upstreams. The DNS-names-in-prefix view is best-effort and incomplete (registry) |
| `RIPEstat` | Named data calls through a documented public API — read its data-call list rather than composing a path | Registry and routing data, global rather than RIPE-region only, graded `A` |

### 4.4 Worked patterns — infrastructure

| Objective | Query | Caveat |
|---|---|---|
| Subdomain sweep with zero packets to the target | `crt.sh` `%.acme.com` in a browser, then `SSLMate Cert Spotter` for the rest of the engagement | CT attests a name was certified, not that a host exists or resolves. That is a separate, checkable claim |
| Every host serving the target's favicon | `Shodan` `http.favicon.hash:<computed mmh3 value>` | Compute the hash from the actual favicon. A guessed hash returns a confident, wrong cluster |
| Exposed admin interfaces inside a known netblock | `Shodan` `net:198.51.100.0/24 http.title:"login"` | Reading Shodan's snapshot is passive; connecting to what you find is not |
| Sibling sites run by the same operator | `PublicWWW` on the literal analytics or ad identifier, then confirm each hit independently | An identifier match is `C3` co-occurrence until something names the operator |
| What a page actually loaded, without loading it | `urlscan.io (search public scans)` `page.domain:acme.com` | If nothing is indexed, submitting is `active` and requires scope confirmation |

## 5. Social platforms

The dominant pattern on every platform below is the same: query the platform through a general
engine's `site:` operator, signed out, rather than through the platform's own search.

| Platform | Own query surface | Off-platform route and constraints |
|---|---|---|
| `LinkedIn` | Requires an account; no useful public operator set | `site:linkedin.com/in/` and `site:linkedin.com/company/` on `Google Search` or `Bing`. **Viewing a profile notifies its owner unless in private-browse mode** — registry marks LinkedIn `active` by default, and this is the single most common way an investigator tips off a corporate target. Content is self-asserted: `B` on what the person claims, `C` on fact |
| `X (formerly Twitter)` | `from:` `to:` `since:` `until:` (`YYYY-MM-DD`), `filter:media` `filter:links` `filter:replies` with a leading minus to invert, `lang:`, `url:`, `min_faves:` `min_retweets:` `min_replies:`, `list:` | Logged-out browsing and search closed in 2023, so the account is mandatory and is itself an exposure. `filter:verified` still parses but stopped meaning identity verification when verification became a paid subscription — worthless as an authenticity signal. `near:` / `geocode:` uncertain. Reading does not notify, but it feeds the recommendation graph, which can surface you to the target (`01-tradecraft-opsec.md` §3) |
| `Reddit` | `subreddit:` and `author:` are stable across every search rewrite. `title:` `selftext:` `url:` `flair:` `nsfw:` are documented but have drifted — confirm in the UI | `site:reddit.com/user/` and `site:reddit.com/r/`. robots.txt now disallows every user-agent and the site serves a bot interstitial to non-browser clients, so expect manual browsing (registry). Pushshift lost public access in 2023 — assume gaps in any historical query, and check archives for deleted content |
| `Bluesky` | `from:` `mentions:` `since:` `until:` `lang:` `domain:` and `#hashtag` | AT Protocol records are retrievable unauthenticated and without notifying the user (registry `fetchable=api`). The **PLC directory's audit log retains handle history** — the DID document itself carries only the current handle — which makes this the best surface for tracking one identity across renames. A custom-domain handle is a hard link into an infrastructure pivot |
| `Keybase` | Browse by username | Signed proofs binding a username to other platforms, to a domain and to a PGP key. A validating proof is one of the very few **hard** cross-platform links — a named linking datapoint in the sense the identity-confusion guard requires. Unmaintained since 2020, so absence means nothing |
| `Gravatar` | Hash the lowercased, trimmed address locally and request the avatar | Silent and cheap — run it early on any `email`. A hit often exposes a public profile with a display name, linked accounts and further verified addresses. Absence proves nothing |
| `Google Scholar` | Author and publication search | Author profiles carry affiliation, a verified-at-domain email indicator (a `domain` pivot) and the co-author graph. Automated querying is blocked aggressively — do not script it. `OpenAlex` is the automatable alternative with a free API |
| `WhatsMyName`, `Sherlock`, `Maigret` | Username enumeration across hundreds of platforms | **`active`** — each probe reaches the platform from your IP. Triage, not evidence: high false-positive and false-negative rates. Confirm every hit by opening the profile yourself |

| Objective | Query | Caveat |
|---|---|---|
| Staff roster without touching the platform | `site:linkedin.com/in/ "Acme Corp" ("Engineer" OR "Director")` on `Bing`; ungrouped alternatives on `Google Search` | Job titles are self-asserted. Corroborate against a filing or a company staff page before it becomes a finding |
| One username across platforms | `WhatsMyName` (its `wmn-data.json` ruleset is usable offline), then confirm each hit by hand, then look for a `Keybase` proof | Enumeration is `active` and needs scope confirmation. A username match alone is **never** an identification |
| Routine and timezone from a pseudonym | `Reddit` user page comment timestamps, plus archives for deleted content | This is behavioural inference about a possibly private individual — check the scope purpose before collecting it at all (`00-legal-ethics.md`) |
| Identity across a rename | `Bluesky` PLC directory audit log for handle history; `GH Archive` for a renamed GitHub account | Both are records of the rename, which is a hard link, unlike a name similarity |

## 6. Documents and filetype hunting

| Engine | Operator |
|---|---|
| `Google Search`, `Bing`, `DuckDuckGo` | `filetype:` / `ext:` |
| `Bing` only | `contains:pdf` — pages *linking to* that filetype, which reaches documents the crawler never indexed |
| `Yandex` | `mime:` |

A `filetype:` miss means "not in this index", never "does not exist". Escalate: the other engine,
then `Common Crawl`, then `Wayback Machine (retrieval)`.

What each format carries once retrieved — extract with `ExifTool`, which reads PDF and Office
metadata, not only image `EXIF`:

| Format | Typical metadata payload |
|---|---|
| `pdf` | Author, Creator, Producer (the authoring tool and version), creation and modification timestamps, sometimes a local filesystem path |
| `docx` `xlsx` `pptx` | Creator, last-modified-by, company, revision count, total editing time, template path |
| Legacy `doc` `xls` `ppt` | The same, plus more residue including prior authors |
| `csv` `sql` `bak` `conf` `env` `ini` `yml` `log` | The contents are the payload; there is no metadata layer to speak of |

**Two OPSEC constraints, both binding** (`01-tradecraft-opsec.md` §1). Downloading a document from
the target's own server is a direct fetch and is `active` — prefer the archived copy. And a document
can carry a callback (remote images, beacons, canary tokens): open it offline in a sandboxed viewer
with the network disabled, and inspect embedded `url`s first.

| Objective | Query |
|---|---|
| Map a company's public document estate | `site:acme.com (filetype:pdf OR filetype:docx OR filetype:xlsx)` on `Bing`; the three alternatives separately on `Google Search`; `site:acme.com mime:pdf` on `Yandex` |
| Names, software and internal paths from that estate | Retrieve via archive where possible, then `exiftool -a -G1 <file>` across the set and cluster on Author and Creator |
| Backups and config left in a webroot | `site:acme.com (ext:bak OR ext:old OR ext:sql OR ext:log)` |
| Documents about a company that it did not publish | `"Acme Corp" filetype:pdf -site:acme.com` — regulator, court, procurement and counterparty filings |
| The same estate as it stood two years ago | `Wayback Machine (retrieval)` CDX with `filter=mimetype:application/pdf` (§7) |

## 7. Archive query syntax

### 7.1 Wayback Machine

Reading existing captures is entirely passive (registry `Wayback Machine (retrieval)`).
`Wayback Machine Save Page Now` is a **separate registry row and is `active`** — it makes Internet
Archive fetch the URL, the target's logs show the crawler hit at the moment you looked, and the
capture is public immediately.

| Form | Effect |
|---|---|
| `https://web.archive.org/web/<YYYYMMDDhhmmss>/<url>` | A specific capture. The timestamp may be truncated (`/web/2019/`) and the nearest capture is served |
| `https://web.archive.org/web/*/acme.com/*` | URL-explorer view: archived URLs under the host |
| `…/web/<timestamp>id_/<url>` | The **original unmodified resource**, without Wayback's toolbar and link rewriting. Use this whenever you are hashing a capture as evidence — the rewritten form hashes differently and is not what the server served |

The CDX interface enumerates captures in bulk:
`https://web.archive.org/cdx/search/cdx?url=acme.com&matchType=domain&output=json&collapse=urlkey&limit=1000`

| Parameter | Values |
|---|---|
| `url` | The target, interpreted per `matchType` |
| `matchType` | `exact` `prefix` `host` `domain` |
| `from` `to` | `YYYYMMDDhhmmss`, truncatable |
| `output` | `json` |
| `fl` | Field list, e.g. `original,timestamp,statuscode,mimetype,digest` |
| `collapse` | Deduplicate, e.g. `collapse=urlkey` for one row per URL |
| `filter` | Field predicate, e.g. `filter=statuscode:200`, negated with a leading `!` |
| `limit` | Row cap |

Verify these against the current CDX documentation before scripting a case around them. Robots-based
exclusions and takedowns silently remove captures — a gap is **not** proof a page never existed
(registry). Grade the archive as `B` for "this capture shows this content at this time"; the claim
inside the page is graded on its underlying source.

### 7.2 The other archives

| Source | Query surface | Use it when |
|---|---|---|
| `Arquivo.pt` | **Full-text search across archived page content** — find an archived page by a phrase inside it, which Wayback cannot do for the general web. Documented public API | You know what the page said but not its URL. Deepest coverage of `.pt` and Lusophone content (registry) |
| `Common Crawl` | Per-crawl URL index, crawl identifiers of the form `CC-MAIN-YYYY-WW` | Enumerating every URL and hostname seen under a domain across years without sending the target a single request. Requires bulk-data handling; per-site coverage is a sample, not exhaustive (registry) |
| `archive.today (retrieval)` | Lookup by URL or domain. No full-text search | Pages Wayback will not capture, including many social-media pages — it disregards robots exclusions. Mirrors rotate across `archive.ph` / `.is` / `.li`; browser only. Anonymous operator, so weaker provenance than Internet Archive: `C` |
| `Ghostarchive` | Lookup by URL | Video and social posts, with the media preserved rather than an empty page shell. Community-run with no funding guarantee — mirror anything you rely on into `evidence/` immediately. Submission is `active` |

| Objective | Query |
|---|---|
| Recover a deleted staff or contact page | `web.archive.org/web/*/acme.com/*`, filter on `team` / `about` / `contact`, then pull the chosen capture with `id_` and hash it |
| Enumerate a domain's historical hosts without touching it | CDX with `matchType=domain&collapse=urlkey&fl=original`, then the same domain against `Common Crawl` |
| A document that was pulled from the site | CDX with `filter=mimetype:application/pdf` over the domain |
| A deleted social post | `archive.today (retrieval)` or `Ghostarchive` by URL; both hold material Wayback does not |

## 8. Query hygiene, and why a CAPTCHA is an OPSEC event

Aggressive dorking gets you rate-limited, CAPTCHA-walled or account-flagged. `Google Search`
triggers CAPTCHAs on unattributed automated querying, `Bing` blocks it outright, `Yandex` CAPTCHAs
under load, and `Google Scholar` blocks it aggressively (all registry). Tooling breaks the same
way: the `num=100` URL parameter that many result-harvesting scripts depended on stopped working
in 2025, and such scripts do not error — they silently return a short result set.

That is not merely an inconvenience.

- **The block is a record.** The engine now holds a behavioural fingerprint of your session tied to
  an IP, a cookie and possibly an account, at a timestamp, against a set of queries naming your
  target. That record outlives the case and you do not control it.
- **Shared egress spreads it.** A corporate or VPN egress IP getting CAPTCHA-walled affects
  colleagues and signals that the organisation is running this activity.
- **A truncated result set reads as a negative result.** This is the dangerous one. A rate-limited
  query returns *some* results, which is indistinguishable from a genuine partial answer, and a
  false negative gets written into `gaps.md` as fact. Log the throttling event in the ledger and
  re-run the query later before recording any absence.
- **A flagged research account is a lost account.** Losing it mid-case costs access, and the
  remediation flow — identity documents, a phone number — can tie the account to a real person.
- **On some surfaces your activity is itself searchable.** A public `urlscan.io (submit new scan)`
  scan of a target is visible to the target (registry). Volume of queries against `Yandex` or
  `FOFA` also discloses interest to an operator in a jurisdiction you may not want to be in.

**Boundary, stated explicitly and consistent with `01-tradecraft-opsec.md` and
`00-legal-ethics.md` §3.5.** This file does not describe, and this plugin does not perform,
CAPTCHA solving or circumvention, CAPTCHA-solving services, IP or user-agent rotation to evade a
rate limit, or any other anti-automation evasion. That is global gate item 5 — a hard stop, not a
tradeoff. It stays a hard stop when the block is inconvenient, when the case is urgent, and when
the target is authorised.

The legitimate responses to a rate limit, in order:

1. Slow down and space the queries. Most limits are per-window.
2. Use the documented API or paid tier the vendor provides for exactly this — `Brave Search` and
   `urlscan.io (search public scans)` both offer keyed access, `SEC EDGAR` requires only a
   descriptive User-Agent with a contact address.
3. Move to a different index: `Bing` → `Brave Search` → `Yandex` cover different crawls, and
   `Common Crawl` and `Arquivo.pt` answer many questions with no live engine at all.
4. Accept the limit, log it in `ledger.jsonl` as a collection constraint, and record the unanswered
   question in `gaps.md`. An honest gap beats a fabricated completeness.
