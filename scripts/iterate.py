# Auto-iterate: read the diagnose JSON, patch lathe radii + preview fit,
# regenerate + rebundle. Usage: python iterate.py <bid> [diagnose-json-inline]
# Pass the diagnose JSON text as argv[2] (string) or default reads no-op.
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
FORGE = os.path.join(os.environ.get('IMG2THREEJS_HOME', os.path.join('..', 'img2threejs')), 'forge')

def main():
    bid = sys.argv[1]
    raw = sys.argv[2] if len(sys.argv) > 2 else '{}'
    start = raw.find('{')
    d = json.loads(raw[start:]) if start >= 0 else {}
    checks = d.get('checks', {})
    iou = checks.get('silhouetteIoU', 0)
    aspect = checks.get('aspectRatioDelta', 0)
    scale = checks.get('scaleDelta', 0)

    spec_path = f'runs/{bid}/object-sculpt-spec.json'
    s = json.load(open(spec_path, encoding='utf-8'))
    changed = False
    # bbox-measured correction: exact aspect ratio ref/render -> radii factor
    try:
        from PIL import Image
        def bbox(path):
            img = Image.open(path).convert('RGB'); w, h = img.size; px = img.load()
            bg = px[3, h//2]
            minx, miny, maxx, maxy = w, h, 0, 0
            for y in range(0, h, 3):
                for x in range(0, w, 3):
                    r, g, b = px[x, y]
                    if abs(r-bg[0]) + abs(g-bg[1]) + abs(b-bg[2]) > 54:
                        minx = min(minx, x); maxx = max(maxx, x); miny = min(miny, y); maxy = max(maxy, y)
            return (maxx-minx)/max(maxy-miny, 1), (maxy-miny)/h
        meta = json.load(open(f'runs/{bid}/meta.json', encoding='utf-8'))
        ref_path = s['sourceImage']
        ra, rf = bbox(ref_path)
        na, nf = bbox(f'runs/{bid}/render-blockout-mapstripped.png')
        ratio = ra / max(na, 0.01)
        if abs(1 - ratio) > 0.05:
            f = max(0.75, min(1.3, ratio))
            for c in s['componentTree']:
                if c['id'] == 'body' and 'geometryDescriptor' in c:
                    pts = c['geometryDescriptor']['latheProfile']['points']
                    c['geometryDescriptor']['latheProfile']['points'] = [[round(r*f, 4), y] for r, y in pts]
                    changed = True
    except Exception as e:
        print('bbox measure failed:', e)
    if changed:
        json.dump(s, open(spec_path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        # regenerate + rebundle
        subprocess_r = os.system(f'python {FORGE}/stage3_build/generate_threejs_factory.py {spec_path} --out runs/{bid}/src/createObjectModel.ts --pass-id blockout --force')
        if subprocess_r == 0:
            os.system(f'cd runs/{bid} && npx --yes esbuild@0.25.0 src/createObjectModel.ts --bundle --format=esm --external:three --outfile=src/createObjectModel.bundle.mjs')
    # frame correction: adjust fit factor in both previews
    if scale > 0.08 and 'nf' in dir():
        f = max(0.7, min(1.15, rf / max(nf, 0.01)))
        scale = 0
    if scale > 0.08:
        f = max(0.7, min(1.1, 1.0 + scale * 0.5))
        for pv in (f'runs/{bid}/preview.html', f'runs/{bid}/preview-stripped.html'):
            txt = open(pv, encoding='utf-8').read()
            m = re.search(r'/ (0\.\d+);', txt)
            if m:
                cur = float(m.group(1))
                txt = txt.replace(m.group(0), f'/ {round(cur*f, 3)};')
                open(pv, 'w', encoding='utf-8').write(txt)
    print(f'iterate {bid}: iou={iou} aspect={aspect} scale={scale} radii_changed={changed}')

if __name__ == '__main__':
    main()
