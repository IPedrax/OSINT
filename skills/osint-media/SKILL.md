---
name: osint-media
description: >
  Image, video and document forensics in one order: provenance first, manipulation second,
  content third. Extracts file metadata locally, reads C2PA Content Credentials, runs reverse
  image search across engines whose indexes do not overlap, establishes the earliest indexed
  instance, pulls video keyframes and thumbnails, and assesses manipulation and generative
  origin — with detector output treated as a weak signal that never carries a finding alone.
  Passive by default; uploads to public-gallery services and any fetch from target-controlled
  infrastructure are marked active and separately gated.
when_to_use: >
  Dispatched by the /osint router for photo, video, document, file_hash and url selectors.
  Use for "is this photo real", "is this image AI-generated", "deepfake", "was this
  photoshopped", "check this video", "reverse image search", "where else does this image
  appear", "who took this photo", "when was this picture taken", "read the EXIF", "does this
  file have metadata", "GPS in this photo", "what camera shot this", "C2PA", "Content
  Credentials", "find the original of this image", "earliest version of this photo", "is this
  a stock photo", "has this image been reused from an older event", "verify this screenshot",
  "extract frames from this video". Run this before any geolocation or attribution work on a
  photo or video. Not for: identifying the place or time in an image (osint-geoint); accounts,
  handles or people records (osint-identity); judging a narrative rather than a file
  (osint-verify).
disable-model-invocation: true
argument-hint: "[photo | video | document | url | file_hash]"
---

# osint-media
Establish where a file came from before saying anything about what it shows.

## Preconditions
1. A case is open: `${CLAUDE_PROJECT_DIR}/cases/<slug>/scope.md` exists. If not, stop and run `/osint:osint-scope`.
2. Read `scope.md` for `question` (numbered `Q1..Qn`), `out_of_bounds[]`, `active_allowed`. The gate ran at intake; do
   not re-ask it.
3. Record the seed in `entities.jsonl` as `photo` `video` `document` `url` or `file_hash`. A file you were handed and a
   file you fetched are different provenance situations — record which, in step 1, before anything else.
4. Default `mode` is `passive`. Step 1 fetches, step 6 in-browser frame extraction and step 7 FotoForensics are
   `active`: each needs `active_allowed: true` **plus** a fresh confirmation naming the exact URL or file.
5. Every step appends a `ledger.jsonl` row whose `query` opens with the scope question id (`"Q1: ..."`) and copies the
   registry row's `mode` and `name` exactly. Grep `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` first; honour
   `verified=no` by using the homepage.

## The play — provenance first, manipulation second, content third. Steps out of order produce confident nonsense.

### 1. Take custody — `url` `photo` `video` `document` → `file_hash` · passive or ACTIVE
- Analyse bytes you hold, at the highest resolution obtainable — every screenshot and re-save destroys what steps 2, 3
  and 7 read. **A file supplied to you costs no fetch: `passive`.** Pulling one from a page lands in the hosting
  server's logs — `active` where the target controls that server, and gated. Prefer a copy already held by **Wayback
  Machine (retrieval)**, **archive.today (retrieval)**, **Common Crawl** or, for video, **Ghostarchive**.
- Hash with sha256, store as `evidence/<sha256>.<ext>`, and archive the carrying page as a separate artifact — the page
  is provenance and it rots first. **Wayback Machine Save Page Now** is `active` and dates your interest publicly;
  snapshot last, not first.
- Grade "the archived copy has sha256 `<hex>`" `A1` — recomputable by anyone holding the file. Grade "this file was
  served from `<url>` at `<ts>`" `A2`: one observation, and a server may serve different bytes to another client. An
  identical `file_hash` across two artifacts is Tier 1 — the only merge-grade datapoint this play produces.

### 2. Local metadata — `photo` `video` `document` → `coordinates` `person_name` `email` · passive
**ExifTool** on the stored copy, **ffmpeg** (`ffprobe`) for video containers. Local, discloses nothing, always first.
Read GPS coordinates and `GPSDateStamp`/`GPSTimeStamp` (UTC — pairing them against the local capture time recovers the
offset), capture time and its offset tag, make, model, body serial, lens, editing software and XMP history, IPTC author
and credit, and the embedded thumbnail, which sometimes still shows the pre-edit frame.
- Grade `C3`, rung `reported`: metadata is a claim by whoever last wrote the file, not an observation of the world, and
  it is trivially rewritten. Not `A` — the parser is reliable, the assertion is not. GPS is a lead for
  `/osint:osint-geoint`, never a located finding on its own.
- **Absence of metadata is normal and is not evidence of anything.** Every mainstream platform strips EXIF on upload.
  "No EXIF, therefore suspicious" is the classic amateur error here and must not reach `findings.md`. All absence weakly
  supports — `C3`, and only against the stripping table in `26-media-forensics.md` — is a platform or an editor in the
  chain. The informative case is the reverse: **intact original metadata means the file probably did not come from a
  public post**. That is a finding, `C3`, and it changes where you look next.

### 3. Content Credentials — `photo` `video` `document` → `person_name` `company` `url` · passive
**c2patool** locally for case material; **Content Credentials** where a web verifier is acceptable. Four outcomes: no
manifest (the normal case, means nothing); valid manifest with a recognised signer; valid signature from an unknown or
self-signed signer, which attests a key and nothing about identity; manifest whose asset hash no longer matches the
bytes — the file changed after signing, and that is evidential.
- Grade a valid manifest from a recognised signer `A2`, or `A3` where nothing else in the case agrees. **Not `A1`.**
  C2PA is self-authenticating but it is *not* independently mirrored, so it does not qualify for the certificate
  transparency exemption in `41-confidence.md`; one signature is one source. It attests what the signing tool asserted
  about creation and editing, never that the depicted scene occurred.
- A manifest declaring a generative claim generator is the strongest single indicator of AI origin in this play, and it
  is still a tool's assertion rather than a measurement. It is step 8's first input.

### 4. Reverse image search — one engine is not a check — `photo` `url` → `url` `photo` `social_profile` · passive
The indexes are disjoint. Running one engine and getting nothing is one index's silence, not a negative result. Run at
least two, and **Yandex Images** must be one of them.
| Engine | Strongest at |
|---|---|
| **Yandex Images** | Faces, near-duplicate crops, mirrored and lightly edited copies; Russian, CIS and Eastern European sites |
| **Google Lens** | Objects, landmarks, products, plants, and OCR on signage — the OCR often solves the question faster than the match |
| **TinEye** | Exact and edited copies, sorted oldest first — the provenance engine, and step 5's tool |
| **Bing Visual Search** | A distinct crawl, and a region-of-interest crop for one object inside a busy frame |
| **Baidu Images** | Chinese-language web, Weibo, Baidu Tieba, Chinese marketplaces |
- Re-run on crops, mirrored and rotated versions, and on the embedded thumbnail from step 2 as a separate image.
- Ledger `mode=passive` — the target learns nothing. But every upload discloses case material to a third party that may
  retain it; that is an evidence-handling decision under `01-tradecraft-opsec.md`, not a mode question. **Never paste a
  target-controlled URL into an engine** — the engine fetches it and that fetch reaches the target's logs. Upload the
  local copy.
- Grade a visual match `C3`. Image similarity is Tier 3: it opens a `candidate_group`, never a merge, at any quantity.

### 5. Earliest instance — a claim about an index on a date, not about the world — `photo` → `url` · passive
**TinEye** oldest-first, then archives: **Wayback Machine (retrieval)** for each carrying page's first capture,
**archive.today (retrieval)** for pages Wayback will not take, **Common Crawl**, **Arquivo.pt** for full-text search.
- Write it as: *"the earliest instance indexed by `<engine>`, queried `<ts>`, is `<url>`, dated `<date>` on the page and
  first archived `<date>`."* Grade `C3`, rung `reported`. Do **not** write "the image first appeared on `<date>`" — no
  index supports a claim about publication, only about its own contents at query time.
- `B2` is the ceiling from index evidence, and needs two engines with disjoint indexes returning the same earliest URL
  *and* an archive capture of that page predating every other copy found. Never above `B2` without a non-index source.
- Page bylines are editable and CMS dates lie; prefer the first archive capture. A deleted original makes a repost look
  like the origin — say so rather than resolving it silently. Not indexed is not not-published: closed groups,
  messaging apps, broadcast channels and paywalled sites are largely unindexed, so absence goes in `gaps.md` as a
  bounded statement of which engines were queried and when.

### 6. Video — `video` `url` → `photo` `file_hash` · passive or ACTIVE
Keyframes are what make a video searchable at all. **ffmpeg** on the copy already in `evidence/` is local and passive.
The **InVID WeVerify Verification Plugin** bundles keyframe extraction, magnification and platform upload metadata, but
its extraction fetches from the hosting server — `active` where the target controls it, and individual modules break
when platform APIs change, so confirm what still works before relying on it.
- Push keyframes through step 4, and the platform's own thumbnail as a separate still. Take the thumbnail from the video
  page; do not reconstruct a CDN path from memory.
- `ffprobe` and **ExifTool** on the container give encoder handler, creation time (usually UTC, usually with no offset)
  and rotation. Every platform re-encodes: post-upload container metadata fingerprints the platform's encoder, not the
  recording device — `C3` as a re-encode tell, never as capture data. **Ghostarchive** and **Wayback Machine
  (retrieval)** hold prior copies, including of videos since deleted. Grade a keyframe match as step 4: `C3`, Tier 3.

### 7. Manipulation analysis — leads, never conclusions — `photo` → `photo` · passive or ACTIVE
**Forensically** runs entirely client-side and uploads nothing, which makes it the default for case material.
**FotoForensics** is `active`: free-tier uploads join a publicly browsable gallery, so submitting publishes both the
image and your interest in it. It needs `active_allowed: true` plus a fresh confirmation naming the file — or use the
paid tier, or Forensically.
- The most evidential output is the JPEG quantisation table: it fingerprints the last encoder and can contradict a claim
  that a file came straight out of a named camera or app. ELA, noise, clone and luminance-gradient maps show compression
  and resampling history, not manipulation. Read `26-media-forensics.md` first — a clean ELA does not mean authentic, a
  noisy one does not mean edited, and neither has a published threshold.
- Grading: the map is `observed` — you ran the tool. Any manipulation conclusion is `inferred`, credibility capped at 3,
  with the assumption and its falsifier stated. Write "compression history differs across region R", not "R was edited".

### 8. Generative origin — provenance decides this, detectors do not — `photo` `video` → `photo` · passive
Work this order, stopping as soon as it settles: C2PA manifest (step 3) → earliest instance and chain of publication
(step 5) → scene-level corroboration, meaning does any independently produced photograph of this event exist at all,
from any other angle or party → structural artifacts in `26-media-forensics.md` → detector, last and least.
- **Hive AI-Generated Content Detection** and **AI or Not** are the registry's classifiers. Grade their output `D3`.
  Never state a score as a conclusion, never on its own, never in a headline finding: a practitioner who publishes on a
  detector score publishes something false sooner or later. They fail in both directions — compression, upscaling,
  denoising and phone beautification push authentic images toward a synthetic verdict, while current models routinely
  evade classifiers trained on their predecessors. Two detectors agreeing is **not** corroboration — they share training
  corpora and fail on the same inputs, collapsing to one source under the independence tests in `41-confidence.md`.
  Disagreement means only that the artifact is hard to classify. Several widely repeated visual tells — finger counts,
  garbled text, waxy skin — no longer discriminate and have driven public false accusations; `26-media-forensics.md`
  separates the real ones from the obsolete.
- If provenance is unobtainable, the correct output is a `gaps.md` line: generative origin could not be established or
  excluded, naming what was run. That is a result. A probability manufactured from a detector score is not.

### 9. Face search and hand-off — `photo` → `url` `person_name` `coordinates` · passive, legally gated
**PimEyes** is `passive` in registry terms and still the most constrained source in this play: face search is biometric
processing, restricted or actionable in the EU, the UK and several US states. Confirm and record written authority
before any query, do not run it against a private individual, and treat self-audit as the defensible case. A match is a
similarity score: `C3`, Tier 3, never an identification without an independent datapoint.
- Hand off under the same `Q<n>`: `coordinates` and any place or time-of-day question to `/osint:osint-geoint` (after
  this play, never before it); `person_name` `email` `username` to `/osint:osint-identity`; a `company` from an IPTC
  credit or C2PA signer to `/osint:osint-corporate`; the narrative the file supports to `/osint:osint-verify`.

## Reference index
| File | Load when |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/references/26-media-forensics.md` | Before interpreting any metadata field, any forensic map, or any AI-origin question. Carries the field table, the platform-stripping table, C2PA validation outcomes, engine selection by subject matter, why ELA misleads, and the real-vs-obsolete artifact list |
| `${CLAUDE_PLUGIN_ROOT}/assets/sources.csv` | Selecting any source. Grep a filtered slice (`accepts` contains `photo` `video` `document` `file_hash`, `mode=passive`, `auth=none` first). Never load whole |
| `${CLAUDE_PLUGIN_ROOT}/references/41-confidence.md` | Grading anything here. Read it before assigning a letter — a local parser is not an authoritative claim, and C2PA is not certificate transparency |
| `${CLAUDE_PLUGIN_ROOT}/references/10-pivot-matrix.md` | Choosing the next pivot. Sections `photo` `document` `file_hash` `coordinates` `url`, plus PIVOTS THAT NOTIFY and LINKING DATAPOINT STRENGTH |
| `${CLAUDE_PLUGIN_ROOT}/references/01-tradecraft-opsec.md` | Before uploading case material anywhere, before any step 1, 6 or 7 fetch or submission, and for evidence-integrity handling |
| `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md` | Face-search authority; §3.8 illegal material; §6 special-category data, since one photograph can expose health, religion, ethnicity or sexual orientation |
| `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md` | A visual match looks conclusive. Linking datapoint tiers, `candidate_group` handling, and the LLM failure modes list |
| `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` | Writing `findings.md`; redacting faces, plates and locations; referencing evidence by hash rather than reproducing it |

## Stop conditions
- The scope question is answered at a stated confidence and every claim names the tool or engine and the query date.
- Two engines with disjoint indexes return nothing not already in `entities.jsonl`, and the earliest instance is stable
  across them. Two consecutive empty passes end enumeration.
- Provenance is exhausted — no manifest, no metadata, no earlier instance in any index or archive. Write the bounded
  negative result in `gaps.md` and stop. That is a result, not a failure.
- The remaining question is about the place, object or time of day: hand to `/osint:osint-geoint`. About the claim the
  file supports: hand to `/osint:osint-verify`.
- Only an original-resolution copy can carry a forensic claim. A screenshot of a screenshot cannot; say so and stop.
- **You are running a third detector hoping for a different answer.** Stop. The answer is provenance or a gap.
- Anti-rabbit-hole: name the `Q<n>` a step advances before running it. A hit on a stock library is inventory.

## Refusals — beyond the global gate in `${CLAUDE_PLUGIN_ROOT}/references/00-legal-ethics.md`
- **Illegal material suspends archive-on-read.** If collection surfaces child sexual abuse material or comparable
  content, stop immediately: do not save, hash, re-upload or "preserve" it, and route to a child-protection body or law
  enforcement per `00-legal-ethics.md` §3.8. This is the one place in the plugin where the evidence rule is overridden.
- **No face search without recorded authority, and none against a private individual.** Nearest legitimate route: the
  platform's own reporting process, or a self-search under a service's opt-out route.
- **No uploading confidential, privileged, victim or third-party material to any third-party engine**, and never to a
  service with a public gallery. **ExifTool**, **ffmpeg**, **c2patool** and **Forensically** run this play locally.
- **No detector score as a conclusion**, no "no EXIF therefore fake", and no first-publication date asserted from a
  search index. Each is a false finding waiting to be published.
- **No de-anonymising a source, whistleblower, bystander or protest participant from imagery.** Redaction is the
  default; `50-reporting.md` governs what ships.
- **No fetching from target-controlled infrastructure without `active_allowed`**, and no handing a target-controlled URL
  to a third-party fetcher to do it indirectly. **No defeating a rate limit, bot challenge or CAPTCHA** to run bulk
  reverse-image or face queries — record the gap.
- **No reproducing the material itself in a report.** Reference it by `file_hash` and describe it.
