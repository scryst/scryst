"""Draws the profile banner from the contribution calendar."""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import people

PHONE = (250, 1030)
W, H = 1280, 570
N, FPS = 84, 12
TW, TH, SKYM, SHOP = 48, 84, 90, 104
CX, HORIZON, BASE, ROOF = 640.0, 408.0, 440.0, 62.0
VP = 1110.0
LAMP = (CX - 4.0, 318.0)
PXM = (BASE - ROOF) / (7 * TH + SHOP) * TH / 3.0 / (BASE - HORIZON)
FEET = (CX - 118.0, 486.0)
FIG_H = 1.72 * PXM * (FEET[1] - HORIZON)
ROAD_HALF = 3.2
THEMES = {
    'dark': dict(page=(13, 17, 23), inks=[(31, 111, 235), (121, 192, 255), (240, 246, 252)], accent=(247, 120, 186)),
    'light': dict(page=(255, 255, 255), inks=[(84, 174, 255), (9, 105, 218), (10, 48, 105)], accent=(191, 57, 137)),
}


def calendar(login):
    q = ('query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{'
         'weeks{contributionDays{date contributionCount weekday}}}}}}')
    raw = subprocess.check_output(['gh', 'api', 'graphql', '-f', 'query=' + q, '-f', 'l=' + login], text=True)
    return json.loads(raw)['data']['user']['contributionsCollection']['contributionCalendar']['weeks'][-53:]


def levels(weeks):
    """53 x 7 array, newest week last: -1 no such day, 0 nothing, 1-4 by rank among the active days (GitHub's quartile idea)."""
    counts = np.full((53, 7), -1, int)
    for i, wk in enumerate(weeks, 53 - len(weeks)):
        for day in wk['contributionDays']:
            counts[i, day['weekday']] = day['contributionCount']
    active = np.sort(counts[counts > 0])
    if not len(active):
        return np.where(counts < 0, -1, 0)
    q = [active[int(len(active) * f)] for f in (.25, .5, .75)]
    return np.where(counts > 0, 1 + (counts > q[0]) + (counts > q[1]) + (counts > q[2]), np.where(counts < 0, -1, 0))


def blur(a, s):
    return ndimage.gaussian_filter(a, s)


class Face:
    """One wall as a flat texture. corner='l' means the corner edge is the texture's left side."""

    def __init__(self, lv, corner, seed, today=None):
        g = np.random.default_rng(seed)
        n = lv.shape[0]
        self.today_pane = None
        self.w, self.h, self.corner = n * TW, SKYM + 7 * TH + SHOP, corner
        wall = np.zeros((self.h, self.w), np.float32)
        lit = np.zeros((self.h, self.w), np.float32)
        top, shop = SKYM, SKYM + 7 * TH
        mott = blur(g.random((self.h, self.w)).astype(np.float32), (16, 5))
        mott = (mott - mott.min()) / (mott.max() - mott.min())
        wall[top:] = .050 + .045 * mott[top:]
        self.flick = []
        recent = []
        for c in range(n):
            x = c * TW
            if c % 7 == 3:
                wall[top:shop, x:x + 3] = .0
                wall[top:shop, x + 3:x + 5] *= 1.5
            for j in range(7):
                y, v = top + j * TH, lv[c, j]
                wall[y + TH - 6:y + TH - 2, x:x + TW] += .05
                wall[y + TH - 2:y + TH, x:x + TW] *= .4
                if v < 0:
                    continue
                wide = g.random() < .2
                x0, x1 = (x + 5, x + TW - 5) if wide else (x + 9, x + TW - 9)
                y0, y1 = y + 13, y + 61
                if today == (c, j):
                    self.today_pane = (slice(y0, y1), slice(x0, x1))
                    v = max(v, 2)
                wall[y0 - 3:y1 + 3, x0 - 3:x1 + 3] = .105
                wall[y0:y1, x0:x1] = .010
                if v == 0:
                    if g.random() < .4:
                        wall[y0:y0 + int(g.integers(8, 22)), x0:x1] = .045
                else:
                    base = (.0, .30, .54, .80, 1.05)[v] * g.uniform(.85, 1.1)
                    ph, pw = y1 - y0, x1 - x0
                    pane = np.full((ph, pw), base, np.float32)
                    kind = g.random()
                    if kind < .42:
                        pane *= (.70 + .30 * np.cos(np.arange(pw) * g.uniform(.45, .8) + g.uniform(0, 6)))[None, :]
                        if g.random() < .5:
                            gap = int(g.integers(4, 10))
                            pane[:, pw // 2 - gap:pw // 2 + gap] *= 1.35
                    elif kind < .66:
                        d = int(g.integers(ph // 3, ph))
                        pane[:d:5] *= .45
                        pane[:d] *= .8
                    else:
                        pane *= (1.2 - .6 * np.linspace(0, 1, ph))[:, None]
                    pane[:, pw // 2 - 1:pw // 2 + 1] *= .22
                    pane[ph // 3 - 1:ph // 3 + 1] *= .30
                    if v >= 3 and g.random() < .40:
                        who, pose = people.bust(pw, ph, g, avoid=recent)
                        recent = (recent + [pose])[-7:]
                        pane *= 1 - .86 * blur(who, .6)
                    lit[y0:y1, x0:x1] = pane
                    r = g.random()
                    if v <= 2 and r < .16:
                        self.flick.append(((slice(y0, y1), slice(x0, x1)), g.uniform(0, 1), 'tv'))
                    elif r > .94:
                        self.flick.append(((slice(y0, y1), slice(x0, x1)), g.uniform(0, 1), 'switch'))
                if wide:
                    wall[y1 - 14:y1 + 3:4, x0 - 4:x1 + 4] = .12
                    lit[y1 - 14:y1 + 3:4, x0:x1] *= .3
                if g.random() < .45:
                    ax = x1 - 17
                    wall[y1 + 5:y1 + 16, ax:ax + 18] = .13
                    wall[y1 + 7:y1 + 15:2, ax + 2:ax + 16] = .035
                    wall[y1 + 16:min(y1 + 60, shop), ax + 4:ax + 12] *= .55
                if g.random() < .18:
                    py = y1 + 6
                    wall[py:py + 2, x0 - 6:x1 + 6] = .13
                    for k in range(int(g.integers(2, 5))):
                        cx = x0 - 4 + k * 9
                        wall[py + 2:py + int(g.integers(9, 18)), cx:cx + 7] = g.uniform(.09, .24)
        wall[top - 6:top, :] = .17
        self.beacons = []
        x = 12
        while x < self.w - 90:
            kind = g.random()
            if kind < .3:
                w, h = int(g.integers(34, 56)), int(g.integers(26, 42))
                wall[top - 6 - h:top - 6, x:x + w] = .05
                wall[top - 6 - h:top - 3 - h, x:x + w] = .12
            elif kind < .55:
                w, h = int(g.integers(50, 84)), int(g.integers(18, 30))
                wall[top - 6 - h:top - 6, x:x + w] = .06
                wall[top - 8 - h:top - 6 - h, x - 2:x + w + 2] = .13
            elif kind < .85:
                h = int(g.integers(40, 80))
                wall[top - 6 - h:top - 6, x:x + 2] = .11
                for k in range(3):
                    wall[top - h + k * 9:top - h + k * 9 + 1, x - 9 + 2 * k:x + 11 - 2 * k] = .10
                if h > 62:
                    self.beacons.append((x, top - 8 - h, g.uniform(0, 1)))
            x += int(g.integers(60, 170))
        wall[shop:, :] = .095
        wall[shop:shop + 4, :] = .17
        x = 8
        first = True
        while x < self.w - 60:
            w = int(g.integers(84, 170))
            at_corner = (corner == 'l' and first) or (corner == 'r' and x + w > self.w - 40)
            if at_corner or g.random() < .3:
                front = shopfront(g, SHOP - 26, w, at_corner)
                lit[shop + 22:shop + SHOP - 4, x:x + w] = front[:, :max(0, min(w, self.w - x))]
                wall[shop + 10:shop + 18, max(x - 6, 0):x + w + 6] = .15
            else:
                wall[shop + 16:shop + SHOP - 3:5, x:x + w] = .17
            first = False
            x += w + int(g.integers(14, 40))
        self.wall, self.lit = wall, lit
        self.acc = np.zeros_like(lit)
        if self.today_pane:
            self.acc[self.today_pane] = np.clip(lit[self.today_pane] * 1.6, .5, 1.3)
            lit[self.today_pane] *= .25
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        du = xx if corner == 'l' else self.w - xx
        lamp_v = SKYM + 7 * TH + SHOP - (BASE - LAMP[1]) / ((BASE - ROOF) / (7 * TH + SHOP))
        d = np.hypot(du, yy - lamp_v)
        self.lampfall = 1 / (1 + (d / 170) ** 2)
        self.air = .30 + .70 * np.exp(-du / (self.w * .62))

    def tone(self, t):
        lit = self.lit.copy()
        for sl, ph, kind in self.flick:
            if kind == 'tv':
                k = int((t + ph) * N / 2)
                lit[sl] *= .45 + .55 * np.random.default_rng(k * 7 + int(ph * 1e4)).random()
            else:
                lit[sl] *= 1.0 if ((t + ph) % 1.0) < .62 else .05
        glow = blur(lit, 9) * .55 + blur(lit, 34) * .55
        wall = self.wall * (1.15 + 1.5 * self.lampfall + 3.0 * np.clip(glow, 0, .6))
        return wall * (.55 + .45 * self.air) + (lit + glow * .20) * self.air


def homography(src, dst):
    """Coefficients for PIL's PERSPECTIVE transform: output point (x, y) -> source point (u, v)."""
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float))


def warp(tex, quad):
    """Put a texture on the sheet with its corners at quad (TL, TR, BR, BL). Far parts come from a softer copy."""
    h, w = tex.shape
    co = homography(quad, [(0, 0), (w, 0), (w, h), (0, h)])
    a = Image.fromarray(tex, 'F').transform((W, H), Image.PERSPECTIVE, tuple(co), Image.BICUBIC)
    b = Image.fromarray(blur(tex, 2.6), 'F').transform((W, H), Image.PERSPECTIVE, tuple(co), Image.BILINEAR)
    far = np.clip((np.abs(np.arange(W) - CX) - 150) / 330, 0, 1)[None, :]
    return np.asarray(a, np.float32) * (1 - far) + np.asarray(b, np.float32) * far


NAME = {
    's': (.66, [[(.54, .17), (.42, .03), (.22, .02), (.08, .15), (.11, .35), (.30, .49), (.49, .63), (.53, .83), (.40, .97), (.19, .98), (.04, .84)]]),
    'c': (.66, [[(.55, .21), (.42, .04), (.23, .02), (.08, .20), (.04, .50), (.08, .80), (.23, .98), (.42, .96), (.55, .79)]]),
    'r': (.52, [[(.08, .02), (.08, 1.0)], [(.08, .36), (.17, .13), (.31, .03), (.46, .06)]]),
    'y': (.66, [[(.04, .02), (.31, .97)], [(.58, .02), (.31, .97), (.20, 1.28), (.02, 1.40)]]),
    't': (.50, [[(.20, -.30), (.20, .76), (.27, .93), (.44, .98)], [(.01, .06), (.44, .06)]]),
}


def catmull(pts, n=14):
    p = np.array(pts, float)
    if len(p) < 3:
        return p
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return np.array(out)


def name_sign(x, y, xh):
    """The name as a small neon tube: one mask per letter so a letter can flicker."""
    masks, cx = [], x
    for ch in 'scryst':
        adv, strokes = NAME[ch]
        im = Image.new('L', (W * 3, H * 3), 0)
        d = ImageDraw.Draw(im)
        for st in strokes:
            pts = catmull(st)
            pts = [((cx + (px - .10 * (py - 1)) * xh) * 3, (y + py * xh) * 3) for px, py in pts]
            d.line(pts, fill=255, width=6, joint='curve')
            for p in (pts[0], pts[-1]):
                d.ellipse((p[0] - 3.5, p[1] - 3.5, p[0] + 3.5, p[1] + 3.5), fill=255)
        masks.append(np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255)
        cx += (adv + .16) * xh
    return masks, cx - x


def shopfront(g, h, w, bright):
    """What shows through one shop's glass: a store with shelves, a bar behind a door curtain, or a laundry."""
    kind = 'store' if bright else g.choice(['store', 'bar', 'laundry'], p=[.45, .35, .20])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f = np.full((h, w), g.uniform(.75, 1.0) if kind != 'bar' else g.uniform(.30, .45), np.float32)
    f *= 1.12 - .30 * yy / h
    if kind == 'store':
        for k in range(int(w // 44) + 1):
            x0 = int(8 + k * 44 + g.integers(-3, 4)); x1 = min(x0 + int(g.integers(22, 30)), w - 4)
            if x1 - x0 < 10:
                continue
            for y in range(int(h * .34), h - 14, 11):
                f[y:y + 2, x0:x1] *= .25
                x = x0 + 1
                while x < x1 - 3:
                    ww, hh = int(g.integers(2, 6)), int(g.integers(4, 9))
                    f[y - hh:y, x:min(x + ww, x1)] *= g.uniform(.25, .95)
                    x += ww + int(g.integers(0, 2))
        f[:int(h * .16), :] *= .55 + .45 * (blur(g.random((int(h * .16), w)).astype(np.float32), (0, 5)) > .5)
        d = int(w * g.uniform(.35, .6))
        f[:, d - 1:d + 1] *= .15; f[:, d + 15:d + 17] *= .15; f[int(h * .5):int(h * .5) + 6, d + 3:d + 5] *= .2
    elif kind == 'bar':
        d0, d1 = int(w * .30), int(w * .30) + 34
        f[:, :d0] *= .35; f[:, d1:] *= .35
        f[:, d0:d1] *= 2.4
        for k in range(4):
            f[:int(h * g.uniform(.28, .36)), d0 + 1 + k * 8:d0 + 8 + k * 8] *= .22
        wx = min(d1 + 14, w - 26)
        f[int(h * .25):int(h * .50), wx:wx + 20] *= 4.0
        f[int(h * .25):int(h * .50), wx + 9:wx + 11] *= .3
    else:
        for k in range(int((w - 16) // 26)):
            cx, cy = 20 + k * 26, h * .56
            rr = np.hypot(xx - cx, yy - cy)
            f[(rr < 9.5) & (rr > 7)] *= .25
            f[rr <= 7] *= g.uniform(.45, .8)
            f[int(h * .28):int(h * .30), cx - 11:cx + 11] *= .3
        f[int(h * .80):int(h * .86), 6:w - 6] *= .35
    step = int(g.integers(26, 40))
    f[:, ::step] *= .22; f[:, 1::step] *= .22
    f[-int(g.integers(10, 16)):, :] *= .35
    return f


class Scene:
    def __init__(self, lv, seed=5):
        g = self.g = np.random.default_rng(seed)
        self.left = Face(lv[:26], 'r', seed + 1)
        days = [j for j in range(7) if lv[52, j] >= 0]
        self.right = Face(lv[26:][::-1], 'l', seed + 2, today=(0, days[-1]))
        f = (VP - 690) / VP
        k = (BASE - ROOF) / (7 * TH + SHOP)
        top = ROOF - SKYM * k
        far_roof, far_base = HORIZON + (top - HORIZON) * f, HORIZON + (BASE - HORIZON) * f
        self.qr = [(CX, top), (CX + 690, far_roof), (CX + 690, far_base), (CX, BASE)]
        self.ql = [(CX - 690, far_roof), (CX, top), (CX, BASE), (CX - 690, far_base)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.kerb = BASE + (far_base - BASE) * np.abs(xx - CX) / 690
        self.street = yy > self.kerb
        body = np.zeros((self.left.h, self.left.w), np.float32); body[SKYM - 6:] = 1
        bodyr = np.zeros((self.right.h, self.right.w), np.float32); bodyr[SKYM - 6:] = 1
        self.cover = np.clip(warp(body, self.ql) + warp(bodyr, self.qr), 0, 1)
        self.masks, self.name_w = name_sign(CX + 24, BASE - 64, 12.0)
        self.edge = np.clip((W / 2 - np.abs(xx - W / 2) - 4) / 190, 0, 1) ** .7
        self.skyline()
        self.figure()
        self.wires()
        z = Image.new('L', (W * 3, H * 3), 0)
        dz = ImageDraw.Draw(z)
        eye = 1 / PXM
        zc = eye * VP / (FEET[1] - HORIZON)
        row = lambda d: HORIZON + eye * VP / d
        col = lambda xm, d: CX + xm * VP / d
        xm = -ROAD_HALF + .25
        while xm + .5 <= ROAD_HALF:
            dz.polygon([(col(xm, zc + 2) * 3, row(zc + 2) * 3), (col(xm + .5, zc + 2) * 3, row(zc + 2) * 3),
                        (col(xm + .5, zc - 2) * 3, row(zc - 2) * 3), (col(xm, zc - 2) * 3, row(zc - 2) * 3)], fill=255)
            xm += 1.0
        self.zebra = np.asarray(z.resize((W, H), Image.LANCZOS), np.float32) / 255

    def skyline(self):
        """Far towers behind the block: only their lit rooms and edges reach us."""
        g = self.g
        sky = np.zeros((H, W), np.float32)
        self.far_beacons = []
        for side in (0, 1):
            x = 0 if side == 0 else W - 420
            end = 420 if side == 0 else W
            while x < end:
                w = int(g.integers(34, 92))
                d = abs((x + w / 2) - CX)
                top = int(g.integers(70, 250))
                sky[top:int(HORIZON) + 8, x:x + w] = .026
                sky[top:top + 1, x:x + w] = .09
                sky[top:int(HORIZON) + 8, x:x + 1] = .07
                for wy in range(top + 6, int(HORIZON), 9):
                    for wx in range(x + 4, x + w - 4, 7):
                        if g.random() < .16:
                            sky[wy:wy + 4, wx:wx + 3] = g.uniform(.14, .5)
                if g.random() < .3:
                    h = int(g.integers(20, 60))
                    sky[top - h:top, x + w // 2:x + w // 2 + 1] = .07
                    self.far_beacons.append((x + w // 2, top - h - 1, g.uniform(0, 1)))
                x += w + int(g.integers(-8, 40))
        glow = np.clip(1 - np.abs(self.yy - (HORIZON - 40)) / 230, 0, 1) ** 2 * .05
        cloud = blur(g.random((H, W)).astype(np.float32), (12, 60))
        cloud = (cloud - cloud.min()) / (cloud.max() - cloud.min())
        self.sky = sky + glow * (.2 + 1.3 * cloud) * (self.yy < HORIZON)

    def figure(self, sway=0.0):
        """Someone waiting at the crossing under an umbrella, looking up at the block."""
        m, ax, ay = people.waiting(FIG_H, sway)
        fig = np.zeros((H, W), np.float32)
        x0, y0 = int(round(FEET[0] - ax)), int(round(FEET[1] - ay))
        fig[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m[:H - y0]
        self.fig = fig

    def wires(self):
        g = self.g
        im = Image.new('L', (W * 2, H * 2), 0)
        d = ImageDraw.Draw(im)
        near = Image.new('L', (W * 2, H * 2), 0)
        dn = ImageDraw.Draw(near)
        self.runs = []

        def pole(dr, x, top, w, arms, ins=12):
            dr.rectangle((x * 2 - w, top * 2, x * 2 + w, H * 2), fill=255)
            ends = []
            for ay, half in arms:
                dr.rectangle(((x - half) * 2, ay * 2 - w // 3, (x + half) * 2, ay * 2 + w // 3), fill=255)
                for k in (-1, -.55, .55, 1):
                    ix = x + k * half
                    dr.rectangle((ix * 2 - w // 3, ay * 2 - ins, ix * 2 + w // 3, ay * 2), fill=255)
                    ends.append((ix, ay - ins / 2))
            return ends

        def run(dr, p, q, sag, width=3, keep=True):
            pts = [(p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u + sag * 4 * u * (1 - u)) for u in np.linspace(0, 1, 200)]
            dr.line([(x * 2, y * 2) for x, y in pts], fill=255, width=width)
            if keep:
                self.runs.append(np.array(pts, np.float32))

        a = pole(dn, 322, -10, 26, [(64, 128), (108, 92)], ins=28)
        dn.rounded_rectangle((346 * 2, 150 * 2, 396 * 2, 246 * 2), radius=22, fill=255)
        dn.rectangle((334 * 2, 172 * 2, 350 * 2, 180 * 2), fill=255)
        dn.rectangle((334 * 2, 218 * 2, 350 * 2, 226 * 2), fill=255)
        fins = Image.new('L', (W * 2, H * 2), 0)
        df = ImageDraw.Draw(fins)
        for i in range(5):
            df.rectangle((350 * 2, (164 + i * 17) * 2, 392 * 2, (166 + i * 17) * 2), fill=255)
        self.fins = np.asarray(fins.resize((W, H), Image.LANCZOS), np.float32) / 255
        for e in a:
            run(d, (-40, e[1] + g.uniform(-30, 50)), e, g.uniform(10, 30), width=3, keep=False)
        for e in a[:4]:
            run(d, e, (W + 1100, e[1] + g.uniform(-8, 8)), g.uniform(190, 240), width=3)
        for e in a[4:]:
            run(d, e, (W + 1100, e[1] + g.uniform(-8, 8)), g.uniform(210, 260), width=3)
        run(d, (384, 160), (W + 40, 290), 70, width=3)
        m = np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255
        n = np.asarray(near.resize((W, H), Image.LANCZOS), np.float32) / 255
        soft = blur(n, 2.6)
        mix = np.clip((self.xx - 420) / 460, 0, 1) * .55
        self.occl = np.clip(np.maximum(blur(m, .8), soft * (1 - mix) + blur(n, 1.0) * mix) * 1.15, 0, 1)
        self.near = np.clip(soft * 1.2, 0, 1)

    def tone(self, t):
        g = np.random.default_rng(int(round(t * N)) + 1000)
        w1 = 2 * math.pi * t
        xx, yy = self.xx, self.yy
        block = warp(self.left.tone(t), self.ql) + warp(self.right.tone(t), self.qr)
        T = self.sky * (1 - self.cover) + block
        A = np.zeros((H, W), np.float32)
        A += warp(self.right.acc, self.qr) * (1 + .06 * math.sin(5 * w1))
        for i, m in enumerate(self.masks):
            on = 1.0
            if i == 3:
                ph = (t * 3 + .5) % 1.0
                on = .15 if (ph < .06 or .12 < ph < .16) else 1.0
            A += m * on
        for face, quad in ((self.left, self.ql), (self.right, self.qr)):
            co = homography([(0, 0), (face.w, 0), (face.w, face.h), (0, face.h)], quad)
            for bx, by, ph in face.beacons:
                den = co[6] * bx + co[7] * by + 1
                sx, sy = (co[0] * bx + co[1] * by + co[2]) / den, (co[3] * bx + co[4] * by + co[5]) / den
                if ((t * 2 + ph) % 1.0) < .5:
                    A += 1.3 * np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / 10.0)
        for bx, by, ph in self.far_beacons:
            if ((t * 2 + ph) % 1.0) < .5:
                A += 1.0 * np.exp(-((xx - bx) ** 2 + (yy - by) ** 2) / 5.0)
        spill = blur(A, 10) * 1.5 + blur(A, 36) * 2.2
        lx, ly = LAMP
        r = np.hypot(xx - lx, yy - ly)
        breathe = 1 + .05 * math.sin(3 * w1) + .03 * math.sin(7 * w1 + 1)
        dx, dy = np.abs(xx - lx), np.abs(yy - ly)
        lamp = 2.0 * np.exp(-(r / 6.5) ** 2) + .60 * np.exp(-r / 22) + .16 * np.exp(-r / 110)
        lamp += .30 * np.exp(-dy / 1.2) * np.exp(-dx / 70) + .10 * np.exp(-dy / 4) * np.exp(-dx / 60)
        lamp += .25 * np.exp(-dx / 1.2) * np.exp(-dy / 26)
        cone = (yy > ly) * np.exp(-((xx - lx) / (10 + .55 * np.clip(yy - ly, 0, None))) ** 2) * np.exp(-np.clip(yy - ly, 0, None) / 150) * .20
        T += lamp * (1 + (breathe - 1) * np.exp(-r / 30)) + cone
        hood = ((np.abs(xx - lx) < 9) & (yy > ly - 11) & (yy < ly - 6)) | ((xx > lx - 1) & (xx < CX + 3) & (yy > ly - 15) & (yy < ly - 10))
        T *= 1 - .95 * blur(hood.astype(np.float32), .6)
        A_all = A * 1.4 + spill * .8
        src = np.clip(2 * self.kerb - yy, 0, H - 1).astype(int)
        cols = np.arange(W)[None, :].repeat(H, 0)
        R, RA = T[src, cols], A_all[src, cols]
        R = ndimage.uniform_filter1d(R, 21, axis=0)
        RA = ndimage.uniform_filter1d(RA, 25, axis=0)
        shift = np.round(3.0 * np.sin(np.arange(H) * 1.3 + w1 * 2)).astype(int)
        R = np.stack([np.roll(R[i], shift[i]) for i in range(H)])
        RA = np.stack([np.roll(RA[i], shift[i]) for i in range(H)])
        depth = np.clip((yy - self.kerb) / (H - BASE + 6), 0, 1)
        pool = np.exp(-np.hypot((xx - lx) / 260, (yy - BASE - 30) / 90) ** 2)
        road = R * .78 * (1 - depth) ** .9 + self.zebra * (.10 + .30 * pool) + .05 * pool
        T = np.where(self.street, road, T)
        A_all = np.where(self.street, RA * .95 * (1 - depth) ** .8, A_all)
        T += np.exp(-np.abs(yy - self.kerb) / 1.5) * .10 * np.exp(-np.abs(xx - CX) / 420)
        T *= 1 - .7 * ndimage.uniform_filter1d(np.roll(self.fig[::-1], int(2 * FEET[1] - H), 0), 9, axis=0) * self.street
        T *= 1 - .97 * self.fig
        A_all *= 1 - .97 * self.fig
        T += np.clip(self.fig - np.roll(self.fig, -2, 1), 0, 1) * .50 * np.exp(-np.abs(yy - ly - 60) / 90)
        u = (t * 1.0) % 1.0
        if u < .62:
            kline = (BASE - HORIZON) / VP * 1.08
            for lag in range(22):
                uu = u - lag * .0012
                if uu <= 0:
                    continue
                e = uu / .62
                px = CX + 70 + (CX + 690 - (CX + 70)) * (1 - (1 - e) ** 2.2)
                py = HORIZON + (CX + VP - px) * kline
                m = PXM * (py - HORIZON)
                half, size = .75 * m, max(.13 * m, .9)
                on = min(u / .05, 1.0) * (1.0 - lag * .043)
                for off in (-1, 1):
                    spot = np.exp(-(((xx - px - off * half) / size) ** 2 + ((yy - py) / (size * .7)) ** 2))
                    wet = np.exp(-((xx - px - off * half) / (size * 1.2)) ** 2) * np.exp(-np.clip(yy - py, 0, None) / (2.2 * m)) * (yy > py)
                    A_all += on * (.9 * spot + .35 * wet)
        air = blur(T, 30) * .085
        T += air
        T *= 1 - .97 * self.occl
        A_all *= 1 - .97 * self.occl
        T += np.clip(self.occl - np.roll(self.occl, 1, 0), 0, 1) * (.10 + .8 * np.exp(-r / 320))
        T += self.near * (.06 + .16 * np.exp(-r / 380)) + np.clip(self.near - np.roll(self.near, -5, 1), 0, 1) * .75 * np.exp(-r / 520)
        T *= 1 - .6 * blur(self.fins, .8)
        for k, pts in enumerate(self.runs[::2]):
            u2 = (t * (1 + k % 2) + k * .29) % 1.0
            x, y = pts[int(u2 * (len(pts) - 1))]
            T += 1.5 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 4.5)
        rain = Image.new('L', (W, H), 0)
        dr = ImageDraw.Draw(rain)
        for _ in range(300):
            x, y = g.uniform(-20, W), g.uniform(-30, H)
            ln = g.uniform(12, 34)
            dr.line((x, y, x + ln * .2, y + ln), fill=int(g.uniform(90, 255)), width=1)
        rn = np.asarray(rain, np.float32) / 255
        T += rn * (.025 + 1.1 * np.clip(blur(T, 12), 0, .5) + .5 * cone)
        return T, A_all


class Plate:
    def __init__(self, seed=11):
        g = np.random.default_rng(seed)
        yy = np.arange(H)[:, None] + 0 * np.arange(W)[None, :]
        tri = np.abs(((yy / 3.0) % 1.0) * 2 - 1)

        def screen():
            n = blur(g.random((H, W)), .5)
            r = np.empty(n.size)
            r[np.argsort(n, axis=None)] = np.arange(n.size) / n.size
            return .80 * tri + .20 * r.reshape(H, W)
        self.s = [screen() for _ in range(4)]
        n = blur(g.random((H, W)), (.6, 2.2))
        r = np.empty(n.size)
        r[np.argsort(n, axis=None)] = np.arange(n.size) / n.size
        self.fade = r.reshape(H, W)

    def pull(self, T, A, edge=None):
        """Index image: 0 clear, 1-3 inks from dim to bright, 4 accent."""
        idx = np.zeros((H, W), np.uint8)
        idx[T > .030 + .22 * self.s[0]] = 1
        idx[T > .27 + .36 * self.s[1]] = 2
        idx[T > .70 + .45 * self.s[2]] = 3
        idx[A > .13 + .95 * self.s[3]] = 4
        if edge is not None:
            idx[self.fade > edge] = 0
        return idx


def rgba(idx, theme):
    c = THEMES[theme]
    pal = np.array([(0, 0, 0)] + c['inks'] + [c['accent']], np.uint8)
    return Image.fromarray(np.dstack([pal[idx], np.where(idx > 0, 255, 0).astype(np.uint8)]), 'RGBA')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'dist'
    os.makedirs(out, exist_ok=True)
    login = os.environ.get('PROFILE_LOGIN') or os.environ.get('GITHUB_REPOSITORY_OWNER') or 'scryst'
    scene, plate = Scene(levels(calendar(login))), Plate()
    frames = [plate.pull(*scene.tone(i / N), scene.edge) for i in range(N)]
    for theme in THEMES:
        full = [rgba(f, theme) for f in frames]
        for name, ims in ((f'night-{theme}.webp', full), (f'night-phone-{theme}.webp', [im.crop((PHONE[0], 0, PHONE[1], H)) for im in full])):
            path = os.path.join(out, name)
            ims[0].save(path, save_all=True, append_images=ims[1:], duration=1000 // FPS, loop=0, lossless=True, method=4, minimize_size=True)
            print(name, os.path.getsize(path))


if __name__ == '__main__':
    main()
