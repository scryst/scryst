"""Shared pieces: the hand placed on the canvas, noise and saving. The canvas
is W x H pixels, 2048 x 720 unless CANVAS=WxH says otherwise."""
import json, math, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

W, H = (int(v) for v in os.environ.get('CANVAS', '2048x720').split('x'))
HERE = os.path.dirname(os.path.abspath(__file__))
HAND = json.load(open(os.path.join(HERE, 'hand.json')))


def placed(scale=1.62, cx=None, cy=None):
    """Strokes as arrays of (x, y, tx, ty, s) in canvas pixels. The word box is
    centered on (cx, cy); by default the x-height band sits a little above middle."""
    b = HAND['box']
    cx = W / 2 if cx is None else cx
    cy = H * 0.5 if cy is None else cy
    mx, my = (b['x0'] + b['x1']) / 2, (b['y0'] + b['y1']) / 2
    out = {}
    for k, pts in HAND['strokes'].items():
        a = np.array(pts, float)
        a[:, 0] = (a[:, 0] - mx) * scale + cx
        a[:, 1] = (a[:, 1] - my) * scale + cy
        a[:, 4] *= scale
        if a.shape[1] > 5:
            a[:, 5] *= scale
        out[k] = a
    return out


def fbm(shape, scale, octaves=5, seed=0, gain=0.5):
    """Smooth value noise in [-1, 1] approx, feature size `scale` pixels."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape); amp = 1.0; tot = 0
    for o in range(octaves):
        s = max(1, scale / 2 ** o)
        gh, gw = int(shape[0] / s) + 3, int(shape[1] / s) + 3
        g = rng.standard_normal((gh, gw))
        z = ndi.zoom(g, (shape[0] / (gh - 2), shape[1] / (gw - 2)), order=3)[:shape[0], :shape[1]]
        out += amp * z; tot += amp; amp *= gain
    return out / tot


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def save_rgba(path, rgb, alpha=None):
    """rgb float [0,1] HxWx3, alpha float HxW or None. Writes a clean PNG (pixels only)."""
    rgb8 = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    if alpha is None:
        im = Image.fromarray(rgb8, 'RGB')
    else:
        a8 = (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
        im = Image.fromarray(np.dstack([rgb8, a8]), 'RGBA')
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    im.save(path, optimize=True)


def hexrgb(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
