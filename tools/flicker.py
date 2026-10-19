"""Measure how calm the picture is.

    python tools/flicker.py OUTDIR "name|query" ...

Renders SEQ frames (default 45) in a row at the page's frame rate (add &fps=30 or
&fps=60 to the query) and reports, per scene:
  blinking  share of pixels whose brightness jumps (second temporal difference > 24/255),
            the thing that reads as flashing or sparkling
  flicker   mean second temporal difference (smooth motion keeps it low)
  motion    mean change between frames
  step95    95th percentile of how far content moves between frames, in pixels
            (phase correlation on 64 px tiles); big steps read as strobing
It also saves a heatmap of where the blinking is.
"""
import os, sys

import numpy as np
from PIL import Image

from ffpage import Page

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
N = int(os.environ.get("SEQ", 45))
page = Page(int(os.environ.get("RW", 1280)), int(os.environ.get("RH", 720)), port=9346)
try:
    for arg in sys.argv[2:]:
        name, query = arg.split("|", 1)
        err = page.open(f"seq={N}&{query}")
        frames = []
        for k in range(N):
            if not page.ev(f"!!(window.__frames && window.__frames[{k}])"):
                break
            frames.append(np.asarray(page.image(f"window.__frames[{k}]")).astype(np.float32))
        if len(frames) < 3:
            print(name, "no frames", err)
            continue
        luma = [f @ np.array([0.299, 0.587, 0.114], np.float32) for f in frames]
        d2 = [np.abs(luma[k + 1] - 2 * luma[k] + luma[k - 1]) for k in range(1, len(luma) - 1)]
        heat = np.mean([(d > 24) for d in d2], axis=0)
        base = (frames[len(frames) // 2] * 0.5).astype(np.uint8)
        base[..., 0] = np.maximum(base[..., 0], (np.clip(heat * 4, 0, 1) * 255).astype(np.uint8))
        Image.fromarray(base).save(os.path.join(out, f"{name}_heat.jpg"), quality=88)
        steps = []
        for k in range(0, len(luma) - 1, 4):
            a, b = luma[k], luma[k + 1]
            for y in range(0, a.shape[0] - 64, 64):
                for x in range(0, a.shape[1] - 64, 64):
                    ta, tb = a[y:y + 64, x:x + 64], b[y:y + 64, x:x + 64]
                    if ta.std() < 6:
                        continue
                    F = np.fft.fft2(ta - ta.mean()) * np.conj(np.fft.fft2(tb - tb.mean()))
                    r = np.fft.ifft2(F / (np.abs(F) + 1e-6)).real
                    py, px = np.unravel_index(np.argmax(r), r.shape)
                    steps.append(np.hypot(px if px < 32 else px - 64, py if py < 32 else py - 64))
        print(f"{name}: blinking={np.mean([(d > 24).mean() for d in d2]) * 100:.2f}% "
              f"flicker={np.mean([d.mean() for d in d2]):.2f} "
              f"motion={np.mean([np.abs(luma[k + 1] - luma[k]).mean() for k in range(len(luma) - 1)]):.2f} "
              f"step95={float(np.percentile(steps, 95)) if steps else 0:.1f}px" + (f" error: {err}" if err else ""))
finally:
    page.close()
