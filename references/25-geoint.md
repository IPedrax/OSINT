*Load when: geolocating or chronolocating a photo or video, reading a scene for locatable features, reasoning about sun position or shadows, choosing an imagery source, or checking a candidate match before it enters `findings.md`.*

# Geolocation and chronolocation

## Order of operations, and why it is fixed

1. **Synthetic-media clearance** (`osint-media`). A generated image contains internally consistent
   signage, plausible architecture and a coherent shadow. Every technique below will "work" on it
   and return a confident wrong answer. Nothing here is valid before clearance.
2. **WHERE**, to a region, then to a candidate set, then to one place.
3. **WHEN**, which mostly needs WHERE first: sun geometry needs a coordinate and a camera bearing,
   weather needs a station, historical imagery needs a tile.
4. **Corroboration** from a process that is not imagery and not your own reading.

Reversing 2 and 3 is the common time sink. A shadow with no coordinate constrains almost nothing.

## Feature checklist

Work top to bottom. Write every feature down before proposing a location: the inventory is what
lets you notice later that you only ever tested the first idea. Constraining power runs roughly:
unique text > distinctive infrastructure geometry > architecture and materials > vegetation and
biome > sky and light.

### Text, script and language

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Script (Cyrillic, Arabic, Devanagari, Han, Thai, Georgian, Amharic) | A script region, instantly, before any word is read | Compare glyph forms; Cyrillic differs between Russian, Serbian, Bulgarian, Ukrainian by a few letters | Diaspora signage, tourist areas and religious sites use scripts far from home |
| Language and orthography | A country, sometimes a region | Diacritics and letter frequency separate close pairs: Czech/Slovak/Polish, Spanish/Portuguese, Dutch/Afrikaans | A shared language spans many countries; product packaging is multilingual |
| Business names, brands, franchises | A retail market, sometimes a chain's national footprint | **OpenStreetMap** tag search on `name`, `brand`, `operator` via Overpass; the chain's own store locator | **A chain has many branches.** A named branch is a candidate set, not a location |
| Phone numbers on signage | Country calling code, then area or mobile-block | National numbering-plan documentation; digit-group formatting is itself regional | Numbers survive on old signage after area codes are renumbered |
| Street name plates, house numbering | A city, often a single street | Plate design and colour are set municipally; **OpenStreetMap** carries the name and the numbering scheme | Street names repeat across a country; numbering conventions repeat across a region |
| Postal codes, VAT or tax numbers | A postal district; a registered company | Format alone identifies the country; the number pivots to `/osint:osint-corporate` | An operator's registered address is not the shop's address |
| Notices, permits, election posters | A jurisdiction and often a dated event | Election posters date a frame to a campaign window | Posters stay up for months; permits are reprinted |
| Emergency and service numbers | A country or bloc | 112 across the EU, 999 in the UK and several Commonwealth states, 911 in North America | Several countries operate more than one number in parallel |

### Road, traffic and rail

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Driving side | Two large groups | Left-hand traffic is the minority: the UK, Ireland, much of southern and eastern Africa, South and Southeast Asia, Japan, Australia, New Zealand | Parked cars on a one-way street prove nothing; steering-wheel side is imported-vehicle dependent |
| Centre-line colour | A road-marking tradition | Yellow centre lines separating opposing traffic in North America; white in most of Europe; Japan uses white with yellow marking no-overtaking | Repainting, worn markings, private roads, and temporary works layouts |
| Edge lines, kerb paint, hatching | A national standard, sometimes a road authority | Compare against a known-good panorama in the candidate country, not against memory | Standards change over decades; older roads keep the old scheme |
| Sign shape, colour and typeface | A sign-standard family (Vienna Convention style, MUTCD style, and national variants) | Typeface is the strong tell: distinct national alphabets exist for road signage | Bilingual and tourist-corridor signage borrows forms |
| Guardrail, barrier and bollard profile | A national roads authority | Cross-section and post spacing are specified nationally and are stable | Motorway standards are converging internationally |
| Road-marking of pedestrian crossings | A country or era | Bar spacing and approach markings are specified nationally | Repainted crossings drift from the standard |
| Railway gauge, sleeper type, electrification | A network | **OpenRailwayMap** carries gauge, electrification and signalling per segment | Industrial and heritage lines diverge from the national norm |
| Catenary mast design, signal type | A network and often an era | Compare against panoramas of known track in the candidate network | Rolling programmes leave several generations in service at once |

### Utility and street furniture

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Utility poles: material, cross-arm, insulator count | A distribution utility | Wood with cross-arms and pole-top transformer cans is characteristic of North American distribution; concrete and steel dominate elsewhere | Rural networks in many countries look alike at low resolution |
| Overhead vs buried distribution | A development era and a wealth band | Panorama comparison in the candidate area | Undergrounding programmes change this within one city |
| Street lighting: mast, bracket, lamp head | A municipality or a supply contract | Head shape is a strong local tell; LED retrofits are dated | A retrofit programme resets the tell and re-dates the scene |
| Fire hydrants: above-ground vs underground, colour | A country, often a water utility | Above-ground pillar hydrants dominate North America; many European systems use flush underground hydrants with wall plates | Industrial sites use their own standards |
| Manhole and utility covers | Frequently the municipality by name, cast into the lid | Read the casting; search the foundry or municipality name | Covers are reused and relocated during works |
| Bins, benches, bus shelters, post boxes | A municipality or a national operator | Livery and typeface; the operator name is often cast or printed | Contracts change; old stock survives in side streets |
| Traffic-signal head layout and mounting | A country, often a city | Vertical vs horizontal, mast-arm vs span-wire, pedestrian signal iconography | Retrofit programmes mix generations at one junction |

### Vehicles and plates

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Plate proportions and colour | A plate-standard family | European plates are long and narrow; North American, Japanese and Australian plates are shorter and taller | **A plate style is regional, not local**: an EU-format plate narrows to a bloc, not a town |
| Plate band, flag or country code | A country or bloc | The left-hand blue band with a country code is the EU pattern, also adopted by non-EU states | Adoption of the look by non-members; personalised and dealer plates |
| Regional prefix or suffix codes | Sometimes a province or city | National issuing-authority documentation | Codes are reassigned, and vehicles move; the registration district is not where the car is |
| Vehicle fleet mix | A market | Model availability differs sharply by market; taxi and bus liveries are municipal | Grey imports; border regions; rental fleets |
| Taxi, bus, emergency livery | A city or operator | Operator name and route numbers pivot into **OpenStreetMap** and operator sites | Liveries are rebranded on a contract cycle |
| Reading a plate to an owner | Nothing available to OSINT | **UK MOT History** gives vehicle data and no keeper | There is no legitimate plate-to-keeper route; see the skill's refusals |

### Built environment

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Roof form and material | A climate band and a building tradition | Compare against oblique imagery (**Bing Maps**) and panoramas | Standard-plan and industrial buildings look identical across continents |
| Window and shutter type | A region and an era | Roller shutter boxes, external louvred shutters and window-opening direction are regional | Replacement windows date to the refurbishment, not the building |
| Facade material, balcony type, panel joints | A construction era and often a standard type-plan | Prefabricated panel blocks follow a small number of type designs repeated across whole countries | **A type-plan block is not a unique building.** Match the *arrangement* of blocks, not one block |
| Building footprint and roofline geometry | A specific building, when the geometry is irregular | Overhead footprint (**OpenStreetMap**, **Google Maps**) against the photographed silhouette | Symmetric or repeated footprints match many candidates |
| Floor and window counts and spacing | A specific building | Count from the image, count from a panorama, compare spacing ratios rather than absolute sizes | Perspective and lens distortion; extensions added later |
| Antennas, satellite-dish orientation | A hemisphere and a satellite arc | Dishes in the northern hemisphere point south; azimuth clusters follow the satellite in use | Terrestrial and mobile-backhaul antennas point anywhere |
| Religious buildings and cemeteries | A confession, often a specific building | Compare against **OpenStreetMap** tags and imagery | Special-category data — see `00-legal-ethics.md` §6 before recording |

### Natural environment

| Feature | Narrows to | How to verify | Failure mode |
|---|---|---|---|
| Biome and dominant vegetation | A latitude band and climate class | Species identification, then a distribution range | Ornamental and imported planting is global; parks are not natural vegetation |
| Leaf state (bare, budding, full, senescent) | A season, and hemisphere-dependent | Compare against imagery of the candidate location in the candidate month | **Deciduous bare branches are winter *or* a drought-deciduous species, or a diseased tree, or a pruned one** |
| Crop stage in fields | A season and a crop calendar | Regional crop calendars; **Copernicus Data Space Ecosystem** timeseries for the same field | Multiple cropping seasons per year; irrigation shifts calendars |
| Snow line, ice, standing water | A season, sometimes a specific event | **NASA Worldview** or Sentinel-2 for the candidate date | A snowfall is a day, not a season; urban snow persists unevenly |
| Terrain: ridge lines, peaks, valley form | Frequently a single viewpoint | **Google Earth Pro** 3D terrain, matching the horizon profile from the estimated eye height | Haze flattens ridges; a long lens compresses depth and changes apparent spacing |
| Coastline, river form, water colour | A stretch of coast or river | Overhead imagery; **OpenStreetMap** water polygons | Tide and flow stage change width and colour drastically |

### Sky, light and shadow — read at step 1, computed at step 6

| Feature | Narrows to | Note |
|---|---|---|
| Shadow direction relative to a known bearing | Solar azimuth, hence a time-of-day and date pairing | Needs a camera bearing, so it waits for a candidate location |
| Shadow length against a measurable object | Solar elevation | Needs a vertical object on level ground |
| Sun visible in frame or specular glare | Solar azimuth directly | Beware reflections mistaken for the sun |
| Sky state (clear, broken, overcast, haze) | A weather window to test against records | Overcast destroys shadow reasoning entirely |
| Contrails, smoke, dust plumes | A day, when they are large enough to be in **NASA Worldview** | Plume direction reads wind, which is in the METAR |
| Moon phase and position at night | A candidate set of dates in the lunar cycle | Phase repeats roughly monthly: a phase gives several candidate dates, not one |
| Star field | Hemisphere and rough date, with a long enough exposure | Rarely usable on compressed social-media video |

## Sun position and shadows

### What the geometry actually says

For a vertical object of height `h` on level ground casting a shadow of length `L`:

- Solar elevation angle `e` satisfies `tan(e) = h / L`. A shadow twice the object's height means
  the sun is low (`e` near 27°); a shadow equal to the object means `e` is 45°.
- The shadow points **away** from the sun: shadow bearing = solar azimuth + 180°.
- Solar declination runs between about +23.44° and −23.44° over the year. At the equinoxes the sun
  rises due east and sets due west everywhere.
- Above the Tropic of Cancer the midday sun is always in the southern half of the sky, so solar-noon
  shadows point north; below the Tropic of Capricorn the reverse.
  **Between the tropics either is possible depending on the date**, which is where naive hemisphere reasoning fails.

Compute with **SunCalc**. Use **ShadeMap** where the shadow falling on the subject is cast by
surrounding buildings or terrain rather than by the subject itself — that is the case SunCalc
cannot model. **timeanddate.com** for sunrise, sunset, the twilight phases, moon phase and
moonrise, and for the daylight-saving and time-zone rule in force on the date in question.

### Procedure

1. Fix the location first. Without a coordinate there is no solar geometry to compute.
2. Fix the camera bearing: identify two mapped features in frame and read the bearing between them
   off **OpenStreetMap** or **Google Maps**.
3. Measure the shadow-to-object ratio on something vertical standing on level ground. Prefer a
   pole, a sign post or a building corner over a person — people lean, and a phone camera's
   perspective distorts a nearby subject far more than a distant one.
4. Derive solar elevation from the ratio and solar azimuth from the shadow bearing.
5. Run SunCalc across the plausible date range and record every date-and-time pair that reproduces
   both values within your measurement error.
6. Convert local solar time to clock time only at the end, applying the time-zone offset, the
   longitude offset inside that zone, and the DST rule that was in force on that date.
7. Resolve the two-date ambiguity (below) with vegetation, weather, or a dated imagery bracket.
8. Report a window, one ICD-203 term, and `precision: approx` in `events.jsonl`.

### What you cannot conclude

- **A timestamp.** The output is a window. Present it as a window.
- **The year.** Solar geometry repeats annually; it cannot distinguish 2019 from 2024.
- **A single date.** For any solar declination other than the solstices there are two dates a year
  producing the same geometry, roughly symmetric about the solstice. A shadow alone yields an
  ambiguous *pair* of windows. Report both, or resolve with independent evidence.
- **Clock time directly.** Solar noon is not 12:00. It moves with longitude inside a time zone (a
  large effect in wide zones such as China's single zone or Spain's), with the equation of time
  (which shifts solar noon by up to roughly a quarter of an hour either way across the year), and
  with DST.
- **Anything from a diffuse-lit scene.** Overcast light casts no usable shadow. Say so and stop.
- **Anything from a non-vertical object or sloping ground.** Both corrupt the ratio, usually by
  more than the precision being claimed.
- **Anything from a mirrored image.** A horizontally flipped frame reverses the shadow bearing and
  turns a northern-hemisphere reading into a southern one. Check text in the frame for reversal
  before trusting any bearing, on every image, including video stills.
- **A precision of minutes.** Measurement error in a shadow ratio propagates into tens of minutes.
  Claiming a five-minute window from a photograph is a claim about the analyst, not the scene.

### Moon and night scenes

Moon phase plus the moon's position gives a candidate set of dates within a lunar cycle, not a
date. Phase repeats roughly every 29.5 days, so a "half moon high in the south-east" is consistent
with one date per month across the whole plausible year. It narrows well when combined with a
weather record (a clear night) and a bracket from imagery. Artificial light gives a different
lever: lamp colour temperature dates a retrofit programme, and lit or unlit shop signage brackets
opening hours.

## Imagery sources — tradeoffs

| Source | Resolution | Recency | Coverage | Historical depth | Cost |
|---|---|---|---|---|---|
| **Google Earth Pro** | Sub-metre where commercial imagery exists | Base layer often lags the web map | Global, uneven | Decades in many areas via the timeline; per-tile acquisition dates | Free |
| **Google Maps** | Sub-metre urban | Satellite layer often older than Google Earth Pro | Global | None in the interface | Free |
| **Bing Maps** | Sub-metre; **oblique aerial** in selected cities | Differs from Google, which is the point: two dates bracket a change | Global base, oblique limited to selected urban areas | None in the interface | Free |
| **Yandex Maps** | Sub-metre | Panorama dates often newer than Western sources for the CIS | Strong for Russia, Belarus, Kazakhstan, other CIS states, Turkey | Panorama dates shown | Free; queries processed in Russia |
| **Google Street View** | Ground level | Multiple dated captures per location | Dense in North America, Western Europe, Japan, Brazil; thin in much of Africa and Central Asia; rural coverage years stale | Time slider | Free |
| **Mapillary** | Ground level, variable | Sometimes the only post-event capture | Patchy but reaches tracks and pedestrian areas no car drove | Per-image capture date and contributor | Account |
| **Copernicus Data Space Ecosystem** | Sentinel-2 near 10 m optical; Sentinel-1 radar | Revisit of a few days; radar sees through cloud and at night | Global | Back to the Sentinel missions | Free with registration |
| **NASA Worldview** | 250 m–1 km | Often within hours of acquisition | Global daily | Long MODIS/VIIRS archive | Free |
| **NASA FIRMS** | Thermal detections, not imagery | Near real time | Global | Long archive | Free; key for bulk |
| **Planet** | PlanetScope near 3 m daily; SkySat sub-metre tasked | Near-daily, and taskable | Global | Since constellation launch | Paid, no self-serve tier |
| **USGS EarthExplorer** | Landsat 30 m; US aerial and CORONA at metre scale | Archive, not current | Global for Landsat and CORONA; US aerial for the US | Landsat from 1972, US aerial from the 1930s, CORONA for the 1960s–70s | Free account; scanned film may cost |
| **National Collection of Aerial Photography** | Film aerial, high detail | Archive only | Worldwide reconnaissance sorties, strong for Europe, North Africa, the Middle East | Second World War and Cold War | Free catalogue search; scans cost |

Choosing: **resolution answers "what is it", revisit answers "when did it change"**, and no source
gives both cheaply. Establish that something happened on a day with a free coarse source before
spending on a fine one. Radar is the answer to persistent overcast, not more optical passes.

## Chronolocation procedure

1. Clear the media (`osint-media`). An undated repost of an older image is the most common false
   "new event", and a reverse-image pass ordered oldest-first is what catches it.
2. Read the metadata locally with `ExifTool`, and treat any embedded timestamp as `reported`: the
   camera clock may be wrong, unset, in the wrong zone, or edited.
3. Establish the location. Almost every dating lever needs it.
4. Bracket with dated overhead imagery: the last capture showing the pre-change state and the first
   showing the post-change state. Cite acquisition dates, never retrieval dates.
5. Bracket with dated street-level captures the same way, using the **Google Street View** time
   slider and **Mapillary** capture dates.
6. Narrow within the day with sun geometry, accepting that the output is a window and a pair of
   date candidates.
7. Test the resulting window against weather records:
   **NOAA National Centers for Environmental Information** as the issuing archive, **Iowa Environmental Mesonet** for
   raw station rows. Weather usually **excludes** a candidate date rather than confirming one.
8. Test against transport records if a vessel, aircraft or identifiable service vehicle is in
   frame — an independent process, so it can genuinely raise credibility.
9. Test against dated public events visible in frame: election posters, seasonal decoration,
   construction hoardings, roadworks, a sports fixture.
10. Write the tightest interval every check survives, with `precision` set honestly:
    `exact|day|month|year|approx`.

## False-confirmation traps

The failure mode of this discipline is not missing the answer; it is confidently matching the wrong
place. Run every item before writing a location or a date.

| Trap | Why it fires | The check that kills it |
|---|---|---|
| **The chain** | A franchise interior or forecourt is identical in hundreds of locations, and it *feels* like a unique match because the branding is distinctive | Match on something the chain did not build: the road geometry outside, the neighbouring buildings, terrain |
| **The type-plan building** | Prefabricated panel blocks, retail sheds and housing-estate designs repeat across whole countries by design | Match the *arrangement* of buildings and the ground between them, never one facade |
| **The regional plate** | A plate style covers a bloc; an EU-format plate narrows to Europe, not to a town | Use plates to exclude regions, not to select one |
| **National street furniture** | Bins, poles, signals and hydrants are specified nationally: they narrow to a country and then stop | Stop treating them as evidence once the country is fixed |
| **Seasonal vegetation read as a date** | Bare branches say "not summer" in a temperate zone, and nothing more; drought-deciduous species, pruning, disease and evergreens all mimic each other | Pair leaf state with a same-year Sentinel-2 timeseries for that field or park |
| **Capture date read as event date** | An imagery tile's acquisition date is when the satellite passed, not when the change happened | Report a bracket between two captures, never a single capture's date |
| **Stale panorama** | A rural Street View capture can be many years old; matching it proves the place, not the time | Separate the location claim from the date claim; grade them apart |
| **The mirrored frame** | A flipped image reverses shadow bearing, traffic side and text | Look for reversed text on every image before any bearing reasoning |
| **Toponym collision** | Twenty villages share a name; gazetteers list them all | **GeoNames**, ranked by population and admin region, then test each candidate |
| **The recycled image** | An old photograph attached to a new event | Oldest-first reverse image search; the earliest instance sets the ceiling on the date |
| **Weather "corroboration" that is one source** | Consumer weather sites, apps and aggregators mostly restate the same METAR and synoptic reports | Apply the corroboration tests in `41-confidence.md`; cite the issuing archive once, not three resellers |
| **The crowdsourced tag** | An **OpenStreetMap** tag is one mapper's claim at one time, sometimes imported from a stale source | Check the object's edit history and corroborate a load-bearing tag against imagery or a primary record |
| **Commitment** | Once a candidate is named, every subsequent feature is read as supporting it | Write the feature inventory before the hypothesis; then run the disconfirmation step in `40-analysis.md` against the leading candidate specifically |

## Video specifics

- Extract frames rather than working from playback: the best geolocatable frame is usually not the
  one on screen when something happens.
- A pan reveals geometry no single frame contains — relative bearings between landmarks, and
  parallax that separates near from far.
- Audio is evidence: language and accent, public-address announcements, sirens (which vary
  nationally), bells, birdsong, and engine notes.
- Continuity across a clip is a check in itself: a shadow that shortens then lengthens, or lighting
  that jumps, means the clip is edited from separate takes and each segment dates separately.
- Platform re-encoding strips metadata and shifts colour; grade the file you were given, and record
  which platform it came from.

## Recording conventions

- `entities.jsonl`: the seed `photo` or `video`, and any `coordinates`, `address`, `vessel`,
  `aircraft` or `vehicle_plate` derived. Coordinates carry the grade of the *claim*, not of the
  imagery source.
- `events.jsonl`: `precision` is `exact|day|month|year|approx`. Any sun-angle output is `approx`.
  A bracket between two captures is `day` at best, and only when the captures are a day apart.
- `findings.md`: rung, grade, the imagery source, its **capture** date, the retrieval timestamp and
  the sha256 of the archived copy. Geolocation is never rung `observed`.
- Coordinate precision in a shared report is a disclosure decision, not a technical one. Record the
  least precise coordinate that answers the question; `50-reporting.md` governs redaction.
