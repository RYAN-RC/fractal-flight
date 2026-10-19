"""Render every favourite in discovered.js, with its sky, as one named gallery image.

    python tools/gallery.py OUT.jpg
"""
import json, sys, urllib.parse

from PIL import Image, ImageDraw, ImageFont

from ffpage import Page, crop16x9, load_discovered

KINDS = ["Mandelbulb", "Mandelbox", "Menger Sponge", "Quaternion Julia", "Kaleidoscope Crystal", "Apollonian Foam"]
objects, planets = load_discovered()
page = Page(800, 520, port=9349)
tiles = []
try:
    for p in planets:
        page.open(f"seed={11 + len(tiles)}&u=0.03&dest={urllib.parse.quote(json.dumps(p))}")
        tiles.append((page.image(), p["name"], p["region"]))
    for g in objects:
        page.open(f"scene=obj&seed={11 + len(tiles)}&u=0.22&genome={urllib.parse.quote(json.dumps(g))}")
        tiles.append((page.image(), g["name"], KINDS[g["kind"]]))
finally:
    page.close()

cols, tw, th = 6, 480, 270
sheet = Image.new("RGB", (cols * tw, ((len(tiles) + cols - 1) // cols) * (th + 34)), (8, 8, 12))
draw = ImageDraw.Draw(sheet)
try:
    bold, small = ImageFont.truetype("segoeuib.ttf", 18), ImageFont.truetype("segoeui.ttf", 14)
except OSError:
    bold = small = ImageFont.load_default()
for i, (im, name, sub) in enumerate(tiles):
    x, y = (i % cols) * tw, (i // cols) * (th + 34)
    sheet.paste(crop16x9(im).resize((tw, th)), (x, y))
    draw.text((x + 10, y + th + 4), name, fill=(240, 240, 245), font=bold)
    draw.text((x + 20 + draw.textlength(name, font=bold), y + th + 8), sub, fill=(150, 150, 165), font=small)
sheet.save(sys.argv[1] if len(sys.argv) > 1 else "gallery.jpg", quality=88)
print(len(tiles), "tiles")
