#!/usr/bin/env python3
"""Archive a URL into a case's evidence directory and record its provenance.

Phase 1, standard library only (CONTRACT.md section 10). Windows-safe: pathlib
throughout, no hardcoded separators, no network calls at import time.

    python archive.py --case ./cases/acme-2026-07 https://example.com/filing.pdf
    python archive.py --case ./cases/acme-2026-07 --wayback --timeout 60 <url>
    python archive.py --selfcheck

What it does, in this order:

  1. Refuses any scheme that is not http or https.
  2. Fetches the URL with urllib, following at most --max-redirects hops and
     refusing to follow a redirect that leaves http(s).
  3. Reads at most --max-bytes. Exceeding the cap ABORTS; a truncated file is
     never stored, because its sha256 would not match the real resource and
     would be worse than no evidence at all.
  4. Writes the exact bytes to evidence/<sha256>.<ext>, re-reads them and
     re-hashes to confirm what landed on disk is what was fetched.
  5. Appends ONE ledger row with the CONTRACT.md section 7 fields, in order:
     action "archive", the URL as source, result_sha256 set, mode passive.
  6. Writes evidence/<sha256>.meta.json holding the full provenance record --
     HTTP status, redirect chain, final URL, content-type, byte length and the
     UTC retrieval timestamp. The section 7 ledger schema is fixed and cannot
     carry a redirect chain, so the structured record lives beside the bytes.
     This sidecar is an addition to the PLAN.md section 3 case layout.

Wayback (--wayback, off by default):
  Save Page Now lives at https://web.archive.org/save/<url> and is requested
  only when --wayback is passed. It is off by default and gets its OWN ledger
  row with mode=active, because it makes the Internet Archive fetch the target:
  the target sees an archive.org crawler hit that it did not see before.
  CONTRACT.md section 9 requires a fresh confirmation for that, and passing the
  flag is it. No SPN job-status or authenticated API shape is used or invented.
  Whether or not SPN is attempted, the standard Wayback lookup URL
  https://web.archive.org/web/*/<url> is recorded in the sidecar; a snapshot
  URL is only recorded as confirmed if the SPN response actually redirected to
  a /web/<timestamp>/ capture path.

Identical bytes are never rewritten: the filename is the hash, so a file that
already exists is already this evidence. The ledger row is still appended --
that you retrieved it again at a new timestamp is itself a fact.

Exit codes: 0 ok; 1 refused scheme, fetch failure, redirect cap exceeded, size
cap exceeded, corrupt evidence store, or an unwritable case dir; 2 argparse
usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit

# CONTRACT.md section 7, exact names and order. Nothing else goes in a ledger row.
LEDGER_FIELDS = (
    "ts",
    "actor",
    "action",
    "source",
    "query",
    "result",
    "result_sha256",
    "mode",
)

ALLOWED_SCHEMES = ("http", "https")

DEFAULT_USER_AGENT = (
    "osint-plugin-archive/1.0 (evidence preservation; stdlib urllib; "
    "contact: see case scope)"
)

DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_REDIRECTS = 5
_CHUNK = 64 * 1024

WAYBACK_SAVE = "https://web.archive.org/save/"
# The calendar/lookup form for every capture of a URL. Recorded, not fetched.
WAYBACK_LOOKUP = "https://web.archive.org/web/*/"
RE_WAYBACK_SNAPSHOT = re.compile(r"^https?://web\.archive\.org/web/(\d{4,14})/", re.I)

# Explicit first so the mapping is deterministic and assertable; mimetypes
# varies by platform and by the Windows registry, and .htm vs .html should not
# depend on which machine ran the collection.
CONTENT_TYPE_EXT = {
    "text/html": ".html",
    "application/xhtml+xml": ".xhtml",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/xml": ".xml",
    "application/xml": ".xml",
    "application/json": ".json",
    "application/ld+json": ".json",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/gzip": ".gz",
    "application/rtf": ".rtf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/octet-stream": ".bin",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/tiff": ".tif",
    "image/svg+xml": ".svg",
    "image/heic": ".heic",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
}

# Suffixes trusted when the server gives no usable content-type.
SAFE_URL_SUFFIXES = frozenset(CONTENT_TYPE_EXT.values()) | {".htm", ".jpeg", ".yaml", ".yml", ".md", ".log"}


class ArchiveError(Exception):
    """Anything that should stop the archive and exit non-zero."""


class SizeCapExceeded(ArchiveError):
    def __init__(self, cap: int):
        super().__init__(
            f"response exceeds --max-bytes ({cap}); nothing was stored, because a "
            f"truncated file hashes differently from the real resource and would be "
            f"misleading evidence. Re-run with a higher --max-bytes if the size is expected."
        )
        self.cap = cap


class RedirectCapExceeded(ArchiveError):
    pass


# ---------------------------------------------------------------------------
# Primitives (all network-free, all directly asserted in demo())
# ---------------------------------------------------------------------------

def utc_now() -> str:
    """UTC ISO8601 with a literal Z, second precision. Matches case_init.py."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_scheme(url: str) -> str:
    """Return the lowercased scheme, or raise. file:, ftp:, data:, javascript: all refused.

    urllib's default redirect handler permits ftp as a redirect target; this
    gate is applied to the initial URL and again to every redirect hop.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ArchiveError(
            f"refusing scheme {scheme or '(none)'!r}: only "
            f"{' and '.join(ALLOWED_SCHEMES)} are archived"
        )
    if not parts.netloc:
        raise ArchiveError(f"no host in URL {url!r}")
    return scheme


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ext_for(content_type: str | None, url: str = "") -> str:
    """Derive a file extension: content-type first, then the URL path, then .bin.

    The content-type header may carry parameters (charset, boundary); only the
    media type is consulted, lowercased and whitespace-stripped.
    """
    if content_type:
        media = content_type.split(";", 1)[0].strip().lower()
        if media in CONTENT_TYPE_EXT:
            return CONTENT_TYPE_EXT[media]
        if media:
            guessed = mimetypes.guess_extension(media)
            if guessed:
                return ".jpg" if guessed == ".jpe" else guessed
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in SAFE_URL_SUFFIXES:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".bin"


def read_capped(fp, max_bytes: int) -> bytes:
    """Read at most max_bytes. Exactly max_bytes is fine; one more raises.

    Never returns a truncated body -- callers must not be able to mistake a
    partial download for the whole resource.
    """
    if max_bytes < 1:
        raise ArchiveError("--max-bytes must be at least 1")
    chunks: list[bytes] = []
    total = 0
    while True:
        want = min(_CHUNK, max_bytes - total + 1)
        chunk = fp.read(want)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise SizeCapExceeded(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


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
        raise ArchiveError(f"mode must be passive or active, got {mode!r}")
    row = {
        "ts": ts or utc_now(),
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


def append_ledger(case_dir: Path, row: dict) -> None:
    """Append one JSON object and a newline. Never rewrites (CONTRACT.md section 10)."""
    path = case_dir / "ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def store_evidence(case_dir: Path, data: bytes, ext: str) -> tuple[Path, str, bool]:
    """Write bytes to evidence/<sha256><ext>. Returns (path, sha256, already_present).

    Identical bytes are never rewritten -- the filename IS the hash, so a file
    that is already there is already this evidence. If a file with that name
    exists but does not hash to its own name, the store is corrupt and that is
    an error, not something to paper over.
    """
    digest = sha256_bytes(data)
    evidence = case_dir / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / f"{digest}{ext}"
    if path.exists():
        existing = path.read_bytes()
        if sha256_bytes(existing) != digest:
            raise ArchiveError(
                f"evidence store corrupt: {path} does not hash to its own filename"
            )
        return path, digest, True
    path.write_bytes(data)
    # Re-read and re-hash: a short write or a disk fault must not silently
    # produce evidence whose recorded hash does not match its own bytes.
    if sha256_bytes(path.read_bytes()) != digest:
        raise ArchiveError(f"wrote {path} but it does not read back to sha256 {digest}")
    return path, digest, False


def wayback_lookup_url(url: str) -> str:
    """The standard Wayback calendar URL for every capture of `url`. Not fetched."""
    return WAYBACK_LOOKUP + url


def wayback_save_url(url: str) -> str:
    """Save Page Now. The path is /save/<url> with the target URL appended raw."""
    return WAYBACK_SAVE + url


def snapshot_from(final_url: str) -> str | None:
    """A confirmed capture URL, or None if the response did not land on one."""
    return final_url if RE_WAYBACK_SNAPSHOT.match(final_url or "") else None


def summarise(meta: dict) -> str:
    """One-line human summary for the ledger `result` field."""
    bits = [
        f"HTTP {meta['http_status']}",
        f"{meta['byte_length']} bytes",
        meta.get("content_type") or "no content-type",
    ]
    if meta["redirects"]:
        bits.append(f"{len(meta['redirects'])} redirect(s) -> {meta['final_url']}")
    if meta.get("evidence_already_present"):
        bits.append("bytes already archived under this hash")
    return "; ".join(bits)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class BoundedRedirectHandler(request.HTTPRedirectHandler):
    """Cap the redirect chain, record it, and refuse to leave http(s).

    A redirect chain that ends somewhere unexpected is exactly what an
    investigator needs to see, so every hop is kept rather than collapsed.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self.chain: list[dict] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append({"status": code, "location": newurl})
        if len(self.chain) > self.limit:
            raise error.HTTPError(
                req.full_url, code,
                f"redirect limit {self.limit} exceeded after {len(self.chain)} hops",
                headers, fp,
            )
        try:
            check_scheme(newurl)
        except ArchiveError as exc:
            raise error.HTTPError(req.full_url, code, str(exc), headers, fp) from None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def harvest(resp, requested_url: str, redirects: list[dict], data: bytes) -> dict:
    """Build the provenance record from a response-like object.

    Deliberately takes any object exposing .status/.geturl()/.headers so the
    selfcheck can drive it with a fake response and never touch the network.
    """
    headers = getattr(resp, "headers", None)
    get = headers.get if headers is not None else (lambda *_a, **_k: None)
    final_url = resp.geturl() if hasattr(resp, "geturl") else requested_url
    return {
        "requested_url": requested_url,
        "final_url": final_url,
        "http_status": getattr(resp, "status", None) or getattr(resp, "code", None),
        "content_type": get("Content-Type"),
        "content_length_header": get("Content-Length"),
        "last_modified": get("Last-Modified"),
        "etag": get("ETag"),
        "server": get("Server"),
        "byte_length": len(data),
        "redirects": redirects,
        "redirect_count": len(redirects),
        "retrieved_utc": utc_now(),
    }


def fetch(url: str, *, timeout: float, max_bytes: int, max_redirects: int,
          user_agent: str) -> tuple[bytes, dict]:
    """GET `url`, returning (bytes, provenance dict). Raises ArchiveError."""
    check_scheme(url)
    handler = BoundedRedirectHandler(max_redirects)
    opener = request.build_opener(handler)
    req = request.Request(url, headers={
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Accept-Encoding": "identity",  # store what the server serves, unmodified
    })
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = read_capped(resp, max_bytes)
            meta = harvest(resp, url, handler.chain, data)
    except error.HTTPError as exc:
        reason = str(exc.reason or "")
        if "redirect limit" in reason:
            raise RedirectCapExceeded(
                f"{reason}; chain: "
                + " -> ".join(f"{h['status']} {h['location']}" for h in handler.chain)
            ) from None
        # Two gates can refuse a redirect target. urllib's own check rejects
        # anything outside http/https/ftp; BoundedRedirectHandler then rejects
        # ftp, which urllib would otherwise have followed. Report both as what
        # they are -- a refused scheme, not an ordinary HTTP error.
        if "refusing scheme" in reason or "is not allowed" in reason:
            raise ArchiveError(
                f"refused a redirect while fetching {url}: {reason}"
            ) from None
        raise ArchiveError(f"HTTP {exc.code} fetching {url}: {reason}") from None
    except error.URLError as exc:
        raise ArchiveError(f"could not fetch {url}: {exc.reason}") from None
    except (TimeoutError, OSError) as exc:
        raise ArchiveError(f"could not fetch {url}: {exc}") from None
    return data, meta


def request_wayback(url: str, *, timeout: float, max_redirects: int,
                    user_agent: str) -> dict:
    """Ask Save Page Now to capture `url`. Never raises: SPN failing must not
    invalidate a local archive that already succeeded."""
    save = wayback_save_url(url)
    out = {
        "attempted": True,
        "save_url": save,
        "lookup_url": wayback_lookup_url(url),
        "snapshot_url": None,
        "snapshot_confirmed": False,
        "http_status": None,
        "final_url": None,
        "error": None,
        "requested_utc": utc_now(),
    }
    handler = BoundedRedirectHandler(max_redirects)
    opener = request.build_opener(handler)
    req = request.Request(save, headers={"User-Agent": user_agent, "Accept": "*/*"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            out["http_status"] = getattr(resp, "status", None)
            out["final_url"] = resp.geturl()
            resp.read(_CHUNK)  # drain a little; the body is an HTML status page
    except error.HTTPError as exc:
        out["http_status"] = exc.code
        out["final_url"] = getattr(exc, "url", None)
        out["error"] = f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - SPN must never break the archive
        out["error"] = str(exc)
    snap = snapshot_from(out["final_url"] or "")
    if snap:
        out["snapshot_url"] = snap
        out["snapshot_confirmed"] = True
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def archive_url(url: str, case_dir: Path, *, actor: str, query: str | None,
                mode: str, timeout: float, max_bytes: int, max_redirects: int,
                user_agent: str, do_wayback: bool) -> dict:
    """Fetch, store, ledger, and optionally submit to Wayback. Returns the sidecar dict."""
    if not case_dir.is_dir():
        raise ArchiveError(f"case directory does not exist: {case_dir}")

    data, meta = fetch(url, timeout=timeout, max_bytes=max_bytes,
                       max_redirects=max_redirects, user_agent=user_agent)
    ext = ext_for(meta.get("content_type"), meta.get("final_url") or url)
    path, digest, already = store_evidence(case_dir, data, ext)

    meta["sha256"] = digest
    meta["evidence_file"] = path.name
    meta["evidence_already_present"] = already
    meta["user_agent"] = user_agent
    meta["mode"] = mode
    meta["wayback"] = {
        "attempted": False,
        "lookup_url": wayback_lookup_url(url),
        "snapshot_url": None,
        "snapshot_confirmed": False,
        "note": "Save Page Now not requested; the lookup URL above is recorded "
                "unconfirmed and may have no capture behind it.",
    }

    # The local archive is the load-bearing part: ledger it before touching the
    # network again, so a slow or rate-limited SPN cannot cost us the record.
    append_ledger(case_dir, build_ledger_row(
        actor=actor,
        action="archive",
        source=url,
        query=query or url,
        result=summarise(meta),
        result_sha256=digest,
        mode=mode,
    ))

    if do_wayback:
        wb = request_wayback(url, timeout=timeout, max_redirects=max_redirects,
                             user_agent=user_agent)
        wb["note"] = (
            "snapshot URL confirmed from the Save Page Now redirect target"
            if wb["snapshot_confirmed"] else
            "no capture URL was confirmed; the lookup URL is recorded unconfirmed "
            "and must be opened by hand before it is cited"
        )
        meta["wayback"] = wb
        append_ledger(case_dir, build_ledger_row(
            actor=actor,
            action="archive",
            source="Wayback Machine Save Page Now",
            query=wb["save_url"],
            result=(
                f"HTTP {wb['http_status']}; "
                + (f"snapshot {wb['snapshot_url']}" if wb["snapshot_confirmed"]
                   else f"snapshot unconfirmed, lookup {wb['lookup_url']}")
                + (f"; error: {wb['error']}" if wb["error"] else "")
            ),
            result_sha256=None,
            # ACTIVE: this makes archive.org fetch the target, and the target
            # sees a crawler hit it would not otherwise have seen.
            mode="active",
        ))

    sidecar = path.with_suffix(path.suffix + ".meta.json")
    sidecar.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8", newline="\n")
    meta["sidecar_file"] = sidecar.name
    return meta


def render(meta: dict, case_dir: Path) -> str:
    lines = [
        f"archived      {meta['requested_url']}",
        f"status        HTTP {meta['http_status']}",
    ]
    if meta["redirects"]:
        lines.append(f"redirects     {meta['redirect_count']}")
        for hop in meta["redirects"]:
            lines.append(f"              {hop['status']} -> {hop['location']}")
        lines.append(f"final url     {meta['final_url']}")
        if urlsplit(meta["final_url"]).netloc.lower() != urlsplit(meta["requested_url"]).netloc.lower():
            lines.append("              NOTE: the chain left the requested host; "
                         "confirm this is the document you meant to archive")
    else:
        lines.append("redirects     none")
    lines += [
        f"content-type  {meta.get('content_type') or 'not sent'}",
        f"bytes         {meta['byte_length']}",
        f"retrieved     {meta['retrieved_utc']}",
        f"sha256        {meta['sha256']}",
        f"evidence      {case_dir / 'evidence' / meta['evidence_file']}"
        + ("  (identical bytes were already archived; not rewritten)"
           if meta["evidence_already_present"] else ""),
        f"provenance    {meta.get('sidecar_file', '')}",
        f"mode          {meta['mode']}",
    ]
    wb = meta["wayback"]
    if wb["attempted"]:
        lines.append(f"wayback       HTTP {wb['http_status']} at {wb['save_url']}")
        if wb["snapshot_confirmed"]:
            lines.append(f"              snapshot {wb['snapshot_url']}")
        else:
            lines.append(f"              snapshot UNCONFIRMED; lookup {wb['lookup_url']}")
        if wb["error"]:
            lines.append(f"              error: {wb['error']}")
        lines.append("              recorded as a separate ledger row, mode=active")
    else:
        lines.append(f"wayback       not requested; lookup URL recorded unconfirmed: {wb['lookup_url']}")
    lines.append(f"ledger        {case_dir / 'ledger.jsonl'}  (1 row appended)"
                 if not wb["attempted"] else
                 f"ledger        {case_dir / 'ledger.jsonl'}  (2 rows appended)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="archive.py",
        description="Archive a URL into a case's evidence directory with full provenance.",
        epilog=(
            "Evidence is named by the sha256 of the exact bytes stored. Identical "
            "bytes are never rewritten. --wayback is off by default: Save Page Now "
            "makes archive.org fetch the target, which the target can see, so it is "
            "recorded as a separate active ledger row."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", nargs="?", help="http or https URL to archive")
    p.add_argument("--case", metavar="DIR", type=Path,
                   help="case directory containing ledger.jsonl and evidence/")
    p.add_argument("--actor", default="main",
                   help="ledger actor: main, or an agent name (default: main)")
    p.add_argument("--query", metavar="TEXT",
                   help="what was being asked; defaults to the URL")
    p.add_argument("--mode", choices=("passive", "active"), default="passive",
                   help="ledger mode for the fetch (default: passive). Set active when "
                        "the URL is on target-controlled infrastructure - the request "
                        "comes from your IP and lands in the target's access log")
    p.add_argument("--wayback", action="store_true",
                   help="also request a Save Page Now capture. ACTIVE: archive.org "
                        "will fetch the target. Logged as its own ledger row")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                   metavar="SEC", help=f"socket timeout (default: {DEFAULT_TIMEOUT:g})")
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, metavar="N",
                   help=f"abort if the body exceeds N bytes (default: {DEFAULT_MAX_BYTES})")
    p.add_argument("--max-redirects", type=int, default=DEFAULT_MAX_REDIRECTS,
                   metavar="N", help=f"redirect hop cap (default: {DEFAULT_MAX_REDIRECTS})")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                   help="User-Agent header sent with every request")
    p.add_argument("--json", action="store_true", help="print the provenance record as JSON")
    p.add_argument("--selfcheck", action="store_true",
                   help="run assert-based checks and exit; makes no network calls")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selfcheck:
        demo()
        print("archive.py selfcheck: all assertions passed (no network calls made)")
        return 0

    if not args.url or not args.case:
        build_parser().print_help()
        print("\nerror: both a URL and --case are required", file=sys.stderr)
        return 2

    try:
        meta = archive_url(
            args.url, args.case,
            actor=args.actor, query=args.query, mode=args.mode,
            timeout=args.timeout, max_bytes=args.max_bytes,
            max_redirects=args.max_redirects, user_agent=args.user_agent,
            do_wayback=args.wayback,
        )
    except ArchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(meta, indent=2, ensure_ascii=False) if args.json
          else render(meta, args.case))
    return 0


# ---------------------------------------------------------------------------
# demo / selfcheck -- no network, local fixtures and a fake response only
# ---------------------------------------------------------------------------

class _FakeHeaders(dict):
    """email.message.Message-alike: case-insensitive .get()."""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class _FakeResponse:
    """Stands in for http.client.HTTPResponse. Never opens a socket."""

    def __init__(self, body: bytes, status: int = 200, url: str = "https://example.com/x",
                 headers: dict | None = None):
        self._body = body
        self._pos = 0
        self.status = status
        self._url = url
        self.headers = _FakeHeaders(headers or {})

    def geturl(self) -> str:
        return self._url

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = len(self._body) - self._pos
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def demo() -> None:
    """Assert-based checks of the non-trivial logic. Makes no network calls."""
    import tempfile

    # -- scheme refusal ------------------------------------------------------
    assert check_scheme("https://example.com/a") == "https"
    assert check_scheme("HTTP://Example.com/a") == "http"
    for bad in ("file:///C:/Windows/win.ini", "ftp://example.com/x",
                "data:text/html,<b>x", "javascript:alert(1)", "gopher://example.com",
                "//example.com/x", "example.com/x"):
        try:
            check_scheme(bad)
        except ArchiveError:
            pass
        else:
            raise AssertionError(f"check_scheme accepted {bad!r}")
    # A URL with a scheme but no host is refused too.
    try:
        check_scheme("https:///nohost")
    except ArchiveError:
        pass
    else:
        raise AssertionError("check_scheme accepted a hostless URL")

    # -- hashing -------------------------------------------------------------
    # Known sha256 of the empty string and of b"abc".
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    body = b"<html><body>filing</body></html>"
    assert sha256_bytes(body) == hashlib.sha256(body).hexdigest()

    # -- extension derivation from content-type ------------------------------
    assert ext_for("text/html") == ".html"
    assert ext_for("text/html; charset=UTF-8") == ".html"
    assert ext_for("  TEXT/HTML ;charset=utf-8") == ".html"
    assert ext_for("application/pdf") == ".pdf"
    assert ext_for("image/jpeg") == ".jpg"
    assert ext_for("image/png") == ".png"
    assert ext_for("application/json") == ".json"
    assert ext_for("application/octet-stream") == ".bin"
    assert ext_for(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == ".xlsx"
    # No content-type: fall back to the URL path suffix.
    assert ext_for(None, "https://example.com/a/report.pdf") == ".pdf"
    assert ext_for("", "https://example.com/a/photo.JPEG") == ".jpg"
    assert ext_for(None, "https://example.com/a/index.htm") == ".htm"
    # Neither usable, and a path suffix that is not a file type.
    assert ext_for(None, "https://example.com/companies/12345678") == ".bin"
    assert ext_for(None, "https://example.com/") == ".bin"
    assert ext_for("application/x-not-a-real-type-xyzzy", "https://example.com/a") == ".bin"
    # A query string must not leak into the extension.
    assert ext_for(None, "https://example.com/f.pdf?download=1") == ".pdf"

    # -- max-bytes cap -------------------------------------------------------
    payload = b"x" * 1000
    assert read_capped(_FakeResponse(payload), 1000) == payload      # exactly at the cap is fine
    assert read_capped(_FakeResponse(payload), 5000) == payload      # under the cap is fine
    for cap in (1, 999):
        try:
            read_capped(_FakeResponse(payload), cap)
        except SizeCapExceeded as exc:
            assert exc.cap == cap
        else:
            raise AssertionError(f"read_capped returned truncated data at cap {cap}")
    # A cap breach must raise rather than return short data -- the whole point.
    big = _FakeResponse(b"y" * (_CHUNK * 3))
    try:
        read_capped(big, _CHUNK)
    except SizeCapExceeded:
        pass
    else:
        raise AssertionError("read_capped did not enforce the cap across chunk boundaries")
    try:
        read_capped(_FakeResponse(b"a"), 0)
    except ArchiveError:
        pass
    else:
        raise AssertionError("read_capped accepted a zero cap")

    # -- redirect cap logic --------------------------------------------------
    h = BoundedRedirectHandler(3)
    for i in range(3):
        h.chain.append({"status": 302, "location": f"https://example.com/{i}"})
    assert len(h.chain) == 3
    h.chain.append({"status": 302, "location": "https://example.com/4"})
    assert len(h.chain) > h.limit, "the cap comparison is len(chain) > limit"
    # The handler refuses to follow a redirect that leaves http(s).
    for hop in ("file:///etc/passwd", "ftp://example.com/x", "data:text/plain,x"):
        try:
            check_scheme(hop)
        except ArchiveError:
            pass
        else:
            raise AssertionError(f"a redirect to {hop!r} would have been followed")
    assert BoundedRedirectHandler(0).limit == 0
    assert BoundedRedirectHandler(5).chain == [], "chain must start empty per fetch"

    # -- ledger row field names and order ------------------------------------
    row = build_ledger_row(
        actor="main", action="archive", source="https://example.com/x",
        query="https://example.com/x", result="HTTP 200; 32 bytes; text/html",
        result_sha256=sha256_bytes(body), mode="passive",
    )
    assert tuple(row.keys()) == LEDGER_FIELDS, tuple(row.keys())
    assert tuple(row.keys()) == ("ts", "actor", "action", "source", "query",
                                 "result", "result_sha256", "mode")
    assert row["action"] == "archive"
    assert row["source"] == "https://example.com/x"
    assert row["mode"] == "passive"
    assert row["result_sha256"] == sha256_bytes(body)
    assert len(row["result_sha256"]) == 64
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["ts"]), row["ts"]
    # Round-trips through JSON with the order intact -- json.dumps preserves
    # insertion order, so a reader sees the CONTRACT.md section 7 layout.
    assert list(json.loads(json.dumps(row)).keys()) == list(LEDGER_FIELDS)
    # null is a legal result_sha256 (CONTRACT.md section 7: "hex or null").
    assert build_ledger_row(actor="main", action="archive", source="s", query="q",
                            result="r", result_sha256=None, mode="active")["result_sha256"] is None
    try:
        build_ledger_row(actor="main", action="archive", source="s", query="q",
                         result="r", result_sha256=None, mode="stealth")
    except ArchiveError:
        pass
    else:
        raise AssertionError("build_ledger_row accepted a mode outside CONTRACT.md section 9")

    # -- harvest from a fake response ---------------------------------------
    resp = _FakeResponse(
        body, status=200, url="https://example.com/final",
        headers={"Content-Type": "text/html; charset=utf-8", "Content-Length": "32",
                 "ETag": '"abc"', "Server": "nginx"},
    )
    data = read_capped(resp, 4096)
    assert data == body
    redirects = [{"status": 301, "location": "https://example.com/mid"},
                 {"status": 302, "location": "https://example.com/final"}]
    meta = harvest(resp, "https://example.com/start", redirects, data)
    assert meta["requested_url"] == "https://example.com/start"
    assert meta["final_url"] == "https://example.com/final"
    assert meta["http_status"] == 200
    assert meta["content_type"] == "text/html; charset=utf-8"
    assert meta["byte_length"] == len(body)
    assert meta["redirect_count"] == 2 and meta["redirects"] == redirects
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", meta["retrieved_utc"])
    # Header lookup is case-insensitive, like the real one.
    assert harvest(_FakeResponse(b"", headers={"content-type": "application/pdf"}),
                   "https://example.com/a", [], b"")["content_type"] == "application/pdf"
    # A response with no headers at all must not explode.
    assert harvest(_FakeResponse(b"z"), "https://example.com/a", [], b"z")["content_type"] is None

    # -- Wayback URL construction and confirmation ---------------------------
    target = "https://example.com/a?b=c"
    assert wayback_save_url(target) == "https://web.archive.org/save/" + target
    assert wayback_lookup_url(target) == "https://web.archive.org/web/*/" + target
    assert snapshot_from("https://web.archive.org/web/20260728120000/https://example.com/a") \
        == "https://web.archive.org/web/20260728120000/https://example.com/a"
    assert snapshot_from("https://web.archive.org/save/https://example.com/a") is None
    assert snapshot_from("https://web.archive.org/web/*/https://example.com/a") is None
    assert snapshot_from("") is None
    assert snapshot_from(None or "") is None

    # -- evidence store, on a real temp directory ----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "case"
        case.mkdir()
        path, digest, already = store_evidence(case, body, ".html")
        assert digest == sha256_bytes(body)
        assert path.name == f"{digest}.html"
        assert path.read_bytes() == body
        assert already is False
        # Same bytes again: never rewritten, and reported as already present.
        mtime = path.stat().st_mtime_ns
        path2, digest2, already2 = store_evidence(case, body, ".html")
        assert (path2, digest2, already2) == (path, digest, True)
        assert path.stat().st_mtime_ns == mtime, "identical bytes were rewritten"
        # Different bytes land in a different file; neither clobbers the other.
        other = b"<html><body>other</body></html>"
        path3, digest3, already3 = store_evidence(case, other, ".html")
        assert digest3 != digest and already3 is False
        assert path.read_bytes() == body and path3.read_bytes() == other
        # A file whose contents no longer hash to its name is a corrupt store.
        path.write_bytes(b"tampered")
        try:
            store_evidence(case, body, ".html")
        except ArchiveError as exc:
            assert "corrupt" in str(exc)
        else:
            raise AssertionError("store_evidence ignored a tampered evidence file")

        # -- ledger append is append-only -----------------------------------
        case2 = Path(tmp) / "case2"
        case2.mkdir()
        append_ledger(case2, row)
        append_ledger(case2, build_ledger_row(
            actor="main", action="archive", source="Wayback Machine Save Page Now",
            query=wayback_save_url("https://example.com/x"),
            result="HTTP 200; snapshot unconfirmed", result_sha256=None, mode="active"))
        lines = (case2 / "ledger.jsonl").read_text("utf-8").splitlines()
        assert len(lines) == 2, lines
        first, second = json.loads(lines[0]), json.loads(lines[1])
        assert list(first.keys()) == list(LEDGER_FIELDS)
        assert first["mode"] == "passive" and second["mode"] == "active"
        # Appending again must not disturb what is already there.
        append_ledger(case2, row)
        again = (case2 / "ledger.jsonl").read_text("utf-8").splitlines()
        assert again[:2] == lines and len(again) == 3

        # -- archive_url refuses a missing case dir and a bad scheme ---------
        for bad_call in (
            lambda: archive_url("https://example.com/x", Path(tmp) / "nope",
                                actor="main", query=None, mode="passive",
                                timeout=1, max_bytes=10, max_redirects=1,
                                user_agent="t", do_wayback=False),
            lambda: archive_url("file:///C:/Windows/win.ini", case2,
                                actor="main", query=None, mode="passive",
                                timeout=1, max_bytes=10, max_redirects=1,
                                user_agent="t", do_wayback=False),
        ):
            try:
                bad_call()
            except ArchiveError:
                pass
            else:
                raise AssertionError("archive_url did not refuse an invalid input")

    # -- summary line --------------------------------------------------------
    s = summarise({"http_status": 200, "byte_length": 32,
                   "content_type": "text/html", "redirects": redirects,
                   "final_url": "https://example.com/final",
                   "evidence_already_present": True})
    assert "HTTP 200" in s and "32 bytes" in s and "2 redirect(s)" in s and "already archived" in s
    assert "no content-type" in summarise(
        {"http_status": 204, "byte_length": 0, "content_type": None, "redirects": [],
         "final_url": "https://example.com/a"})

    # -- the default UA is descriptive, not a browser impersonation ----------
    assert "archive" in DEFAULT_USER_AGENT.lower()
    assert "Mozilla" not in DEFAULT_USER_AGENT


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
