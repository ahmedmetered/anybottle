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

## Honest limits

A single photo cannot show the back, the base, or the thread detail. The spec records per-region confidence and the back-face assumption (mirrored, plain) instead of pretending certainty. Bottles whose every photo fails admission keep their procedural fallback model; the pipeline documents the blocker and moves on.
