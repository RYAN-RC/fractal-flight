"""Shared helpers: drive Fractal Flight in headless Chrome over the DevTools protocol.

Needs Chrome (set CHROME to its path if it is not in the usual place) and
`pip install websocket-client numpy pillow`.
"""
import base64, io, json, os, shutil, subprocess, tempfile, time, urllib.request
from pathlib import Path

import websocket
from PIL import Image

PAGE = (Path(__file__).resolve().parents[1] / "index.html").as_uri()


def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
        if os.path.exists(c):
            return c
    for name in ["google-chrome", "chromium", "chromium-browser", "chrome"]:
        if shutil.which(name):
            return shutil.which(name)
    raise SystemExit("Chrome not found: set CHROME to its path")


class Page:
    """A headless Chrome tab using the real GPU (ANGLE/D3D11 on Windows)."""

    def __init__(self, width=1280, height=720, port=9341):
        flags = [find_chrome(), "--headless=new", f"--remote-debugging-port={port}", "--remote-allow-origins=*",
                 f"--user-data-dir={tempfile.mkdtemp(prefix='ffchrome')}", f"--window-size={width},{height}",
                 "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--enable-gpu",
                 "--ignore-gpu-blocklist", "about:blank"]
        if os.name == "nt":
            flags.insert(-1, "--use-angle=d3d11")
        self.proc = subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                tab = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")) if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], suppress_origin=True, timeout=900)
        self.mid = 0

    def call(self, method, **params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m.get("result", m)

    def ev(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True)
        return r.get("result", {}).get("value")

    def open(self, query, timeout=300):
        """Load index.html?still=1&<query> and wait until it says done. Returns the error text, if any."""
        self.call("Page.navigate", url=f"{PAGE}?still=1&labels=0&{query}&_={time.time()}")
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.3)
            st = self.ev("document.title + '|' + (document.getElementById('err') || {}).textContent")
            if st and (st.startswith("done") or (st.split("|", 1)[1] not in ("", "undefined"))):
                break
        return self.ev("document.getElementById('err').textContent")

    def image(self, expr="document.getElementById('c').toDataURL('image/jpeg', 0.92)"):
        d = self.ev(expr)
        return Image.open(io.BytesIO(base64.b64decode(d.split(",", 1)[1]))).convert("RGB")

    def close(self):
        self.proc.kill()


def crop16x9(im):
    w, h = im.size
    ch = min(h, w * 9 // 16)
    cw = ch * 16 // 9
    return im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch))


def load_discovered():
    """The favourites in discovered.js: (objects, planets)."""
    src = (Path(__file__).resolve().parents[1] / "discovered.js").read_text(encoding="utf-8")
    def grab(name):
        a = src.index("window." + name + " = ") + len("window." + name + " = ")
        b = src.index("];", a) + 1
        return json.loads(src[a:b])
    return grab("DISCOVERED"), grab("DISCOVERED_PLANETS")
