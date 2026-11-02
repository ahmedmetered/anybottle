# Auto-iterate: read the diagnose JSON, patch lathe radii + preview fit,
# regenerate + rebundle. Usage: python iterate.py <bid> [diagnose-json-inline]
# Pass the diagnose JSON text as argv[2] (string) or default reads no-op.
import json, re, sys, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
FORGE = os.path.join(os.environ.get('IMG2THREEJS_HOME', os.path.join('..', 'img2threejs')), 'forge')

def main():
    bid = sys.argv[1]
    raw = sys.argv[2] if len(sys.argv) > 2 else f'runs/{bid}/diag.json'
    if os.path.exists(raw):
        raw = open(raw, encoding='utf-8').read()
    start = raw.find('{')
    d = json.loads(raw[start:]) if start >= 0 else {}
    checks = d.get('checks', {})
    iou = checks.get('silhouetteIoU', 0)
    aspect = checks.get('aspectRatioDelta', 0)
    scale = checks.get('scaleDelta', 0)

    spec_path = f'runs/{bid}/object-sculpt-spec.json'
    s = json.load(open(spec_path, encoding='utf-8'))
    changed = False
    # bbox-measured correction via the framework's foreground mask
    # (border-sampled background + connected components: immune to props/boxes)
    changed = False
    try:
        forge_intake = os.path.join(os.environ.get('IMG2THREEJS_HOME', os.path.join('..', 'img2threejs')), 'forge', 'stage1_intake')
        if forge_intake not in sys.path:
            sys.path.insert(0, forge_intake)
        from extract_pbr_evidence import build_foreground_mask

        def mask_bbox(path):
            img = Image.open(path).convert('RGB')
            img.thumbnail((384, 384))
            w, h = img.size
            px = img.load()
            pixels = [(px[x, y][0], px[x, y][1], px[x, y][2], 255) for y in range(h) for x in range(w)]
            mask, diag, _ = build_foreground_mask(w, h, pixels)
            # grid + largest 4-connected blob
            g = 96
            cell = [[False] * g for _ in range(g)]
            for idx, on in enumerate(mask):
                if not on:
                    continue
                x, y = idx % w, idx // w
                cell[min(g - 1, y * g // h)][min(g - 1, x * g // w)] = True
            best = []
            seen = [[False] * g for _ in range(g)]
            for gy in range(g):
                for gx in range(g):
                    if not cell[gy][gx] or seen[gy][gx]:
                        continue
                    stack, blob = [(gy, gx)], []
                    seen[gy][gx] = True
                    while stack:
                        cy, cx = stack.pop()
                        blob.append((cy, cx))
                        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                            ny, nx = cy+dy, cx+dx
                            if 0 <= ny < g and 0 <= nx < g and cell[ny][nx] and not seen[ny][nx]:
                                seen[ny][nx] = True
                                stack.append((ny, nx))
                    if len(blob) > len(best):
                        best = blob
            ys = [p[0] for p in best]; xs = [p[1] for p in best]
            bw = (max(xs)-min(xs)+1) / g
            bh = (max(ys)-min(ys)+1) / g
            return bw / max(bh, 0.01), bh

        meta = json.load(open(f'runs/{bid}/meta.json', encoding='utf-8'))
        ref_path = s['sourceImage']
        ra, rf = mask_bbox(ref_path)
        na, nf = mask_bbox(f'runs/{bid}/render-blockout-mapstripped.png')
        ratio = ra / max(na, 0.01)
        if abs(1 - ratio) > 0.05:
            f = max(0.75, min(1.3, ratio))
            for c in s['componentTree']:
                if c['id'] == 'body' and 'geometryDescriptor' in c:
                    pts = c['geometryDescriptor']['latheProfile']['points']
                    c['geometryDescriptor']['latheProfile']['points'] = [[round(r*f, 4), y] for r, y in pts]
                    changed = True
    except Exception as e:
        print('mask measure failed:', e)
    # frame correction: adjust fit factor in both previews
    if scale > 0.08 and 'nf' in dir():
        f = max(0.7, min(1.15, rf / max(nf, 0.01)))
        for pv in (f'runs/{bid}/preview.html', f'runs/{bid}/preview-stripped.html'):
            txt = open(pv, encoding='utf-8').read()
            # fitDist = size*0.5/tan(fov/2)/divisor: LARGER divisor = CLOSER camera.
            # The divisor may exceed 1 (e.g. `/ 1.056;`) — a `/ 0\.\d+` pattern
            # silently no-ops on it. Assert on the match, never trust a silent skip.
            m = re.search(r'/ ([0-9.]+);', txt)
            if m:
                cur = float(m.group(1))
                txt = txt.replace(m.group(0), f'/ {round(cur*f, 3)};')
                open(pv, 'w', encoding='utf-8').write(txt)
        scale = 0
    if scale > 0.08:
        f = max(0.7, min(1.1, 1.0 + scale * 0.5))
        for pv in (f'runs/{bid}/preview.html', f'runs/{bid}/preview-stripped.html'):
            txt = open(pv, encoding='utf-8').read()
            m = re.search(r'/ ([0-9.]+);', txt)
            if m:
                cur = float(m.group(1))
                txt = txt.replace(m.group(0), f'/ {round(cur*f, 3)};')
                open(pv, 'w', encoding='utf-8').write(txt)
    print(f'iterate {bid}: iou={iou} aspect={aspect} scale={scale} radii_changed={changed}')

if __name__ == '__main__':
    main()
