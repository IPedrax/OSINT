*Load when: reading metadata off a photo, video or document; interpreting a C2PA manifest; choosing or comparing reverse image engines; establishing the earliest instance of an image; reading an ELA, noise or clone map; or assessing whether media is AI-generated. Mandatory before any manipulation or generative-origin claim reaches `findings.md`.*

# Media forensics

Provenance first, manipulation second, content third. The order is not stylistic: manipulation
analysis on a file whose chain of custody is unknown produces a map nobody can act on, and content
analysis of a generated image produces a fabricated finding.

Two rules govern everything below.

- **Metadata is a claim by whoever last wrote the file.** The tool that reads a field writes it too.
- **Absence proves nothing.** Stripped metadata, a missing manifest, a null reverse-image result and
  a clean forensic map are all the normal, expected state of an ordinary file.

## Metadata fields worth reading

| Field | What it actually tells you |
|---|---|
| `DateTimeOriginal` | The device's clock at capture, as the device believed it. **No timezone** unless an offset tag is also present. Device clocks are user-set and drift |
| `OffsetTimeOriginal` / `OffsetTime` | The UTC offset in force at capture. Newer phones and bodies write it; older ones do not. Its absence is a gap, not a discrepancy |
| `GPSDateStamp` / `GPSTimeStamp` | UTC from the GNSS receiver, independent of the device clock. Differencing it against `DateTimeOriginal` recovers the offset the device was set to — which sometimes contradicts the claimed location |
| `GPSLatitude` / `GPSLongitude` / their `Ref` tags | A position that may be a live fix, a cached fix from hours earlier, a Wi-Fi-derived estimate with kilometre error, or a manual tag. A lead for `/osint:osint-geoint`, never a located finding alone |
| `GPSAltitude` / `GPSAltitudeRef` | Often barometric on phones and frequently wrong by tens of metres. The `Ref` byte carries above/below sea level — read it, or you invert the sign |
| `GPSHPositioningError` / `GPSDOP` | Fix quality, where written. The only in-file signal of how much the coordinates are worth |
| `Make` / `Model` | Device family. Commonly the only field surviving a partial strip |
| `BodySerialNumber` / `SerialNumber` / `LensSerialNumber` | A device identifier. Links two files to one body — but the field is self-supplied and rewritable. Tier 3 by default (`40-analysis.md`); Tier 2 only where both files retain an intact capture chain and independent evidence ties the device to a holder |
| `LensModel` `FocalLength` `FNumber` `ExposureTime` `ISO` | Shooting parameters, useful as a consistency check against the depicted scene. A multi-second exposure with frozen motion is a contradiction worth chasing |
| `Software` | The last writer. "Passed through an editor" — not "content was altered". Phone HDR and computational-photography pipelines write here on every capture |
| `CreateDate` vs `ModifyDate` vs `DateTimeOriginal` | A later `ModifyDate` means a re-save. It does not mean an edit to the pixels |
| XMP `DocumentID` `InstanceID` `OriginalDocumentID` `DerivedFrom` | Adobe edit lineage. A shared `OriginalDocumentID` across two files means they descend from one source document — strong for linking files to each other, silent about anything else |
| XMP `xmpMM:History` | An action list with software agent and timestamps. Often survives when EXIF is gone |
| IPTC `By-line` `Credit` `Source` `CopyrightNotice` `Caption-Abstract` `DateCreated` `Keywords` | The agency and newsroom block. Its presence means the file passed a professional workflow, and the caption usually names the event, date and place outright. The highest-value block in journalism work |
| IPTC `SpecialInstructions` | Sometimes carries platform-inserted strings. Facebook's `FBMD` block is the commonly observed example and survives download, marking a file as having passed through that platform |
| MakerNotes | Vendor-proprietary: shutter count, focus data, lens corrections, sometimes a second embedded preview. ExifTool's coverage varies by vendor and firmware |
| `ThumbnailImage` / `PreviewImage` / `JpgFromRaw` | A separate embedded image. Some editors update the main image and not the thumbnail, so comparing them occasionally exposes the pre-edit frame. Check it every time — it costs one command |
| `Orientation` | A rotation flag. An image displaying "sideways" is almost always this, not tampering |
| ICC profile / `ColorSpace` | Weak pipeline hint (Display P3 suggests an Apple chain). Never a finding |
| JPEG quantisation and Huffman tables | Not an EXIF field — read from the JPEG structure. Fingerprints the **last encoder**, survives metadata stripping, and can contradict "straight out of camera X". The most evidential thing in this table |
| PNG `tEXt` / `iTXt` chunks | Some generative tooling writes prompts and parameters here. Present is strong; absent is nothing, because any conversion drops it |
| PDF `Creator` vs `Producer` | `Creator` is the authoring application, `Producer` the export path. A mismatch describes the workflow, not deceit |
| PDF `CreationDate` / `ModDate`, incremental update history | A PDF appended to rather than rewritten retains prior revisions. Genuinely recoverable content, and routinely overlooked |
| Office `LastModifiedBy`, `Company`, tracked changes, comment authors | Survive far more often than authors expect. Treat as personal data under `00-legal-ethics.md` §5 before recording |

### Traps in this table

- A perfectly consistent metadata block is not authentication. Consistency is what a competent
  forger produces; it is also what an unedited file produces. It does not separate them.
- An inconsistent block is not proof of forgery. Cloud sync, backup tools, messaging clients,
  format converters and HDR pipelines rewrite fields as a matter of course.
- `DateTimeOriginal` without an offset tag is a wall-clock reading with no zone. A "03:00" capture
  is 03:00 somewhere.
- Filenames are metadata and are trivially renamed, but the commonly observed patterns are still a
  cheap first read: `IMG_nnnn` / `DSC_nnnn` from camera firmware, `PXL_YYYYMMDD_...` from Pixel
  camera, `IMG-YYYYMMDD-WAnnnn` from WhatsApp, `Screenshot_...` from a screen capture. Confirm the
  pattern against a known sample rather than trusting the shape.
- Every field above is writable with ExifTool itself. Grade metadata `C3`, rung `reported`.

## Platform stripping

**This table is a prior, not a fact.** Platforms change behaviour without announcing it and differ
by upload path, client version and file type. Where it matters to the case, test it: upload a file
with known metadata through the same path, re-download it, and diff. That test touches no target
and settles the question for that platform on that date.

| Path | EXIF / GPS | C2PA | Re-encoded | Notes |
|---|---|---|---|---|
| X/Twitter, Facebook, Instagram, LinkedIn, Reddit, Imgur | Stripped | Assume stripped | Yes | Facebook commonly writes its own IPTC `FBMD` string, which survives download and marks the path |
| WhatsApp photo | Stripped | Stripped | Yes, and resized | The `IMG-YYYYMMDD-WAnnnn` filename is the durable tell |
| Telegram — photo | Stripped | Stripped | Yes | |
| Telegram — sent "as file" | Preserved | Preserved | No | The single most useful distinction on this table: the same app, two paths, opposite outcomes |
| Signal and comparable privacy messengers | Stripped | Stripped | Yes | Stripping is a product feature, not a signal about the sender |
| Discord attachments | Often preserved | Often preserved | Not always | Historically serves original attachment bytes. Verify per case; do not assume either way |
| Slack file share, email attachment | Usually preserved | Usually preserved | No | Some clients resize inline images; sent-as-attachment usually survives |
| Google Photos, Flickr, dedicated photo hosts | Preserved | Often preserved | Downloads usually original | Flickr surfaces EXIF subject to the uploader's privacy setting |
| YouTube, TikTok, Instagram video, any video platform | Container rebuilt | Stripped | Always | Post-upload container metadata describes the platform encoder, not the camera |
| Screenshot of anything | Destroyed and replaced | Destroyed | Yes | The screenshot carries the *screenshotting* device's metadata. That is evidence about the forwarder, never about the originator |
| Photo of a screen, print-and-scan | Destroyed | Destroyed | Yes | Adds moiré, screen-refresh banding and paper texture. Forensic maps become uninterpretable |

Because nearly every image an investigation receives arrives through the top rows, **absence of
metadata is the default expectation**. It supports, at most and at `C3`, a statement about the
distribution channel. It supports nothing whatsoever about authenticity, and "no EXIF, therefore
fake" is the error this section exists to prevent.

The informative case is the inverse: a file arriving with an intact original metadata chain
probably did not come from a public post, which relocates the question to who supplied it.

## C2PA and Content Credentials in practice

A C2PA manifest is a signed assertion set bound to the asset by a hash. It carries the claim
generator (the producing tool), declared actions (created, opened, placed, colour adjustments),
ingredients (parent assets and their own manifests), an optional creator identity, and a signing
certificate. Read it with **c2patool** locally, or **Content Credentials** where a web verifier is
acceptable for the material.

| Validation outcome | What it means | What you may write |
|---|---|---|
| No manifest | The normal case for almost every file in circulation | Nothing. Record it as absent and move on |
| Valid manifest, signer chains to a trust list you accept | The named tool asserted these actions at that time | "Signer S asserted actions A at T" — rung `reported`, grade `A3` alone, `A2` where other collected material agrees |
| Valid signature, unknown or self-signed signer | A key made these assertions. The key is not an identity | The assertions, attributed to the key, not to a name |
| Manifest present, asset hash mismatch | The bytes changed after signing | "The current bytes differ from those signed" — rung `observed`, and recomputable, so `A1` |
| Malformed or truncated manifest | Usually a lossy pipeline, occasionally tampering | Record the state; do not infer intent |

Grading, and this is where the certificate-transparency habit misfires: **C2PA is
self-authenticating but it is not independently mirrored.** There is no public append-only log to
check a manifest against, so the single-source `A1` exemption in `41-confidence.md` — which exists
for CT and only for CT — does not apply. One valid manifest is one source: `A2` where it is
consistent with other collected material, `A3` where it stands alone.

What it does not attest: that the depicted scene occurred, that the assertion list is complete,
that no unlogged edit happened before signing, or that the certificate's subject name corresponds
to a real accountable party unless you validated the chain against a trust list you can defend.

Practical behaviour:

- Any re-encode, resize, screenshot, format conversion or platform upload drops the manifest.
  Absence is therefore overwhelmingly uninformative.
- "Durable" credentials pair the manifest with an invisible watermark and a fingerprint so a
  stripped manifest can be looked up again. Recovery is best-effort; a failed recovery says nothing.
- A small number of platforms surface credentials in their interface. Most strip them. Check the
  specific platform rather than generalising.
- Invisible-watermark schemes shipped by individual model providers are **not** C2PA, are
  provider-specific, and are generally not verifiable by a third party. Do not conflate the two or
  report one as the other.
- A generative-disclosure manifest is the strongest single indicator of AI origin available, and it
  is still an assertion by a tool. Its absence is worth nothing: stripping it takes one command.

## Reverse image engines

The indexes are disjoint. One engine returning nothing is one index's silence — not a negative
result, and not a check. Run at least two, and one of them is **Yandex Images**.

| Engine | Index character | Blind spots |
|---|---|---|
| **Yandex Images** | Faces, near-duplicate crops, mirrored and lightly edited copies; deep coverage of Russian, CIS and Eastern European sites including VK and Odnoklassniki | Patchy on small Western sites; availability and interface vary by region; queries are processed in Russia |
| **Google Lens** | Objects, landmarks, products, plants, semantic similarity, and OCR on signage — the OCR often answers the question faster than the image match does | Poor at finding an exact reposted crop; results are personalised and localised, so two analysts see different sets |
| **TinEye** | Exact and edited copies, with a reliable oldest-first sort. The provenance engine | Much smaller index; will not find a different photograph of the same scene; misses heavily recomposed images |
| **Bing Visual Search** | A distinct crawl, plus a region-of-interest crop for isolating one object in a busy frame | Generally weakest for exact-copy discovery |
| **Baidu Images** | Chinese-language web, Weibo, Baidu Tieba, Chinese marketplaces | Chinese-only interface; domestically filtered, so absence carries less weight than elsewhere |
| **PimEyes** | Faces across crawled web images | Legally constrained (`00-legal-ethics.md`); returns similarity scores, never identifications |

### Which to run, by subject matter

| Subject | Run first | Then |
|---|---|---|
| A person's face | Yandex Images | TinEye for reposts of the same file. PimEyes only with recorded authority |
| "This photo is from the event happening now" | TinEye, oldest first | Yandex Images, Google Lens, then the archives — this is a reuse question, not a matching question |
| Product, packaging, uniform, insignia, weapon | Google Lens | Bing Visual Search region crop; Baidu Images where the market is Chinese |
| Building, street scene, landmark | Google Lens, including its OCR on any signage | Yandex Images, then hand `coordinates` to `/osint:osint-geoint` |
| Screenshot of a post | Search the **text** verbatim in a search engine first — it beats image search on this class every time | TinEye on the image; archives for the original post |
| Meme or heavily edited image | Yandex Images near-duplicate | TinEye edited-copy match |
| Suspected AI-generated image | TinEye and Yandex Images for earliest instance | Google Lens for the visual source or style; detectors last and least |

### Technique

- Crop out watermarks, borders and platform chrome before searching; they defeat matching.
- Search a distinctive region on its own, then the whole frame.
- Try the mirrored image. Reposters mirror to evade matching, and Yandex handles it best.
- Search the embedded thumbnail from the metadata as a separate image.
- Upscaling before searching helps nothing and can hurt. Search the highest-resolution original you
  hold, not an enhanced version.
- **Never hand a target-controlled URL to an engine.** The engine fetches it and the fetch lands in
  the target's logs. Upload the local copy.

## Establishing the earliest instance

This is the highest-value output of the whole play and the easiest to overclaim. What an engine
returns is a property of **that index at that moment**, not a fact about publication.

1. **TinEye**, sorted oldest first. Record the engine and the query timestamp with the result.
2. Repeat on at least one engine with a disjoint index. Disagreement is normal and is itself
   reportable.
3. For every candidate earliest URL, fetch the page's first capture from **Wayback Machine
   (retrieval)** and **archive.today (retrieval)**. The archive capture date is evidence; the page's
   byline is not — CMS dates are editable and are edited.
4. Test whether the apparent original is a re-poster: no prior related content, an account created
   after the event, another outlet's watermark, or a crop line where a watermark used to be.
5. Look for the same image at higher resolution elsewhere. The higher-resolution copy usually sits
   closer to the origin, because every re-post degrades.
6. Look for an earlier instance of the **scene** rather than the **file**. A different frame from
   the same shoot demonstrates reuse even when the exact file is nowhere indexed.
7. Write the claim bounded: *"the earliest instance indexed by `<engine>`, queried `<ts>`, is
   `<url>`, dated `<date>` on the page and first archived `<date>`."* Rung `reported`, grade `C3`.

Never write "the image first appeared on `<date>`". That is a claim about the world, and an index
does not carry it. `B2` is the ceiling from index evidence and requires two engines with disjoint
indexes returning the same earliest URL **and** an archive capture of that page predating every
other copy found. Above `B2` needs a non-index source — the photographer, the agency, the filing.

Failure modes to state rather than resolve silently: deleted originals make a repost look like the
origin; material that circulated only in closed groups, messaging apps or broadcast channels is
largely unindexed; agency images behind paywalls are never crawled; and pages get de-indexed.
Record which engines were queried and when — a bounded negative is a result.

## Error level analysis, noise, and why they mislead

ELA re-saves a JPEG at a known quality and displays the per-pixel difference. Regions with a
different compression history show a different error level. That is all it measures.

Why it misleads, in the order it will mislead you:

- Error level tracks local texture and edge density far more strongly than editing history. Flat
  sky is always dark; foliage, hair and text edges are always bright. Analysts read structure as
  manipulation.
- A single re-save equalises the whole image. Every platform in the stripping table performs one.
  **After a platform upload, ELA is dead** — and that covers most files in most cases.
- A composite that was assembled and then screenshotted has exactly one compression history
  everywhere, so the fabrication looks pristine.
- Resizing, cropping and format conversion each change the map on their own.
- There is no published threshold, no validated error rate, and no accepted stand-alone use in
  forensic practice. It is a triage visualisation; its own popularisers say so.

Adjacent techniques, same ceiling:

| Technique | What it shows | Why it is not a conclusion |
|---|---|---|
| Noise analysis | Local noise variance | Real sensor-noise attribution (PRNU) needs many reference images from the *same* body and a lightly compressed chain. A browser noise map is not PRNU and cannot attribute a camera |
| Clone detection | Similar repeated blocks | False-positives on brickwork, foliage, sky gradients, crowds, tiled interface elements — i.e. on most photographs |
| Luminance gradient | Lighting discontinuities | Low specificity; compression artifacts read as discontinuities |
| Level sweep, PCA | Faint traces in narrow value ranges | Purely interpretive. Two analysts routinely see two things |

What is genuinely evidential in this family:

- **JPEG quantisation tables** fingerprint the last encoder. Compare against the claimed device or
  app: a mismatch contradicts a stated provenance chain, and that is a real finding.
- **JPEG structure** — segment order and metadata placement — differs between encoders and survives
  when fields do not.
- **Embedded thumbnail versus main image**, as above.

Rule: run these to generate a question, then answer the question with provenance. A manipulation
conclusion supported only by a map is `inferred`, capped at credibility 3, and should usually not
be written at all. Write "compression history differs across region R", not "R was edited".

## AI-generated media

The defensible finding is provenance-based. Everything in this section is subordinate to the
manifest, the earliest instance, and whether any independently produced imagery of the same event
exists at all.

| Signal | Status | Reading |
|---|---|---|
| Generative metadata: a C2PA generative claim generator, a model name in `Software`/`Creator`, a PNG parameters chunk | **Real** | Strong when present. Meaningless when absent — one command strips it |
| No earlier instance in any index or archive, first appearance on an account with no relevant history, and no other party's imagery of the event | **Real, and the strongest practical one** | This is provenance, not pixels. It is also what survives compression |
| Scene logic that cannot close: shadows inconsistent with a single light source, reflections that do not correspond to the scene, geometry that does not resolve, an object that changes on the far side of an occluder (strap, railing, cable, fence) | **Real** | Check outdoor shadow claims against `SunCalc` / `ShadeMap` via `/osint:osint-geoint` rather than by eye |
| Background signage that is nearly a real script but non-lexical | **Real but weakening** | Small background text still fails more often than foreground text |
| Repeated textures, tiled background elements, duplicated faces in a crowd | **Real** | Survives moderate compression |
| Output dimensions matching a common model's default size, with no camera metadata | Weak | Cheap to check, never sufficient |
| Waxy or oversmoothed skin | Weak | Phone beautification, denoising and upscaling produce the identical look |
| Overly aesthetic lighting and composition | Weak | Stock and advertising photography looks exactly like this |
| Missing catchlights in eyes | Weak | Destroyed by resolution and compression before it is diagnostic |
| **Counting fingers** | **Obsolete** | Current models render hands correctly most of the time, and real photographs contain occluded, blurred and overlapping fingers constantly |
| **Garbled text anywhere in frame** | **Obsolete** | Headline-scale text renders correctly now |
| **Mismatched earrings, asymmetric glasses** | **Obsolete** | Improved in current models, and real people wear mismatched jewellery |
| **"Too perfect" teeth or skin** | **Obsolete** | Matched by every beauty filter shipped on every phone |
| Absence of EXIF | **Not a tell** | See the stripping table |
| A detector score | **Not a tell on its own** | See below |
| "It looks AI to me" | **Not a tell** | This intuition has produced repeated public misidentification of real photographs of real people at real events |

### Video

Temporal inconsistency is where video differs: jewellery, teeth, hairlines, background text and
patterned fabric that change between adjacent frames; a face-swap boundary that shifts under head
rotation or when a hand crosses the face; lighting mismatched between face and neck; audio-visual
desync at plosives. All of it is destroyed by compression — a 480p re-upload is untestable, and
saying so is the correct output. Use these to raise a question; answer it with provenance.

### Detector reliability, stated plainly

- Detectors are classifiers trained on outputs of generators that existed when they were trained.
  They degrade against newer generators **by construction**, not by accident.
- Headline accuracy figures come from balanced benchmark sets. Casework is unbalanced and
  adversarial: compressed, cropped, re-uploaded, screenshotted, upscaled. Those transformations push
  authentic images toward a synthetic verdict, so the realised false-positive rate on real casework
  is far worse than the published number.
- Base rates finish the argument. Applied to a population where synthetic images are rare, even a
  detector with a genuinely high accuracy returns mostly false positives among its "synthetic"
  calls. Say this to any user pressing for a verdict from a score.
- Two detectors agreeing is **not** corroboration. They share training corpora and fail on the same
  inputs, which collapses them to one source under the independence tests in `41-confidence.md`.
  Disagreement carries one meaning only: the artifact is hard to classify.
- Ceiling: grade any detector output `D3`. Never a headline finding, never on its own, never a
  number pasted into a report as a probability.
- When provenance cannot be established, the correct output is a `gaps.md` line naming what was run
  and stating that generative origin could not be established or excluded. That is a result.

## What you can defensibly claim

| What you actually have | What you may write | Rung | Grade |
|---|---|---|---|
| The file, hashed | "the archived copy has sha256 `<hex>`" | `observed` | `A1` — recomputable by anyone holding it |
| A retrieval from a URL | "this file was served from `<url>` at `<ts>`" | `observed` | `A2` — one observation; a server may serve other bytes to another client |
| Metadata present | "the file's metadata asserts capture at `<t>` on device `<d>`" | `reported` | `C3` |
| Metadata absent | "ExifTool reports no EXIF, XMP or IPTC fields in this file" | `observed` | `A1` for the observation — **and it licenses no inference at all.** The clearest illustration in this plugin that a high reliability letter transfers nothing to a claim the source does not attest |
| Valid C2PA, recognised signer | "signer `<s>` asserted actions `<a>` at `<t>`" | `reported` | `A3` alone, `A2` where other collected material agrees |
| C2PA asset-hash mismatch | "the current bytes differ from those signed" | `observed` | `A1` |
| A reverse-image match | "the same image appears at `<url>`, retrieved `<ts>`" | `correlated` | `C3`, Tier 3 — a `candidate_group`, never a merge |
| Earliest indexed instance | "the earliest instance indexed by `<engine>`, queried `<ts>`, is `<url>`" | `reported` | `C3`; `B2` only under the two-engine-plus-archive rule above |
| Quantisation-table mismatch | "the encoder fingerprint is inconsistent with a file written directly by `<device>`" | `inferred` | `C3`, with the assumption and falsifier stated |
| An ELA or noise map | "compression history differs across region R" | `observed` for the map; any edit conclusion is `inferred` | `C3` maximum |
| A detector score | "classifier `<c>` returned `<score>` on `<date>`" | `reported` | `D3` |
| A face-search hit | "the engine returned `<url>` as a similarity match" | `correlated` | `C3`, Tier 3 |
| Nothing found | "engines E1..En queried on `<date>`; no instance earlier than `<x>` located" | `observed` negative | State the bound. A bounded negative is a finding |

Never write, in any grade: that absent metadata indicates fakery; that an image "first appeared" on
a date, from index evidence; that a forensic map shows an edit; that a detector score establishes
generative origin; or that a visual match establishes identity.
