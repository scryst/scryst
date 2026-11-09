"""The scryst hand: a broad-nib italic. Strokes are Catmull-Rom
runs between cusps; width comes from the pen angle, not from a font.
Writes hand.json beside this file (samples with a per-sample nib width);
with an argument, also a plain preview PNG at that path.
Units: baseline 0, x-height -100, ascender -158, descender +112."""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

SLANT = math.tan(math.radians(9))
NIB_ANGLE = math.radians(36)   # nib edge, from horizontal
NIB = 20.0                     # nib width, units
HAIR = 2.6


def S(x0):
    """An italic s: a hooked head, a steep spine, a foot that turns up."""
    p = [(46, -86), (40, -98), (26, -101), (12, -94), (8, -78), (16, -63), (30, -53), (42, -42), (46, -24), (40, -8), (24, 1), (8, -2), (0, -12)]
    return [[(x + x0, y) for x, y in p]]


GLYPHS = {
    's1': S(0),
    'c': [[(112, -86), (104, -98), (88, -101), (72, -90), (64, -66), (63, -36), (70, -12), (86, 0), (103, -4), (114, -16)]],
    # r: the stem, then out of it a short arch that ends high
    'r': [[(136, -101), (134, -50), (132, 0)],
          [(132, 0), (133, -44), (138, -72), (150, -94), (164, -101), (176, -96)]],
    # y: the cup, up to the right stem, then the descender with a hook (no loop)
    'y': [[(194, -101), (192, -60), (193, -24), (202, -4), (216, 0), (230, -10), (240, -36), (244, -101)],
          [(244, -101), (243, -40), (240, 30), (232, 82), (218, 108), (198, 112), (184, 100)]],
    's2': S(262),
    't': [[(334, -158), (331, -100), (328, -44), (330, -12), (340, 1), (354, -2), (364, -14)]],
    'bar': [[(312, -101), (330, -102), (350, -103), (366, -101)]],
}


def catmull(pts, n=40):
    P = [tuple(2 * a - b for a, b in zip(pts[0], pts[1]))] + pts + [tuple(2 * a - b for a, b in zip(pts[-1], pts[-2]))]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        def tj(ti, a, b): return ti + max(math.dist(a, b), 1e-6) ** 0.5
        t0 = 0; t1 = tj(t0, p0, p1); t2 = tj(t1, p1, p2); t3 = tj(t2, p2, p3)
        for k in range(n + (1 if i == len(P) - 3 else 0)):
            t = t1 + (t2 - t1) * k / n
            def L(a, b, ta, tb): return tuple(((tb - t) * x + (t - ta) * y) / (tb - ta) for x, y in zip(a, b))
            A1, A2, A3 = L(p0, p1, t0, t1), L(p1, p2, t1, t2), L(p2, p3, t2, t3)
            B1, B2 = L(A1, A2, t0, t2), L(A2, A3, t1, t3)
            out.append(L(B1, B2, t1, t2))
    return out


def stroke(runs):
    pts = []
    for r in runs:
        c = catmull(r)
        pts += c if not pts else c[1:]
    pts = [(x - y * SLANT, y) for x, y in pts]
    out, acc, total = [list(pts[0]) + [0, 0, 0, 0]], 0.0, 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b); total += L; acc += L
        while acc >= 1.0:
            acc -= 1.0; f = 1 - acc / L if L else 1
            out.append([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, 0, 0, total - acc, 0])
    for i, p in enumerate(out):
        a, b = out[max(0, i - 2)], out[min(len(out) - 1, i + 2)]
        dx, dy = b[0] - a[0], b[1] - a[1]; n = math.hypot(dx, dy) or 1
        p[2], p[3] = dx / n, dy / n
        th = math.atan2(dy, dx)
        # the nib's edge is fixed; the mark is wide when the pen moves across it
        p[5] = HAIR + NIB * abs(math.sin(th - NIB_ANGLE))
    # ease the nib on and off the paper
    tot = out[-1][4]
    for p in out:
        e = min(1.0, p[4] / 10, (tot - p[4]) / 8)
        p[5] *= 0.45 + 0.55 * max(0.0, e)
    w = np.array([p[5] for p in out]); w = np.convolve(np.pad(w, 4, mode='edge'), np.ones(9) / 9, mode='valid')
    for p, v in zip(out, w): p[5] = v
    return [[round(v, 2) for v in p] for p in out]


if __name__ == '__main__':
    strokes = {k: stroke(v) for k, v in GLYPHS.items()}
    xs = [p[0] for s in strokes.values() for p in s]; ys = [p[1] for s in strokes.values() for p in s]
    box = dict(x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys))
    json.dump({'strokes': strokes, 'box': box}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.json'), 'w'))
    if len(sys.argv) < 2:
        sys.exit(0)
    Sc, pad = 3, 24
    im = Image.new('L', (int((box['x1'] - box['x0'] + 2 * pad) * Sc), int((box['y1'] - box['y0'] + 2 * pad) * Sc)), 255)
    d = ImageDraw.Draw(im)
    for y in (0, -100, -158, 112):
        yy = (y - box['y0'] + pad) * Sc; d.line([(0, yy), (im.width, yy)], fill=225)
    for s in strokes.values():
        for x, y, tx, ty, _, w in s:
            cx, cy = (x - box['x0'] + pad) * Sc, (y - box['y0'] + pad) * Sc
            # the nib: a short segment at the nib angle, width w
            hx, hy = math.cos(NIB_ANGLE) * w / 2 * Sc, -math.sin(NIB_ANGLE) * w / 2 * Sc
            d.line([(cx - hx, cy - hy), (cx + hx, cy + hy)], fill=0, width=int(HAIR * Sc * 0.9))
    im.save(sys.argv[1]); print(box)
