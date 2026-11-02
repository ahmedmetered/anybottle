---
name: anybottle
description: Turn bottle product photos into quality-gated procedural Three.js models, measured from the image. Use when batch-reconstructing bottles (perfume, beverage, cosmetics) from reference photos into runtime-built 3D models.
---

# anybottle

Measured, quality-gated reconstruction of bottle photos into procedural Three.js factories. Orchestration layer over the [img2threejs](https://github.com/img2threejs/img2threejs) pipeline (Apache-2.0; clone it to `../img2threejs` or set `IMG2THREEJS_HOME`).

## When to use

You have one clean product photo per bottle (full bottle in frame, plain background) and want runtime-built Three.js models gated against the photo, not hand-modeled meshes or downloaded assets.

## The loop

Full recipe with pitfalls: [docs/recipe.md](docs/recipe.md). Short form:

1. `python -I scripts/batch_pipeline.py <ids...>` — measures silhouette, palette, cap from each photo; emits strict-valid img2threejs specs; generates TypeScript factories + headless preview pages.
2. Serve `runs/` over HTTP, capture render + map-stripped render with `scripts/capture.mjs`.
3. `python ../../../img2threejs/forge/stage4_review/diagnose_render.py ...` (from the run dir) — deterministic gates: silhouette IoU, aspect delta, scale delta, bilateral symmetry.
4. `python -I scripts/iterate.py <id> "$(cat runs/<id>/diag.json)"` — bbox-measured corrections; regenerate; re-diagnose.
5. To ship into a static site: copy `runs/<id>/src/createObjectModel.ts` into the site, then `python -I scripts/rebuild_bundles.py --src-dir site/js/models --out-dir site/js/models --registry site/js/models/registry.js` — esbuild-bundles each factory and applies the mandatory textureless + baseColor patches (docs/recipe.md explains why both).

Ship gates: IoU >= 0.85, aspect <= 0.05, scale <= 0.08. Two correction iterations per pass, then stop honestly.

## Hard rules

- Reference admission is deterministic (`check_reference_admission.py` from img2threejs). A cropped, tilted, or fragmented photo is rejected before any work is spent on it.
- The spec validator is fail-closed. Never hand-patch generated code; fix the spec. The spec is the only source of truth — a bundle or .ts older than its spec's last edit is a stale artifact; regenerate before shipping.
- Lathe profiles are bottom-up. A measured top-down profile must be flipped before use. Extrude profile2D points must span 0..H to match attachment frames.
- Corrections are measured (reference bbox / render bbox), never sign-guessed. Assert every template/regex patch; a non-matching pattern is a silent no-op.
- Single-view reconstruction: state the back-face assumption and per-region confidence instead of faking certainty.

## Layout

```
bottles.json       bottle descriptions (id, name, house, print lines)
images/            admitted reference photos, one per bottle (gitignored)
runs/<id>/         per-bottle spec, factory, previews, renders, diagnostics
scripts/           the pipeline
```
