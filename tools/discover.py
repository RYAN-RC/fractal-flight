"""Discovery sweep for 3D fractal objects.

    python tools/discover.py OUTDIR N_PER_KIND [kinds...]

Kinds: 0 Mandelbulb, 1 Mandelbox, 2 Menger sponge, 3 quaternion Julia,
4 kaleidoscopic IFS, 5 Apollonian foam. For each kind the page renders N random
genomes from a standard viewpoint on black (index.html?discover=N&kind=K), resizes
each to a common size from its measured extent and measures it. Here every one gets a
score (detail x contrast x colour x coverage); OUTDIR gets every render,
results.json, and a contact sheet of the top 24 per kind to pick favourites from.
Favourites go into discovered.js (window.DISCOVERED) with a "name".
"""
import json, os, sys, time

from PIL import Image, ImageDraw

from ffpage import Page

out, n = sys.argv[1], int(sys.argv[2])
kinds = [int(k) for k in sys.argv[3:]] or [0, 1, 2, 3, 4, 5]
os.makedirs(out, exist_ok=True)


def score(st):
    if st["cov"] < 0.01:
        return 0.0
    cov_ok = min(1.0, st["cov"] / 0.06) * (1.0 if st["cov"] < 0.55 else 0.5)
    return st["detail"] * (0.5 + st["contrast"] / 60.0) * (0.75 + min(st["chroma"], 120) / 240.0) * cov_ok


page = Page(640, 360, port=9347)
try:
    results = []
    for kind in kinds:
        t0 = time.time()
        err = page.open(f"nosky=1&discover={n}&kind={kind}&dseed={1000 + kind * 77}", timeout=900)
        count = page.ev("window.__disc ? window.__disc.length : 0") or 0
        res = []
        for i in range(count):
            rec = json.loads(page.ev(f"JSON.stringify({{g: window.__disc[{i}].g, st: window.__disc[{i}].st}})"))
            rec["score"] = score(rec["st"])
            rec["file"] = f"k{kind}_{i:03d}.jpg"
            page.image(f"window.__disc[{i}].img").save(os.path.join(out, rec["file"]), quality=88)
            res.append(rec)
        res.sort(key=lambda r: -r["score"])
        results += res
        sheet = Image.new("RGB", (6 * 320, 4 * 180))
        draw = ImageDraw.Draw(sheet)
        for j, rec in enumerate(res[:24]):
            sheet.paste(Image.open(os.path.join(out, rec["file"])).resize((320, 180)), ((j % 6) * 320, (j // 6) * 180))
            draw.text(((j % 6) * 320 + 6, (j // 6) * 180 + 4), f"{rec['file'][:-4]} {rec['score']:.0f}", fill=(255, 255, 255))
        sheet.save(os.path.join(out, f"sheet_k{kind}.jpg"), quality=86)
        print(f"kind {kind}: {count} in {time.time() - t0:.0f}s" + (f" error: {err}" if err else ""))
    json.dump(results, open(os.path.join(out, "results.json"), "w"), indent=1)
finally:
    page.close()
