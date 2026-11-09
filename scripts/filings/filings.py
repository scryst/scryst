"""scryst in iron filings. Magnetite dust over a sheet magnet cut as the hand.
Near the word the dust sits on the magnet (dense, short grains across the
field); further out it chains along the field lines of the word as one bar
magnet, thinning with distance.
  python filings.py <out.png> <light|dark> [options]"""
import math, sys, argparse
import numpy as np
from scipy import ndimage as ndi
from common import W, H, placed, fbm, smoothstep, save_rgba, hexrgb
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('theme')
ap.add_argument('--seed', type=int, default=5)
ap.add_argument('--scale', type=float, default=2.22)
ap.add_argument('--cx', type=float, default=0.47)
ap.add_argument('--cy', type=float, default=0.47)
ap.add_argument('--z0', type=float, default=26.0)
ap.add_argument('--near', type=int, default=290000)
ap.add_argument('--lines', type=float, default=19.0, help='field-line spacing, px')
ap.add_argument('--reach', type=float, default=1.35)
ap.add_argument('--fur', type=float, default=3.2)
ap.add_argument('--hair', type=float, default=2.6)
A = ap.parse_args()


NIB_ANGLE = math.radians(36)


def ribbon_mask(strokes):
    """The magnet: the broad-nib italic, stamped with the nib at its fixed angle."""
    img = Image.new('L', (W * 2, H * 2), 0); d = ImageDraw.Draw(img)
    for name, a in strokes.items():
        for x, y, tx, ty, s_, w in a:
            hx, hy = math.cos(NIB_ANGLE) * w / 2 * 2, -math.sin(NIB_ANGLE) * w / 2 * 2
            d.line([(x * 2 - hx, y * 2 - hy), (x * 2 + hx, y * 2 + hy)], fill=255, width=max(2, int(A.hair * 2)))
    return np.asarray(img.resize((W, H), Image.LANCZOS), float) / 255


def poles(strokes):
    """North at the word's left end, south at its right end."""
    allp = np.concatenate([a[:, :2] for a in strokes.values()])
    left = allp[np.argmin(allp[:, 0])]; right = allp[np.argmax(allp[:, 0])]
    return left, right


def pole_field(strokes):
    (lx, ly), (rx, ry) = poles(strokes)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    z = A.z0
    bx = np.zeros((H, W)); by = np.zeros((H, W)); bz = np.zeros((H, W))
    for (px, py, q) in ((lx, ly, 1.0), (rx, ry, -1.0)):
        dx, dy = xx - px, yy - py
        den = (dx ** 2 + dy ** 2 + z ** 2) ** 1.5
        bx += q * dx / den; by += q * dy / den; bz += q * z / den
    return bx, by, bz, (lx, ly), (rx, ry)


def streamlines(ux, uy, mag, dist, rng, north, south):
    """Evenly spaced field lines (Jobard-Lefer style occupancy grid)."""
    sep = A.lines
    cell = sep / 2
    gw, gh = int(W / cell) + 1, int(H / cell) + 1
    occ = np.zeros((gh, gw), bool)
    # never seed or run inside the word itself
    word = dist < 10
    for gy_ in range(gh):
        for gx_ in range(gw):
            y, x = min(H - 1, int(gy_ * cell)), min(W - 1, int(gx_ * cell))
            if word[y, x]: occ[gy_, gx_] = True
    lines = []
    # seed first on a ring round the north pole, evenly by angle, then fill the gaps
    ang = np.linspace(0, 2 * math.pi, 40, endpoint=False) + rng.uniform(0, 0.08)
    ring = np.stack([north[1] + 70 * np.sin(ang), north[0] + 70 * np.cos(ang)], 1).astype(int)
    ring = ring[(ring[:, 0] > 2) & (ring[:, 0] < H - 2) & (ring[:, 1] > 2) & (ring[:, 1] < W - 2)]
    rest = np.argwhere((dist > 12))
    rng.shuffle(rest)
    seeds = np.concatenate([ring, rest[:20000]])
    def free(x, y):
        if not (0 <= x < W and 0 <= y < H): return False
        gx_, gy_ = int(x / cell), int(y / cell)
        y0, y1, x0, x1 = max(0, gy_ - 1), min(gh, gy_ + 2), max(0, gx_ - 1), min(gw, gx_ + 2)
        return not occ[y0:y1, x0:x1].any()
    for (sy, sx) in seeds:
        if not free(sx, sy): continue
        line = [(float(sx), float(sy))]
        for direction in (1, -1):
            x, y = float(sx), float(sy); pts = []
            for k in range(900):
                ix, iy = int(x), int(y)
                vx, vy = ux[iy, ix], uy[iy, ix]
                x2, y2 = x + direction * vx * 1.5, y + direction * vy * 1.5
                if not free(x2, y2) and k > 3: break
                if not (2 <= x2 < W - 2 and 2 <= y2 < H - 2): break
                if dist[int(y2), int(x2)] < 8: break
                if min(math.hypot(x2 - north[0], y2 - north[1]), math.hypot(x2 - south[0], y2 - south[1])) < 44 + rng.uniform(0, 30): break
                x, y = x2, y2; pts.append((x, y))
            line = (pts[::-1] + line) if direction == -1 else (line + pts)
        if len(line) < 12: continue
        for (x, y) in line[::2]:
            occ[int(y / cell), int(x / cell)] = True
        lines.append(np.array(line))
    return lines


def render():
    rng = np.random.default_rng(A.seed)
    st = placed(scale=A.scale, cx=W * A.cx, cy=H * A.cy)
    mask = ribbon_mask(st)
    dist = ndi.distance_transform_edt(mask < 0.5)
    bx, by, bz, NP, SP = pole_field(st)
    bm = np.hypot(bx, by)
    ux, uy = bx / (bm + 1e-12), by / (bm + 1e-12)
    S = 2
    layers = {k: Image.new('L', (W * S, H * S), 0) for k in ('cov', 'lum', 'glint', 'shadow')}
    dr = {k: ImageDraw.Draw(v) for k, v in layers.items()}
    PSI = math.radians(-128)          # the one light: high, from the top left
    SH = np.array([1.3, 1.8])         # where a grain's shadow falls, px

    def grain(p, q, tone, wd, floor=0.25):
        p, q = np.asarray(p, float), np.asarray(q, float)
        phi = math.atan2(q[1] - p[1], q[0] - p[0])
        across = abs(math.sin(phi - PSI))           # a sliver lying across the light catches it
        P, Q = tuple(p * S), tuple(q * S)
        dr['shadow'].line([tuple((p + SH) * S), tuple((q + SH) * S)], fill=255, width=wd + S)
        dr['cov'].line([P, Q], fill=tone, width=wd)
        dr['lum'].line([P, Q], fill=int(tone * (floor + (1 - floor) * across ** 1.5)), width=wd)
        g = across ** 14 * rng.uniform(0.4, 1.0)
        if g > 0.05:
            # the glint runs along the lit edge, shorter than the grain
            n = np.array([-math.sin(phi), math.cos(phi)]) * (wd / S) * 0.3
            m = (p + q) / 2; h = (q - p) * rng.uniform(0.15, 0.4)
            dr['glint'].line([tuple((m - h - n) * S), tuple((m + h - n) * S)], fill=int(255 * g), width=max(1, wd // 2))

    # near: dust on and just around the magnet
    # on the magnet the dust piles up at its edges, where the poles are
    din = ndi.distance_transform_edt(mask >= 0.5)
    nd = mask * (0.75 + 0.25 * np.exp(-din / 3.5)) + (1 - mask) * np.exp(-dist / A.fur)
    nd = nd ** 1.3
    # the dust was shaken on by hand: thicker in some places than others
    yy0, xx0 = np.mgrid[0:H, 0:W]
    dpole = np.minimum(np.hypot(xx0 - NP[0], yy0 - NP[1]), np.hypot(xx0 - SP[0], yy0 - SP[1]))
    shake = 0.72 + 0.28 * np.clip(fbm((H, W), 70, 3, seed=A.seed + 3) * 1.8, -1, 1)
    nd = nd * shake * (1 - (1 - mask) * np.exp(-dpole / 45))
    gy_d, gx_d = np.gradient(ndi.gaussian_filter(din, 1.5))
    gn = np.hypot(gx_d, gy_d) + 1e-9
    ngx, ngy = gx_d / gn, gy_d / gn   # points into the magnet
    N = A.near * 4
    px = rng.uniform(0, W - 1, N); py = rng.uniform(0, H - 1, N)
    keep = rng.uniform(0, 1, N) < nd[py.astype(int), px.astype(int)]
    px, py = px[keep][:A.near], py[keep][:A.near]
    for x, y in zip(px, py):
        ix, iy = int(x), int(y)
        on = mask[iy, ix]
        edge = din[iy, ix] if on > 0.5 else 0.0
        if on > 0.5 and edge > 3.0:
            # over the face of the magnet the field points out of the paper: grains stand on end,
            # seen from above as short stubs at any angle
            ang = rng.uniform(0, math.pi)
            L = min(5.0, rng.lognormal(0.75, 0.45))
        elif on > 0.5:
            # at the edge they lean outward, across the edge, as bristles
            ang = math.atan2(-ngy[iy, ix], -ngx[iy, ix]) + rng.normal(0, 0.35)
            L = min(12.0, rng.lognormal(1.35, 0.45))
        else:
            ang = math.atan2(uy[iy, ix], ux[iy, ix]) + rng.normal(0, 0.2)
            L = min(13.0, rng.lognormal(1.3, 0.45)) + rng.uniform(0, 3)
        dx, dy = math.cos(ang) * L / 2, math.sin(ang) * L / 2
        tone = int(rng.uniform(170, 255))
        wd = max(1, round(rng.choice([0.9, 1.1, 1.4, 1.9], p=[0.35, 0.35, 0.2, 0.1]) * S))
        grain((x - dx, y - dy), (x + dx, y + dy), tone, wd, floor=0.25 + 0.4 * on)
        if rng.uniform() < 0.08:   # a clump: a second grain lying alongside
            nx_, ny_ = -dy / (L / 2 + 1e-9) * 1.3, dx / (L / 2 + 1e-9) * 1.3
            grain((x - dx * 0.8 + nx_, y - dy * 0.8 + ny_), (x + dx * 0.6 + nx_, y + dy * 0.6 + ny_), tone, wd)
    # fine dust: specks too small to chain, thick near the word, a few far out
    dust = 0.07 * np.exp(-dist / 16)
    M = 400000
    qx = rng.uniform(0, W - 1, M); qy = rng.uniform(0, H - 1, M)
    k2 = rng.uniform(0, 1, M) < dust[qy.astype(int), qx.astype(int)]
    for x, y in zip(qx[k2], qy[k2]):
        r = rng.uniform(0.35, 0.8) * S
        t_ = int(rng.uniform(90, 200)); box = [x * S - r, y * S - r, x * S + r, y * S + r]
        dr['cov'].ellipse(box, fill=t_); dr['lum'].ellipse(box, fill=int(t_ * rng.uniform(0.2, 0.8)))
    # far: chains along evenly spaced field lines, thinning with distance from the word
    yy_, xx_ = np.mgrid[0:H, 0:W]
    border = smoothstep(0, 160, np.minimum.reduce([xx_, W - 1 - xx_, yy_ * 2.0, (H - 1 - yy_) * 2.0]))
    bref = np.percentile(bm[dist > 30], 97)
    region = np.clip(0.75 + 0.6 * fbm((H, W), 240, 2, seed=A.seed + 9), 0.35, 1.0)
    for line in streamlines(ux, uy, bm, dist, rng, NP, SP):
        dd = dist[line[:, 1].astype(int), line[:, 0].astype(int)]
        bd = border[line[:, 1].astype(int), line[:, 0].astype(int)]
        # how much dust this line gathered drifts along it
        drift = np.interp(np.arange(len(line)), np.linspace(0, len(line), 8), rng.uniform(0.55, 1.0, 8))
        # grains land at random along the line and overlap, as real chains do
        n_g = int(len(line) * 0.42)
        for j in np.sort(rng.integers(0, len(line) - 2, n_g)):
            keep_p = math.exp(-max(0, dd[j] - 10) / (230 * A.reach)) * drift[j] * bd[j] * region[int(line[j][1]), int(line[j][0])]
            if rng.uniform() >= keep_p * 0.75:
                continue
            g = min(len(line) - 1 - j, max(2, int(rng.lognormal(1.0, 0.55))))
            off = rng.normal(0, 1.1, 2)
            q = line[j:j + g + 1] + off
            ang_j = rng.normal(0, 0.12)
            m = (q[0] + q[-1]) / 2; h = (q[-1] - q[0]) / 2
            h = np.array([h[0] * math.cos(ang_j) - h[1] * math.sin(ang_j), h[0] * math.sin(ang_j) + h[1] * math.cos(ang_j)])
            st_ = min(1.0, bm[int(m[1]) % H, int(m[0]) % W] / bref)
            grain(m - h, m + h, int(min(255, rng.uniform(150, 250) * (0.6 + 0.4 * keep_p) * (0.72 if A.theme == 'light' else 1.25))),
                  max(1, round((0.7 + 0.8 * st_ ** 0.5 * rng.uniform(0.5, 1.0)) * S)))
    ds = {k: np.asarray(v.resize((W, H), Image.LANCZOS), float) / 255 for k, v in layers.items()}
    cov = np.clip(ds['cov'] * 1.15, 0, 1)
    lum = np.clip(ds['lum'] / np.maximum(ds['cov'], 1e-3), 0, 1)
    glint = np.clip(ndi.gaussian_filter(ds['glint'], 0.4) * 1.6, 0, 1)
    shadow = np.clip(ndi.gaussian_filter(ds['shadow'], 1.7) * 0.9, 0, 1)
    if A.theme == 'light':
        dark_m, lit_m = hexrgb('#0a0a0b'), hexrgb('#2c2c31')
        metal = dark_m + (lit_m - dark_m) * lum[..., None]
        metal = metal + (1 - metal) * glint[..., None] * 0.4
        # shadow on the page under everything, metal over it
        sa = shadow * 0.13 * (1 - cov)
        alpha = cov + sa
        rgb = (metal * cov[..., None]) / np.maximum(alpha, 1e-4)[..., None]
    else:
        dark_m, lit_m = hexrgb('#5a5a60'), hexrgb('#e2e0db')
        metal = dark_m + (lit_m - dark_m) * lum[..., None]
        metal = metal + (1 - metal) * glint[..., None]
        alpha = cov
        rgb = metal
    return np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)


if __name__ == '__main__':
    rgb, a = render()
    save_rgba(A.out, rgb, a)
