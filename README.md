# anybottle

Turn a product photo of a bottle into a quality-gated procedural Three.js model, measured from the image. Built to mass-produce perfume-bottle 3D models for [Perfume Finder](https://ahmedmetered.github.io/perfume-finder/), where every result renders its own bottle at runtime. Works for any roughly rotationally symmetric bottle: flacons, columns, orbs, tapers, urns.

The method is reconstruction-by-code: no photogrammetry, no mesh extraction, no downloaded assets. The silhouette is measured from the photo, the spec is authored by a script, and the [img2threejs](https://github.com/img2threejs/img2threejs) pipeline gates the result before it ships.

**Status:** the pilot bottle reached silhouette IoU 0.80 against its reference within two automatic correction iterations, from nothing but the photo. 39 of 40 bottles of the first production run are through the pipeline and live — every result on [Perfume Finder](https://ahmedmetered.github.io/perfume-finder/) renders its own measured factory at runtime; the one reference-blocked bottle keeps its documented procedural fallback.

## How it works

1. **Measure** (`measure_bottle.py`) — reads the reference photo, segments the bottle from the background, takes a per-row width profile, finds the neck (the width minimum between cap and belly), and derives a lathe profile, cap dimensions, and material colors sampled from the image. Emits an img2threejs `ObjectSculptSpec`.
2. **Validate** — the img2threejs validator holds the spec to its strict schema: attachment contracts, material PBR evidence, lighting intent, detail inventory. Fail-closed; a shallow spec never becomes code.
3. **Generate** — img2threejs's fail-closed generator turns the spec into a TypeScript factory that builds the model procedurally at runtime.
4. **Render + diagnose** — a headless Chromium capture of the factory render is compared against the reference photo: silhouette IoU, aspect-ratio delta, scale delta, bilateral symmetry.
5. **Iterate** (`iterate.py`) — measures both bounding boxes and applies the exact aspect ratio as a radii correction and the height fraction as a frame correction, then regenerates and re-diagnoses. Two iterations per pass, bounded.

The `batch_pipeline.py` driver runs steps 1-3 for a list of bottles; `iterate.py` closes the loop.

## Requirements

- Python 3.10+ with Pillow (`pip install pillow`)
- Node 18+ with Playwright (`npm i playwright`) and a Chromium install
- The [img2threejs](https://github.com/img2threejs/img2threejs) repo (Apache-2.0) cloned next to this one, or pointed at via `IMG2THREEJS_HOME`
- esbuild (fetched on demand via `npx`)

Expected layout (or set `IMG2THREEJS_HOME` and `CHROME_PATH`):

```
parent/
├── anybottle/        <- this repo
└── img2threejs/      <- the framework checkout
```

## Usage

Describe your bottles in `bottles.json` (see `examples/`), put one admitted reference photo per bottle in `images/` as `<id>.png`, then:

```
python -I scripts/batch_pipeline.py bottle-id-1 bottle-id-2     # measure, validate, generate, preview
# serve runs/ on :8792, then per bottle:
node scripts/capture.mjs http://localhost:8792/<id>/preview.html runs/<id>/render-blockout.png 3000
node scripts/capture.mjs http://localhost:8792/<id>/preview-stripped.html runs/<id>/render-blockout-mapstripped.png 3000
python scripts/iterate.py <id> "$(cat runs/<id>/diag.json)"     # bbox-measured correction pass
# ship to a static site (importmap + native ESM):
cp runs/<id>/src/createObjectModel.ts site/js/models/<id>.ts
python -I scripts/rebuild_bundles.py --src-dir site/js/models --out-dir site/js/models --registry site/js/models/registry.js
```

Gate targets before a bottle ships: silhouette IoU >= 0.85, aspect delta <= 0.05, scale delta <= 0.08 against the reference.

## What we learned

Documented in `docs/recipe.md`, but the short version: the internet's most common perfume photos are unusable as reconstruction references (tilted affiliate shots, cropped bottles, flanker variants), frosted white bottles defeat foreground segmentation on white backgrounds, three.js lathes run bottom-up so a measured top-down profile must be flipped, and guess-based correction signs are unreliable — measure both bounding boxes and apply the exact ratio.

## License

MIT. The img2threejs framework this orchestrates is Apache-2.0, by its authors.
