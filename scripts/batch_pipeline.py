# Batch driver: for each bottle with an admitted reference, measure palette,
# emit spec via measure_bottle.py, strict-validate, generate factory, bundle.
# Usage: python batch_pipeline.py <id1> <id2> ...
# Reads meta from bottles.json; reference = images/<id>*.png (first admitted variant per ledger).
import json, os, subprocess, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
FORGE = os.path.join(os.environ.get('IMG2THREEJS_HOME', os.path.join('..', 'img2threejs')), 'forge')

def palette_from(ref, regions):
    from PIL import Image
    img = Image.open(ref).convert('RGB')
    w, h = img.size
    def avg(l, t, r, b):
        px = img.crop((int(w*l), int(h*t), int(w*r), int(h*b))).resize((8, 8))
        p = px.load()
        rs = [p[x, y] for x in range(8) for y in range(8)]
        n = len(rs)
        return '#%02X%02X%02X' % tuple(sum(c[i] for c in rs)//n for i in range(3))
    return {k: avg(*v) for k, v in regions.items()}

def find_ref(bid):
    # first existing png matching <id>* (prefer -ref, then c-variants)
    cands = [f'images/{bid}-ref.png', f'images/{bid}.png', f'images/{bid}-c1.png',
             f'images/{bid}-c2.png', f'images/{bid}-c3.png', f'images/{bid}-c4.png']
    for c in cands:
        if os.path.exists(c):
            return c
    return None

def main():
    bottles = json.load(open('bottles.json', encoding='utf-8'))
    results = {}
    for bid in sys.argv[1:]:
        entry = bottles.get(bid)
        if not entry:
            print(f'!! {bid}: no bottles.json entry'); continue
        ref = find_ref(bid)
        if not ref:
            print(f'!! {bid}: no reference png'); continue
        rundir = f'runs/{bid}'
        os.makedirs(rundir, exist_ok=True)
        # 1. palette
        regions = entry.get('regions', {
            'body': (.3, .55, .7, .78), 'cap': (.36, .02, .64, .14),
            'collar': (.34, .16, .66, .24), 'ink': (.3, .4, .7, .5)
        })
        pal = palette_from(ref, regions)
        meta = {
            'id': bid, 'palette': pal,
            'family': entry.get('family', 'eau de parfum'),
            'print': {'lines': entry.get('printLines', [entry['house'].upper(), entry['name'].upper()])},
        }
        meta_path = os.path.join(rundir, 'meta.json')
        json.dump(meta, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False)
        # 2. spec
        spec_path = os.path.join(rundir, 'object-sculpt-spec.json')
        r = subprocess.run([sys.executable, 'measure_bottle.py', ref, entry['name'], entry['house'],
                            spec_path, meta_path], capture_output=True, text=True)
        if r.returncode != 0:
            print(f'!! {bid}: measure failed: {r.stderr[-200:]}'); continue
        print(f'-- {bid}: {r.stdout.strip().splitlines()[-1]}')
        # 3. strict validate
        r = subprocess.run([sys.executable, os.path.join(FORGE, 'stage2_spec', 'validate_sculpt_spec.py'),
                            spec_path, '--strict-quality'], capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()
        if 'PASS' not in (r.stdout + r.stderr):
            print(f'!! {bid}: strict FAIL: {tail[-1][:160] if tail else "no output"}')
            results[bid] = 'strict-fail'
            continue
        print(f'-- {bid}: strict PASS')
        # 4. generate factory
        r = subprocess.run([sys.executable, os.path.join(FORGE, 'stage3_build', 'generate_threejs_factory.py'),
                            spec_path, '--out', os.path.join(rundir, 'src', 'createObjectModel.ts'),
                            '--pass-id', 'blockout', '--force'], capture_output=True, text=True)
        if r.returncode != 0:
            print(f'!! {bid}: generate failed: {r.stderr[-200:]}'); continue
        print(f'-- {bid}: factory generated')
        # 5. read export names from the generated TS (bundling happens in bash step)
        ts = open(os.path.join(rundir, 'src', 'createObjectModel.ts'), encoding='utf-8').read()
        m_model = re.search(r'export function (create\w+Model)\(', ts)
        m_lights = re.search(r'export function (create\w+LookDevLights)\(', ts)
        if not m_model:
            print(f'!! {bid}: no model export found'); continue
        model_fn = m_model.group(1)
        lights_fn = m_lights.group(1) if m_lights else None
        # 6. preview + strip preview (from template, rewritten imports)
        tpl = open('preview-template.html', encoding='utf-8').read()
        tpl = tpl.replace('__MODEL_FN__', model_fn)
        if lights_fn:
            tpl = tpl.replace('__LIGHTS_IMPORT__', f", {lights_fn}").replace(
                "__LIGHTS_ADD__", f"scene.add({lights_fn}('reference'));")
        else:
            tpl = tpl.replace('__LIGHTS_IMPORT__', '').replace('__LIGHTS_ADD__', '')
        open(os.path.join(rundir, 'preview.html'), 'w', encoding='utf-8').write(tpl)
        stripped = tpl.replace(
            f"const model = {model_fn}({{ qualityPriority: 'reference-fidelity' }});",
            f"const model = {model_fn}({{ qualityPriority: 'reference-fidelity' }});\n"
            "model.traverse(o => { if (o.isMesh) o.material = new THREE.MeshBasicMaterial({ color: 0xE8E8E8 }); });")
        open(os.path.join(rundir, 'preview-stripped.html'), 'w', encoding='utf-8').write(stripped)
        results[bid] = 'ok'
    json.dump(results, open('batch-results.json', 'w', encoding='utf-8'), indent=1)
    print('batch done:', results)

if __name__ == '__main__':
    main()
