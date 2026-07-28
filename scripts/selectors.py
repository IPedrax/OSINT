#!/usr/bin/env python3
"""Classify and normalise an OSINT selector, then rank the sources that accept it.

Phase 1, standard library only (CONTRACT.md section 10). Windows-safe: pathlib
throughout, no hardcoded separators, no network calls at import time.

    python selectors.py acme.example
    python selectors.py "jane.doe@acme.example" --passive-only
    python selectors.py 8.8.8.8 --auth none,free_key
    python selectors.py AS15169 --json
    python selectors.py "48.8584, 2.2945" --type coordinates
    python selectors.py --selfcheck

Classification is deliberately plural. A bare token like "acme" is a legitimate
username AND a legitimate company name, and a tool that picks one and hides the
other sends the investigator down a single path without telling them a fork
existed. Every candidate carries a score and the reason it was proposed.

Exit codes: 0 ok; 1 no candidate type could be assigned, --type was not a
CONTRACT.md section 4 selector type, or assets/sources.csv is missing or
malformed; 2 argparse usage error.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import re
import shutil
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit, urlunsplit

# CONTRACT.md section 4, exact strings, same order. No synonyms, no plurals.
SELECTOR_TYPES = (
    "email", "username", "person_name", "phone", "domain", "subdomain", "ip", "asn",
    "netblock", "url", "ssl_cert", "company", "company_number", "address", "photo",
    "video", "document", "crypto_address", "tx_hash", "vehicle_plate", "vessel",
    "aircraft", "coordinates", "file_hash", "social_profile", "breach_record",
)

# CONTRACT.md section 5 header, exact and in order.
SOURCES_HEADER = (
    "name", "category", "accepts", "yields", "endpoint", "auth", "rate_limit",
    "mode", "verified", "fetchable", "jurisdiction_notes", "reliability", "notes",
)

AUTH_VALUES = ("none", "free_key", "paid", "account")
MODE_VALUES = ("passive", "active")
# CONTRACT.md section 5. `verified` is a claim about the URL being correct as
# written; `fetchable` is a claim about whether a plain HTTP client gets the
# content. They are independent -- SEC EDGAR is verified=yes, fetchable=api.
FETCHABLE_VALUES = ("yes", "no", "api", "unknown")

# Shared assets live at the PLUGIN ROOT (CONTRACT.md section 1), one level up
# from scripts/. Resolved from __file__ so the script works from any cwd.
DEFAULT_SOURCES = Path(__file__).resolve().parent.parent / "assets" / "sources.csv"


class Candidate(NamedTuple):
    """One possible reading of a raw value. Higher score = better supported."""

    type: str
    score: int
    why: str


# ---------------------------------------------------------------------------
# Pattern vocabulary
# ---------------------------------------------------------------------------

# A DNS label: alphanumeric, internal hyphens, 1-63 chars.
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
RE_HOSTNAME = re.compile(rf"^{_LABEL}(?:\.{_LABEL})*\.?$", re.I)

# Heuristic TLD set, NOT the IANA root zone. Only entries that are certainly
# delegated are listed; the classifier degrades gracefully rather than relying
# on completeness -- an unrecognised last label still produces a `domain`
# candidate, just ranked below `username`. Add entries freely; a missing one
# costs ranking, never correctness.
COMMON_TLDS = frozenset("""
com net org edu gov mil int info biz name pro mobi asia jobs tel travel
aero coop museum cat arpa xxx
app dev page xyz online site website space store shop tech cloud digital
network systems solutions group ltd llc inc gmbh limited company ventures
capital finance fund bank insurance legal law tax agency media news press
blog wiki forum social chat email security club live life world today
link click top fyi run one
example test invalid localhost onion
""".split())

# Two-level public suffixes seen often enough to matter for the
# subdomain-vs-domain call. This is a shortcut for the Public Suffix List,
# which is not in the standard library; both readings are always returned as
# candidates so an entry missing here degrades ranking, not correctness.
TWO_LEVEL_SUFFIXES = frozenset("""
co.uk org.uk ac.uk gov.uk net.uk plc.uk me.uk
com.au net.au org.au edu.au gov.au
co.nz com.br net.br org.br gov.br edu.br
co.jp or.jp ne.jp ac.jp go.jp
co.kr or.kr com.cn net.cn org.cn gov.cn edu.cn
co.in net.in org.in gov.in nic.in
co.za org.za com.mx com.ar com.sg com.tr com.tw com.hk com.my com.ph
co.th co.id com.vn com.pk com.eg com.sa com.ua co.ke com.ng co.il
""".split())

# Company-form suffixes. Presence of one makes `company` the strong reading of
# a multi-word token instead of `person_name`.
COMPANY_SUFFIXES = frozenset("""
ltd ltd. limited llc l.l.c. inc inc. incorporated corp corp. corporation
plc gmbh mbh ag sa s.a. nv n.v. bv b.v. oy ab as a/s aps srl s.r.l. spa
s.p.a. sarl s.a.r.l. pty kft sp sp. zoo z.o.o. co co. company kk k.k.
holdings group llp lp gbr ug se
""".split())

RE_EMAIL_SHAPE = re.compile(r"^(?:mailto:)?([^@\s]{1,64})@([^@\s]{1,255})$", re.I)
RE_ASN = re.compile(r"^(?:as|asn)[\s:-]?(\d{1,10})$", re.I)
RE_ETH_ADDR = re.compile(r"^0x[0-9a-f]{40}$", re.I)
RE_ETH_TXHASH = re.compile(r"^0x[0-9a-f]{64}$", re.I)
RE_HEX = re.compile(r"^[0-9a-f]+$", re.I)
# Base58 excludes 0 O I l by construction; P2PKH starts 1, P2SH starts 3.
RE_BTC_BASE58 = re.compile(r"^[13][1-9A-HJ-NP-Za-km-z]{25,34}$")
# Bech32/bech32m: hrp "bc", separator "1", charset excludes 1 b i o.
RE_BTC_BECH32 = re.compile(r"^bc1[023456789acdefghjklmnpqrstuvwxyz]{11,71}$", re.I)
RE_USERNAME = re.compile(r"^@?[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?$")
RE_COMPANY_NUMBER = re.compile(r"^[A-Z]{0,3}[-\s]?\d[\dA-Z-]{3,14}$", re.I)
RE_ALPHA_TOKEN = re.compile(r"^[A-Za-z][A-Za-z'’-]*$")

RE_DECIMAL_COORDS = re.compile(
    r"""^\s*([+-]?\d{1,2}(?:\.\d+)?)\s*([NSns])?
        \s*[,;/]\s*
        ([+-]?\d{1,3}(?:\.\d+)?)\s*([EWew])?\s*$""",
    re.X,
)
RE_DMS_COORDS = re.compile(
    r"""^\s*(\d{1,2})\s*[°d:\s]\s*(\d{1,2})\s*['\u2032\u2019m:\s]\s*
        (\d{1,2}(?:\.\d+)?)\s*["\u2033\u201ds]?\s*([NSns])
        \s*[,;\s]+\s*
        (\d{1,3})\s*[°d:\s]\s*(\d{1,2})\s*['\u2032\u2019m:\s]\s*
        (\d{1,2}(?:\.\d+)?)\s*["\u2033\u201ds]?\s*([EWew])\s*$""",
    re.X,
)

_PHONE_SEPARATORS = str.maketrans("", "", " \t()-./\u00a0\u2013\u2014")


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

def _tld_of(host: str) -> str:
    return host.rstrip(".").rsplit(".", 1)[-1].lower()


def _registrable_label_count(host: str) -> int:
    """How many labels the registrable domain occupies: 2, or 3 for co.uk-alikes."""
    parts = host.rstrip(".").lower().split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_LEVEL_SUFFIXES:
        return 3
    return 2


def _host_candidates(host: str, base: int, prefix: str) -> list[Candidate]:
    """Score a hostname as domain and/or subdomain. `base` caps the confidence."""
    out: list[Candidate] = []
    stripped = host.rstrip(".")
    if not stripped or not RE_HOSTNAME.match(host):
        return out
    labels = stripped.split(".")
    if len(labels) < 2:
        return out
    tld = _tld_of(stripped)
    # A 2-letter alphabetic last label is a plausible ccTLD even when it is not
    # in COMMON_TLDS; ccTLDs are ISO 3166-1 alpha-2 and there are ~250 of them.
    known = tld in COMMON_TLDS or (len(tld) == 2 and tld.isalpha())
    score = base if known else max(base - 55, 10)
    why = f"{prefix}dotted hostname, TLD {tld!r} " + (
        "recognised" if known else "not recognised - could be any dotted token"
    )
    if len(labels) > _registrable_label_count(stripped):
        out.append(Candidate("subdomain", score, why + "; more labels than the registrable name"))
        out.append(Candidate("domain", score - 10, why + "; readable as a domain if the suffix is multi-level"))
    else:
        out.append(Candidate("domain", score, why))
        if len(labels) > 2:
            out.append(Candidate("subdomain", score - 15, why + "; could be a subdomain of a shorter registrable name"))
    return out


def classify(value: str) -> list[Candidate]:
    """Return every plausible CONTRACT.md section 4 type for `value`, best first.

    Ambiguity is the normal case, not an error. Callers should present the list
    rather than silently taking [0].
    """
    raw = (value or "").strip()
    out: list[Candidate] = []
    if not raw:
        return out

    # -- URL: a scheme is unambiguous, so nothing else needs checking first.
    if "://" in raw and re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        out.append(Candidate("url", 98, "explicit scheme://"))
        host = urlsplit(raw).hostname or ""
        out.extend(_host_candidates(host, 55, "host part of the URL: "))
        return _rank(out)

    # -- Email.
    m = RE_EMAIL_SHAPE.match(raw)
    if m and RE_HOSTNAME.match(m.group(2)) and "." in m.group(2):
        out.append(Candidate("email", 96, "local@host with a dotted host part"))
        return _rank(out)

    # -- Netblock before IP: ip_network accepts a bare address as a /32.
    if "/" in raw:
        try:
            ipaddress.ip_network(raw, strict=False)
            out.append(Candidate("netblock", 97, "parses as an IP network with a prefix length"))
            return _rank(out)
        except ValueError:
            pass

    # -- IP address. Rejects version strings like 2.4.1 for free: three octets
    #    is not a valid IPv4 address, so no `ip` candidate is emitted at all.
    try:
        addr = ipaddress.ip_address(raw)
        out.append(Candidate("ip", 97, f"valid IPv{addr.version} address"))
        return _rank(out)
    except ValueError:
        pass

    # -- ASN with an explicit prefix is unambiguous.
    m = RE_ASN.match(raw)
    if m:
        out.append(Candidate("asn", 96, "AS-prefixed autonomous system number"))
        return _rank(out)

    # -- Coordinates.
    m = RE_DMS_COORDS.match(raw)
    if m:
        out.append(Candidate("coordinates", 95, "degrees/minutes/seconds pair with hemispheres"))
        return _rank(out)
    m = RE_DECIMAL_COORDS.match(raw)
    if m:
        lat, lon = abs(float(m.group(1))), abs(float(m.group(3)))
        if lat <= 90 and lon <= 180:
            out.append(Candidate("coordinates", 95, "decimal degree pair inside valid lat/lon range"))
            return _rank(out)

    # -- 0x-prefixed hex: Ethereum-family address or transaction hash.
    if RE_ETH_ADDR.match(raw):
        out.append(Candidate("crypto_address", 96, "0x + 40 hex, EVM account or contract address"))
        return _rank(out)
    if RE_ETH_TXHASH.match(raw):
        out.append(Candidate("tx_hash", 96, "0x + 64 hex, EVM transaction hash"))
        out.append(Candidate("file_hash", 30, "the same 64 hex digits are a sha256 shape once 0x is dropped"))
        return _rank(out)

    # -- Bitcoin address shapes.
    if RE_BTC_BECH32.match(raw):
        out.append(Candidate("crypto_address", 95, "bc1 bech32/bech32m segwit address"))
        return _rank(out)
    if RE_BTC_BASE58.match(raw):
        out.append(Candidate("crypto_address", 88,
                             "base58 starting 1 or 3; Bitcoin P2PKH/P2SH shape, but several "
                             "other chains reuse base58 - confirm the chain before pivoting"))

    # -- Bare hex of a hash length.
    if RE_HEX.match(raw) and len(raw) in (32, 40, 64):
        algo = {32: "md5", 40: "sha1", 64: "sha256"}[len(raw)]
        out.append(Candidate("file_hash", 92, f"{len(raw)} hex digits, {algo} length"))
        if len(raw) == 64:
            out.append(Candidate("tx_hash", 60, "64 bare hex is also the Bitcoin txid shape"))
        out.append(Candidate("username", 25, "a handle can coincidentally be hex-only"))

    # -- Phone.
    digits = raw.translate(_PHONE_SEPARATORS)
    if re.match(r"^\+[1-9]\d{6,14}$", digits):
        out.append(Candidate("phone", 94, "leading + and 7-15 digits, E.164 shape"))
    elif re.match(r"^00[1-9]\d{6,14}$", digits):
        out.append(Candidate("phone", 88, "00 international prefix and 7-15 digits"))
    elif digits.isdigit() and 7 <= len(digits) <= 15 and raw != digits:
        out.append(Candidate("phone", 70, "digit groups with separators, no country code present"))

    # -- Hostname shapes.
    if "." in raw and " " not in raw:
        out.extend(_host_candidates(raw, 90, ""))

    # -- Bare digits: ASN without the prefix, or a numeric registration number.
    if raw.isdigit():
        n = len(raw)
        if 1 <= n <= 10:
            out.append(Candidate("asn", 45, "bare digits; an ASN without its AS prefix looks identical"))
        if 5 <= n <= 15:
            out.append(Candidate("company_number", 45, "bare digits in company-registration length range"))
        if 7 <= n <= 15:
            out.append(Candidate("phone", 35, "bare digits could be a national number with no country code"))
        out.append(Candidate("username", 20, "numeric handles exist on most platforms"))

    # -- Company registration number with letters (SC123456, 12-3456789).
    if not raw.isdigit() and " " not in raw and RE_COMPANY_NUMBER.match(raw) and any(c.isdigit() for c in raw):
        out.append(Candidate("company_number", 50,
                             "letter-prefixed or hyphenated alphanumeric in registration-number "
                             "shape; format is jurisdiction-specific, so confirm the register"))

    # -- Single token: username, company, weak person_name.
    if " " not in raw and RE_USERNAME.match(raw):
        handled = raw.lstrip("@")
        if raw.startswith("@"):
            out.append(Candidate("username", 90, "@-prefixed handle"))
        elif raw.isdigit():
            pass  # the bare-digit branch already scored username, and lower:
                  # an all-numeric token is far more often an identifier than a handle
        elif not out or max(c.score for c in out) < 90:
            out.append(Candidate("username", 55, "handle-safe character set, no separators"))
        if RE_ALPHA_TOKEN.match(handled) and 2 <= len(handled) <= 40:
            out.append(Candidate("company", 40, "a single word is as likely a trading name as a handle"))
            out.append(Candidate("person_name", 20, "could be a mononym or a surname alone"))

    # -- Multiple words: person or company.
    words = raw.split()
    if len(words) >= 2 and all(RE_ALPHA_TOKEN.match(w.strip(",.")) or w.strip(",.").isdigit() for w in words):
        tail = words[-1].lower().strip(",.")
        if tail in COMPANY_SUFFIXES or any(w.lower().strip(",.") in COMPANY_SUFFIXES for w in words):
            out.append(Candidate("company", 90, f"trailing company form {tail!r}"))
            out.append(Candidate("person_name", 20, "a personal name can precede a company form"))
        else:
            out.append(Candidate("person_name", 80, "two or more alphabetic words, no company form"))
            out.append(Candidate("company", 45, "an unsuffixed trading name looks the same"))
        out.append(Candidate("address", 25, "a street address also reads as several words"))

    return _rank(out)


def _rank(cands: list[Candidate]) -> list[Candidate]:
    """Dedupe by type keeping the best score, then sort best first."""
    best: dict[str, Candidate] = {}
    for c in cands:
        if c.type not in best or c.score > best[c.type].score:
            best[c.type] = c
    return sorted(best.values(), key=lambda c: (-c.score, c.type))


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

def _idna_host(host: str) -> str:
    """Lowercase, drop the root dot, and punycode non-ASCII labels.

    Uses the stdlib `idna` codec, which implements IDNA2003 (RFC 3490) only.
    IDNA2008 differs on a handful of characters, notably the German sharp s and
    the final sigma, which IDNA2003 maps away rather than encoding. A label the
    codec rejects is left as-is rather than dropped, so nothing is silently lost.
    """
    host = host.strip().rstrip(".").lower()
    if host.isascii():
        return host
    parts = []
    for label in host.split("."):
        if label.isascii():
            parts.append(label)
            continue
        try:
            parts.append(label.encode("idna").decode("ascii"))
        except (UnicodeError, ValueError):
            parts.append(label)
    return ".".join(parts)


def normalize(value: str, type: str) -> str:
    """Canonicalise `value` as `type`. Idempotent: normalize(normalize(x))==normalize(x).

    Unknown types and values that do not parse are returned whitespace-stripped
    rather than mangled -- a normaliser that guesses is worse than one that
    declines.
    """
    v = (value or "").strip()
    if not v:
        return ""

    if type == "email":
        v = re.sub(r"^mailto:", "", v, flags=re.I)
        if "@" in v:
            local, _, host = v.rpartition("@")
            # RFC 5321 makes the local part case-sensitive, but no mainstream
            # provider treats it that way and every OSINT corpus is folded.
            # Folding both keeps joins across datasets working; if a case-exact
            # local part is ever evidence, keep the raw value alongside.
            return f"{local.lower()}@{_idna_host(host)}"
        return v.lower()

    if type in ("domain", "subdomain"):
        return _idna_host(v)

    if type == "url":
        parts = urlsplit(v)
        host = _idna_host(parts.hostname or "")
        if parts.port and not (
            (parts.scheme.lower() == "http" and parts.port == 80)
            or (parts.scheme.lower() == "https" and parts.port == 443)
        ):
            host = f"{host}:{parts.port}"
        if parts.username:
            host = f"{parts.username}@{host}"
        # Path case is preserved: on most servers it is significant.
        return urlunsplit((parts.scheme.lower(), host, parts.path, parts.query, parts.fragment))

    if type in ("ip", "netblock"):
        try:
            if type == "netblock" or "/" in v:
                return str(ipaddress.ip_network(v, strict=False))
            return str(ipaddress.ip_address(v))
        except ValueError:
            return v

    if type == "asn":
        m = RE_ASN.match(v)
        n = m.group(1) if m else (v if v.isdigit() else None)
        return f"AS{int(n)}" if n is not None else v

    if type == "phone":
        digits = v.translate(_PHONE_SEPARATORS)
        if digits.startswith("+"):
            rest = digits[1:]
            return "+" + rest if rest.isdigit() else v
        if digits.startswith("00") and digits[2:].isdigit():
            # 00 is the ITU international access prefix; rewriting it to + adds
            # no country code that was not already typed.
            return "+" + digits[2:].lstrip("0") if digits[2:].lstrip("0") else v
        # No country code was supplied. Strip separators and stop -- guessing a
        # country here would fabricate the single most load-bearing digit group.
        return digits if digits.isdigit() else v

    if type == "crypto_address":
        if RE_ETH_ADDR.match(v):
            # EIP-55 mixed-case checksumming needs Keccak-256. hashlib does not
            # provide it: hashlib.sha3_256 is NIST SHA-3, which uses a different
            # padding byte and produces a different digest, so using it here
            # would emit a plausible-looking but wrong checksum. Lowercase is
            # the canonical all-lower form every EVM tool accepts.
            return v.lower()
        if RE_BTC_BECH32.match(v):
            # BIP-173 requires a bech32 string to be all one case; lower is canonical.
            return v.lower()
        # Base58Check is case-sensitive. Changing case invalidates the address.
        return v

    if type in ("tx_hash", "file_hash"):
        return v.lower()

    if type == "username":
        return v.lstrip("@").strip().lower()

    if type == "person_name":
        # Collapse whitespace only. Case carries meaning in names (van der Berg,
        # McDonald, d'Souza) and folding it loses a real signal.
        return " ".join(v.split())

    if type == "company":
        return " ".join(v.split())

    if type == "company_number":
        return re.sub(r"\s+", "", v).upper()

    if type == "coordinates":
        parsed = parse_coordinates(v)
        if parsed:
            return f"{_fmt_coord(parsed[0])},{_fmt_coord(parsed[1])}"
        return v

    if type == "address":
        return " ".join(v.split())

    return v


def _fmt_coord(x: float) -> str:
    """Six decimal places is ~11 cm at the equator; trailing zeros stripped so
    the output re-parses to the identical string."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def parse_coordinates(v: str) -> tuple[float, float] | None:
    """Return (lat, lon) in signed decimal degrees, or None."""
    m = RE_DMS_COORDS.match(v)
    if m:
        lat = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
        lon = int(m.group(5)) + int(m.group(6)) / 60 + float(m.group(7)) / 3600
        if m.group(4).upper() == "S":
            lat = -lat
        if m.group(8).upper() == "W":
            lon = -lon
        return (lat, lon) if abs(lat) <= 90 and abs(lon) <= 180 else None
    m = RE_DECIMAL_COORDS.match(v)
    if m:
        lat, lon = float(m.group(1)), float(m.group(3))
        if m.group(2) and m.group(2).upper() == "S":
            lat = -abs(lat)
        if m.group(4) and m.group(4).upper() == "W":
            lon = -abs(lon)
        return (lat, lon) if abs(lat) <= 90 and abs(lon) <= 180 else None
    return None


# ---------------------------------------------------------------------------
# pivots
# ---------------------------------------------------------------------------

# Rank order, applied in this sequence:
#   1. mode  -- passive first. Default scope is passive-only (CONTRACT.md
#      section 9); an active source is often not merely worse, it is unusable
#      without a fresh confirmation, so it must never outrank a passive one.
#   2. auth  -- none, then free_key, then account, then paid. Cheapest access first.
#   3. reliability -- Admiralty A before F (CONTRACT.md section 6).
#   4. verified -- yes before no, so confirmed endpoints float up.
#   5. name -- stable tie-break.
_MODE_RANK = {"passive": 0, "active": 1}
_AUTH_RANK = {"none": 0, "free_key": 1, "account": 2, "paid": 3}


def load_sources(path: Path = DEFAULT_SOURCES) -> list[dict[str, str]]:
    """Read sources.csv, validating the header contract. Raises ValueError."""
    if not path.is_file():
        raise ValueError(f"sources.csv not found at {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"{path} is empty") from None
        if tuple(header) != SOURCES_HEADER:
            raise ValueError(
                f"{path} header does not match CONTRACT.md section 5.\n"
                f"  expected: {','.join(SOURCES_HEADER)}\n"
                f"  found:    {','.join(header)}"
            )
        rows = []
        for lineno, rec in enumerate(reader, start=2):
            if not rec:
                continue
            if len(rec) != len(SOURCES_HEADER):
                raise ValueError(
                    f"{path}:{lineno} has {len(rec)} columns, expected "
                    f"{len(SOURCES_HEADER)} (unquoted comma?)"
                )
            rows.append(dict(zip(SOURCES_HEADER, rec)))
    return rows


def _sort_key(row: dict[str, str]) -> tuple:
    return (
        _MODE_RANK.get(row["mode"], 9),
        _AUTH_RANK.get(row["auth"], 9),
        row["reliability"],
        0 if row["verified"] == "yes" else 1,
        row["name"].lower(),
    )


def pivots(
    type: str,
    *,
    sources: list[dict[str, str]] | None = None,
    passive_only: bool = False,
    auth_filter: frozenset[str] | None = None,
    fetchable_only: bool = False,
) -> list[dict[str, str]]:
    """Rows whose `accepts` contains `type`, ranked cheapest-and-quietest first.

    `fetchable` is displayed by the renderer but is deliberately NOT part of
    `_sort_key`: an unfetchable authoritative registry still beats a fetchable
    aggregator, and ranking on it would invert that every time.
    """
    if type not in SELECTOR_TYPES:
        raise ValueError(f"{type!r} is not a CONTRACT.md section 4 selector type")
    rows = load_sources() if sources is None else sources
    out = []
    for row in rows:
        if type not in row["accepts"].split("|"):
            continue
        if passive_only and row["mode"] != "passive":
            continue
        if auth_filter is not None and row["auth"] not in auth_filter:
            continue
        # `api` is excluded on purpose: those rows are retrievable, but not at
        # the URL in the endpoint column, so handing one to a fetcher fails.
        if fetchable_only and row["fetchable"] != "yes":
            continue
        out.append(row)
    return sorted(out, key=_sort_key)


# ---------------------------------------------------------------------------
# Terminal rendering
# ---------------------------------------------------------------------------

def _clip(s: str, n: int) -> str:
    # ASCII ellipsis on purpose: a redirected stdout on Windows uses the locale
    # codepage, and cp1252 cannot encode U+2026.
    s = " ".join(s.split())
    return s if len(s) <= n else s[: max(n - 3, 1)].rstrip() + "..."


def render_candidates(value: str, cands: list[Candidate]) -> str:
    lines = [f"value: {value}", ""]
    if not cands:
        return "\n".join(lines + ["no candidate type matched"])
    lines.append("classification candidates")
    w = max(len(c.type) for c in cands)
    for c in cands:
        norm = normalize(value, c.type)
        lines.append(f"  {c.type:<{w}}  {c.score:>3}  {c.why}")
        if norm != value:
            lines.append(f"  {'':<{w}}       normalised: {norm}")
    if len(cands) > 1:
        lines.append(f"  ({len(cands)} readings; pivoting on the wrong one wastes the collection)")
    return "\n".join(lines)


def render_pivots(type: str, rows: list[dict[str, str]], width: int) -> str:
    if not rows:
        return f"\npivots accepting {type}: none matched the filters"
    name_w = min(max(len(r["name"]) for r in rows), 34)
    yield_w = min(max(len(r["yields"]) for r in rows), 32)
    fixed = name_w + 9 + 10 + 9 + yield_w + 4 + 8
    note_w = max(24, width - fixed)
    head = (
        f"{'source':<{name_w}}  {'mode':<7}  {'auth':<8}  {'fetch':<7}  "
        f"{'rel':<3}  {'yields':<{yield_w}}  notes"
    )
    lines = [f"\npivots accepting {type} ({len(rows)}), passive and no-auth first", head, "-" * min(len(head) + note_w, width)]
    for r in rows:
        lines.append(
            f"{_clip(r['name'], name_w):<{name_w}}  {r['mode']:<7}  {r['auth']:<8}  "
            f"{r['fetchable']:<7}  "
            f"{r['reliability']:<3}  {_clip(r['yields'], yield_w):<{yield_w}}  "
            f"{_clip(r['notes'], note_w)}"
        )
    unverified = sum(1 for r in rows if r["verified"] == "no")
    if unverified:
        lines.append(f"\n{unverified} of {len(rows)} rows are verified=no: endpoint unconfirmed, open it by hand first")
    unfetchable = sum(1 for r in rows if r["fetchable"] != "yes")
    if unfetchable:
        lines.append(
            f"{unfetchable} of {len(rows)} are not plain-fetchable (fetch=no needs a browser, "
            f"api needs the documented API, unknown is untested)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="selectors.py",
        description="Classify an OSINT selector and list the sources that accept it.",
        epilog=(
            "Classification returns every plausible reading, not one guess. "
            "Pivots are ranked passive-before-active, then none < free_key < "
            "account < paid, then Admiralty reliability."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("value", nargs="?", help="the selector to classify (email, domain, IP, hash, ...)")
    p.add_argument("--type", metavar="T",
                   help="skip classification and treat the value as this CONTRACT.md section 4 type")
    p.add_argument("--passive-only", action="store_true",
                   help="drop active sources; use this whenever scope has active_allowed=false")
    p.add_argument("--auth", metavar="LIST",
                   help="comma-separated auth values to keep, e.g. none,free_key")
    p.add_argument("--fetchable-only", action="store_true",
                   help="keep only fetchable=yes rows, i.e. ones a plain HTTP client can "
                        "retrieve at the endpoint as written; drops no, api and unknown")
    p.add_argument("--all", action="store_true",
                   help="show pivots for every candidate type, not just the best-scoring one")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--selfcheck", action="store_true", help="run assert-based checks and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selfcheck:
        demo()
        print("selectors.py selfcheck: all assertions passed")
        return 0

    if not args.value:
        build_parser().print_help()
        return 2

    auth_filter = None
    if args.auth:
        auth_filter = frozenset(a.strip() for a in args.auth.split(",") if a.strip())
        bad = auth_filter - set(AUTH_VALUES)
        if bad:
            print(f"error: unknown auth value(s): {', '.join(sorted(bad))}; "
                  f"allowed: {', '.join(AUTH_VALUES)}", file=sys.stderr)
            return 1

    if args.type:
        if args.type not in SELECTOR_TYPES:
            print(f"error: {args.type!r} is not a CONTRACT.md section 4 selector type",
                  file=sys.stderr)
            return 1
        cands = [Candidate(args.type, 100, "forced with --type")]
    else:
        cands = classify(args.value)
        if not cands:
            print(f"error: no candidate type matched {args.value!r}", file=sys.stderr)
            return 1

    try:
        rows = load_sources()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    targets = [c.type for c in cands] if args.all else [cands[0].type]

    if args.json:
        payload = {
            "value": args.value,
            "candidates": [
                {"type": c.type, "score": c.score, "why": c.why,
                 "normalized": normalize(args.value, c.type)}
                for c in cands
            ],
            "pivots": {
                t: pivots(t, sources=rows, passive_only=args.passive_only,
                          auth_filter=auth_filter, fetchable_only=args.fetchable_only)
                for t in targets
            },
            "filters": {"passive_only": args.passive_only,
                        "auth": sorted(auth_filter) if auth_filter else None,
                        "fetchable_only": args.fetchable_only},
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    width = shutil.get_terminal_size(fallback=(120, 24)).columns
    print(render_candidates(args.value, cands))
    for t in targets:
        print(render_pivots(t, pivots(t, sources=rows, passive_only=args.passive_only,
                                      auth_filter=auth_filter,
                                      fetchable_only=args.fetchable_only), width))
    if not args.all and len(cands) > 1:
        print(f"\nshowing pivots for {cands[0].type} only; --all covers "
              f"{', '.join(c.type for c in cands[1:])}")
    return 0


# ---------------------------------------------------------------------------
# demo / selfcheck
# ---------------------------------------------------------------------------

def demo() -> None:
    """Assert-based checks of the non-trivial logic. No network, no fixtures."""

    def top(v: str) -> str:
        c = classify(v)
        assert c, f"no candidate for {v!r}"
        return c[0].type

    def types(v: str) -> list[str]:
        return [c.type for c in classify(v)]

    # -- straightforward classification -------------------------------------
    assert top("jane.doe@acme.example") == "email"
    assert top("mailto:jane.doe@acme.example") == "email"
    assert top("acme.example") == "domain"
    assert top("mail.acme.example") == "subdomain"
    assert top("192.0.2.10") == "ip"
    assert top("2001:db8::1") == "ip"
    assert top("192.0.2.0/24") == "netblock"
    assert top("2001:db8::/32") == "netblock"
    assert top("https://acme.example/a/b?c=d") == "url"
    assert top("+1 415 555 2671") == "phone"
    assert top("0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed") == "crypto_address"
    assert top("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") == "crypto_address"
    assert top("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "crypto_address"
    assert top("d41d8cd98f00b204e9800998ecf8427e") == "file_hash"
    assert top("da39a3ee5e6b4b0d3255bfef95601890afd80709") == "file_hash"
    assert top("48.8584, 2.2945") == "coordinates"
    assert top("48.8584,2.2945") == "coordinates"
    assert top("Maria van der Berg") == "person_name"
    assert top("Acme Holdings Ltd") == "company"
    assert top("@acme_corp") == "username"

    # -- adversarial: an IP that looks like a version string -----------------
    # 10.0.0.1 is both, and it is an address, so `ip` must win outright.
    assert top("10.0.0.1") == "ip"
    # 2.4.1 is a version string. Three octets is not an address, so `ip` must
    # not appear at all -- a false ip candidate would send a scan at nothing.
    assert "ip" not in types("2.4.1"), types("2.4.1")
    assert "netblock" not in types("2.4.1")
    # 1.2.3.4.5 is five octets: also not an address.
    assert "ip" not in types("1.2.3.4.5")

    # -- adversarial: a domain-looking string that is really a local part ----
    # `doe` is not a delegated TLD, so `username` must outrank `domain`.
    jd = types("john.doe")
    assert jd[0] == "username", jd
    assert "domain" in jd, jd
    assert jd.index("username") < jd.index("domain"), jd
    # ...but with a real TLD the domain reading wins.
    assert top("john.io") == "domain"
    assert top("john.uk") == "domain"

    # -- adversarial: hash-length string that is really a username -----------
    # 32 characters but not hex: no file_hash candidate at all.
    handle = "abcdefghijklmnopqrstuvwxyz012345"
    assert len(handle) == 32
    assert "file_hash" not in types(handle), types(handle)
    assert top(handle) == "username"
    # 32 hex digits: file_hash wins, but username is still offered.
    hexy = types("deadbeefdeadbeefdeadbeefdeadbeef")
    assert hexy[0] == "file_hash", hexy
    assert "username" in hexy, hexy
    # 64 bare hex is a sha256 AND a Bitcoin txid. Both must be offered.
    sha = types("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert sha[0] == "file_hash" and "tx_hash" in sha, sha
    # 0x + 64 hex flips the ranking to tx_hash.
    evm = types("0x" + "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert evm[0] == "tx_hash", evm

    # -- adversarial: ASN with and without the AS prefix ---------------------
    assert top("AS15169") == "asn"
    assert top("as15169") == "asn"
    assert top("ASN15169") == "asn"
    bare = types("15169")
    assert "asn" in bare, bare
    assert "company_number" in bare, bare
    # Bare digits are genuinely ambiguous: nothing may claim high confidence,
    # or the CLI would print one pivot table and hide the other readings.
    assert max(c.score for c in classify("15169")) < 60, classify("15169")
    assert normalize("as015169", "asn") == "AS15169"
    assert normalize("15169", "asn") == "AS15169"

    # -- adversarial: a bare word is a handle AND a trading name ------------
    acme = types("acme")
    assert "username" in acme and "company" in acme, acme

    # -- normalisation correctness ------------------------------------------
    assert normalize("MAILTO:Jane.Doe@ACME.Example.", "email") == "jane.doe@acme.example"
    assert normalize("ACME.Example.", "domain") == "acme.example"
    assert normalize("2001:0DB8:0000:0000:0000:0000:0000:0001", "ip") == "2001:db8::1"
    assert normalize("192.0.2.37/24", "netblock") == "192.0.2.0/24"
    assert normalize("HTTP://Example.COM:80/Path?A=B", "url") == "http://example.com/Path?A=B"
    assert normalize("https://Example.COM:8443/x", "url") == "https://example.com:8443/x"
    assert normalize("+1 (415) 555-2671", "phone") == "+14155552671"
    assert normalize("0044 20 7946 0958", "phone") == "+442079460958"
    # No country code supplied: separators go, nothing is invented.
    assert normalize("(415) 555-2671", "phone") == "4155552671"
    assert normalize("@AcmeCorp", "username") == "acmecorp"
    assert normalize("  Maria  van der Berg ", "person_name") == "Maria van der Berg"
    assert normalize("d41d8cd98f00b204e9800998ECF8427E", "file_hash") == "d41d8cd98f00b204e9800998ecf8427e"
    assert normalize("sc 123456", "company_number") == "SC123456"
    # EIP-55 checksum case is NOT computed: Keccak-256 is not in hashlib.
    mixed = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    assert normalize(mixed, "crypto_address") == mixed.lower()
    # Base58Check is case-sensitive; the value must survive untouched.
    btc = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert normalize(btc, "crypto_address") == btc
    assert normalize("48.8584, 2.2945", "coordinates") == "48.8584,2.2945"
    assert normalize("48\u00b051'30.2\"N 2\u00b017'40.2\"E", "coordinates").startswith("48.858")
    assert normalize("40.7128 N, 74.0060 W", "coordinates") == "40.7128,-74.006"
    # IDNA where the stdlib supports it.
    assert normalize("B\u00fccher.example", "domain") == "xn--bcher-kva.example"

    # -- normalisation idempotence ------------------------------------------
    idem = [
        ("MAILTO:Jane.Doe@ACME.Example.", "email"),
        ("ACME.Example.", "domain"),
        ("WWW.Sub.Acme.Example.", "subdomain"),
        ("HTTP://Example.COM:80/Path?A=B#f", "url"),
        ("2001:0DB8::0001", "ip"),
        ("192.0.2.37/24", "netblock"),
        ("as015169", "asn"),
        ("+1 (415) 555-2671", "phone"),
        ("0044 20 7946 0958", "phone"),
        ("(415) 555-2671", "phone"),
        (mixed, "crypto_address"),
        (btc, "crypto_address"),
        ("bc1QAR0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", "crypto_address"),
        ("D41D8CD98F00B204E9800998ECF8427E", "file_hash"),
        ("0xDEADBEEF" + "0" * 56, "tx_hash"),
        ("@AcmeCorp", "username"),
        ("  Maria  van der Berg ", "person_name"),
        ("  Acme  Holdings Ltd ", "company"),
        ("sc 123456", "company_number"),
        ("48.8584, 2.2945", "coordinates"),
        ("48\u00b051'30.2\"N 2\u00b017'40.2\"E", "coordinates"),
        ("40.7128 N, 74.0060 W", "coordinates"),
        ("B\u00fccher.example", "domain"),
        ("  221B Baker Street ", "address"),
    ]
    for raw, t in idem:
        once = normalize(raw, t)
        twice = normalize(once, t)
        assert once == twice, f"not idempotent for {t}: {raw!r} -> {once!r} -> {twice!r}"

    # Idempotence must also hold for every type the classifier proposes.
    for probe in ("jane.doe@acme.example", "mail.acme.example", "10.0.0.1", "AS15169",
                  "john.doe", "acme", "Acme Holdings Ltd", "15169", "+1 415 555 2671",
                  "https://acme.example/a", "48.8584, 2.2945"):
        for c in classify(probe):
            once = normalize(probe, c.type)
            assert normalize(once, c.type) == once, f"{probe!r} as {c.type}"

    # -- the real registry, so a regression in sources.csv breaks this -------
    rows = load_sources()
    assert len(rows) >= 100, f"sources.csv has only {len(rows)} rows"
    known = set(SELECTOR_TYPES)
    for r in rows:
        for col in ("accepts", "yields"):
            for tok in r[col].split("|"):
                assert tok in known, f"{r['name']}: {col} token {tok!r} is not in CONTRACT.md section 4"
        assert r["auth"] in AUTH_VALUES, f"{r['name']}: auth {r['auth']!r}"
        assert r["mode"] in MODE_VALUES, f"{r['name']}: mode {r['mode']!r}"
        assert r["verified"] in ("yes", "no"), f"{r['name']}: verified {r['verified']!r}"
        # The fetchable column must exist on every row and hold one of the four
        # legal strings -- a typo here silently drops rows from --fetchable-only.
        assert "fetchable" in r, f"{r['name']}: no fetchable column"
        assert r["fetchable"] in FETCHABLE_VALUES, f"{r['name']}: fetchable {r['fetchable']!r}"
        assert r["reliability"] in tuple("ABCDEF"), f"{r['name']}: reliability {r['reliability']!r}"
    names = [r["name"] for r in rows]
    assert len(names) == len(set(names)), "duplicate name in sources.csv"
    # verified and fetchable are independent claims. If every fetchable=no row
    # were also verified=no the two columns would have been conflated again.
    assert any(r["verified"] == "yes" and r["fetchable"] != "yes" for r in rows), \
        "no row is verified=yes with an unfetchable endpoint; the columns look conflated"

    # -- pivot ranking -------------------------------------------------------
    for t in ("domain", "email", "ip", "username", "company"):
        ranked = pivots(t, sources=rows)
        assert ranked, f"no sources accept {t}"
        modes = [_MODE_RANK[r["mode"]] for r in ranked]
        assert modes == sorted(modes), f"{t}: an active source outranks a passive one"
        # Within the passive block, no-auth must come first.
        passive = [r for r in ranked if r["mode"] == "passive"]
        auths = [_AUTH_RANK[r["auth"]] for r in passive]
        assert auths == sorted(auths), f"{t}: paid source outranks a no-auth one"
        assert _sort_key(ranked[0]) <= _sort_key(ranked[-1])
        if passive:
            assert ranked[0]["mode"] == "passive", f"{t}: first pivot is not passive"
            if any(r["auth"] == "none" for r in passive):
                assert ranked[0]["auth"] == "none", f"{t}: first pivot is not auth=none"

    # Filters actually filter.
    assert all(r["mode"] == "passive" for r in pivots("domain", sources=rows, passive_only=True))
    fetch_ok = pivots("domain", sources=rows, fetchable_only=True)
    assert fetch_ok and all(r["fetchable"] == "yes" for r in fetch_ok)
    assert len(fetch_ok) < len(pivots("domain", sources=rows)), \
        "--fetchable-only dropped nothing; the column is not being read"
    # Ranking must be unchanged by the new column: the same rows in the same order.
    unfiltered = pivots("domain", sources=rows)
    assert [r["name"] for r in fetch_ok] == \
        [r["name"] for r in unfiltered if r["fetchable"] == "yes"], \
        "fetchable filtering reordered the ranking"
    cheap = pivots("email", sources=rows, auth_filter=frozenset({"none", "free_key"}))
    assert cheap and all(r["auth"] in ("none", "free_key") for r in cheap)
    assert len(cheap) <= len(pivots("email", sources=rows))
    # Every returned row genuinely accepts the type.
    assert all("ip" in r["accepts"].split("|") for r in pivots("ip", sources=rows))
    # A near-miss token must not match by substring: "ip" is a substring of
    # nothing in the vocabulary, but "domain" vs "subdomain" is the real trap.
    for r in pivots("domain", sources=rows):
        assert "domain" in r["accepts"].split("|")
    sub_only = [r for r in rows if r["accepts"].split("|") == ["subdomain"]]
    for r in sub_only:
        assert r not in pivots("domain", sources=rows), f"{r['name']} matched domain by substring"

    # Bad type is rejected, not silently empty.
    try:
        pivots("emails", sources=rows)
    except ValueError:
        pass
    else:
        raise AssertionError("pivots() accepted a plural selector type")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
