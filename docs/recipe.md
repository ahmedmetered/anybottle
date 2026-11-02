# The recipe

Everything below was learned by shipping it. The pipeline rebuilds bottles from single product photos; these are the rules that keep it honest.

## Reference admission comes first

Run the deterministic admission check (`img2threejs/forge/stage1_intake/check_reference_admission.py`) before spending any effort. It catches what your eyes will excuse: tilted affiliate shots, bottles cropped at the frame edge, flanker variants, fragmented foregrounds. Roughly half of search-engine results for a famous bottle fail admission.

Known failure classes:
- Frosted white bottles on white backgrounds: mask coherence collapses (largest blob < 0.6 of foreground). Requery for a contrasting background.
- Red-on-red or busy-scene shots: foreground coverage 1.0, no separable silhouette. Requery.
- The frame must show the WHOLE bottle. A close-up crops the silhouette and the IoU gate becomes unwinnable.

JPG references must be converted to PNG before the check on Windows (the checker's decoder only reads PNG there).

## The spec is measured, not authored

`measure_bottle.py` derives everything from the photo: per-row foreground width profile, neck = the width minimum in the 12-55% height band, cap = rows above the neck, body = rows below. Radii are scaled so the widest row matches the measured aspect ratio. Palettes are sampled from fixed fractional regions (cap top, collar band, body mid, print zone). A measured spec passes strict validation on the first try once the boilerplate blocks are in place.

## Geometry conventions that bite

- three.js LatheGeometry runs bottom-up (first point at y=0). A measured top-down profile must be reversed and Y-flipped, or the bottle renders upside down.
- The generator applies `dimensions` as a geometry scale ON TOP of the authored profile. A lathe profile authored at final size needs unit dimensions ({width:1,height:1,depth:1}) or it double-transforms.
- Component placement uses `transform.position` plus `attachment.localStart/localEnd`. A component `position` field alone is ignored. Nested components (cap under collar under body) double-apply offsets: parent everything to the top-level body, never to a translated sibling.
- The preview page must set `camera.aspect` to match the renderer size, and never reference `renderer` before its declaration (a temporal-dead-zone crash kills the module silently, leaving a blank canvas).

## Corrections are measured, not guessed

After each diagnose, measure the reference and render bounding boxes and apply the exact ratio: `radii_factor = ref_aspect / render_aspect`, `frame_fit = ref_fracH / render_fracH`, both clamped. Guessing the correction sign from the delta alone failed twice before this rule landed.

Preview fit divisor semantics: the generated previews fit with `fitDist = size * 0.5 / tan(fov/2) / divisor` — a LARGER divisor puts the camera CLOSER. To zoom out, decrease the divisor. And the patch regex must match any divisor (`/ ([0-9.]+);`), not just `/ 0.\d+;` — divisors above 1 legitimately occur, and a pattern that doesn't match is a silent no-op that costs a debugging session. Assert every patch.

## Materials on the web: textureless + baseColor is a pair

Shipping factories to a static site with `rebuild_bundles.py` applies two patches together:

1. `textureless: {declared: true}` on every material — the generated factories reference solid-color PBR swatch PNGs via relative paths; on a deployed site those paths 404 and the material falls back to an empty white texture. Textureless skips textures entirely and colors from the spec.
2. `baseColor` inserted beside every material `color` key — the generator's `clampedAlbedoColor` reads `spec.baseColor`, but the material defs carry `spec.color`. Without the inserted key every material silently renders the same fallback tan (#8A7A5F). The tell: every bottle on the page is the exact same beige.

Also required: the site's importmap must map `"three/examples/jsm/"` (the generated factories import RoomEnvironment/EffectComposer from that path, not `three/addons/`). A missing mapping fails the whole module graph, not just one bottle.

## The spec is the only source of truth

Never trust a generated `.ts` or `.bundle.mjs` whose timestamp predates the last edit of its spec. Hand-fixes edit specs; correction passes regenerate factories. A stale artifact ships old geometry (spout caps from attachment-radius defaults, floating label plates, pre-fix profiles) and looks plausible until you compare against the spec. When in doubt: regenerate from the spec, then bundle.

PBR swatch traps that only show up on recolor: the solid-color albedo swatch OVERRIDES the material's hex — when you change a material's color in the spec, rewrite its `pbr-<mid>/<mid>_albedo.png` swatch too (or go textureless). A DARK solid AO swatch multiplies the whole albedo to near-black — neutralize all five maps (albedo = color, AO = white, normal = (128,128,255), height mid-grey, roughness mid-grey). And under warm key lights, metalness above ~0.6 renders any albedo warm-bronze: keep silver at ≤0.5; gold reads fine at 0.85.

## Non-lathe forms: the extrude path

Stiletto heels, ingots, stars, torsos are not rotationally symmetric — a lathe can't represent them. The generator's `extrude` primitive takes a `geometryDescriptor.profile2D` ({points: [[x,y]...], depth}) and works well, with three rules:

- Shift the profile points so Y spans 0..H, matching the body's attachment frame. A profile centered at origin makes every attached component float half a body above it.
- The strict validator's flatness gate requires depth/diagonal ≥ 0.15 — real perfume bottles are chunkier than they look; give the extrude real depth.
- Keep attached caps TINY on narrow features (a star's arm tip): a box cap wider than the feature pokes out and defaces the silhouette.

## Honest limits

A single photo cannot show the back, the base, or the thread detail. The spec records per-region confidence and the back-face assumption (mirrored, plain) instead of pretending certainty. Bottles whose every photo fails admission keep their procedural fallback model; the pipeline documents the blocker and moves on.
