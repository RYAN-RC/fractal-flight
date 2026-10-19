/* Fractal Flight: picks deep, interesting Mandelbrot destinations.
   The page runs this inside a Web Worker (it stringifies finderModule), or on
   the main thread when a worker is not available. Node can require it for tests. */
function finderModule(workerScope) {
  'use strict';

  // Famous regions of the Mandelbrot set: centre (x, y) and search radius r.
  const REGIONS = [
    { name: 'Seahorse Valley', x: -0.7453, y: 0.1127, r: 0.012 },
    { name: 'Seahorse Spirals', x: -0.74364, y: 0.13183, r: 0.0009 },
    { name: 'Elephant Valley', x: 0.2925, y: 0.0149, r: 0.012 },
    { name: 'Triple Spiral Valley', x: -0.0880, y: 0.6540, r: 0.006 },
    { name: 'Quad Spiral Valley', x: 0.2620, y: 0.4950, r: 0.010 },
    { name: 'Scepter Valley', x: -1.2550, y: 0.0170, r: 0.012 },
    { name: 'Feigenbaum Point', x: -1.4012, y: 0.0000, r: 0.0025 },
    { name: 'Spiral Galaxy', x: -0.761574, y: -0.0847596, r: 0.0015 },
    { name: 'Northern Crown', x: -0.1011, y: 0.9563, r: 0.012 },
    { name: 'Pentagon Valley', x: -0.4818, y: 0.5317, r: 0.008 },
    { name: 'Western Minibrot', x: -1.7549, y: 0.0000, r: 0.012 },
  ];

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Main cardioid or period-2 bulb: never escapes, skip the iteration.
  function inMainBodies(x, y) {
    const xq = x - 0.25, q = xq * xq + y * y;
    if (q * (q + xq) <= 0.25 * y * y) return true;
    const x1 = x + 1;
    return x1 * x1 + y * y <= 0.0625;
  }

  // Smooth escape count, or -1 when the point did not escape.
  function escapeNu(cx, cy, maxIt) {
    if (inMainBodies(cx, cy)) return -1;
    let x = 0, y = 0, x2 = 0, y2 = 0;
    for (let i = 0; i < maxIt; i++) {
      y = 2 * x * y + cy;
      x = x2 - y2 + cx;
      x2 = x * x; y2 = y * y;
      if (x2 + y2 > 1e6) return i + 2 - Math.log2(0.5 * Math.log(x2 + y2) / Math.log(1000));
    }
    return -1;
  }

  // Iterations where |z| reaches a new minimum: the periods of the minibrots
  // whose atom domains hold c.
  function partials(cx, cy, maxIt) {
    const out = [];
    let x = 0, y = 0, best = Infinity;
    for (let i = 1; i <= maxIt; i++) {
      const nx = x * x - y * y + cx;
      y = 2 * x * y + cy; x = nx;
      const m = x * x + y * y;
      if (m > 4) break;
      if (m < best) { best = m; out.push(i); }
    }
    return out;
  }

  // Newton's method for the nucleus (centre) of a period-p minibrot near (cx, cy).
  function nucleus(cx, cy, p) {
    let x = cx, y = cy;
    for (let k = 0; k < 80; k++) {
      let zx = 0, zy = 0, dx = 0, dy = 0;
      for (let i = 0; i < p; i++) {
        const ndx = 2 * (zx * dx - zy * dy) + 1;
        dy = 2 * (zx * dy + zy * dx); dx = ndx;
        const nzx = zx * zx - zy * zy + x;
        zy = 2 * zx * zy + y; zx = nzx;
        if (zx * zx + zy * zy > 1e20) return null;
      }
      const den = dx * dx + dy * dy;
      if (!(den > 0) || !isFinite(den)) return null;
      const ex = (zx * dx + zy * dy) / den, ey = (zy * dx - zx * dy) / den;
      x -= ex; y -= ey;
      if (!isFinite(x) || !isFinite(y)) return null;
      if (Math.hypot(ex, ey) < 1e-15 * Math.max(1, Math.hypot(x, y))) return [x, y];
    }
    return null;
  }

  // Newton can land on a nucleus whose period divides p.
  function truePeriod(cx, cy, p) {
    let x = 0, y = 0;
    for (let i = 1; i < p; i++) {
      const nx = x * x - y * y + cx; y = 2 * x * y + cy; x = nx;
      if (x * x + y * y < 1e-18 && p % i === 0) return i;
    }
    return p;
  }

  // Approximate size of the minibrot at nucleus c with period p (relative to the
  // whole set, whose cardioid is about 1.5 wide).
  function miniSize(cx, cy, p) {
    let zx = 0, zy = 0, lx = 1, ly = 0, bx = 1, by = 0;
    for (let q = 1; q < p; q++) {
      const nzx = zx * zx - zy * zy + cx; zy = 2 * zx * zy + cy; zx = nzx;
      const nlx = 2 * (zx * lx - zy * ly); ly = 2 * (zx * ly + zy * lx); lx = nlx;
      const ld = lx * lx + ly * ly;
      if (!(ld > 0) || !isFinite(ld)) return 0;
      bx += lx / ld; by -= ly / ld;
    }
    const l2x = lx * lx - ly * ly, l2y = 2 * lx * ly;
    const dx = bx * l2x - by * l2y, dy = bx * l2y + by * l2x;
    return 1 / Math.hypot(dx, dy);
  }

  // Reference orbit Z_0..Z_n at c, packed as float pairs for the GPU.
  function refOrbit(cx, cy, n) {
    const data = new Float32Array(2 * (n + 1));
    let x = 0, y = 0, len = n + 1;
    for (let i = 1; i <= n; i++) {
      const nx = x * x - y * y + cx; y = 2 * x * y + cy; x = nx;
      if (x * x + y * y > 16) { len = i; break; }
      data[2 * i] = x; data[2 * i + 1] = y;
    }
    return { data, len };
  }

  // Pick a region, find a boundary point with a high escape count there, then
  // find a minibrot near it whose size is close to a random target depth.
  function findDestination(seed, opts) {
    opts = Object.assign({ minSize: 2e-12, maxSize: 2e-6, maxPeriod: 4000, refCap: 8000, avoid: -1, region: null }, opts || {});
    if (opts.fixed) {
      // A destination found earlier (a discovered planet): just build its orbit.
      const f = opts.fixed;
      const ref = refOrbit(f.x, f.y, opts.refCap);
      const R = REGIONS[f.regionIndex] || REGIONS[0];
      return { region: f.region || R.name, regionIndex: f.regionIndex | 0, regionR: R.r, x: f.x, y: f.y,
               period: f.period, size: f.size, name: f.name, ref: ref.data, refLen: ref.len };
    }
    const rng = mulberry32(seed >>> 0);
    for (let attempt = 0; attempt < 40; attempt++) {
      let ri = opts.region;
      if (ri == null || attempt > 4) {
        do { ri = Math.floor(rng() * REGIONS.length); } while (ri === opts.avoid && REGIONS.length > 1);
      }
      const R = REGIONS[ri];
      const samples = [];
      for (let k = 0; k < 1500; k++) {
        const a = rng() * 2 * Math.PI, d = R.r * Math.sqrt(rng());
        const cx = R.x + d * Math.cos(a), cy = R.y + d * Math.sin(a);
        const nu = escapeNu(cx, cy, 6000);
        if (nu > 0) samples.push([nu, cx, cy]);
      }
      if (samples.length < 20) continue;
      samples.sort((p, q) => q[0] - p[0]);
      const top = samples.slice(0, Math.max(5, (samples.length * 0.03) | 0));
      const s = top[Math.floor(rng() * top.length)];
      const want = Math.exp(Math.log(opts.minSize * 4) + rng() * (Math.log(opts.maxSize) - Math.log(opts.minSize * 4)));
      let best = null;
      for (const p of partials(s[1], s[2], 6000)) {
        if (p < 12 || p > opts.maxPeriod) continue;
        const n = nucleus(s[1], s[2], p);
        if (!n) continue;
        const per = truePeriod(n[0], n[1], p);
        if (per < 12) continue;
        const size = miniSize(n[0], n[1], per);
        if (!(size >= opts.minSize && size <= opts.maxSize)) continue;
        if (Math.hypot(n[0] - R.x, n[1] - R.y) > R.r * 3) continue;
        const score = Math.abs(Math.log(size / want));
        if (!best || score < best.score) best = { x: n[0], y: n[1], period: per, size, score };
      }
      if (!best) continue;
      const flip = rng() < 0.5 ? -1 : 1;
      const ref = refOrbit(best.x, flip * best.y, opts.refCap);
      return {
        region: R.name, regionIndex: ri, regionR: R.r,
        x: best.x, y: flip * best.y, period: best.period, size: best.size,
        ref: ref.data, refLen: ref.len,
      };
    }
    return null;
  }

  const api = { REGIONS, findDestination, escapeNu, partials, nucleus, miniSize, mulberry32 };
  if (workerScope) {
    workerScope.onmessage = (e) => {
      const { id, seed, opts } = e.data;
      let res = null;
      try { res = findDestination(seed, opts); } catch (err) { res = null; }
      workerScope.postMessage({ id, res }, res ? [res.ref.buffer] : []);
    };
  }
  return api;
}
if (typeof module !== 'undefined' && module.exports) module.exports = finderModule;
