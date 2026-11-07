"""Shared pieces: hand-built letter skeletons, distance fields, grade, grain, vignette, lamp tint."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter
from PIL import Image


def catmull(pts, n=40):
    pts = np.asarray(pts, float)
    P = np.vstack([pts[0], pts, pts[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t = np.linspace(0, 1, n, endpoint=False)[:, None]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3))
    out.append(pts[-1:])
    return np.vstack(out)


def arc(cx, cy, rx, ry, a0, a1, n=120):
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], 1)


def line(a, b, n=60):
    t = np.linspace(0, 1, n)[:, None]
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


# Letter skeletons in x-height units, origin at baseline-left, y up.
# Each letter: (advance width, [strokes]); strokes are polylines.
def skeletons():
    S = [catmull([(0.80, 0.80), (0.58, 0.98), (0.28, 0.97), (0.09, 0.80), (0.16, 0.60),
                  (0.45, 0.50), (0.76, 0.38), (0.84, 0.18), (0.64, 0.02), (0.30, 0.00), (0.05, 0.17)])]
    C = [arc(0.48, 0.5, 0.47, 0.5, 38, 322)[::-1]]
    R = [line((0.12, 0.0), (0.12, 1.0)),
         catmull([(0.12, 0.68), (0.26, 0.90), (0.45, 0.99), (0.70, 0.95)])]
    Y = [line((0.02, 1.0), (0.46, 0.04)),
         catmull([(0.90, 1.0), (0.62, 0.30), (0.44, -0.14), (0.33, -0.36), (0.18, -0.46), (0.05, -0.42)])]
    T = [catmull([(0.30, 1.18), (0.30, 0.5), (0.31, 0.15), (0.42, 0.01), (0.66, 0.04)]),
         line((0.04, 1.0), (0.66, 1.0))]
    return [('s', 0.88, S), ('c', 0.90, C), ('r', 0.74, R), ('y', 0.92, Y), ('s', 0.88, S), ('t', 0.70, T)]


def layout(W, H, xh_frac=0.32, base_frac=0.635, gap=0.30, xoff=0.0):
    """Return list of dicts with pixel-space strokes per letter."""
    xh = xh_frac * H
    sk = skeletons()
    total = sum(a for _, a, _ in sk) + gap * (len(sk) - 1)
    x = (W - total * xh) / 2 + xoff * W
    by = base_frac * H
    out = []
    for name, adv, strokes in sk:
        px = []
        for s in strokes:
            s = np.asarray(s, float)
            px.append(np.stack([x + s[:, 0] * xh, by - s[:, 1] * xh], 1))
        out.append(dict(name=name, strokes=px, x0=x, x1=x + adv * xh, xh=xh, base=by))
        x += (adv + gap) * xh
    return out


def resample(poly, step):
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(poly, axis=0).T))]
    n = max(2, int(d[-1] / step) + 1)
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, poly[:, 0]), np.interp(t, d, poly[:, 1])], 1), t / max(d[-1], 1e-9)


def fields(W, H, letter, step=0.5):
    """Distance to skeleton, unit tangent at nearest skeleton point, arc param, stroke id."""
    pts, tan, par, sid = [], [], [], []
    for k, s in enumerate(letter['strokes']):
        p, u = resample(s, step)
        t = np.gradient(p, axis=0)
        t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
        pts.append(p); tan.append(t); par.append(u); sid.append(np.full(len(p), k))
    pts, tan, par, sid = map(np.concatenate, (pts, tan, par, sid))
    yy, xx = np.mgrid[0:H, 0:W]
    q = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1)
    d, i = cKDTree(pts).query(q)
    return (d.reshape(H, W), tan[i].reshape(H, W, 2), par[i].reshape(H, W), sid[i].reshape(H, W))


def grain(H, W, seed=0, amt=0.05, size=1.0):
    g = np.random.default_rng(seed).standard_normal((H, W))
    if size > 1:
        g = gaussian_filter(g, size * 0.5) * size
    return g * amt


def bloom(L, s1, s2, a1=0.25, a2=0.12):
    return L + a1 * gaussian_filter(L, s1) + a2 * gaussian_filter(L, s2)


def grade(L, g=None, edge=None):
    """Split-toned grade into GitHub's page color at the edges. edge: 0 at frame edge -> 1 inside."""
    L = np.clip(L, 0, None)
    L = 1 - np.exp(-L)
    if g is not None:
        L = np.clip(L + g * (0.3 + 0.7 * np.sqrt(np.clip(L, 0, 1))) * (1 if edge is None else edge), 0, 1)
    # split tone from GitHub's dark page through slate to warm paper white
    stops = [(0.0, (13, 17, 23)), (0.18, (34, 42, 52)), (0.55, (150, 156, 158)), (1.0, (246, 238, 222))]
    xs = [s[0] for s in stops]
    out = np.stack([np.interp(L, xs, [s[1][c] for s in stops]) for c in range(3)], -1) / 255
    return out


def save(rgb, path):
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def vignette(H, W, n=4.0, inner=0.62):
    """Superelliptic falloff that reaches 0 at every frame edge: the pool dissolves into the page."""
    yy, xx = np.mgrid[0:H, 0:W]
    dx, dy = np.abs((xx + 0.5) / W * 2 - 1), np.abs((yy + 0.5) / H * 2 - 1)
    r = (dx ** n + dy ** n) ** (1 / n)
    e = np.clip((1 - r) / (1 - inner), 0, 1)
    return e * e * (3 - 2 * e)


def lamp_tint(rgb, H, W, light, warm=(1.035, 1.0, 0.93), cool=(0.95, 0.99, 1.04)):
    """Warm near the lamp, cool away from it: the one light has a color and a side."""
    lx, ly, rx, ry = light
    yy, xx = np.mgrid[0:H, 0:W]
    w = 1.0 / (1.0 + ((xx - lx * W) / (rx * W)) ** 2 + ((yy - ly * H) / (ry * H)) ** 2)
    w = (w / w.max())[..., None]
    L = rgb.mean(-1, keepdims=True)  # tint the lights, leave the blacks matched to the page
    k = np.clip(L * 1.4, 0, 1)
    tint = np.array(cool) * (1 - w) + np.array(warm) * w
    return np.clip(rgb * (1 + (tint - 1) * k), 0, 1)
