"""Discovery sweep for Mandelbrot planets.

    python tools/planet_discover.py OUTDIR PER_REGION

Node runs finder.js to pick PER_REGION destinations in each famous region; each is
rendered mid-dive and at the end, the ground's detail is scored, and OUTDIR gets
planets.json plus a contact sheet of the best 16. Favourites go into discovered.js
(window.DISCOVERED_PLANETS) with a "name". Needs Node.js.
"""
import json, os, subprocess, sys, urllib.parse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ffpage import Page

out, per = sys.argv[1], int(sys.argv[2])
os.makedirs(out, exist_ok=True)
finder = (Path(__file__).resolve().parents[1] / "finder.js").as_posix()
node = f"""
const F = require({json.dumps(finder)})();
const res = [];
for (let ri = 0; ri < F.REGIONS.length; ri++) for (let k = 0; k < {per}; k++) {{
  const d = F.findDestination(50000 + ri * 101 + k * 7, {{ region: ri, refCap: 10 }});
  if (d && d.regionIndex === ri) res.push({{ x: d.x, y: d.y, period: d.period, size: d.size, region: d.region, regionIndex: ri }});
}}
console.log(JSON.stringify(res));
"""
cands = json.loads(subprocess.check_output(["node", "-e", node], text=True))
print(len(cands), "candidates")


def detail(img):
    a = np.asarray(img).astype(np.float32)[img.height // 3:]     # the ground, not the sky
    lum = a @ np.array([0.3, 0.55, 0.15], np.float32)
    grad = np.abs(np.diff(lum, axis=1)).mean() + np.abs(np.diff(lum, axis=0)).mean()
    chroma = (a.max(2) - a.min(2)).mean()
    dark = (lum < 25).mean()
    return float(grad * (0.6 + chroma / 150) * (1.0 - 0.7 * max(0.0, dark - 0.35)))


page = Page(480, 400, port=9348)
try:
    for i, c in enumerate(cands):
        q = urllib.parse.quote(json.dumps(c))
        shots = []
        for u in (0.55, 0.92):
            page.open(f"seed=7&u={u}&dest={q}")
            shots.append(page.image())
        c["score"] = detail(shots[0]) + detail(shots[1])
        c["file"] = f"p{i:03d}.jpg"
        pair = Image.new("RGB", (shots[0].width * 2, shots[0].height))
        pair.paste(shots[0], (0, 0))
        pair.paste(shots[1], (shots[0].width, 0))
        pair.save(os.path.join(out, c["file"]), quality=86)
    cands.sort(key=lambda c: -c["score"])
    json.dump(cands, open(os.path.join(out, "planets.json"), "w"), indent=1)
    tw, th = 960, 270
    sheet = Image.new("RGB", (2 * tw, 8 * th))
    draw = ImageDraw.Draw(sheet)
    for j, c in enumerate(cands[:16]):
        sheet.paste(Image.open(os.path.join(out, c["file"])).resize((tw, th)), ((j % 2) * tw, (j // 2) * th))
        draw.text(((j % 2) * tw + 6, (j // 2) * th + 4), f"{c['file'][:-4]} {c['region']} p={c['period']} {c['score']:.0f}", fill=(255, 255, 255))
    sheet.save(os.path.join(out, "sheet.jpg"), quality=84)
finally:
    page.close()
