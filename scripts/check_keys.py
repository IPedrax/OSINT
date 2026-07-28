#!/usr/bin/env python3
"""Report which OSINT sources this environment unlocks, and which need no key at all.

Phase 0, standard library only (CONTRACT.md section 10). Reads each value only to test
whether it is non-empty. A key value is never printed, logged, or returned - see demo().

    python check_keys.py
    python check_keys.py --selfcheck

Env var name confidence is marked in the output:
    (none)  vendor-documented name
    *       conventional name used by the vendor's own CLI/SDK ecosystem
    ?       name is unverified - the vendor documents an API key but not an env var
            name, so this is the community convention. A key set under a different
            name will scan as missing. That is a naming gap, not a missing key.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Mapping, NamedTuple

DOCUMENTED, CONVENTIONAL, UNVERIFIED = "documented", "conventional", "unverified"
_MARK = {DOCUMENTED: "", CONVENTIONAL: "*", UNVERIFIED: "?"}


class Source(NamedTuple):
    name: str
    env: tuple[str, ...]
    require_all: bool  # True: every var needed. False: any one is enough.
    unlocks: str
    free_tier: str  # yes | limited | no | unknown, plus a qualifier
    url: str  # homepage only; empty when not certain (CONTRACT.md section 0)
    name_status: str


# Endpoints are homepages, never API paths. Free-tier terms change; `unknown` is
# an honest answer and is used wherever the current terms were not verified.
SOURCES: tuple[Source, ...] = (
    Source(
        "Shodan",
        ("SHODAN_API_KEY",),
        True,
        "host and service banners, port history, favicon and certificate search",
        "limited (account required; most API use is paid membership)",
        "https://www.shodan.io",
        CONVENTIONAL,
    ),
    Source(
        "Censys",
        ("CENSYS_API_ID", "CENSYS_API_SECRET"),
        True,
        "host and certificate search, certificate-to-host pivots",
        "limited",
        "https://censys.io",
        CONVENTIONAL,
    ),
    Source(
        "Have I Been Pwned",
        ("HIBP_API_KEY",),
        True,
        "breach exposure for an email address, paste appearances",
        "no (API key is a paid subscription; the web UI is free)",
        "https://haveibeenpwned.com",
        UNVERIFIED,
    ),
    Source(
        "Hunter.io",
        ("HUNTER_API_KEY",),
        True,
        "organizational email-pattern inference, domain to named mailboxes",
        "limited (small monthly quota)",
        "https://hunter.io",
        UNVERIFIED,
    ),
    Source(
        "SecurityTrails",
        ("SECURITYTRAILS_API_KEY",),
        True,
        "historical DNS and WHOIS, subdomain inventory",
        "unknown",
        "https://securitytrails.com",
        UNVERIFIED,
    ),
    Source(
        "VirusTotal",
        ("VT_API_KEY", "VIRUSTOTAL_API_KEY"),
        False,
        "file, URL, domain and IP reputation; passive DNS; related samples",
        "yes (public API, heavily rate-limited)",
        "https://www.virustotal.com",
        CONVENTIONAL,
    ),
    Source(
        "IPinfo",
        ("IPINFO_TOKEN",),
        True,
        "IP geolocation, ASN, hosting and privacy-service flags",
        "yes",
        "https://ipinfo.io",
        CONVENTIONAL,
    ),
    Source(
        "OpenCorporates",
        ("OPENCORPORATES_API_KEY",),
        True,
        "cross-jurisdiction company records, officers, filings",
        "limited (API access by application)",
        "https://opencorporates.com",
        UNVERIFIED,
    ),
    Source(
        "Brave Search API",
        ("BRAVE_API_KEY",),
        True,
        "independent web index for dorking without driving a browser",
        "yes (free tier with quota)",
        "https://brave.com/search/api",
        CONVENTIONAL,
    ),
    Source(
        "Serper",
        ("SERPER_API_KEY",),
        True,
        "Google SERP results as JSON, useful for site: and filetype: dorks",
        "yes (free credits on signup)",
        "https://serper.dev",
        CONVENTIONAL,
    ),
    Source(
        "GitHub",
        ("GITHUB_TOKEN",),
        True,
        "code and commit search, commit author emails, org and member listing, higher rate limits",
        "yes",
        "https://github.com",
        DOCUMENTED,
    ),
    Source(
        "Firecrawl",
        ("FIRECRAWL_API_KEY",),
        True,
        "scrape, crawl, search and change monitoring; also wired as an MCP server here",
        "yes (free credits)",
        "https://firecrawl.dev",
        DOCUMENTED,
    ),
    Source(
        "Etherscan",
        ("ETHERSCAN_API_KEY",),
        True,
        "EVM address history, token transfers, verified contract source",
        "yes",
        "https://etherscan.io",
        CONVENTIONAL,  # vendor documents apikey= as a query parameter, not an env var name
    ),
    Source(
        "WhoisXML API",
        ("WHOISXML_API_KEY",),
        True,
        "current and historical WHOIS, reverse WHOIS by registrant",
        "yes (free credits)",
        "https://whoisxmlapi.com",
        UNVERIFIED,
    ),
    Source(
        "Intelligence X",
        ("INTELX_API_KEY",),
        True,
        "selector search across archived indexes - CONTRACT rule 6 still bars non-public breach corpora",
        "limited",
        "https://intelx.io",
        UNVERIFIED,
    ),
    Source(
        "FOFA",
        ("FOFA_EMAIL", "FOFA_KEY"),
        True,
        "host and banner search, strong coverage of CN-hosted infrastructure",
        "limited",
        "https://fofa.info",
        UNVERIFIED,
    ),
    Source(
        "ZoomEye",
        ("ZOOMEYE_API_KEY",),
        True,
        "host and web-application fingerprint search",
        "limited",
        "",  # homepage not verified; search the vendor name rather than trust a guess
        UNVERIFIED,
    ),
)

# Zero-key baseline: no key, no account, no signup. This is the floor a case runs on.
ZERO_KEY: tuple[tuple[str, str], ...] = (
    (
        "DNS (nslookup, Resolve-DnsName, dig)",
        "A/AAAA, MX, NS, TXT, SOA, SPF and DMARC records; mail-provider inference",
    ),
    (
        "Certificate transparency search (https://crt.sh)",
        "subdomain inventory from issued certificates, historical hostnames",
    ),
    (
        "Wayback Machine (https://web.archive.org)",
        "historical page states, removed content, archive-on-read for evidence",
    ),
    (
        "Public corporate registries (UK Companies House, US state secretaries of state, EU business registers)",
        "company records, officers, filings, registered addresses",
    ),
    (
        "Search engines, plus Claude's own WebSearch and WebFetch",
        "dorking, adverse media, corroboration of a claim",
    ),
    (
        "RDAP and system whois against registries",
        "registration dates, registrar, nameservers, EPP status codes",
    ),
)


class Result(NamedTuple):
    source: Source
    state: str  # unlocked | partial | missing
    present: tuple[str, ...]
    absent: tuple[str, ...]


def marked(env_name: str, status: str) -> str:
    return env_name + _MARK[status]


def scan(env: Mapping[str, str], sources: Iterable[Source] = SOURCES) -> list[Result]:
    """Classify each source by env var presence. Values are read for emptiness only."""
    out: list[Result] = []
    for src in sources:
        present = tuple(v for v in src.env if (env.get(v) or "").strip())
        absent = tuple(v for v in src.env if v not in present)
        if src.require_all:
            state = "unlocked" if not absent else ("partial" if present else "missing")
        else:
            state = "unlocked" if present else "missing"
        out.append(Result(src, state, present, absent))
    return out


def render(results: list[Result]) -> str:
    unlocked = [r for r in results if r.state == "unlocked"]
    rest = [r for r in results if r.state != "unlocked"]
    lines = [
        f"OSINT key scan: {len(unlocked)} of {len(results)} keyed sources unlocked. "
        "No key value is read beyond emptiness, and none is ever printed.",
        "",
        f"UNLOCKED ({len(unlocked)})",
    ]
    if unlocked:
        lines += ["| source | env var | unlocks |", "|---|---|---|"]
        for r in unlocked:
            names = " + ".join(marked(v, r.source.name_status) for v in r.present)
            lines.append(f"| {r.source.name} | {names} | {r.source.unlocks} |")
    else:
        lines.append("none - every keyed source below is unset. The zero-key baseline still applies.")

    lines += ["", f"MISSING ({len(rest)})", "| source | env var | unlocks | free tier | signup |", "|---|---|---|---|---|"]
    for r in rest:
        needed = " + ".join(marked(v, r.source.name_status) for v in r.source.env)
        if r.state == "partial":
            have = ", ".join(r.present)
            miss = ", ".join(r.absent)
            needed = f"{needed} (partial: {have} set, {miss} not set)"
        elif not r.source.require_all and len(r.source.env) > 1:
            needed = needed.replace(" + ", " or ")
        url = r.source.url or "(homepage not recorded - search the vendor name)"
        lines.append(
            f"| {r.source.name} | {needed} | {r.source.unlocks} | {r.source.free_tier} | {url} |"
        )

    lines += [
        "",
        "WORKS WITH NO KEY AT ALL",
        "A case can be opened, worked and reported with zero keys. Do not tell a user they need",
        "one before running these; keys buy scale, history and convenience, not admissibility.",
        "",
        "| source | gives |",
        "|---|---|",
    ]
    lines += [f"| {name} | {gives} |" for name, gives in ZERO_KEY]
    lines += [
        "",
        "Env var name confidence: no mark = vendor-documented, * = conventional name used by the",
        "vendor's own CLI or SDK, ? = unverified community convention. A key set under a different",
        "name scans as missing; that is a naming gap, not a missing key.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="check_keys.py",
        description="Report which OSINT sources this environment unlocks. Never prints a key value.",
    )
    p.add_argument("--selfcheck", action="store_true", help="run internal assertions and exit")
    args = p.parse_args(argv)
    if args.selfcheck:
        return demo()
    print(render(scan(os.environ)))
    return 0


def demo() -> int:
    sentinel = "SECRET-VALUE-MUST-NOT-APPEAR-9f2c1a"
    fake = {
        "SHODAN_API_KEY": sentinel,
        "CENSYS_API_ID": sentinel,  # secret half absent -> partial
        "VIRUSTOTAL_API_KEY": sentinel,  # any-of group -> unlocked
        "HIBP_API_KEY": "   ",  # whitespace only -> missing
    }
    results = scan(fake)
    by_name = {r.source.name: r for r in results}

    assert by_name["Shodan"].state == "unlocked"
    assert by_name["VirusTotal"].state == "unlocked"
    assert by_name["Censys"].state == "partial"
    assert by_name["Censys"].absent == ("CENSYS_API_SECRET",)
    assert by_name["Have I Been Pwned"].state == "missing", "whitespace-only value must not count"
    assert by_name["Hunter.io"].state == "missing"

    # No key value may survive anywhere: not in the returned structures, not in output.
    assert sentinel not in repr(results), "a key value leaked into the scan result"
    out = render(results)
    assert sentinel not in out, "a key value leaked into the output"
    assert sentinel[:8] not in out, "a truncated key value leaked into the output"

    assert "SHODAN_API_KEY*" in out, "conventional-name marker missing"
    assert "HIBP_API_KEY?" in out, "unverified-name marker missing"
    assert "GITHUB_TOKEN |" in out, "documented name should carry no marker"
    assert "partial: CENSYS_API_ID set, CENSYS_API_SECRET not set" in out
    assert "VT_API_KEY? or" not in out  # VirusTotal group is conventional, not unverified

    empty = render(scan({}))
    assert (
        "VT_API_KEY* or VIRUSTOTAL_API_KEY*" in empty
    ), "any-of group must render with 'or', not '+'"
    assert "UNLOCKED (0)" in empty
    assert "none - every keyed source below is unset" in empty
    assert "crt.sh" in empty and "web.archive.org" in empty
    assert "Companies House" in empty and "WebSearch" in empty
    assert "(homepage not recorded" in empty, "unverified homepage must be flagged, not invented"

    # Every source is classified exactly once, and every env var name is non-empty.
    assert len(results) == len(SOURCES)
    assert all(r.state in ("unlocked", "partial", "missing") for r in results)
    assert all(src.env and all(src.env) for src in SOURCES)
    assert len({src.name for src in SOURCES}) == len(SOURCES), "duplicate source name"

    print("selfcheck ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
