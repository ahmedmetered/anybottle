# Rebuild browser-ready ES module bundles from the per-bottle factory sources,
# for wiring into a static site (importmap + native ESM, no bundler required).
#
# For every <id>.ts in --src-dir:
#   1. esbuild --bundle --external:three (+ the three jsm externals the generated
#      factories import) -> <out-dir>/<id>.bundle.mjs
#   2. patch "textureless" onto every material (solid authored colors, ZERO
#      network texture requests -> no 404s on a deployed site)
#   3. insert "baseColor" beside every material "color" key
#      (the generator's clampedAlbedoColor reads spec.baseColor; the material
#      defs carry spec.color. Without baseColor every material silently falls
#      back to the same #8A7A5F tan. textureless and baseColor are a PAIR.)
#   4. optionally emit a registry.js: `export const registry = { <id>: <ns>, ... }`
#
# Usage:
#   python rebuild_bundles.py --src-dir site/js/models --out-dir site/js/models \
#       [--ids a,b,c] [--registry site/js/models/registry.js]
#
# Assumes <out-dir> already holds the factory .ts sources (copy them from
# runs/<id>/src/createObjectModel.ts first). esbuild is fetched via npx.
#
# THE STALE-ARTIFACT RULE: never trust a bundle or .ts that predates its spec's
# last edit. When in doubt, regenerate the .ts from runs/<id>/object-sculpt-spec.json
# (generate_threejs_factory.py --pass-id blockout --force) BEFORE bundling — the
# spec is the only source of truth; hand-fixes edit specs, not generated code.
import argparse, os, re, subprocess

JSM_EXTERNALS = [
    '--external:three',
    '--external:three/examples/jsm/environments/RoomEnvironment.js',
    '--external:three/examples/jsm/postprocessing/EffectComposer.js',
    '--external:three/examples/jsm/postprocessing/OutputPass.js',
]

def patch_bundle(path):
    t = open(path, encoding='utf-8').read()
    n = t.count('"referencePbr"')
    assert n > 0, f'{path}: no referencePbr found (not a generated factory?)'
    if '"textureless"' not in t:
        t = t.replace('"referencePbr": {', '"textureless": {"declared": true}, "referencePbr": {')
        assert t.count('"textureless"') == n, f'{path}: textureless insert mismatch'
    if '"baseColor"' not in t:
        mids = re.findall(r'materialMap\["([^"]+)"\] = createSculptMaterial', t)
        assert len(mids) >= 1, f'{path}: materialMap assignments not found'
        for mid in mids:
            i = -1
            for a in ('{ "id": "%s",' % mid, '{"id": "%s",' % mid):
                i = t.find(a)
                if i >= 0:
                    break
            assert i >= 0, f'{path}: no material def for {mid}'
            j = t.find('"color": "#', i)
            assert 0 <= j < i + 2000, f'{path}: color key not near {mid} def'
            k = t.find('"', j + 11)
            value = t[j + 9:k + 1]  # the quoted hex only
            assert value.startswith('"#'), f'{path}: bad color slice {value!r}'
            t = t[:j] + f'"baseColor": {value}, ' + t[j:]
    open(path, 'w', encoding='utf-8').write(t)
    return n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True, help='dir holding <id>.ts factory sources')
    ap.add_argument('--out-dir', required=True, help='dir to write <id>.bundle.mjs into')
    ap.add_argument('--ids', help='comma-separated subset of ids (default: every .ts)')
    ap.add_argument('--registry', help='optional path for a generated registry.js')
    args = ap.parse_args()

    if args.ids:
        ids = [i.strip() for i in args.ids.split(',') if i.strip()]
    else:
        ids = sorted(os.path.splitext(f)[0] for f in os.listdir(args.src_dir) if f.endswith('.ts'))
    assert ids, 'no factory sources found'

    for bid in ids:
        ts = os.path.join(args.src_dir, f'{bid}.ts')
        assert os.path.exists(ts), f'missing {ts}'
        out = os.path.join(args.out_dir, f'{bid}.bundle.mjs')
        r = subprocess.run(['npx', '--yes', 'esbuild@0.25.0', ts, '--bundle', '--format=esm',
                            *JSM_EXTERNALS, f'--outfile={out}'],
                           capture_output=True, text=True, shell=(os.name == 'nt'))
        assert r.returncode == 0, f'{bid}: esbuild failed: {r.stderr[-300:]}'
        n = patch_bundle(out)
        print(f'-- {bid}: bundle ok ({n} materials textureless+baseColor)')

    if args.registry:
        lines = []
        reg = []
        for i, bid in enumerate(ids):
            lines.append(f'import * as _m{i} from "./{bid}.bundle.mjs";')
            reg.append(f'  "{bid}": _m{i},')
        src = '\n'.join(lines) + '\n\nexport const registry = {\n' + '\n'.join(reg) + '\n};\n'
        open(args.registry, 'w', encoding='utf-8').write(src)
        print(f'registry written: {args.registry} ({len(ids)} entries)')

if __name__ == '__main__':
    main()
