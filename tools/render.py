"""Render still frames.

    python tools/render.py OUTDIR "name|query" ["name|query" ...]

query is added to index.html?still=1, for example
    "planet|dest=<json>&u=0.03"   a planet from space (u = how far through the flight)
    "deep|region=3&seed=5&u=0.9"   deep in a Mandelbrot dive
    "obj|scene=obj&kind=4&seed=2&u=0.3"   a random 3D fractal object
Size with RW / RH (default 1920 x 1080 after cropping to 16:9).
"""
import os, sys

from ffpage import Page, crop16x9

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
W, H = int(os.environ.get("RW", 1920)), int(os.environ.get("RH", 1080))
page = Page(W, H + 160)
try:
    for arg in sys.argv[2:]:
        name, query = arg.split("|", 1)
        err = page.open(query + "&scale=1")
        crop16x9(page.image()).resize((W, H)).save(os.path.join(out, name + ".jpg"), quality=92)
        print(name, "error: " + err if err else "ok")
finally:
    page.close()
