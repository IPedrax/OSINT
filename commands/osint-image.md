---
description: Work a single image or video end to end — synthetic-media and provenance check first, then metadata, reverse image search and earliest instance, then place and time. Routes to /osint:osint-media and only then to /osint:osint-geoint, because geolocating a generated or misdated file produces a confident fabrication. Takes a local path or a URL. Use when the user says "check this photo", "is this image real", "is this AI-generated", "was this photoshopped", "reverse image search this", "where was this taken", "when was this taken", "geolocate this image", "verify this screenshot", "check this video", or drops an image into a case.
argument-hint: [path or URL | blank to be prompted]
---

# Single-image workflow

Two department skills in a fixed order. This command is the ordering and the hand-off; the method
lives in `/osint:osint-media` and `/osint:osint-geoint`, and neither is duplicated here.

`$1` is a local path or a URL. If it is blank, ask for one. If the user pasted an image into the
conversation with no file on disk, say so: bytes that never landed on disk cannot be hashed,
archived, or run through a local metadata tool, and every downstream step is weaker for it. Ask
them to save it first.

## 0. Preconditions

1. A case must be open — `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md`. None → run
   `/osint:osint-scope` and come back. Do not analyse first and scope afterwards.
2. Read `scope.md` for the numbered `question`, `target_category`, `out_of_bounds[]` and
   `active_allowed`. The gate ran at intake; do not re-ask it.
3. Name the `Q<n>` this image is meant to advance before touching it. No question id, no run.

## 1. Custody, before anything else

| Input | What it is | Mode |
|---|---|---|
| Local path | Bytes already held. Hash and store, no fetch. | `passive` |
| URL on a third-party host | A fetch that lands in that host's logs. | `passive` unless the target controls the host |
| URL on target-controlled infrastructure | A fetch the target can see. | `active` — needs `active_allowed: true` plus a fresh confirmation naming the URL |

Prefer a copy already held by an archive over a fetch from the live page. Store as
`cases/<slug>/evidence/<sha256>.<ext>`, archive the carrying page as a separate artifact, and
append the `ledger.jsonl` row. `${CLAUDE_PLUGIN_ROOT}/scripts/archive.py` does the fetch, hash,
store and ledger row in one call — run it with `--help` first.

Work on the highest-resolution copy obtainable. A screenshot of a screenshot cannot carry a
forensic claim; if that is all there is, say so now rather than after eight steps.

## 2. Route to `/osint:osint-media` — always first, no exceptions

Run its play in its own order: custody → local metadata → Content Credentials → reverse image
search → earliest instance → video keyframes → manipulation analysis → generative origin.

Three outputs decide what happens next:

| Outcome | Next |
|---|---|
| Not cleared, or generative origin uncertain | Stop. Write the bounded negative to `gaps.md`, naming what was run. Nothing downstream of an uncleared image is valid, and a shadow renders just as coherently in a generated scene |
| Cleared, and the question was about the file itself | Done. Findings to `findings.md`, hand any `person_name`, `email` or `username` to `/osint:osint-identity` and any IPTC or C2PA `company` to `/osint:osint-corporate` |
| Cleared, and the question is about place or time | Section 3 |

Embedded GPS is a lead, not an answer: it is a claim by whoever last wrote the file, rung
`reported` at best, and it gets tested in section 3 like any other hypothesis.

## 3. Route to `/osint:osint-geoint` — only after section 2 clears

Hand over the cleared file, the metadata verdict, any GPS lead and the same `Q<n>`. That play runs
scene inventory → text and script → search-area narrowing → street-level confirmation → historical
imagery → sun and shadow → weather → transport tracking → corroboration.

Two grading points that get inverted constantly, and both are the reference's, not this file's —
read `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` before writing either:

- A geolocation is never rung `observed`. You did not watch the photograph being taken. A
  street-level match is `correlated`; "taken at these coordinates" is `inferred`, credibility
  capped at 3, with one ICD-203 word and no percentage.
- A sun-angle result is a **range**, and solar geometry repeats twice a year about the solstice.
  A range is the answer, not a partial one.

## 4. Stop conditions

- The question is answered at a stated grade and rung, and every claim names its tool or engine
  and the query date.
- The image was not cleared in section 2. Stop there.
- The scene carries no invariant features — interior, tight crop, plain wall, sky. Not
  geolocatable; write it as a gap.
- Provenance is exhausted: no manifest, no metadata, no earlier instance in any index or archive.
  That is a result.
- You are running a third detector hoping for a different answer. The answer is provenance, or a
  gap.

## 5. Refusals

The department skills carry the full lists; these are the ones this entry point trips first.

- **A set of images of one private person resolved into the places that person is** is a movement
  profile, refused however each frame was published. One image of a public event is geolocatable;
  the distinction is in `osint-geoint`'s Refusals and it is not negotiable.
- **No face search without recorded authority, and none against a private individual.**
- **Illegal material suspends archive-on-read.** Do not save, hash, or re-upload it; route per
  `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` §3.8.
- **No uploading confidential, privileged, victim or third-party material to any third-party
  engine**, and never to one with a public gallery.
- **No detector score as a conclusion**, no "no EXIF therefore fake", and no first-publication date
  asserted from a search index.
- **No reproducing the material in a report.** Reference it by `file_hash` and describe it.

If a department skill does not resolve in this build, say so in one line and run the play inline
under the same case discipline — the order in sections 2 and 3 is what matters, not the tooling.
