"""How colourful and how jumpy the colours are.

    python tools/colorfulness.py OUTDIR "name|query" ...

Renders SEQ frames (default 30) of each scene and reports
  colorful   Hasler-Suesstrunk colourfulness of the middle frame (~15 dull, ~60 vivid, ~100+ garish)
  chroma     mean saturation-like spread, max(R,G,B) - min(R,G,B), 0-255
  hues       how many distinct hue bins (of 24) cover 2% or more of the picture
  hueshift   mean per-frame change of hue on coloured pixels, degrees (colour flicker)
and saves the middle frame for side-by-side comparison.
"""
import colorsys, os, sys

import numpy as np

from ffpage import Page

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
N = int(os.environ.get("SEQ", 30))
page = Page(int(os.environ.get("RW", 1280)), int(os.environ.get("RH", 720)), port=9351)


def hue(img):
    a = img / 255.0
    mx, mn = a.max(2), a.min(2)
    d = mx - mn + 1e-6
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, (g - b) / d, np.where(mx == g, 2 + (b - r) / d, 4 + (r - g) / d))
    return (h * 60) % 360, d


try:
    for arg in sys.argv[2:]:
        name, query = arg.split("|", 1)
        err = page.open(f"seq={N}&{query}")
        frames = [np.asarray(page.image(f"window.__frames[{k}]")).astype(np.float32) for k in range(N)
                  if page.ev(f"!!(window.__frames && window.__frames[{k}])")]
        mid = frames[len(frames) // 2]
        rg = mid[..., 0] - mid[..., 1]
        yb = 0.5 * (mid[..., 0] + mid[..., 1]) - mid[..., 2]
        colorful = np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean())
        chroma = (mid.max(2) - mid.min(2)).mean()
        h, d = hue(mid)
        hist = np.histogram(h[d > 0.15], bins=24, range=(0, 360))[0]
        hues = int((hist > 0.02 * h.size).sum())
        shifts = []
        for k in range(len(frames) - 1):
            h1, d1 = hue(frames[k])
            h2, d2 = hue(frames[k + 1])
            m = (d1 > 0.2) & (d2 > 0.2)
            dh = np.abs(h1 - h2)[m]
            shifts.append(np.minimum(dh, 360 - dh).mean() if m.any() else 0)
        from PIL import Image
        Image.fromarray(mid.astype(np.uint8)).save(os.path.join(out, name + ".jpg"), quality=88)
        print(f"{name}: colorful={colorful:.0f} chroma={chroma:.0f} hues={hues} hueshift={np.mean(shifts):.2f}deg" + (f" error: {err}" if err else ""))
finally:
    page.close()
