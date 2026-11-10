"""People for the night banner, as silhouettes built from a skeleton: limbs are tapered and fused at the joints."""
import math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SS = 10


class Pen:
    def __init__(self, w, h, unit, ox, oy):
        self.im = Image.new('L', (int(w * SS), int(h * SS)), 0)
        self.d = ImageDraw.Draw(self.im)
        self.u, self.ox, self.oy = unit * SS, ox * SS, oy * SS

    def p(self, x, y):
        return (self.ox + x * self.u, self.oy - y * self.u)

    def limb(self, a, b, ra, rb):
        (ax, ay), (bx, by) = self.p(*a), self.p(*b)
        ra, rb = ra * self.u, rb * self.u
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        self.d.polygon([(ax + nx * ra, ay + ny * ra), (bx + nx * rb, by + ny * rb), (bx - nx * rb, by - ny * rb), (ax - nx * ra, ay - ny * ra)], fill=255)
        self.d.ellipse((ax - ra, ay - ra, ax + ra, ay + ra), fill=255)
        self.d.ellipse((bx - rb, by - rb, bx + rb, by + rb), fill=255)

    def poly(self, pts):
        self.d.polygon([self.p(*q) for q in pts], fill=255)

    def oval(self, c, rx, ry, rot=0.0, n=40):
        ca, sa = math.cos(rot), math.sin(rot)
        self.poly([(c[0] + rx * math.cos(t) * ca - ry * math.sin(t) * sa, c[1] + rx * math.cos(t) * sa + ry * math.sin(t) * ca)
                   for t in np.linspace(0, 2 * math.pi, n, endpoint=False)])

    def line(self, a, b, w):
        self.d.line([self.p(*a), self.p(*b)], fill=255, width=max(1, int(round(w * self.u))))

    def mask(self, fuse):
        """Fuse the parts (a blur and a cut rounds every joint the way cloth does), then bring it down to size."""
        a = np.asarray(self.im, np.float32) / 255
        a = ndimage.gaussian_filter(a, fuse * self.u) > .5
        lab, n = ndimage.label(~a)
        if n > 1:
            size = ndimage.sum(np.ones_like(lab), lab, np.arange(1, n + 1))
            a |= np.isin(lab, 1 + np.flatnonzero(size < (.04 * self.u) ** 2))
        a = a.astype(np.float32)
        im = Image.fromarray((a * 255).astype(np.uint8))
        return np.asarray(im.resize((im.width // SS, im.height // SS), Image.LANCZOS), np.float32) / 255


def waiting(h=74.0, sway=0.0):
    """Side on, facing right. Units are body heights; y is up from the ground."""
    w_px, h_px = int(h * 1.1), int(h * 1.34)
    pen = Pen(w_px, h_px, h, w_px * .46, h_px - 2)
    lean = .012 * sway
    pen.limb((-.01, .50), (-.012, .27), .046, .038)
    pen.limb((-.012, .27), (-.03, .05), .036, .028)
    pen.limb((-.058, .017), (.05, .012), .021, .013)
    pen.limb((.012, .50), (.086, .285), .045, .037)
    pen.limb((.086, .285), (.10, .05), .035, .027)
    pen.limb((.072, .017), (.19, .012), .021, .013)
    pen.limb((0, .52), (-.012 + lean, .70), .062, .070)
    pen.limb((-.012 + lean, .70), (-.008 + lean, .80), .070, .050)
    pen.poly([(-.070 + lean, .805), (.050 + lean, .805), (.070 + lean, .74), (.066, .60), (.082, .33),
              (-.02, .325), (-.100 - .008 * sway, .32), (-.082, .60), (-.082 + lean, .74)])
    pen.limb((-.040 + lean, .79), (-.086, .655), .034, .029)
    pen.limb((-.086, .655), (-.058, .56), .029, .024)
    nb, hd = (.0 + lean, .82), (.026 + lean, .915)
    pen.limb(nb, (.014 + lean, .872), .025, .023)
    pen.oval(hd, .046, .056, rot=-.18)
    pen.oval((hd[0] - .012, hd[1] + .010), .047, .050)
    a = math.radians(10 + 1.5 * sway)
    C, R, dome, shaft = (.03 + lean, 1.085), .33, .135, .40
    rot = lambda x, y: (C[0] + x * math.cos(a) - y * math.sin(a), C[1] + x * math.sin(a) + y * math.cos(a))
    hand = rot(0, -shaft)
    pen.limb((.020 + lean, .79), (.072, .625), .033, .028)
    pen.limb((.072, .625), hand, .027, .022)
    top = [rot(R * math.cos(t), dome * math.sin(t) ** .85) for t in np.linspace(0, math.pi, 40)]
    tips = [-R * math.cos(t) for t in np.linspace(0, math.pi, 7)]
    edge = []
    for x0, x1 in zip(tips[:-1], tips[1:]):
        for s in np.linspace(0, 1, 8):
            edge.append(rot(x0 + (x1 - x0) * s, .030 * math.sin(math.pi * s) * (.5 + .5 * (x1 - x0) / (R * .5))))
    pen.poly(top + edge)
    fused = pen.mask(.006)
    thin = Pen(w_px, h_px, h, w_px * .46, h_px - 2)
    thin.line(rot(0, dome * .9), rot(0, dome + .05), .012)
    thin.line(rot(0, .02), rot(0, -shaft - .03), .013)
    hx, hy = rot(0, -shaft - .03)
    thin.d.arc([thin.p(hx, hy)[0] - .0 * thin.u, thin.p(hx, hy)[1] - .022 * thin.u, thin.p(hx, hy)[0] + .05 * thin.u, thin.p(hx, hy)[1] + .028 * thin.u], 20, 180, fill=255, width=int(.013 * thin.u))
    m = np.maximum(fused, thin.mask(.001))
    return m, w_px * .46, h_px - 2


POSES = ['frame', 'phone', 'cup', 'crossed', 'sill', 'smoke', 'desk', 'read', 'talk', 'curtain', 'walk', 'sofa', 'shoulder']


def bust(pw, ph, g, avoid=()):
    """Someone in a lit room, seen through one pane, doing something. Units are pane heights; y is up from the sill."""
    pen = Pen(pw, ph, ph, 0, ph)
    X = pw / ph
    kind = str(g.choice([k for k in POSES if k not in avoid] or POSES))
    s = float(g.uniform(.84, 1.04))
    sw = float(g.uniform(.104, .138))
    hair = str(g.choice(['short', 'short', 'long', 'bun', 'tail', 'cap']))
    R = math.radians

    def person(cx, hip_y, lean=0.0, tilt=0.0, turn=0.0, left=(8, 6), right=(8, 6), s=s, sw=sw, hair=hair, head=0.0, legs=True):
        """lean: spine off vertical (deg, + to the right). left/right: (upper arm, elbow) angles from hanging, + outward."""
        ux, uy = math.sin(R(lean)), math.cos(R(lean))
        px, py = -uy, ux
        neck = (cx + ux * .33 * s, hip_y + uy * .33 * s)
        w = sw * s * (1 - .28 * abs(turn))
        sl = (neck[0] + px * w + ux * .012 * tilt, neck[1] + py * w - .012 * tilt * s)
        sr = (neck[0] - px * w - ux * .012 * tilt, neck[1] - py * w + .012 * tilt * s)
        hl, hr = (cx + px * .095 * s, hip_y + py * .095 * s), (cx - px * .095 * s, hip_y - py * .095 * s)
        pen.poly([(neck[0] + px * .04 * s, neck[1] + .03 * s), (neck[0] - px * .04 * s, neck[1] + .03 * s), sr,
                  (cx - px * .082 * s + ux * .14 * s, hip_y + uy * .14 * s), hr, hl, (cx + px * .082 * s + ux * .14 * s, hip_y + uy * .14 * s), sl])
        if legs:
            pen.poly([hl, hr, (hr[0] + .012, -.06), (hl[0] - .012, -.06)])
        hands = []
        for (a1, a2), sh, side in ((left, sl, -1), (right, sr, 1)):
            b1 = R(a1) * side + R(lean)
            el = (sh[0] + math.sin(b1) * .165 * s, sh[1] - math.cos(b1) * .165 * s)
            b2 = b1 + R(a2) * side
            hd = (el[0] + math.sin(b2) * .155 * s, el[1] - math.cos(b2) * .155 * s)
            pen.limb((sh[0] - side * .012 * s, sh[1] - .014 * s), el, .031 * s, .026 * s)
            pen.limb(el, hd, .026 * s, .022 * s)
            hands.append(hd)
        hc = (neck[0] + ux * .095 * s + turn * .022 * s + math.sin(R(head)) * .03 * s, neck[1] + uy * .095 * s)
        pen.limb((neck[0], neck[1] + .01 * s), (hc[0], hc[1] - .05 * s), .028 * s, .026 * s)
        hw, hh = .058 * s * (1 - .10 * abs(turn)), .074 * s
        pen.oval(hc, hw, hh, rot=-R(head))
        back = -1 if turn >= 0 else 1
        if hair == 'long':
            pen.limb((hc[0], hc[1] + .012 * s), (hc[0] + back * .012 * s, neck[1] - .03 * s), hw * 1.12, hw * 1.15)
        elif hair == 'bun':
            pen.oval((hc[0] + back * .03 * s, hc[1] + hh * .92), .032 * s, .03 * s)
            pen.oval((hc[0], hc[1] + .016 * s), hw * 1.06, hh * .84)
        elif hair == 'tail':
            pen.oval((hc[0], hc[1] + .016 * s), hw * 1.06, hh * .84)
            pen.limb((hc[0] + back * hw, hc[1] + .02 * s), (hc[0] + back * (hw + .035 * s), hc[1] - .08 * s), .024 * s, .012 * s)
        elif hair == 'cap':
            pen.oval((hc[0], hc[1] + .026 * s), hw * 1.08, hh * .70)
            pen.poly([(hc[0], hc[1] + .03 * s), (hc[0] - back * (hw + .05 * s), hc[1] + .018 * s), (hc[0] - back * hw, hc[1] + .045 * s)])
        else:
            pen.oval((hc[0], hc[1] + .016 * s), hw * 1.06, hh * .84)
        return dict(neck=neck, head=hc, hands=hands, sl=sl, sr=sr)

    cx = X * float(g.uniform(.36, .64))
    hip = .13
    if kind == 'frame':
        cx = X * .60
        person(cx, hip, lean=12, tilt=2, right=(104, 52), left=(12, 10), head=-10)
    elif kind == 'phone':
        person(cx, hip, lean=-4, tilt=-1.5, left=(10, -158), right=(9, 12), head=14, turn=.3)
    elif kind == 'cup':
        q = person(cx, hip, lean=3, turn=.55, right=(14, -118), left=(12, -22), head=-6)
        hx, hy = q['hands'][1]
        pen.poly([(hx - .012, hy + .03), (hx + .03, hy + .03), (hx + .026, hy - .012), (hx - .008, hy - .012)])
    elif kind == 'crossed':
        person(cx, hip, lean=-5, tilt=1, left=(5, -97), right=(5, -94), head=-14)
    elif kind == 'sill':
        q = person(cx, -.10, lean=6, tilt=-1.5, left=(40, -128), right=(58, -92), head=10, legs=False)
        pen.limb(q['hands'][0], (q['head'][0] - .03, q['head'][1] - .07 * s), .026 * s, .028 * s)
    elif kind == 'smoke':
        q = person(cx, -.06, lean=12, turn=.5, left=(55, -70), right=(20, -138), head=6, legs=False)
        hx, hy = q['hands'][1]
        pen.line((hx, hy + .01), (hx + .05, hy + .028), .009)
    elif kind == 'desk':
        cx = X * .36
        q = person(cx, .10, lean=14, turn=.8, sw=sw * .8, left=(30, -75), right=(34, -78), head=16, legs=False)
        dy = q['hands'][1][1] - .02
        mx = min(X - .05, cx + .33 * s)
        pen.poly([(cx + .10 * s, dy), (X, dy), (X, dy - .026), (cx + .10 * s, dy - .026)])
        pen.poly([(mx - .012, dy), (mx + .012, dy), (mx + .034, dy + .22 * s), (mx + .010, dy + .22 * s)])
        pen.poly([(cx - .13 * s, -.06), (cx - .10 * s, -.06), (cx - .155 * s, .30 * s), (cx - .185 * s, .30 * s)])
    elif kind == 'read':
        cx = X * .46
        q = person(cx, .06, lean=-13, turn=-.6, sw=sw * .85, left=(26, -96), right=(32, -104), head=-20, legs=False)
        bx, by = (q['hands'][0][0] + q['hands'][1][0]) / 2, max(q['hands'][0][1], q['hands'][1][1])
        pen.poly([(bx - .06, by + .055), (bx + .012, by + .07), (bx + .03, by - .01), (bx - .045, by - .02)])
        pen.poly([(cx + .10 * s, -.06), (cx + .22 * s, -.06), (cx + .25 * s, .34 * s), (cx + .17 * s, .36 * s)])
    elif kind == 'talk':
        person(X * .30, hip, lean=5, turn=.7, right=(38, -70), left=(8, 8), sw=sw * .9, hair='long', head=-10)
        person(X * .74, -.14, lean=-8, turn=-.7, left=(12, -40), right=(10, 6), sw=sw * .9, hair='short', head=12, legs=False)
    elif kind == 'curtain':
        edge = X * .26
        pen.poly([(0, 1.1), (edge, 1.1)] + [(edge + .018 * math.sin(k * 1.9), 1.0 - k * .11) for k in range(11)] + [(0, -.06)])
        person(edge + .07 * s, hip, lean=-6, turn=.6, left=(46, -118), right=(8, 10), head=-12)
    elif kind == 'walk':
        cx = X * float(g.choice([.14, .86]))
        d = 1 if cx < X / 2 else -1
        person(cx, hip, lean=5 * d, turn=.9 * d, sw=sw * .72, left=(-22 * d, 14), right=(26 * d, 18), head=0)
    elif kind == 'sofa':
        q = person(cx, .0, lean=-3, left=(86, 6), right=(10, -30), head=9, legs=False)
        top = q['neck'][1] - .13 * s
        pen.poly([(0, top), (X, top), (X, -.06), (0, -.06)])
        pen.oval((.02, top), .05, .03); pen.oval((X - .02, top), .05, .03)
    else:
        person(cx, hip, lean=-7, turn=-.85, tilt=-2, left=(10, -18), right=(36, -112), head=-16)
    m = pen.mask(.007)
    if g.random() < .5 and kind not in ('desk', 'read'):
        m = m[:, ::-1]
    return m, kind
