#!/usr/bin/env python3
"""Snapshot a target's observable footprint, and diff two snapshots.

Phase 3, standard library only (CONTRACT.md section 10). Windows-safe: pathlib
throughout, no hardcoded separators, no network calls at import time.

    python monitor.py snapshot --case ./cases/acme-2026-07 --target acme.example
    python monitor.py snapshot --case ./cases/acme-2026-07 --target acme.example --active
    python monitor.py diff     --case ./cases/acme-2026-07 --target acme.example
    python monitor.py list     --case ./cases/acme-2026-07
    python monitor.py --selfcheck

The point of the tool is that an investigator reads WHAT CHANGED instead of
re-reading the whole footprint every week. Snapshots are the raw material; the
diff is the product.

Four signals, and what each one costs you
-----------------------------------------
  dns       Record sets (A AAAA CNAME MX NS TXT SOA CAA) through a public DoH
            resolver -- dns.google/resolve or cloudflare-dns.com/dns-query, both
            recorded in assets/sources.csv as confirmed live. The query still
            reaches the target's authoritative nameservers, so sources.csv marks
            both rows mode=active and so does this script. The target sees a
            Google or Cloudflare resolver IP, not yours.
  tls       The certificate the host actually serves, read with the stdlib ssl
            module. ACTIVE: a TLS handshake to the target, from your address.
            This is the SERVED LEAF, not a Certificate Transparency log entry --
            which matters for grading; see grade_for() below.
  http      One GET with urllib: status, a fixed allowlist of stable response
            headers, and the sha256 of the body. ACTIVE: it lands in the
            target's access log.
  entities  The case's own entities.jsonl. Reads a local file, touches nothing.
            PASSIVE, and the only signal collected without --active.

No source API is invented here. DNS goes through two documented DoH endpoints
already in sources.csv; TLS and HTTP are the stdlib talking to the host itself;
everything else is read out of the case directory.

--active is the gate
--------------------
Without it, the three network signals are skipped and recorded as skipped, and
the snapshot's ledger row is mode=passive. With it, they run and the row is
mode=active. CONTRACT.md section 9 wants a fresh confirmation naming the
specific action for anything active; passing the flag is it. Repeated polling
is more detectable than a single fetch -- a weekly cadence draws a line in the
target's logs that a one-off lookup does not.

A diff is always passive: it compares two files that are already on disk.

Where the output goes
---------------------
  cases/<slug>/monitor/<ISO8601Z>.json   one snapshot, basic-format timestamp
                                         (20260728T145501Z) because a colon is
                                         not a legal Windows filename character
  cases/<slug>/ledger.jsonl              one appended row per snapshot (action
                                         "collect") and per changed diff
                                         (action "monitor", mode passive)
  cases/<slug>/entities.jsonl            appended rows for selectors the change
                                         introduced

A new subdomain appearing is a finding. It enters the case through
entities.jsonl like any other finding, graded, with its sources -- it does not
sit in a side file waiting to be noticed.

Exit codes: 0 ok (including "nothing changed", which is a clean PASS and the
most common result); 1 only with --exit-changed, when a diff found changes;
2 argparse usage error; 3 the case directory, a snapshot file, or the monitor
directory is missing or unreadable.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from urllib import error, parse, request

# scripts/selectors.py, not the stdlib `selectors` module. Same import dance as
# graph.py: running as a script puts this directory first on sys.path so the
# local module wins; imported any other way the stdlib module answers, has no
# classify(), and we fall back to a label-count heuristic. Only hostname typing
# depends on it, and guessing a different type is worse than degrading loudly.
try:
    from selectors import classify as _classify  # type: ignore[attr-defined]
    from selectors import normalize as _normalize  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on how this file is loaded
    _classify = None
    _normalize = None

# CONTRACT.md section 7, exact names and order. Nothing else goes in a ledger row.
LEDGER_FIELDS = (
    "ts", "actor", "action", "source", "query", "result", "result_sha256", "mode",
)

# CONTRACT.md section 7, exact names and order for an entities.jsonl line.
ENTITY_FIELDS = (
    "id", "type", "value", "first_seen", "grade", "sources", "candidate_group", "notes",
)

# CONTRACT.md section 4. Exact strings, no synonyms, no plurals.
SELECTOR_TYPES: tuple[str, ...] = (
    "email", "username", "person_name", "phone", "domain", "subdomain", "ip", "asn",
    "netblock", "url", "ssl_cert", "company", "company_number", "address", "photo",
    "video", "document", "crypto_address", "tx_hash", "vehicle_plate", "vessel",
    "aircraft", "coordinates", "file_hash", "social_profile", "breach_record",
)

# CONTRACT.md section 6: reliability letter + credibility digit, always both.
GRADES = frozenset(letter + digit for letter in "ABCDEF" for digit in "123456")

SCHEMA = "osint-monitor-snapshot/1"

SIGNALS: tuple[str, ...] = ("dns", "tls", "http", "entities")
NETWORK_SIGNALS: tuple[str, ...] = ("dns", "tls", "http")

DNS_TYPES: tuple[str, ...] = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA")

# Both endpoints are assets/sources.csv rows, verified=yes fetchable=yes, and both
# are recorded there as mode=active. The JSON form takes `name` and `type`.
DOH_ENDPOINTS = {
    "google": "https://dns.google/resolve",
    "cloudflare": "https://cloudflare-dns.com/dns-query",
}
DOH_ACCEPT = "application/dns-json"

# RFC 1035 and successors. Only the types this script queries.
DOH_TYPE_NUMBERS = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257,
}

# Response headers worth diffing. An allowlist, not a blocklist: Date, Age,
# Set-Cookie, Content-Length and every CDN request id change on every fetch, and
# a diff that cries wolf weekly is a diff nobody reads.
HTTP_HEADERS = (
    "server",
    "content-type",
    "location",
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "access-control-allow-origin",
    "x-powered-by",
    "via",
)

# TLS fields compared as scalars. SAN is compared as a set, separately.
TLS_SCALARS = ("subject_cn", "issuer", "serial", "not_before", "not_after", "chain_verified")
HTTP_SCALARS = ("status", "final_url", "body_sha256", "body_length")

DEFAULT_USER_AGENT = (
    "osint-plugin-monitor/1.0 (footprint change detection; stdlib urllib; "
    "contact: see case scope)"
)
DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
_CHUNK = 64 * 1024

RE_ENTITY_ID = re.compile(r"^e-([0-9]+)$")
RE_SNAPSHOT_NAME = re.compile(r"^(\d{8}T\d{6}Z)(?:-(\d+))?\.json$")


class MonitorError(Exception):
    """Anything that should stop the run and exit non-zero."""


# ---------------------------------------------------------------------------
# Primitives -- no network, all directly asserted in demo()
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ts_extended(when: datetime) -> str:
    """ISO8601 extended with a literal Z. Ledger and entity timestamps."""
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_basic(when: datetime) -> str:
    """ISO8601 basic with a literal Z. Filenames: a colon is illegal on Windows."""
    return when.strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value: str, type_: str) -> str:
    """Canonical form for duplicate detection, from selectors.py where available."""
    v, t = str(value or ""), str(type_ or "")
    if _normalize is not None:
        try:
            return _normalize(v, t)
        except Exception:  # a normaliser that crashes must not take the run down
            pass
    return " ".join(v.split()).lower()


def host_type(host: str) -> str:
    """`subdomain` or `domain` for a hostname, via selectors.py when importable.

    Fallback is a label count, which is wrong for co.uk-style suffixes. That is a
    known ceiling and it is why selectors.py is tried first.
    """
    h = (host or "").strip().rstrip(".").lower()
    if not h:
        return "domain"
    if _classify is not None:
        try:
            for cand in _classify(h):
                if cand.type in ("subdomain", "domain"):
                    return cand.type
        except Exception:
            pass
    return "subdomain" if h.count(".") >= 2 else "domain"


def hostname_from_rdata(rrtype: str, data: str) -> str | None:
    """Pull the hostname out of an rdata string.

    MX rdata is "<preference> <exchange>"; NS and CNAME rdata is the name alone.
    The trailing root dot is dropped so the value matches what the rest of the
    plugin writes. Anything else returns None -- TXT and CAA rdata are not
    hostnames and must never be minted as one.
    """
    d = (data or "").strip()
    if not d:
        return None
    if rrtype == "MX":
        parts = d.split()
        if len(parts) < 2:
            return None
        d = parts[-1]
    elif rrtype not in ("NS", "CNAME"):
        return None
    d = d.strip().rstrip(".").lower()
    if not d or "." not in d or " " in d:
        return None
    return d


def build_ledger_row(
    *,
    actor: str,
    action: str,
    source: str,
    query: str,
    result: str,
    result_sha256: str | None,
    mode: str,
    ts: str | None = None,
) -> dict:
    """A CONTRACT.md section 7 ledger row: these eight keys, in this order, no others."""
    if mode not in ("passive", "active"):
        raise MonitorError(f"mode must be passive or active, got {mode!r}")
    row = {
        "ts": ts or ts_extended(utc_now()),
        "actor": actor,
        "action": action,
        "source": source,
        "query": query,
        "result": result,
        "result_sha256": result_sha256,
        "mode": mode,
    }
    assert tuple(row) == LEDGER_FIELDS, "ledger field order drifted from CONTRACT.md section 7"
    return row


def build_entity(
    *,
    eid: str,
    type_: str,
    value: str,
    first_seen: str,
    grade: str,
    sources: list[str],
    notes: str,
    candidate_group: str | None = None,
) -> dict:
    """A CONTRACT.md section 7 entities.jsonl row: these eight keys, in this order."""
    if type_ not in SELECTOR_TYPES:
        raise MonitorError(f"type {type_!r} is not in the CONTRACT.md section 4 vocabulary")
    if grade not in GRADES:
        raise MonitorError(f"grade {grade!r} is not an Admiralty pair (CONTRACT.md section 6)")
    if not sources:
        raise MonitorError("an entity with no sources is not a finding (provenance or it does not exist)")
    row = {
        "id": eid,
        "type": type_,
        "value": value,
        "first_seen": first_seen,
        "grade": grade,
        "sources": sources,
        "candidate_group": candidate_group,
        "notes": notes,
    }
    assert tuple(row) == ENTITY_FIELDS, "entity field order drifted from CONTRACT.md section 7"
    return row


def append_jsonl(path: Path, rows: list[dict]) -> None:
    """Append JSON objects, one per line. Never rewrites (CONTRACT.md section 10)."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    """Every well-formed object in a jsonl file. Malformed lines are skipped, not guessed at."""
    if not path.is_file():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def next_entity_id(existing: list[dict]) -> int:
    """One past the highest e-<n> already used. Ids are never reused."""
    top = 0
    for row in existing:
        m = RE_ENTITY_ID.match(str(row.get("id") or ""))
        if m:
            top = max(top, int(m.group(1)))
    return top + 1


def entity_index(existing: list[dict]) -> set[tuple[str, str]]:
    """(type, normalized value) already in the case. Used to avoid duplicate rows."""
    return {
        (str(r.get("type") or ""), norm(str(r.get("value") or ""), str(r.get("type") or "")))
        for r in existing
        if r.get("type") and r.get("value")
    }


# ---------------------------------------------------------------------------
# Collection -- the only code in this file that touches the network
# ---------------------------------------------------------------------------

def _http_get(url: str, *, timeout: float, user_agent: str, accept: str,
              max_bytes: int) -> tuple[int, str, dict, bytes]:
    """GET a URL. Returns (status, final_url, headers-as-dict, body). Raises URLError."""
    req = request.Request(url, headers={
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Encoding": "identity",  # hash what the server serves, unmodified
    })
    with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - scheme is fixed by callers
        chunks: list[bytes] = []
        total = 0
        while total < max_bytes:
            chunk = resp.read(min(_CHUNK, max_bytes - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return (getattr(resp, "status", None) or resp.getcode(), resp.geturl(),
                headers, b"".join(chunks))


def parse_doh(payload: dict, rrtype: str) -> list[str]:
    """Sorted rdata strings from a DNS-JSON response.

    The JSON form returns {"Status": n, "Answer": [{"name","type","TTL","data"}]}.
    Answers for other rrtypes appear in a CNAME chain, so filter by the numeric
    type when it is present and keep everything when it is not.
    """
    want = DOH_TYPE_NUMBERS.get(rrtype)
    out: list[str] = []
    for ans in payload.get("Answer") or []:
        if not isinstance(ans, dict):
            continue
        data = ans.get("data")
        if not isinstance(data, str) or not data:
            continue
        got = ans.get("type")
        if want is not None and isinstance(got, int) and got != want:
            continue
        out.append(data.strip())
    return sorted(set(out))


def collect_dns(host: str, *, resolver: str, timeout: float, user_agent: str) -> dict:
    """Record sets for DNS_TYPES through a public DoH resolver. ACTIVE."""
    base = DOH_ENDPOINTS[resolver]
    records: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    for rrtype in DNS_TYPES:
        url = base + "?" + parse.urlencode({"name": host, "type": rrtype})
        try:
            status, _final, _hdrs, body = _http_get(
                url, timeout=timeout, user_agent=user_agent,
                accept=DOH_ACCEPT, max_bytes=1024 * 1024)
        except (error.URLError, OSError, TimeoutError) as exc:
            errors[rrtype] = str(getattr(exc, "reason", exc))
            continue
        if status != 200:
            errors[rrtype] = f"HTTP {status}"
            continue
        try:
            payload = json.loads(body.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            errors[rrtype] = f"response was not JSON ({exc.msg})"
            continue
        if not isinstance(payload, dict):
            errors[rrtype] = "response JSON was not an object"
            continue
        answers = parse_doh(payload, rrtype)
        if answers:
            records[rrtype] = answers
        elif payload.get("Status") not in (0, None):
            errors[rrtype] = f"resolver Status {payload.get('Status')}"
    ips = sorted(set(records.get("A", [])) | set(records.get("AAAA", [])))
    return {
        "collected": True,
        "mode": "active",
        "resolver": resolver,
        "endpoint": base,
        "records": records,
        "ips": ips,
        "errors": errors,
    }


def _cn_of(rdns) -> str:
    """commonName out of getpeercert()'s nested-tuple subject/issuer structure."""
    for rdn in rdns or ():
        for pair in rdn:
            if len(pair) == 2 and pair[0] == "commonName":
                return str(pair[1])
    return ""


def _org_of(rdns) -> str:
    for rdn in rdns or ():
        for pair in rdn:
            if len(pair) == 2 and pair[0] == "organizationName":
                return str(pair[1])
    return ""


def summarise_cert(cert: dict, *, chain_verified: bool) -> dict:
    """The stable, diffable fields of a served certificate."""
    san = sorted({
        str(v).rstrip(".").lower()
        for kind, v in (cert.get("subjectAltName") or ())
        if kind in ("DNS", "IP Address") and v
    })
    issuer_cn = _cn_of(cert.get("issuer"))
    issuer_o = _org_of(cert.get("issuer"))
    return {
        "subject_cn": _cn_of(cert.get("subject")),
        "issuer": " / ".join(x for x in (issuer_o, issuer_cn) if x),
        "serial": str(cert.get("serialNumber") or ""),
        "not_before": str(cert.get("notBefore") or ""),
        "not_after": str(cert.get("notAfter") or ""),
        "chain_verified": chain_verified,
        "san": san,
    }


def collect_tls(host: str, *, port: int, timeout: float) -> dict:
    """The certificate the host actually serves. ACTIVE: a handshake from your address.

    A chain that fails verification is captured anyway with chain_verified false --
    a self-signed or expired certificate on a production name is a finding, not a
    reason to record nothing. Nothing is sent over the connection beyond the
    handshake itself.
    """
    out: dict = {"collected": False, "mode": "active", "port": port, "error": None}
    for verify in (True, False):
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as tls:
                    cert = tls.getpeercert()
                    out.update(summarise_cert(cert or {}, chain_verified=verify))
                    out["tls_version"] = tls.version()
                    out["collected"] = True
                    out["error"] = None if verify else out.get("error")
                    return out
        except ssl.SSLError as exc:
            out["error"] = f"TLS: {exc}"
            continue  # retry once without verification to capture the cert anyway
        except (OSError, TimeoutError) as exc:
            out["error"] = str(exc)
            return out
    return out


def collect_http(url: str, *, timeout: float, user_agent: str, max_bytes: int) -> dict:
    """One GET. ACTIVE: it lands in the target's access log."""
    try:
        status, final_url, headers, body = _http_get(
            url, timeout=timeout, user_agent=user_agent, accept="*/*", max_bytes=max_bytes)
    except error.HTTPError as exc:
        # A 404 or a 403 is a perfectly good observation and must be recorded, not lost.
        body = b""
        try:
            body = exc.read()[:max_bytes]
        except Exception:  # noqa: BLE001 - an unreadable error body is not fatal
            pass
        headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
        status, final_url = exc.code, getattr(exc, "url", url) or url
    except (error.URLError, OSError, TimeoutError) as exc:
        return {"collected": False, "mode": "active", "url": url,
                "error": str(getattr(exc, "reason", exc))}
    return {
        "collected": True,
        "mode": "active",
        "url": url,
        "status": status,
        "final_url": final_url,
        "headers": {k: headers[k] for k in HTTP_HEADERS if k in headers},
        "body_sha256": sha256_bytes(body),
        "body_length": len(body),
        "error": None,
    }


def collect_entities(case_dir: Path) -> dict:
    """The case's own entity set. PASSIVE: reads one local file, touches nothing."""
    rows = read_jsonl(case_dir / "entities.jsonl")
    latest: dict[str, dict] = {}
    for row in rows:
        eid = row.get("id")
        if isinstance(eid, str) and eid:
            latest[eid] = row  # append-only file: the last row for an id wins
    values = sorted({
        f"{r.get('type')}:{r.get('value')}"
        for r in latest.values() if r.get("type") and r.get("value")
    })
    return {"collected": True, "mode": "passive", "count": len(values), "values": values}


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def http_url_for(target: str) -> str:
    """https:// on the bare name unless the target already carries a scheme."""
    return target if "://" in target else "https://" + target.rstrip("/") + "/"


def host_of(target: str) -> str:
    """The hostname to resolve and handshake with, whether or not a URL was given."""
    if "://" in target:
        return parse.urlsplit(target).hostname or target
    return target.split("/", 1)[0].strip().rstrip(".").lower()


def take_snapshot(case_dir: Path, target: str, *, signals: tuple[str, ...], active: bool,
                  resolver: str, port: int, timeout: float, user_agent: str,
                  max_bytes: int, when: datetime | None = None) -> dict:
    """Build a snapshot dict. Network signals run only when `active` is true."""
    when = when or utc_now()
    host = host_of(target)
    if not host:
        raise MonitorError(f"could not read a hostname out of target {target!r}")

    out: dict = {
        "schema": SCHEMA,
        "ts": ts_extended(when),
        "target": target,
        "host": host,
        "case": case_dir.name,
        "active": bool(active),
        "signals": {},
    }
    for name in signals:
        if name in NETWORK_SIGNALS and not active:
            out["signals"][name] = {
                "collected": False, "mode": "active", "skipped": "requires --active",
            }
            continue
        if name == "dns":
            out["signals"][name] = collect_dns(
                host, resolver=resolver, timeout=timeout, user_agent=user_agent)
        elif name == "tls":
            out["signals"][name] = collect_tls(host, port=port, timeout=timeout)
        elif name == "http":
            out["signals"][name] = collect_http(
                http_url_for(target), timeout=timeout, user_agent=user_agent,
                max_bytes=max_bytes)
        elif name == "entities":
            out["signals"][name] = collect_entities(case_dir)
    return out


def snapshot_mode(snap: dict) -> str:
    """active if any network signal actually ran; passive otherwise. Honestly, per row."""
    for name in NETWORK_SIGNALS:
        if (snap.get("signals") or {}).get(name, {}).get("collected"):
            return "active"
    return "passive"


def monitor_dir(case_dir: Path) -> Path:
    return case_dir / "monitor"


def write_snapshot(case_dir: Path, snap: dict, when: datetime) -> tuple[Path, str]:
    """Write to monitor/<ISO8601Z basic>.json. Returns (path, sha256 of the bytes)."""
    mdir = monitor_dir(case_dir)
    mdir.mkdir(parents=True, exist_ok=True)
    stem = ts_basic(when)
    path = mdir / f"{stem}.json"
    n = 1
    while path.exists():  # two snapshots inside one second must not clobber
        path = mdir / f"{stem}-{n}.json"
        n += 1
    payload = json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path, sha256_bytes(payload.encode("utf-8"))


def load_snapshots(case_dir: Path, target: str | None = None) -> list[tuple[Path, dict]]:
    """Every readable snapshot, oldest first by filename timestamp then by name."""
    mdir = monitor_dir(case_dir)
    if not mdir.is_dir():
        return []
    out: list[tuple[str, int, Path, dict]] = []
    for path in mdir.iterdir():
        m = RE_SNAPSHOT_NAME.match(path.name)
        if not m or not path.is_file():
            continue
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(snap, dict) or snap.get("schema") != SCHEMA:
            continue
        if target and snap.get("target") != target and snap.get("host") != host_of(target):
            continue
        # Sort on the collision suffix as a NUMBER: "...Z-1.json" sorts before
        # "...Z.json" as a string, which would silently reverse the pair a diff
        # picks when two snapshots land inside the same second.
        out.append((m.group(1), int(m.group(2) or 0), path, snap))
    out.sort(key=lambda t: (t[0], t[1]))
    return [(path, snap) for _stamp, _n, path, snap in out]


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

class Change(NamedTuple):
    signal: str   # dns | tls | http | entities
    kind: str     # added | removed | changed
    key: str      # what inside the signal: "A", "san", "status", "header:server", ...
    old: str      # "" for added
    new: str      # "" for removed


class Skipped(NamedTuple):
    signal: str
    reason: str


def _set_changes(signal: str, key: str, old: list, new: list) -> list[Change]:
    o, n = set(map(str, old or [])), set(map(str, new or []))
    out = [Change(signal, "added", key, "", v) for v in sorted(n - o)]
    out += [Change(signal, "removed", key, v, "") for v in sorted(o - n)]
    return out


def _fmt(v) -> str:
    return v if isinstance(v, str) else json.dumps(v)


def _scalar_changes(signal: str, keys, old: dict, new: dict) -> list[Change]:
    out: list[Change] = []
    for k in keys:
        a, b = old.get(k), new.get(k)
        if k in old and k in new and a != b:
            out.append(Change(signal, "changed", k, _fmt(a), _fmt(b)))
    return out


def diff_snapshots(old: dict, new: dict) -> tuple[list[Change], list[Skipped]]:
    """Compare two snapshots. Returns (changes, signals that could not be compared).

    A signal is compared only when BOTH snapshots collected it. A signal present
    in one and absent in the other is reported as skipped, never as a wholesale
    removal -- "we did not look" and "it is gone" are different facts and
    conflating them is how a monitor invents an incident.
    """
    changes: list[Change] = []
    skipped: list[Skipped] = []
    old_sig = old.get("signals") or {}
    new_sig = new.get("signals") or {}

    for name in SIGNALS:
        o, n = old_sig.get(name), new_sig.get(name)
        if not isinstance(o, dict) or not isinstance(n, dict):
            if isinstance(o, dict) or isinstance(n, dict):
                skipped.append(Skipped(name, "present in only one snapshot"))
            continue
        if not o.get("collected") or not n.get("collected"):
            reason = (n.get("skipped") or n.get("error")
                      or o.get("skipped") or o.get("error") or "not collected")
            skipped.append(Skipped(name, str(reason)))
            continue

        if name == "dns":
            o_rec, n_rec = o.get("records") or {}, n.get("records") or {}
            for rrtype in sorted(set(o_rec) | set(n_rec)):
                changes += _set_changes(name, rrtype, o_rec.get(rrtype, []), n_rec.get(rrtype, []))
            changes += _set_changes(name, "ip", o.get("ips") or [], n.get("ips") or [])
        elif name == "tls":
            changes += _scalar_changes(name, TLS_SCALARS, o, n)
            changes += _set_changes(name, "san", o.get("san") or [], n.get("san") or [])
        elif name == "http":
            changes += _scalar_changes(name, HTTP_SCALARS, o, n)
            oh, nh = o.get("headers") or {}, n.get("headers") or {}
            for hk in sorted(set(oh) | set(nh)):
                if hk not in oh:
                    changes.append(Change(name, "added", f"header:{hk}", "", str(nh[hk])))
                elif hk not in nh:
                    changes.append(Change(name, "removed", f"header:{hk}", str(oh[hk]), ""))
                elif str(oh[hk]) != str(nh[hk]):
                    changes.append(Change(name, "changed", f"header:{hk}", str(oh[hk]), str(nh[hk])))
        elif name == "entities":
            changes += _set_changes(name, "entity", o.get("values") or [], n.get("values") or [])

    return changes, skipped


# ---------------------------------------------------------------------------
# Grading -- read references/41-confidence.md before touching this
# ---------------------------------------------------------------------------

def grade_for(signal: str, key: str) -> tuple[str, str]:
    """(grade, rationale) for a selector a change introduced.

    Both grades are credibility 3: ONE authoritative source alone is A3, or A2
    only where it is consistent with other collected material -- which is a
    judgement this script cannot make and the analyst can. Credibility 1 would
    need a second, independently generated observation.

    The one stated single-source A1 exemption in 41-confidence.md is CERTIFICATE
    TRANSPARENCY: a CT log entry is self-authenticating and mirrored across logs.
    It does NOT apply here. This script reads the leaf certificate the host
    served over one connection -- an authoritative primary artifact (A), but not
    an append-only mirrored log, so the exemption is off and the digit stays 3.
    """
    if signal == "tls":
        return "A3", (
            "the served leaf certificate is an authoritative primary artifact (A); "
            "credibility 3 because this is a single observation and the "
            "certificate-transparency A1 exemption applies to CT log entries, not "
            "to a certificate read off one TLS connection"
        )
    if signal == "dns":
        return "B3", (
            f"live {key} answer through a public recursive resolver; sources.csv grades "
            "Google Public DNS and Cloudflare 1.1.1.1 as B, and credibility is 3 because "
            "one resolver at one moment is a single uncorroborated observation"
        )
    return "F6", "no grading rule for this signal; treat as ungraded and check by hand"


def selectors_from(changes: list[Change]) -> list[tuple[str, str, str, str, str]]:
    """New selectors a diff introduced: (type, value, grade, rationale, provenance).

    Only additions mint entities, and only from signals whose rdata IS a selector.
    TXT, CAA, SOA and HTTP header values are changes worth reading; they are not
    selectors and are never minted as one.
    """
    out: list[tuple[str, str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(type_: str, value: str, signal: str, key: str, prov: str) -> None:
        value = value.strip()
        if not value:
            return
        k = (type_, norm(value, type_))
        if k in seen:
            return
        seen.add(k)
        grade, why = grade_for(signal, key)
        out.append((type_, value, grade, why, prov))

    for ch in changes:
        if ch.kind != "added":
            continue
        if ch.signal == "dns":
            if ch.key in ("A", "AAAA"):
                add("ip", ch.new, "dns", ch.key, f"new {ch.key} record")
            elif ch.key in ("MX", "NS", "CNAME"):
                host = hostname_from_rdata(ch.key, ch.new)
                if host:
                    add(host_type(host), host, "dns", ch.key, f"new {ch.key} record {ch.new!r}")
        elif ch.signal == "tls" and ch.key == "san":
            v = ch.new
            add("ip" if _looks_like_ip(v) else host_type(v), v, "tls", "san",
                "new subjectAltName on the served certificate")
    return out


def _looks_like_ip(value: str) -> bool:
    """Strict: ipaddress rejects the short forms inet_aton accepts ("1" is not an IP)."""
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_PLAIN = {
    ("dns", "ip"): "resolved address",
    ("dns", "A"): "IPv4 address",
    ("dns", "AAAA"): "IPv6 address",
    ("dns", "MX"): "mail exchanger",
    ("dns", "NS"): "nameserver",
    ("dns", "CNAME"): "alias target",
    ("dns", "TXT"): "TXT record",
    ("dns", "SOA"): "zone SOA",
    ("dns", "CAA"): "CAA issuance policy",
    ("tls", "san"): "certificate subjectAltName",
    ("tls", "serial"): "certificate serial",
    ("tls", "issuer"): "certificate issuer",
    ("tls", "not_after"): "certificate expiry",
    ("tls", "not_before"): "certificate start",
    ("tls", "subject_cn"): "certificate common name",
    ("tls", "chain_verified"): "certificate chain validity",
    ("http", "status"): "HTTP status",
    ("http", "final_url"): "URL after redirects",
    ("http", "body_sha256"): "page content hash",
    ("http", "body_length"): "page byte length",
    ("entities", "entity"): "case entity",
}


def plain(ch: Change) -> str:
    """One line an investigator can read without decoding the field name."""
    label = _PLAIN.get((ch.signal, ch.key)) or ch.key.replace("header:", "response header ")
    if ch.kind == "added":
        return f"new {label}: {ch.new}"
    if ch.kind == "removed":
        return f"{label} gone: {ch.old}"
    return f"{label} changed: {ch.old} -> {ch.new}"


def summarise_changes(changes: list[Change]) -> str:
    """The ledger `result` field: dense, one line, counts by signal."""
    if not changes:
        return "no change"
    by: dict[str, int] = {}
    for ch in changes:
        by[ch.signal] = by.get(ch.signal, 0) + 1
    counts = ", ".join(f"{s} {by[s]}" for s in SIGNALS if s in by)
    kinds = ", ".join(
        f"{k} {sum(1 for c in changes if c.kind == k)}"
        for k in ("added", "removed", "changed")
        if any(c.kind == k for c in changes)
    )
    return f"{len(changes)} change(s) [{counts}] ({kinds})"


def render_diff(old_path: Path, new_path: Path, changes: list[Change],
                skipped: list[Skipped], new_entities: list[dict],
                wrote: bool) -> str:
    lines = [
        f"baseline      {old_path.name}",
        f"current       {new_path.name}",
    ]
    if not changes:
        lines += [
            "result        PASS - no change across the compared signals",
            "",
            "Nothing moved. Silence is a result: it is evidence the footprint held",
            "steady between these two snapshots. Nothing was written to the case.",
        ]
    else:
        lines.append(f"result        {len(changes)} change(s)")
        lines.append("")
        for signal in SIGNALS:
            rows = [c for c in changes if c.signal == signal]
            if not rows:
                continue
            lines.append(f"[{signal}]")
            for kind in ("added", "removed", "changed"):
                for ch in [c for c in rows if c.kind == kind]:
                    lines.append(f"  {kind:<8} {plain(ch)}")
            lines.append("")
    if skipped:
        lines.append("[not compared]")
        for sk in skipped:
            lines.append(f"  {sk.signal:<9} {sk.reason}")
        lines.append("  A signal that was not collected in both snapshots is not a")
        lines.append("  disappearance. Nothing was concluded from it.")
        lines.append("")
    if new_entities:
        lines.append("[entities appended]")
        for ent in new_entities:
            lines.append(f"  {ent['id']:<6} {ent['type']:<10} {ent['value']}  grade {ent['grade']}")
        lines.append("")
    elif changes:
        lines.append("[entities appended]  none - no change introduced a new selector")
        lines.append("")
    lines.append("ledger        " + ("1 row appended (action monitor, mode passive)"
                                     if wrote and changes else
                                     "no row - nothing changed" if not changes else
                                     "dry run, nothing written"))
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def require_case(case_dir: Path) -> Path:
    if not case_dir.is_dir():
        raise MonitorError(f"case directory does not exist: {case_dir}")
    return case_dir


def cmd_snapshot(args) -> int:
    case_dir = require_case(Path(args.case))
    when = utc_now()
    signals = tuple(args.signals)
    snap = take_snapshot(
        case_dir, args.target, signals=signals, active=args.active,
        resolver=args.resolver, port=args.port, timeout=args.timeout,
        user_agent=args.user_agent, max_bytes=args.max_bytes, when=when)
    path, digest = write_snapshot(case_dir, snap, when)
    mode = snapshot_mode(snap)

    collected = [s for s in signals if snap["signals"][s].get("collected")]
    missing = [s for s in signals if not snap["signals"][s].get("collected")]
    result = (f"snapshot {path.name}; collected {', '.join(collected) or 'nothing'}"
              + (f"; skipped {', '.join(missing)}" if missing else ""))

    append_jsonl(case_dir / "ledger.jsonl", [build_ledger_row(
        actor=args.actor,
        # "collect" is a CONTRACT.md section 7 action. A snapshot IS a collection
        # step; only the diff uses the Phase 3 "monitor" action.
        action="collect",
        source="monitor.py",
        query=args.query or f"footprint snapshot of {args.target}",
        result=result,
        result_sha256=digest,
        mode=mode,
        ts=snap["ts"],
    )])

    print(f"snapshot      {path}")
    print(f"target        {args.target}  (host {snap['host']})")
    print(f"ts            {snap['ts']}")
    print(f"mode          {mode}"
          + ("" if mode == "active" else "  - no network signal ran; pass --active to enable"))
    for name in signals:
        sig = snap["signals"][name]
        if sig.get("collected"):
            detail = {
                "dns": lambda s: f"{sum(len(v) for v in (s.get('records') or {}).values())} record(s) "
                                 f"across {len(s.get('records') or {})} type(s)",
                "tls": lambda s: f"{len(s.get('san') or [])} SAN name(s), expires {s.get('not_after') or '?'}"
                                 + ("" if s.get("chain_verified") else ", CHAIN DID NOT VERIFY"),
                "http": lambda s: f"HTTP {s.get('status')}, {s.get('body_length')} bytes",
                "entities": lambda s: f"{s.get('count')} entity value(s) in the case",
            }[name](sig)
            print(f"  {name:<9} {detail}")
        else:
            print(f"  {name:<9} not collected: {sig.get('skipped') or sig.get('error') or 'unknown'}")
    print(f"sha256        {digest}")
    print(f"ledger        {case_dir / 'ledger.jsonl'}  (1 row appended)")
    if len(load_snapshots(case_dir, args.target)) < 2:
        print("\nFirst snapshot for this target: this is the baseline. There is nothing")
        print("to diff yet, which is a clean PASS. Run `diff` after the next snapshot.")
    return 0


def resolve_pair(case_dir: Path, target: str | None, from_: str | None, to: str | None
                 ) -> tuple[Path, dict, Path, dict] | None:
    """The two snapshots to compare, or None when there is no baseline yet."""
    snaps = load_snapshots(case_dir, target)
    if from_ or to:
        by_name = {p.name: (p, s) for p, s in snaps}
        for want in (from_, to):
            if want and want not in by_name:
                raise MonitorError(
                    f"no snapshot named {want!r} in {monitor_dir(case_dir)}; "
                    f"have: {', '.join(sorted(by_name)) or '(none)'}")
        if not (from_ and to):
            raise MonitorError("--from and --to must be given together")
        (op, os_), (np, ns) = by_name[from_], by_name[to]
        return op, os_, np, ns
    if len(snaps) < 2:
        return None
    (op, os_), (np, ns) = snaps[-2], snaps[-1]
    return op, os_, np, ns


def cmd_diff(args) -> int:
    case_dir = require_case(Path(args.case))
    pair = resolve_pair(case_dir, args.target, getattr(args, "from"), args.to)
    if pair is None:
        n = len(load_snapshots(case_dir, args.target))
        print("baseline      none" if n == 0 else f"baseline      {n} snapshot on file")
        print("result        PASS - nothing to compare yet")
        print("")
        print("A first run with no baseline is not an error. Take another snapshot")
        print("later and diff then; the first snapshot IS the baseline.")
        return 0

    old_path, old_snap, new_path, new_snap = pair
    changes, skipped = diff_snapshots(old_snap, new_snap)

    new_entities: list[dict] = []
    wrote = False
    if changes and not args.dry_run:
        ledger_ts = ts_extended(utc_now())
        digest = sha256_bytes(new_path.read_bytes())
        append_jsonl(case_dir / "ledger.jsonl", [build_ledger_row(
            actor=args.actor,
            action="monitor",
            source="monitor.py",
            query=args.query or f"footprint diff {old_path.name} -> {new_path.name} "
                                f"for {new_snap.get('target')}",
            result=summarise_changes(changes),
            result_sha256=digest,
            # A diff compares two files already on disk. Nothing is contacted.
            mode="passive",
            ts=ledger_ts,
        )])
        wrote = True

        existing = read_jsonl(case_dir / "entities.jsonl")
        index = entity_index(existing)
        nid = next_entity_id(existing)
        for type_, value, grade, why, prov in selectors_from(changes):
            if (type_, norm(value, type_)) in index:
                continue
            index.add((type_, norm(value, type_)))
            new_entities.append(build_entity(
                eid=f"e-{nid}",
                type_=type_,
                value=value,
                first_seen=new_snap.get("ts") or ledger_ts,
                grade=grade,
                sources=[ledger_ts],
                notes=(f"appeared between monitor snapshots {old_path.name} and "
                       f"{new_path.name}: {prov}. Grading: {why}. rung observed. "
                       f"Not merged with anything; no linking datapoint is asserted."),
            ))
            nid += 1
        append_jsonl(case_dir / "entities.jsonl", new_entities)

    print(render_diff(old_path, new_path, changes, skipped, new_entities, wrote), end="")
    return 1 if (changes and args.exit_changed) else 0


def cmd_list(args) -> int:
    case_dir = require_case(Path(args.case))
    snaps = load_snapshots(case_dir, args.target)
    if not snaps:
        print(f"no snapshots in {monitor_dir(case_dir)}")
        return 0
    print(f"{'file':<28} {'ts':<21} {'mode':<8} target")
    for path, snap in snaps:
        print(f"{path.name:<28} {snap.get('ts', ''):<21} "
              f"{snapshot_mode(snap):<8} {snap.get('target', '')}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _signal_list(text: str) -> tuple[str, ...]:
    names = tuple(s.strip().lower() for s in text.split(",") if s.strip())
    bad = [n for n in names if n not in SIGNALS]
    if bad:
        raise argparse.ArgumentTypeError(
            f"unknown signal(s) {', '.join(bad)}; choose from {', '.join(SIGNALS)}")
    return names or SIGNALS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="monitor.py",
        description=(
            "Snapshot a target's observable footprint and diff two snapshots, so an "
            "investigator reads what changed rather than re-reading everything."),
        epilog=(
            "Network signals (dns, tls, http) are ACTIVE and off unless --active is "
            "passed: DNS reaches the target's nameservers, TLS and HTTP reach the "
            "target itself, and repeated polling is more detectable than a single "
            "fetch. The entities signal is passive. A diff is always passive. "
            "Nothing changing is a clean PASS, not an error."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--selfcheck", action="store_true",
                   help="run assert-based checks and exit; makes no network calls")
    sub = p.add_subparsers(dest="cmd", metavar="{snapshot,diff,list}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--case", metavar="DIR", required=True, type=Path,
                        help="case directory holding ledger.jsonl, entities.jsonl and monitor/")
    common.add_argument("--actor", default="main",
                        help="ledger actor: main, or an agent name (default: main)")
    common.add_argument("--query", metavar="TEXT",
                        help="ledger query text; start it with the scope question id, "
                             "e.g. \"Q2: weekly footprint diff\"")

    s = sub.add_parser("snapshot", parents=[common],
                       help="record the current state of the target's footprint")
    s.add_argument("--target", required=True, metavar="NAME",
                   help="hostname or URL already in the case, or the case's primary target")
    s.add_argument("--active", action="store_true",
                   help="ALLOW the network signals. Without it dns, tls and http are "
                        "skipped and only the passive entities signal is recorded")
    s.add_argument("--signals", type=_signal_list, default=SIGNALS, metavar="LIST",
                   help=f"comma-separated subset of {','.join(SIGNALS)} (default: all)")
    s.add_argument("--resolver", choices=tuple(DOH_ENDPOINTS), default="cloudflare",
                   help="public DoH resolver for the dns signal (default: cloudflare)")
    s.add_argument("--port", type=int, default=443, metavar="N",
                   help="TLS port for the tls signal (default: 443)")
    s.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SEC",
                   help=f"per-request socket timeout (default: {DEFAULT_TIMEOUT:g})")
    s.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, metavar="N",
                   help=f"cap on the hashed HTTP body (default: {DEFAULT_MAX_BYTES})")
    s.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                   help="User-Agent header sent with every request")
    s.set_defaults(func=cmd_snapshot)

    d = sub.add_parser("diff", parents=[common],
                       help="compare two snapshots and record what changed")
    d.add_argument("--target", metavar="NAME",
                   help="only consider snapshots of this target (default: all in the case)")
    d.add_argument("--from", metavar="FILE",
                   help="baseline snapshot filename; default is the second most recent")
    d.add_argument("--to", metavar="FILE",
                   help="current snapshot filename; default is the most recent")
    d.add_argument("--dry-run", action="store_true",
                   help="print the diff without appending to ledger.jsonl or entities.jsonl")
    d.add_argument("--exit-changed", action="store_true",
                   help="exit 1 when changes were found, for a scheduler that alerts "
                        "on a non-zero exit. Default exit is 0 either way")
    d.set_defaults(func=cmd_diff)

    ls = sub.add_parser("list", parents=[common], help="list the snapshots on file")
    ls.add_argument("--target", metavar="NAME", help="filter to one target")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selfcheck:
        demo()
        print("monitor.py selfcheck: all assertions passed (no network calls made)")
        return 0
    if not getattr(args, "func", None):
        parser.print_help()
        print("\nerror: a subcommand is required (snapshot, diff or list)", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except MonitorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


# ---------------------------------------------------------------------------
# demo / selfcheck -- no network, crafted fixtures only
# ---------------------------------------------------------------------------

def _snap(ts: str, target: str = "acme.example", **signals) -> dict:
    return {"schema": SCHEMA, "ts": ts, "target": target, "host": target,
            "case": "acme-2026-07", "active": True, "signals": dict(signals)}


def _dns(records: dict, ips: list[str] | None = None) -> dict:
    return {"collected": True, "mode": "active", "resolver": "cloudflare",
            "endpoint": DOH_ENDPOINTS["cloudflare"], "records": records,
            "ips": ips if ips is not None else sorted(
                set(records.get("A", [])) | set(records.get("AAAA", []))),
            "errors": {}}


def demo() -> None:
    """Assert-based checks of the non-trivial logic. Makes no network calls."""
    import tempfile

    # -- timestamps ----------------------------------------------------------
    when = datetime(2026, 7, 28, 14, 55, 1, tzinfo=timezone.utc)
    assert ts_extended(when) == "2026-07-28T14:55:01Z"
    assert ts_basic(when) == "20260728T145501Z"
    # The filename form must be legal on Windows: no colons anywhere.
    assert ":" not in ts_basic(when)
    assert RE_SNAPSHOT_NAME.match(ts_basic(when) + ".json")
    assert RE_SNAPSHOT_NAME.match(ts_basic(when) + "-1.json")
    assert not RE_SNAPSHOT_NAME.match("notes.json")

    # -- target parsing ------------------------------------------------------
    assert host_of("acme.example") == "acme.example"
    assert host_of("https://acme.example/a/b?c=d") == "acme.example"
    assert host_of("ACME.Example.") == "acme.example"
    assert http_url_for("acme.example") == "https://acme.example/"
    assert http_url_for("http://acme.example/x") == "http://acme.example/x"

    # -- rdata parsing -------------------------------------------------------
    assert hostname_from_rdata("MX", "10 mail.acme.example.") == "mail.acme.example"
    assert hostname_from_rdata("MX", "0 .") is None
    assert hostname_from_rdata("MX", "mail.acme.example") is None  # no preference field
    assert hostname_from_rdata("NS", "ns1.acme.example.") == "ns1.acme.example"
    assert hostname_from_rdata("CNAME", "edge.cdn.example.") == "edge.cdn.example"
    # TXT and CAA rdata are not hostnames and must never be minted as selectors.
    assert hostname_from_rdata("TXT", "v=spf1 include:_spf.example -all") is None
    assert hostname_from_rdata("CAA", '0 issue "letsencrypt.org"') is None
    assert hostname_from_rdata("A", "1.2.3.4") is None
    assert hostname_from_rdata("NS", "") is None

    # -- DoH JSON parsing, on a fixture; nothing is fetched ------------------
    payload = {"Status": 0, "Answer": [
        {"name": "acme.example.", "type": 5, "TTL": 60, "data": "edge.cdn.example."},
        {"name": "edge.cdn.example.", "type": 1, "TTL": 60, "data": "203.0.113.9"},
        {"name": "edge.cdn.example.", "type": 1, "TTL": 60, "data": "203.0.113.8"},
    ]}
    assert parse_doh(payload, "A") == ["203.0.113.8", "203.0.113.9"]
    assert parse_doh(payload, "CNAME") == ["edge.cdn.example."]
    assert parse_doh(payload, "MX") == []
    assert parse_doh({"Status": 3}, "A") == []
    assert parse_doh({"Status": 0, "Answer": [{"data": ""}, "junk", {}]}, "A") == []
    assert DOH_TYPE_NUMBERS["AAAA"] == 28 and DOH_TYPE_NUMBERS["CAA"] == 257

    # -- certificate summary, from a getpeercert()-shaped fixture ------------
    cert = {
        "subject": ((("commonName", "acme.example"),),),
        "issuer": ((("organizationName", "Example CA"),), (("commonName", "Example CA R3"),)),
        "serialNumber": "0A1B2C",
        "notBefore": "Jun  1 00:00:00 2026 GMT",
        "notAfter": "Aug 30 23:59:59 2026 GMT",
        "subjectAltName": (("DNS", "acme.example"), ("DNS", "www.acme.example"),
                           ("DNS", "VPN.Acme.Example."), ("IP Address", "203.0.113.9")),
    }
    cs = summarise_cert(cert, chain_verified=True)
    assert cs["subject_cn"] == "acme.example"
    assert cs["issuer"] == "Example CA / Example CA R3"
    assert cs["serial"] == "0A1B2C"
    assert cs["san"] == ["203.0.113.9", "acme.example", "vpn.acme.example", "www.acme.example"]
    assert cs["chain_verified"] is True
    assert summarise_cert({}, chain_verified=False)["san"] == []

    # -- ledger row: exact CONTRACT.md section 7 fields, in order ------------
    row = build_ledger_row(actor="main", action="monitor", source="monitor.py",
                           query="Q2: footprint diff", result="3 change(s)",
                           result_sha256="ab" * 32, mode="passive")
    assert tuple(row.keys()) == LEDGER_FIELDS
    assert tuple(row.keys()) == ("ts", "actor", "action", "source", "query",
                                 "result", "result_sha256", "mode")
    assert row["action"] == "monitor" and row["mode"] == "passive"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["ts"])
    assert list(json.loads(json.dumps(row)).keys()) == list(LEDGER_FIELDS)
    assert build_ledger_row(actor="main", action="collect", source="monitor.py", query="q",
                            result="r", result_sha256=None, mode="active")["result_sha256"] is None
    try:
        build_ledger_row(actor="main", action="monitor", source="s", query="q",
                         result="r", result_sha256=None, mode="stealth")
    except MonitorError:
        pass
    else:
        raise AssertionError("build_ledger_row accepted a mode outside CONTRACT.md section 9")

    # -- entity row: exact CONTRACT.md section 7 fields, in order ------------
    ent = build_entity(eid="e-7", type_="subdomain", value="vpn.acme.example",
                       first_seen="2026-07-28T14:55:01Z", grade="A3",
                       sources=["2026-07-28T14:55:02Z"], notes="n")
    assert tuple(ent.keys()) == ENTITY_FIELDS
    assert tuple(ent.keys()) == ("id", "type", "value", "first_seen", "grade",
                                 "sources", "candidate_group", "notes")
    assert ent["candidate_group"] is None
    for bad in (dict(type_="hostname"), dict(grade="A9"), dict(sources=[])):
        kw = dict(eid="e-8", type_="subdomain", value="a.b", first_seen="x",
                  grade="A3", sources=["s"], notes="n")
        kw.update(bad)
        try:
            build_entity(**kw)
        except MonitorError:
            pass
        else:
            raise AssertionError(f"build_entity accepted {bad}")

    # -- snapshot round-trips through JSON unchanged -------------------------
    snap = _snap("2026-07-28T14:55:01Z",
                 dns=_dns({"A": ["203.0.113.8"], "MX": ["10 mail.acme.example."],
                           "TXT": ["v=spf1 -all"]}),
                 tls={"collected": True, "mode": "active", "port": 443, **cs},
                 http={"collected": True, "mode": "active", "url": "https://acme.example/",
                       "status": 200, "final_url": "https://acme.example/",
                       "headers": {"server": "nginx", "content-type": "text/html"},
                       "body_sha256": sha256_bytes(b"page"), "body_length": 4, "error": None},
                 entities={"collected": True, "mode": "passive", "count": 1,
                           "values": ["domain:acme.example"]})
    text = json.dumps(snap, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(text) == snap, "snapshot did not round-trip through JSON"
    assert json.loads(json.dumps(json.loads(text))) == snap, "second round-trip drifted"
    assert list(json.loads(text)["signals"]) == list(snap["signals"]), "signal order drifted"
    assert snapshot_mode(snap) == "active"
    assert snapshot_mode(_snap("t", entities={"collected": True, "mode": "passive",
                                              "count": 0, "values": []})) == "passive"
    assert snapshot_mode(_snap("t", dns={"collected": False, "mode": "active",
                                         "skipped": "requires --active"})) == "passive"

    # -- diff: no change -----------------------------------------------------
    same = json.loads(json.dumps(snap))
    same["ts"] = "2026-08-04T14:55:01Z"
    changes, skipped = diff_snapshots(snap, same)
    assert changes == [], changes
    assert skipped == []
    assert summarise_changes(changes) == "no change"

    # -- diff: added, removed, changed ---------------------------------------
    later = json.loads(json.dumps(snap))
    later["ts"] = "2026-08-04T14:55:01Z"
    later["signals"]["dns"] = _dns({
        "A": ["203.0.113.8", "203.0.113.44"],          # added an address
        "MX": ["10 mx.mailvendor.example."],           # changed provider (add + remove)
        # TXT removed entirely
    })
    # + api.acme.example, - www.acme.example and the IP SAN
    later["signals"]["tls"]["san"] = ["acme.example", "api.acme.example", "vpn.acme.example"]
    later["signals"]["tls"]["not_after"] = "Nov 30 23:59:59 2026 GMT"
    later["signals"]["http"]["status"] = 301
    later["signals"]["http"]["headers"] = {"server": "cloudflare",
                                           "location": "https://www.acme.example/"}
    later["signals"]["entities"]["values"] = ["domain:acme.example", "ip:203.0.113.44"]
    later["signals"]["entities"]["count"] = 2
    changes, skipped = diff_snapshots(snap, later)
    assert skipped == []
    kinds = {c.kind for c in changes}
    assert kinds == {"added", "removed", "changed"}, kinds

    def has(signal, kind, key, old=None, new=None):
        return any(c.signal == signal and c.kind == kind and c.key == key
                   and (old is None or c.old == old) and (new is None or c.new == new)
                   for c in changes)

    assert has("dns", "added", "A", new="203.0.113.44")
    assert has("dns", "added", "ip", new="203.0.113.44")
    assert has("dns", "added", "MX", new="10 mx.mailvendor.example.")
    assert has("dns", "removed", "MX", old="10 mail.acme.example.")
    assert has("dns", "removed", "TXT", old="v=spf1 -all")
    assert not has("dns", "removed", "A")
    assert has("tls", "added", "san", new="api.acme.example")
    assert has("tls", "removed", "san", old="www.acme.example")
    assert has("tls", "removed", "san", old="203.0.113.9")
    assert has("tls", "changed", "not_after")
    assert not has("tls", "changed", "serial")
    assert has("http", "changed", "status")
    assert has("http", "changed", "header:server")
    assert has("http", "added", "header:location")
    assert has("http", "removed", "header:content-type")
    assert has("entities", "added", "entity", new="ip:203.0.113.44")
    s = summarise_changes(changes)
    assert s.startswith(f"{len(changes)} change(s)") and "dns" in s and "added" in s

    # Reversing the pair turns every addition into a removal and back.
    back, _ = diff_snapshots(later, snap)
    assert sum(1 for c in back if c.kind == "added") == sum(1 for c in changes if c.kind == "removed")
    assert sum(1 for c in back if c.kind == "removed") == sum(1 for c in changes if c.kind == "added")

    # -- diff: a signal collected in only one snapshot is SKIPPED, not removed
    partial = json.loads(json.dumps(snap))
    partial["ts"] = "2026-08-11T14:55:01Z"
    partial["signals"]["dns"] = {"collected": False, "mode": "active",
                                 "skipped": "requires --active"}
    changes2, skipped2 = diff_snapshots(snap, partial)
    assert [sk.signal for sk in skipped2] == ["dns"], skipped2
    assert skipped2[0].reason == "requires --active"
    assert not any(c.signal == "dns" for c in changes2), \
        "an uncollected signal was reported as a removal"
    assert changes2 == []
    # Same when the signal key is missing from one side entirely.
    absent = json.loads(json.dumps(snap))
    del absent["signals"]["tls"]
    _c3, skipped3 = diff_snapshots(snap, absent)
    assert ("tls", "present in only one snapshot") in [(s_.signal, s_.reason) for s_ in skipped3]

    # -- first run with no baseline -----------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "acme-2026-07"
        (case / "monitor").mkdir(parents=True)
        assert load_snapshots(case) == []
        assert resolve_pair(case, None, None, None) is None, "no snapshots must not raise"
        p1, d1 = write_snapshot(case, snap, when)
        assert p1.name == "20260728T145501Z.json"
        assert d1 == sha256_bytes(p1.read_bytes())
        assert len(load_snapshots(case)) == 1
        assert resolve_pair(case, None, None, None) is None, \
            "one snapshot is a baseline, not a diff"
        # A second write in the same second must not clobber the first.
        p2, _ = write_snapshot(case, later, when)
        assert p2.name == "20260728T145501Z-1.json" and p1.exists()
        # Snapshots read back byte-identical to what was built.
        assert json.loads(p1.read_text(encoding="utf-8")) == snap
        pair = resolve_pair(case, None, None, None)
        assert pair is not None and pair[0].name == p1.name and pair[2].name == p2.name
        # Target filtering.
        assert len(load_snapshots(case, "acme.example")) == 2
        assert load_snapshots(case, "other.example") == []
        # A named pair that does not exist is an error, not a silent fallback.
        try:
            resolve_pair(case, None, "nope.json", p2.name)
        except MonitorError:
            pass
        else:
            raise AssertionError("resolve_pair accepted a missing snapshot name")

        # -- ledger and entity appends are append-only ----------------------
        led = case / "ledger.jsonl"
        append_jsonl(led, [row])
        append_jsonl(led, [build_ledger_row(actor="main", action="collect",
                                            source="monitor.py", query="q", result="r",
                                            result_sha256=None, mode="active")])
        lines = led.read_text("utf-8").splitlines()
        assert len(lines) == 2
        assert list(json.loads(lines[0])) == list(LEDGER_FIELDS)
        assert json.loads(lines[0])["mode"] == "passive"
        assert json.loads(lines[1])["mode"] == "active"
        append_jsonl(led, [row])
        assert led.read_text("utf-8").splitlines()[:2] == lines
        ents = case / "entities.jsonl"
        append_jsonl(ents, [ent])
        assert list(json.loads(ents.read_text("utf-8").splitlines()[0])) == list(ENTITY_FIELDS)
        append_jsonl(ents, [])  # empty append writes nothing and does not create noise
        assert len(ents.read_text("utf-8").splitlines()) == 1

    # -- entity id allocation and dedupe -------------------------------------
    existing = [{"id": "e-1", "type": "domain", "value": "acme.example"},
                {"id": "e-4", "type": "ip", "value": "203.0.113.8"},
                {"id": "e-2", "type": "domain", "value": "acme.example"}]
    assert next_entity_id(existing) == 5
    assert next_entity_id([]) == 1
    assert next_entity_id([{"id": "bogus"}]) == 1
    idx = entity_index(existing)
    assert ("ip", norm("203.0.113.8", "ip")) in idx
    assert ("subdomain", norm("vpn.acme.example", "subdomain")) not in idx

    # -- selectors minted from a diff ----------------------------------------
    minted = selectors_from(changes)
    got = {(t, v): g for t, v, g, _w, _p in minted}
    assert ("ip", "203.0.113.44") in got and got[("ip", "203.0.113.44")] == "B3"
    assert ("subdomain", "api.acme.example") in got
    assert got[("subdomain", "api.acme.example")] == "A3"
    assert ("subdomain", "mx.mailvendor.example") in got
    assert got[("subdomain", "mx.mailvendor.example")] == "B3"
    # Removals never mint. TXT rdata never mints. Nothing is minted twice.
    assert not any(v == "v=spf1 -all" for _t, v, _g, _w, _p in minted)
    assert not any(v == "www.acme.example" for _t, v, _g, _w, _p in minted)
    assert len({(t, v) for t, v, _g, _w, _p in minted}) == len(minted)
    for t, _v, g, _w, _p in minted:
        assert t in SELECTOR_TYPES and g in GRADES
    assert selectors_from([]) == []

    # -- grading: one authoritative source ALONE is 3, never 1 ---------------
    # 41-confidence.md: the single-source A1 exemption is CERTIFICATE TRANSPARENCY,
    # and this script reads a served leaf certificate, which is not a CT log entry.
    for signal, key in (("tls", "san"), ("dns", "A"), ("dns", "MX"), ("http", "status")):
        grade, why = grade_for(signal, key)
        assert grade in GRADES and why
        assert not grade.endswith("1"), f"{signal}/{key} graded {grade}: single source is not 1"
    assert grade_for("tls", "san")[0] == "A3"
    assert grade_for("dns", "A")[0] == "B3"
    assert grade_for("http", "status")[0] == "F6"
    assert "certificate-transparency" in grade_for("tls", "san")[1].lower()

    # -- hostname typing and IP detection ------------------------------------
    assert host_type("vpn.acme.example") == "subdomain"
    assert host_type("acme.example") == "domain"
    assert host_type("") == "domain"
    assert _looks_like_ip("203.0.113.9")
    assert _looks_like_ip("2001:db8::1")
    assert not _looks_like_ip("vpn.acme.example")
    assert not _looks_like_ip("")

    # -- plain-language rendering -------------------------------------------
    assert plain(Change("dns", "added", "A", "", "203.0.113.44")) == \
        "new IPv4 address: 203.0.113.44"
    assert plain(Change("tls", "removed", "san", "old.acme.example", "")) == \
        "certificate subjectAltName gone: old.acme.example"
    assert plain(Change("http", "changed", "status", "200", "301")) == \
        "HTTP status changed: 200 -> 301"
    assert "response header server" in plain(Change("http", "changed", "header:server", "a", "b"))
    quiet = render_diff(Path("a.json"), Path("b.json"), [], [], [], False)
    assert "PASS" in quiet and "error" not in quiet.lower()
    loud = render_diff(Path("a.json"), Path("b.json"), changes, [], [ent], True)
    assert "change(s)" in loud and "[dns]" in loud and "e-7" in loud
    assert "action monitor, mode passive" in loud
    noisy = render_diff(Path("a.json"), Path("b.json"), [], skipped2, [], False)
    assert "not compared" in noisy and "PASS" in noisy

    # -- the default UA is descriptive, not a browser impersonation ----------
    assert "monitor" in DEFAULT_USER_AGENT.lower()
    assert "Mozilla" not in DEFAULT_USER_AGENT

    # -- parser wiring -------------------------------------------------------
    pr = build_parser()
    a = pr.parse_args(["snapshot", "--case", "c", "--target", "acme.example"])
    assert a.cmd == "snapshot" and a.active is False and a.signals == SIGNALS
    assert a.resolver in DOH_ENDPOINTS
    a = pr.parse_args(["snapshot", "--case", "c", "--target", "t",
                       "--active", "--signals", "dns,tls"])
    assert a.active is True and a.signals == ("dns", "tls")
    a = pr.parse_args(["diff", "--case", "c"])
    assert a.cmd == "diff" and a.dry_run is False and a.exit_changed is False
    assert pr.parse_args(["--selfcheck"]).selfcheck is True
    try:
        _signal_list("dns,bogus")
    except argparse.ArgumentTypeError:
        pass
    else:
        raise AssertionError("_signal_list accepted an unknown signal")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
