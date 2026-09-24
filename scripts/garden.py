"""Prints the profile's living risograph, stdlib only.

  GH_TOKEN=... python3 scripts/garden.py dist/

The page is torn open and a garden is printed behind it. Four drums, as on a
real riso: yellow, fluorescent pink, blue and black. Every colour in the garden
is one of those inks or two of them overprinted, and each drum lands a little
out of register, differently on every print. The torn page is GitHub's own, so
the print comes in a light and a dark copy.

What the picture measures:
  meadow      one stem per day of the last year, height = contributions that day;
              the best days flower
  mountains   weekly totals; snow on the biggest
  fields      one field per month, brighter and busier for bigger months
  name        "scryst", drawn by hand as one inked vine growing out of the ground;
              its leaves are the year's days, left to right, in the season's
              overprint, and the biggest weeks bloom on it
  tendril     today: a bud that opens once there is work today
  ivy         the current streak, one pair of leaves a day, climbing out of the tear
  petals      this week's work, blowing out through the tear; today's lie on the page
  butterflies only on days with work, more on bigger days
  birds       the days worked in the last fortnight
  sky         the sun, or the moon in its real phase, where it is over Los Angeles
  wind        quickens when this week outpaces the year and just after a push
Only aggregate counts and the latest push time are read.
"""
import base64
import datetime as dt
import json
import math
import os
import random
import re
import struct
import sys
import urllib.request
import zlib
from pathlib import Path
from zoneinfo import ZoneInfo

W, H = 1280, 740
PAPER = (236, 235, 230)
INK = {"yellow": "#FFE800", "pink": "#FF48B0", "blue": "#0078BF", "black": "#2A2627"}
ANGLE = {"yellow": 0, "pink": 75, "blue": 15, "black": 45}
LA = ZoneInfo("America/Los_Angeles")


def on_paper(ink):
    """An ink's colour as it lands on the paper stock."""
    return "#" + "".join(f"{round(int(ink[i:i + 2], 16) * c / 255):02X}" for i, c in zip((1, 3, 5), PAPER))

# Every motion steps on one shared clock, like a flipbook animated on twos. It is
# the look, and it is what keeps the page light: the print is redrawn when the clock
# ticks, not on every screen refresh.
FPS = 12


def beat(seconds):
    """A time on the shared clock, as a whole number of frames."""
    return round(seconds * FPS)


def tempo(length, phase=0.0):
    """A looping motion's length, frame count and phase, all on the shared clock."""
    k = max(2, beat(length))
    return f"--t:{k / FPS:.4f}s;--k:{k};--d:{beat(phase) / FPS:.4f}s"


def glide(path, length, begin, turn=False):
    """Style that carries a shape along a path on the shared clock. CSS, not SMIL:
    browsers redraw a SMIL motion every screen frame even when it has not moved."""
    return f"offset-path:path('{path}');offset-rotate:{'auto' if turn else '0deg'};{tempo(length, begin)}"

# The torn page: GitHub's light and dark canvas, the paper's fibrous core where it
# tore, and the back of the page on the flaps that peeled away.
PAGE = {
    "light": {"rim": "#ffffff", "rim_op": 1, "shade": .15, "flap": ("#ffffff", "#dddcd6"), "crease": "#c4c3bd", "drop": .2},
    "dark": {"rim": "#c9d1d9", "rim_op": .6, "shade": .34, "flap": ("#343c47", "#1a2029"), "crease": "#05070a", "drop": .6},
}
CX, CY, RX, RY = 640, 372, 580, 314
FLAPS = [(-2.45, 230, 74), (-.1, 150, 48), (2.66, 130, 50)]   # (angle round the tear, crease length, depth)

# Leaf recipes per month: (drum, tone) pairs overprinted. Winter blue, spring lime,
# summer deep green, autumn oranges and plums.
LEAF = {
    12: [[("blue", .8)], [("blue", .55), ("pink", .15)]],
    1: [[("blue", .8)], [("blue", .6)]],
    2: [[("blue", .7), ("yellow", .3)], [("blue", .8)]],
    3: [[("yellow", 1), ("blue", .35)], [("yellow", .9), ("blue", .25)]],
    4: [[("yellow", 1), ("blue", .4)], [("yellow", 1), ("blue", .3)]],
    5: [[("yellow", 1), ("blue", .55)], [("yellow", 1), ("blue", .4)]],
    6: [[("yellow", 1), ("blue", .75)], [("yellow", 1), ("blue", .6)]],
    7: [[("yellow", 1), ("blue", .85)], [("yellow", .9), ("blue", 1)]],
    8: [[("yellow", 1), ("blue", .8)], [("yellow", 1), ("blue", .5)]],
    9: [[("yellow", 1), ("blue", .5)], [("yellow", 1), ("pink", .45)], [("yellow", 1), ("blue", .7)]],
    10: [[("yellow", 1), ("pink", .6)], [("yellow", 1), ("pink", .9)], [("pink", .7), ("blue", .35)]],
    11: [[("pink", .8), ("blue", .35)], [("yellow", 1), ("pink", 1)], [("pink", .6), ("yellow", .6)]],
}
FLOWER = {m: [("pink", 1)] if m in (3, 4, 5, 9, 10) else [("yellow", 1)] if m in (6, 7, 8) else [("pink", .8), ("blue", .6)]
          for m in range(1, 13)}
DEEP = [("blue", .95), ("yellow", .9), ("black", .3)]   # shade green
# Fields by season: (ground, drum for its furrows or blossom). Frost, lime, green, ochre.
FIELD = {m: ([("blue", .16)], "blue") if m in (12, 1, 2) else ([("yellow", .8), ("blue", .2)], "pink") if m in (3, 4, 5)
         else ([("yellow", .9), ("blue", .55)], "blue") if m in (6, 7, 8) else ([("yellow", .85), ("pink", .3)], "pink")
         for m in range(1, 13)}
AUTUMN = [[("yellow", 1), ("pink", .5)], [("yellow", .9), ("pink", .3)], [("yellow", 1), ("blue", .25), ("pink", .3)]]

# "scryst" as one cursive vine rooted in the ground: baseline y=0, x-height -100,
# ascender -176. Drawn by hand.
NAME = (
    "M-66 224 C-58 160 -86 40 -40 12 C-20 10 0 -40 48 -102 C40 -84 30 -66 44 -50 C62 -32 74 -14 60 0 C48 12 20 10 14 -4 "
    "C40 8 70 4 82 -30 C88 -55 94 -80 104 -92 C110 -100 126 -104 128 -94 C129 -86 120 -84 117 -90 "
    "C108 -96 86 -70 86 -40 C86 -12 100 0 116 -2 C134 -4 152 -16 170 -40 C176 -64 182 -92 190 -110 "
    "C194 -100 198 -92 204 -94 C210 -96 214 -100 217 -98 C214 -60 208 -30 214 -4 C218 8 234 2 248 -40 "
    "C252 -60 254 -80 256 -100 C248 -60 242 -14 260 -4 C276 6 294 -40 304 -100 "
    "C298 -40 294 40 282 104 C274 142 242 140 250 108 C258 72 302 20 352 -8 C364 -40 374 -76 390 -102 "
    "C382 -84 372 -66 386 -50 C404 -32 416 -14 402 0 C390 12 362 10 356 -4 "
    "C380 12 424 6 434 -30 C442 -70 446 -130 448 -176 C446 -120 438 -40 444 -8 C448 10 472 4 488 -22"
)
TENDRIL = "M488 -22 C502 -46 528 -30 518 -10 C510 4 492 -4 498 -16 C502 -24 511 -20 509 -14"
CROSS = "M416 -108 C438 -112 464 -116 490 -114"
SCALE, OX, OY = 1.38, 306, 352


# ---------- data ----------

def api(path, token, body=None):
    req = urllib.request.Request(f"https://api.github.com/{path}", body and json.dumps(body).encode(),
                                 {"Authorization": f"bearer {token}", "User-Agent": "scryst-garden"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def activity(login, token):
    q = ('query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{'
         'totalContributions weeks{contributionDays{date contributionCount}}}}}}')
    body = api("graphql", token, {"query": q, "variables": {"l": login}})
    if "errors" in body:
        sys.exit(f"graphql: {body['errors']}")
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    try:                                             # recency only nudges the wind; never fail on it
        events = api(f"users/{login}/events?per_page=1", token)
        last = dt.datetime.fromisoformat(events[0]["created_at"].replace("Z", "+00:00"))
    except (OSError, IndexError, KeyError, ValueError):
        last = None
    return days, cal["totalContributions"], last


def gust_period(days, total, last, now):
    pace = sum(c for _, c in days[-7:]) / max(1, total / 52.14)
    idle = (now - last).total_seconds() / 3600 if last else 1e9
    heat = 1.0 if idle < 1 else 0.5 if idle < 6 else 0.0
    return max(3.5, min(14.0, 11 / math.sqrt(max(pace, 0.25)) / (1 + heat)))


def streak(counts):
    """Days in a row with work, not broken by a today that has not started yet."""
    n, i = 0, len(counts) - 1 - (counts[-1] == 0)
    while i >= 0 and counts[i]:
        n, i = n + 1, i - 1
    return n


# ---------- the press ----------

class Press:
    """Collects artwork per drum; a shape inked on two drums overprints.

    Artwork is defined once and placed on each drum by reference. `knock` clears
    paper through every drum first, so a subject prints clean over what is behind it.
    Two layers: the garden behind the page, and what has got loose in front of it.
    """

    def __init__(self):
        self.layers = {"world": {p: [] for p in INK}, "free": {p: [] for p in INK}}
        self.over = {"world": [], "free": []}
        self.layer = "world"
        self.knocks: tuple[str, ...] = ("yellow", "pink", "blue")   # black joins once it has something to cut
        self.screens, self.defs, self.keyframes = {}, [], []

    def ink(self, plate, tone, fine=False):
        """A drum's ink at a tone: solid, or a dot screen. Small things (a leaf, a petal)
        get a finer screen, or three dots across would read as beads instead of a tint."""
        if tone >= 0.97:
            return INK[plate]
        pid = f"{plate}{round(tone * 100)}{'f' if fine else ''}"
        if pid not in self.screens:
            pitch = 2.7 if fine else 4.6
            r = pitch * math.sqrt(tone / math.pi)
            self.screens[pid] = (f'<pattern id="{pid}" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse" '
                                 f'patternTransform="rotate({ANGLE[plate]})"><circle cx="{pitch / 2}" cy="{pitch / 2}" '
                                 f'r="{r:.2f}" fill="{INK[plate]}"/></pattern>')
        return f"url(#{pid})"

    def texture(self, plate, kind, angle, size=9.0, weight=.35):
        """Line and dot work drawn by hand across a field: rows, dots or crosshatch."""
        pid = f"{kind}{plate}{round(angle)}{round(size * 10)}{round(weight * 100)}"
        if pid not in self.screens:
            c, s = INK[plate], size
            art = {"rows": f'<rect width="{s}" height="{s * weight:.2f}" fill="{c}"/>',
                   "dots": f'<circle cx="{s / 2}" cy="{s / 2}" r="{s * weight / 2:.2f}" fill="{c}"/>',
                   "hatch": f'<rect width="{s}" height="{s * weight / 2:.2f}" fill="{c}"/><rect width="{s * weight / 2:.2f}" height="{s}" fill="{c}"/>'}[kind]
            self.screens[pid] = (f'<pattern id="{pid}" width="{s}" height="{s}" patternUnits="userSpaceOnUse" '
                                 f'patternTransform="rotate({angle:.0f})">{art}</pattern>')
        return f"url(#{pid})"

    def raw(self, plate, svg):
        self.layers[self.layer][plate].append(svg)

    def glow(self, svg):
        """Light laid over every drum, for small bright things that move: a knockout
        would have to move on every drum with them."""
        self.over[self.layer].append(svg)

    def ref(self, svg):
        if svg.startswith("#"):
            return svg
        self.defs.append(f'<g id="a{len(self.defs)}">{svg}</g>')
        return f"#a{len(self.defs) - 1}"

    def put(self, recipe, svg, knock=True, paint="fill", fine=False):
        ref = self.ref(svg)
        if knock:
            self.clear(ref, paint=paint)
        for plate, tone in recipe:
            self.raw(plate, f'<use href="{ref}" {paint}="{tone if isinstance(tone, str) else self.ink(plate, tone, fine)}"/>')
        return ref

    def clear(self, svg, plates=None, paint="fill"):
        ref = self.ref(svg)
        for plate in plates or self.knocks:
            self.raw(plate, f'<use href="{ref}" {paint}="#fff"/>')
        return ref

    def run(self, rng):
        offs = {}
        for plate in INK:
            reach = 1.0 if plate == "black" else 2.4
            offs[plate] = (rng.uniform(-reach, reach), rng.uniform(-reach, reach))
        layers = {name: "".join(f'<g transform="translate({offs[p][0]:.1f} {offs[p][1]:.1f})" style="mix-blend-mode:multiply">'
                                f'{"".join(parts)}</g>' for p, parts in plates.items() if parts) + "".join(self.over[name])
                  for name, plates in self.layers.items()}
        return "".join(self.screens.values()) + "".join(self.defs), layers


# ---------- geometry ----------

NUM = re.compile(r"[MC]|-?\d*\.?\d+")


def place(d):
    toks, i, cur, segs, cmd = NUM.findall(d), 0, None, [], None
    f = lambda x, y: (OX + x * SCALE, OY + y * SCALE)
    while i < len(toks):
        if toks[i] in "MC":
            cmd, i = toks[i], i + 1
        v = [float(t) for t in toks[i:i + (2 if cmd == "M" else 6)]]
        if cmd == "M":
            cur, i, cmd = f(*v), i + 2, "C"
        else:
            p = [f(v[0], v[1]), f(v[2], v[3]), f(v[4], v[5])]
            segs.append((cur, *p))
            cur, i = p[2], i + 6
    return segs


def bez(s, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = s
    u = 1 - t
    x = u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3
    y = u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3
    dx = 3 * u * u * (x1 - x0) + 6 * u * t * (x2 - x1) + 3 * t * t * (x3 - x2)
    dy = 3 * u * u * (y1 - y0) + 6 * u * t * (y2 - y1) + 3 * t * t * (y3 - y2)
    n = math.hypot(dx, dy) or 1
    return x, y, dx / n, dy / n


def samples(segs, step=1.6):
    out, length = [], 0.0
    for s in segs:
        rough = sum(math.dist(bez(s, k / 16)[:2], bez(s, (k + 1) / 16)[:2]) for k in range(16))
        n = max(4, int(rough / step))
        for k in range(0 if not out else 1, n + 1):
            x, y, tx, ty = bez(s, k / n)
            if out:
                length += math.dist(out[-1][:2], (x, y))
            out.append((x, y, tx, ty, length))
    return out


def pen(pts, wmin, wmax):
    """Pointed pen: pressure on down-slanted strokes, eased along the line, tapered at both ends."""
    down = (-math.sin(math.radians(18)), math.cos(math.radians(18)))
    raw = [max(0.0, tx * down[0] + ty * down[1]) ** 1.4 for _, _, tx, ty, _ in pts]
    k, total = 14, pts[-1][4]
    out = []
    for i, (_, _, _, _, length) in enumerate(pts):
        win = raw[max(0, i - k):i + k + 1]
        taper = max(0.0, min(1.0, length / 40, (total - length) / 50))
        out.append((wmin + (wmax - wmin) * sum(win) / len(win)) * (0.3 + 0.7 * taper))
    return out


def wobble(rng, length, every=5.0, amp=0.9):
    """Smooth 1-D noise along a stroke, for ink that bleeds unevenly into the paper."""
    knots = [rng.uniform(-amp, amp) for _ in range(int(length / every) + 3)]

    def at(s):
        i, f = int(s / every), (s / every) % 1
        f = (1 - math.cos(math.pi * f)) / 2
        return knots[i] * (1 - f) + knots[i + 1] * f
    return at


def ribbon(pts, widths, rng):
    total = pts[-1][4]
    left_n, right_n = wobble(rng, total), wobble(rng, total)
    fine_l, fine_r = wobble(rng, total, 1.7, 0.35), wobble(rng, total, 1.7, 0.35)
    d = []
    for a in range(0, len(pts) - 1, 48):
        seg = list(zip(pts[a:a + 49], widths[a:a + 49]))
        left, right = [], []
        for (x, y, tx, ty, s), w in seg:
            wl = max(0.5, w / 2 + left_n(s) * min(1, w / 6) + fine_l(s))
            wr = max(0.5, w / 2 + right_n(s) * min(1, w / 6) + fine_r(s))
            left.append((x - ty * wl, y + tx * wl))
            right.append((x + ty * wr, y - tx * wr))
        d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in left + right[::-1]) + "Z")
    return "".join(d)


def line(pts, every=3):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y, *_ in pts[::every])


def poly(pts, close=True):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + ("Z" if close else "")


def smooth(values, sigma):
    r = int(3 * sigma)
    out = []
    for i in range(len(values)):
        ws = [(math.exp(-(j * j) / (2 * sigma * sigma)), values[i + j]) for j in range(-r, r + 1) if 0 <= i + j < len(values)]
        out.append(sum(w * v for w, v in ws) / sum(w for w, _ in ws))
    return out


def spline(points, closed=False):
    """Catmull-Rom curve through points, as a cubic path."""
    n = len(points)
    d = f"M{points[0][0]:.0f} {points[0][1]:.0f}"
    for i in range(n if closed else n - 1):
        p0, p1 = points[(i - 1) % n if closed else max(0, i - 1)], points[i]
        p2, p3 = points[(i + 1) % n], points[(i + 2) % n if closed else min(n - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.0f} {c1[1]:.0f} {c2[0]:.0f} {c2[1]:.0f} {p2[0]:.0f} {p2[1]:.0f}"
    return d


def noise(rng, length, octaves, loop=False):
    """Fractal value noise along a line (or round a loop) of the given length. Short
    wavelengths interpolate straight, which tears like paper instead of rippling."""
    layers = []
    for wl, amp in octaves:
        n = max(3, round(length / wl))
        layers.append((n, wl < 10, [rng.uniform(-amp, amp) for _ in range(n + 1)]))

    def at(s):
        v = 0.0
        for n, sharp, knots in layers:
            u = s / length * n
            u = u % n if loop else min(max(u, 0), n - 1e-9)
            i, f = int(u), u % 1
            if not sharp:
                f = (1 - math.cos(math.pi * f)) / 2
            v += knots[i] * (1 - f) + knots[(i + 1) % n if loop else i + 1] * f
        return v
    return at


def blade(x, base, h, lean, w):
    return (f"M{x - w / 2:.1f} {base:.1f}Q{x - w / 2 + lean * .15:.1f} {base - h * .55:.1f} {x + lean:.1f} {base - h:.1f}"
            f"Q{x + w / 2 + lean * .25:.1f} {base - h * .5:.1f} {x + w / 2:.1f} {base:.1f}Z")


def arch(p0, p1, p2, p3, w):
    """A tapered stroke along one cubic: grass flopping over, a stem arching out."""
    pts = [bez((p0, p1, p2, p3), k / 24) for k in range(25)]
    left = [(x - ty * w * (1 - k / 24) ** .8 / 2, y + tx * w * (1 - k / 24) ** .8 / 2) for k, (x, y, tx, ty) in enumerate(pts)]
    right = [(x + ty * w * (1 - k / 24) ** .8 / 2, y - tx * w * (1 - k / 24) ** .8 / 2) for k, (x, y, tx, ty) in enumerate(pts)]
    return poly(left + right[::-1])


def leaf(size, width=.42):
    return (f'M0 0C{size * .25:.1f} {-size * width:.1f} {size * .72:.1f} {-size * width * .95:.1f} {size:.1f} 0'
            f'C{size * .72:.1f} {size * width * .95:.1f} {size * .25:.1f} {size * width:.1f} 0 0Z')


def petals(r, n, turn):
    return "".join(f'<ellipse cx="{r * .55:.1f}" cy="0" rx="{r * .55:.1f}" ry="{r * .3:.1f}" transform="rotate({turn + 360 / n * p:.0f})"/>'
                   for p in range(n))


# ---------- the tear ----------

def tear(rng):
    """The hole in the page: a rough oval torn with fractal teeth, straight where a
    flap peeled back along a crease. Returns the outline and each flap's crease."""
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    raw = []
    for i in range(900):
        th = 2 * math.pi * i / 900
        c, s = math.cos(th), math.sin(th)
        r = (abs(c) ** 5 / RX ** 5 + abs(s) ** 5 / RY ** 5) ** (-1 / 5)
        r *= 1 + .026 * math.sin(2 * th + ph[0]) + .03 * math.sin(3 * th + ph[1]) + .02 * math.sin(5 * th + ph[2]) + .014 * math.sin(8 * th + ph[3])
        raw.append((CX + r * c, CY + r * s))
    seg = [math.dist(raw[i], raw[(i + 1) % 900]) for i in range(900)]
    total = sum(seg)
    n = int(total / 2.4)
    pts, i, acc = [], 0, 0.0
    for k in range(n):
        target = k * total / n
        while acc + seg[i] < target:
            acc, i = acc + seg[i], i + 1
        f = (target - acc) / seg[i]
        a, b = raw[i], raw[(i + 1) % 900]
        pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    normals = []
    for k in range(n):
        (ax, ay), (bx, by) = pts[k - 1], pts[(k + 1) % n]
        l = math.hypot(bx - ax, by - ay)
        nx, ny = (by - ay) / l, -(bx - ax) / l
        if nx * (pts[k][0] - CX) + ny * (pts[k][1] - CY) < 0:
            nx, ny = -nx, -ny
        normals.append((nx, ny))
    rough = noise(rng, total, [(190, 10), (64, 5), (22, 2.4), (7, 1.3), (2.6, .7)], loop=True)
    edge = [(x + nx * rough(k * total / n), y + ny * rough(k * total / n)) for k, ((x, y), (nx, ny)) in enumerate(zip(pts, normals))]
    flaps = []
    for ang, length, depth in FLAPS:
        k0 = min(range(n), key=lambda k: abs(math.remainder(math.atan2(pts[k][1] - CY, pts[k][0] - CX) - ang, 2 * math.pi)))
        half = int(length / 2 / (total / n))
        a, b = k0 - half, k0 + half
        A, B = edge[a % n], edge[b % n]
        for k in range(a + 1, b):
            f = (k - a) / (b - a)
            edge[k % n] = (A[0] + (B[0] - A[0]) * f + rng.uniform(-.25, .25), A[1] + (B[1] - A[1]) * f + rng.uniform(-.25, .25))
        flaps.append((A, B, depth, range(a, b)))
    return edge, normals, flaps


def page(theme, edge, normals, flaps, period, rng):
    """GitHub's page around the tear: the torn fibre edge and the flaps peeled back."""
    t = PAGE[theme]
    n = len(edge)
    on_flap = set(k % n for *_, ks in flaps for k in ks)
    hairs = []
    for k in range(0, n, 2):
        if k in on_flap or rng.random() > .6:
            continue
        (x, y), (nx, ny) = edge[k], normals[k]
        a = math.atan2(-ny, -nx) + rng.uniform(-.9, .9)
        s, l = rng.uniform(-1.2, .8), rng.uniform(1.5, 5.5)
        x0, y0 = x + nx * s, y + ny * s
        hairs.append(f"M{x0:.1f} {y0:.1f}l{math.cos(a) * l:.1f} {math.sin(a) * l:.1f}")
    rim = (f'<use href="#tear" fill="none" stroke="{t["rim"]}" stroke-opacity="{t["rim_op"]}" stroke-width="3.2" clip-path="url(#hole)"/>'
           f'<path d="{"".join(hairs)}" stroke="{t["rim"]}" stroke-opacity="{t["rim_op"]}" stroke-width=".7" fill="none"/>')
    art = []
    for i, (A, B, depth, _) in enumerate(flaps):
        ux, uy = B[0] - A[0], B[1] - A[1]
        length = math.hypot(ux, uy)
        ux, uy = ux / length, uy / length
        nx, ny = uy, -ux
        if nx * ((A[0] + B[0]) / 2 - CX) + ny * ((A[1] + B[1]) / 2 - CY) < 0:
            nx, ny = -nx, -ny
        # paper tears in straight runs between corners, ragged only at the fibre scale
        corners = [(length, 0), (length * rng.uniform(.72, .9), depth * rng.uniform(.45, .7)),
                   (length * rng.uniform(.35, .6), depth), (length * rng.uniform(.08, .22), depth * rng.uniform(.3, .55)), (0, 0)]
        jag = noise(rng, length * 3, [(9, 1.6), (3, .8)])
        free, s = [], 0.0
        for (ax, ay), (bx, by) in zip(corners, corners[1:]):
            steps = max(2, int(math.dist((ax, ay), (bx, by)) / 3))
            for k in range(steps):
                f = k / steps
                x, y = ax + (bx - ax) * f, ay + (by - ay) * f
                s += 3
                free.append((x, y + jag(s)))
        shape = poly([(0, 0)] + free[1:])
        lx, ly = 3 * ux + 5 * uy, 3 * nx + 5 * ny                 # the page's drop shadow, in the flap's frame
        grad = (f'<linearGradient id="fg{theme}{i}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{depth:.0f}">'
                f'<stop offset="0" stop-color="{t["flap"][0]}"/><stop offset="1" stop-color="{t["flap"][1]}"/></linearGradient>')
        delay = beat(0.5 * A[0] / W * period) / FPS
        art.append(
            f'{grad}<g transform="matrix({ux:.4f} {uy:.4f} {nx:.4f} {ny:.4f} {A[0]:.1f} {A[1]:.1f})">'
            f'<g class="flap" style="--d:{delay:.4f}s">'
            f'<path d="{shape}" transform="translate({lx * .5:.1f} {ly * .5:.1f})" fill="#000" fill-opacity="{t["drop"] * .6:.2f}"/>'
            f'<path d="{shape}" transform="translate({lx:.1f} {ly:.1f})" fill="#000" fill-opacity="{t["drop"] * .35:.2f}"/>'
            f'<path d="{shape}" fill="url(#fg{theme}{i})"/>'
            f'<path d="M0 0H{length:.1f}" stroke="{t["crease"]}" stroke-width="1.2" stroke-opacity=".7"/></g></g>')
    shade = "".join(f'<use href="#paper-page" transform="translate({dx} {dy})" fill="#000" fill-opacity="{t["shade"] * o:.3f}"/>'
                    for dx, dy, o in ((1, 1.8, 1), (2.5, 4, .8), (4.5, 7, .6), (7.5, 11.5, .42), (12, 18, .27), (18, 27, .15)))
    return shade, rim + "".join(art)


# ---------- paper ----------

def png(width, height, rows, kind):
    chunk = lambda t, data: struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data))
    raw = b"".join(b"\0" + r for r in rows)
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, kind, 0, 0, 0))
                            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")).decode()


def paper_tiles(rng):
    """Fibre grain (multiplied), plus paper-coloured mottle and pinholes laid over the ink."""
    grain = png(96, 96, [bytes(rng.randint(170, 255) for _ in range(96)) for _ in range(96)], 0)
    n = 7                                            # wraps at the edges so the tile repeats without seams
    grid = [[rng.random() for _ in range(n)] for _ in range(n)]
    ease = lambda t: (1 - math.cos(math.pi * t)) / 2
    rows = []
    for y in range(64):
        row = bytearray()
        for x in range(64):
            gx, gy = x / 64 * n, y / 64 * n
            i, j, fx, fy = int(gx), int(gy), ease(gx % 1), ease(gy % 1)
            a, b = grid[j][i], grid[j][(i + 1) % n]
            c, d = grid[(j + 1) % n][i], grid[(j + 1) % n][(i + 1) % n]
            v = (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
            row += bytes((*PAPER, int(max(0, v - 0.45) * 190)))
        rows.append(bytes(row))
    mottle = png(64, 64, rows, 6)
    holes = []
    for y in range(128):
        row = bytearray()
        for x in range(128):
            row += bytes((*PAPER, 255 if rng.random() < 0.009 else 0))
        holes.append(bytes(row))
    pinholes = png(128, 128, holes, 6)
    return grain, mottle, pinholes


# ---------- sky ----------

def sun_or_moon(now):
    """(is_day, x fraction across the sky, low = closeness to the horizon, moon age in days)."""
    local = now.astimezone(LA)
    n = local.timetuple().tm_yday
    decl = math.radians(-23.44) * math.cos(2 * math.pi * (n + 10) / 365)
    day_len = 2 * math.degrees(math.acos(-math.tan(math.radians(34.05)) * math.tan(decl))) / 15
    h = now.hour + now.minute / 60
    f = ((h - (19.88 - day_len / 2)) % 24) / day_len  # solar noon 19:53 UTC; 0 sunrise .. 1 sunset
    age = ((now - dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)).total_seconds() / 86400) % 29.530589
    if f <= 1:
        return True, f, min(f, 1 - f), age
    g = (f - 1) / ((24 - day_len) / day_len)
    return False, g, min(g, 1 - g), age


def wash(press, plate, y0, y1, tones, clip="sky"):
    """Halftone gradient in bands of shrinking dots."""
    bands, (t0, t1) = 12, tones
    rows = "".join(f'<rect x="-10" y="{y0 + (y1 - y0) * b / bands:.0f}" width="{W + 20}" height="{(y1 - y0) / bands + 1:.0f}" '
                   f'fill="{press.ink(plate, max(.02, t0 + (t1 - t0) * b / (bands - 1)))}"/>' for b in range(bands))
    press.raw(plate, f'<g clip-path="url(#{clip})">{rows}</g>')


def sky(press, now, far_y, rng, fortnight, name):
    day, f, low, age = sun_or_moon(now)
    mood = "night" if not day else "dusk" if low < .08 else "day"
    if mood == "day":
        wash(press, "blue", 30, 430, [.42, .04])
        wash(press, "pink", 260, 430, [.0, .14])
    elif mood == "dusk":
        wash(press, "blue", 30, 430, [.5, .05])
        wash(press, "pink", 90, 430, [.05, .6])
        wash(press, "yellow", 250, 430, [.05, .5])
    else:
        press.knocks = tuple(INK)
        wash(press, "blue", 30, 430, [1, .62])
        wash(press, "black", 30, 430, [.42, .04])
        wash(press, "pink", 280, 430, [0, .16])
    sx, sy = 170 + f * 940, 420 - math.sin(math.pi * f) * 320
    if day:
        # the disc in a halo of shrinking dots, its outer rings turning slowly
        warm = [("pink", .9)] if mood == "dusk" else []
        for k, (r, tone) in enumerate(((150, .1), (124, .2), (100, .34), (82, .55))):
            ring = f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r}" clip-path="url(#sky)"/>'
            if k < 2:
                ring = f'<g class="rays" style="transform-origin:{sx:.0f}px {sy:.0f}px;animation-direction:{("normal", "reverse")[k]}">{ring}</g>'
            press.put([("yellow", tone)] + [(p, t * tone) for p, t in warm], ring)
        press.put([("yellow", 1)] + warm, f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="64"/>')
    else:
        lit = 1 - abs(2 * age / 29.530589 - 1)       # 0 new .. 1 full
        off = 2 * 58 * lit * (-1 if age < 14.77 else 1)
        disc = f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="58"'
        box = f'maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}"'
        press.defs.append(f'<mask id="moonlit" {box}>{disc} fill="#fff"/><circle cx="{sx + off:.0f}" cy="{sy:.0f}" r="58"/></mask>')
        for r, tone in ((190, .82), (150, .7), (116, .58), (88, .46)):   # moonlight thins the sky round it
            press.put([("blue", tone), ("black", tone * .12)], f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r}" clip-path="url(#sky)"/>')
        press.put([("yellow", .35)], f'{disc} mask="url(#moonlit)"/>')
        # Most stars are paper left bare. A third twinkle: they are drawn as light over
        # the ink instead, which is cheaper than knocking a hole through every drum,
        # and so none of those may sit where the name will cross the sky.
        stars, lit, sparks = [], [], []
        for _ in range(90):
            x, y = rng.uniform(40, W - 40), rng.uniform(40, 400)
            if y < far_y(x) - 24 and math.dist((x, y), (sx, sy)) > 140:
                open_sky = min(math.dist((x, y), p[:2]) for p in name) > 28
                twinkle = f'class="star" style="{tempo(rng.uniform(1.6, 4.5), -rng.uniform(0, 5))}"'
                if rng.random() < .15 and open_sky:
                    r = rng.uniform(5, 9)
                    sparks.append(f'<path {twinkle} d="M{x:.0f} {y - r:.0f}Q{x:.0f} {y:.0f} {x + r:.0f} {y:.0f}Q{x:.0f} {y:.0f} {x:.0f} {y + r:.0f}'
                                  f'Q{x:.0f} {y:.0f} {x - r:.0f} {y:.0f}Q{x:.0f} {y:.0f} {x:.0f} {y - r:.0f}Z"/>')
                elif rng.random() < .35 and open_sky:
                    lit.append(f'<circle {twinkle} cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(1.4, 2.6):.1f}"/>')
                else:
                    stars.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(1.4, 2.6):.1f}"/>')
        press.clear("".join(stars))
        press.glow(f'<g fill="{on_paper("#FFFFFF")}">{"".join(lit)}</g><g fill="{on_paper(INK["yellow"])}">{"".join(sparks)}</g>')

    # Clouds: paper knocked out of every drum, a shaded belly, drifting on the wind.
    belly = {"day": ("pink", .22), "dusk": ("pink", .55), "night": ("blue", .45)}[mood]
    for k in range(5):
        cy = rng.uniform(70, 250)
        span = rng.uniform(140, 280)
        puffs = "".join(f'<ellipse cx="{rng.uniform(-span / 2, span / 2):.0f}" cy="{rng.uniform(-14, 4):.0f}" '
                        f'rx="{rng.uniform(26, 56):.0f}" ry="{rng.uniform(16, 30):.0f}"/>' for _ in range(7))
        base = f'<rect x="{-span / 2 - 20:.0f}" y="-4" width="{span + 40:.0f}" height="18" rx="9"/>'
        dur = rng.uniform(160, 260)
        wrap = f'<g clip-path="url(#sky)"><g class="cloud" style="{tempo(dur, -dur * (k + rng.random()) / 5)}"><g transform="translate(0 {cy:.0f})">'
        body = press.ref(puffs + base)
        cid = f"cl{k}"
        press.defs.append(f'<clipPath id="{cid}"><use href="{body}"/></clipPath>')
        for plate in INK:
            art = f'<use href="{body}" fill="#fff"/>'
            if mood == "night" and plate == "blue":        # moonlit, not paper-white
                art += f'<use href="{body}" fill="{press.ink("blue", .4)}"/>'
            if plate == belly[0]:
                art += f'<rect x="{-span:.0f}" y="2" width="{span * 2:.0f}" height="40" clip-path="url(#{cid})" fill="{press.ink(*belly)}"/>'
            press.raw(plate, wrap + art + "</g></g></g>")

    # Birds, one for each day worked in the last fortnight, while it is light.
    if day and fortnight:
        flock = []
        for b in range(fortnight):
            bx, by = -b * rng.uniform(16, 26) + rng.uniform(-8, 8), (b % 2 * 2 - 1) * b * rng.uniform(4, 9) + rng.uniform(-6, 6)
            s = rng.uniform(.8, 1.25)
            flock.append(f'<g transform="translate({bx:.0f} {by:.0f}) scale({s:.2f})"><path class="bird" style="{tempo(rng.choice((.25, .33)), -rng.random())}" '
                         f'd="M-7 0Q-3.5 -4.5 0 0Q3.5 -4.5 7 0"/></g>')
        route = f"M-120 {rng.uniform(150, 220):.0f}C300 {rng.uniform(90, 160):.0f} 800 {rng.uniform(180, 260):.0f} 1500 {rng.uniform(100, 180):.0f}"
        press.raw("black", f'<g clip-path="url(#sky)"><g class="glide" style="{glide(route, rng.uniform(48, 62), -rng.uniform(8, 30))}">'
                           f'<g fill="none" stroke="{INK["black"]}" stroke-width="1.5" stroke-linecap="round">{"".join(flock)}</g></g></g>')
    return mood, (sx, sy)


# ---------- land ----------

def ranges_for(weeks, rng):
    """Two ranges of peaks, (x, base, height, left reach, right reach) each. The far
    range has a peak per four weeks, as tall as the best of them; the foothills in
    front follow the weeks smoothed."""
    top = max(weeks) or 1
    out = []
    for base, lift, reach, group, spread, vals in ((430, 34, 250, 4, (1.1, 1.7), weeks),
                                                  (470, 14, 104, 6, (1.5, 2.3), smooth(weeks, 2.5))):
        peaks = []
        for g0 in range(0, len(vals), group):
            h = lift + reach * math.sqrt(max(vals[g0:g0 + group]) / top) * rng.uniform(.85, 1.1)
            px = -30 + (W + 60) * (g0 + group / 2) / len(vals) + rng.uniform(-22, 22)
            peaks.append((px, base, h, h * rng.uniform(*spread), h * rng.uniform(*spread)))
        out.append(peaks)
    return out


def ridge(peaks, x):
    """The skyline of a range at x, flanks taken straight."""
    return min(base - h + h * abs(x - px) / (wl if x < px else wr) for px, base, h, wl, wr in peaks)


def crag(rng, a, b):
    """A flank from a to b, broken by midpoint displacement into rock."""
    pts, amp = [a, b], math.dist(a, b) * .07
    for _ in range(5):
        nxt = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            nxt += [((p[0] + q[0]) / 2 + rng.uniform(-amp, amp) * .5, (p[1] + q[1]) / 2 + rng.uniform(-amp, amp)), q]
        pts, amp = nxt, amp * .55
    return pts


def mountains(press, ranges, rng, light_x, mood):
    """Peaks stacked tallest at the back, each with its flank away from the light in
    shade along a diagonal facet; snow on the three biggest."""
    recipes = [([("blue", .45), ("pink", .12)], [("blue", .78), ("pink", .22)]), ([("blue", .72), ("pink", .28)], [("blue", 1), ("pink", .42)])]
    if mood == "night":
        recipes = [([("blue", .7)], [("blue", .9), ("black", .2)]), ([("blue", .9), ("black", .25)], [("blue", 1), ("black", .45)])]
    snowy = sorted(ranges[0], key=lambda p: -p[2])[:3]
    for k, peaks in enumerate(ranges):
        lit, shade = recipes[k]
        for peak in sorted(peaks, key=lambda p: -p[2]):
            px, base, h, wl, wr = peak
            summit = (px, base - h)
            left, right = crag(rng, (px - wl, base + 70), summit), crag(rng, summit, (px + wr, base + 70))
            shape = poly(left + right[1:])
            vary = rng.uniform(-.05, .05)
            press.put([(p, t + vary) for p, t in lit], f'<path d="{shape}"/>')
            side = right if light_x < px else left[::-1]
            facet = poly(side + [(px + (side[-1][0] - px) * .28, base + 70)])
            press.put(shade, f'<path d="{facet}"/>')
            if peak in snowy:
                snow_y = base - h + 16 + h * .16
                jag = noise(rng, wl + wr, [(40, 7), (12, 3), (4, 1.4)])
                band = poly([(px - wl, base - h - 10), (px + wr, base - h - 10)]
                            + [(x, snow_y + jag(x - px + wl)) for x in range(int(px + wr), int(px - wl), -4)])
                for cid, where, recipe in ((f"snow{len(press.defs)}", shape, []), (f"snow{len(press.defs)}s", facet, [("blue", .3)])):
                    press.defs.append(f'<clipPath id="{cid}"><path d="{where}"/></clipPath>')
                    press.put(recipe, f'<path d="{band}" clip-path="url(#{cid})"/>')


def trees(press, contour, x0, x1, big, rng, month, wave):
    """A hedge of round trees and pines along a hill's crest, bending as gusts pass.
    Each stand of about 300px bends as one, which keeps the running animations few."""
    x, stand, sx = x0, {}, x0

    def bend():
        crowns = {key: "".join(parts) for key, parts in stand.items()}
        for key, d in crowns.items():
            press.clear(f'<path d="{d}"/>')           # cut once at rest; the ink leans out of it in a gust
            press.put(AUTUMN[key] if key >= 0 else DEEP, f'<g class="sway" style="{wave(sx)}"><path d="{d}"/></g>', knock=False, fine=True)
        stand.clear()

    while x < x1:
        if x - sx > 300:
            bend()
            sx = x
        cluster = []
        turned = month in (9, 10, 11) and rng.random() < .15
        for _ in range(rng.randint(2, 5)):
            tx = x + rng.uniform(-6, 6)
            ty = contour(tx) + 4
            if not turned and rng.random() < .35:
                s = rng.uniform(10, 18) * big
                cluster.append(f"M{tx:.0f} {ty - s * 2:.0f}L{tx + s * .55:.0f} {ty:.0f}L{tx - s * .55:.0f} {ty:.0f}Z")
            else:
                r = rng.uniform(6, 12) * big
                cluster.append(f'M{tx - r:.0f} {ty - r * .8:.0f}a{r:.0f} {r:.0f} 0 1 0 {2 * r:.0f} 0a{r:.0f} {r:.0f} 0 1 0 {-2 * r:.0f} 0Z'
                               f'M{tx - 1.2:.1f} {ty - r * .5:.0f}h2.4V{ty:.0f}h-2.4Z')
            x += rng.uniform(7, 16) * big
        stand.setdefault(rng.randrange(len(AUTUMN)) if turned else -1, []).extend(cluster)
        x += rng.uniform(4, 70) * big
    bend()


def fields(press, months, top_a, top_b, rng, wave):
    """Two bands of hill, cut into one field per month, oldest at the back left."""
    peak = max(t for _, t in months) or 1
    for band, (top, count, offset) in enumerate(((top_a, 7, 0), (top_b, 5, 7))):
        cuts = [-60] + [-60 + (W + 120) * i / count + rng.uniform(-40, 40) for i in range(1, count)] + [W + 60]
        slants = [0] + [rng.uniform(-40, 40) for _ in range(count - 1)] + [0]
        for i in range(count):
            label, total = months[offset + i]
            m = int(label[5:7])
            weight = math.sqrt(total / peak)
            l_top, r_top = cuts[i] + slants[i], cuts[i + 1] + slants[i + 1]
            l_foot, r_foot = cuts[i] - slants[i], cuts[i + 1] - slants[i + 1]
            crest = [(x, top(x)) for x in range(int(l_top), int(r_top) + 1, 8)] + [(r_top, top(r_top))]
            # the back band only runs a little way under the front one; nothing below is seen
            foot = (lambda _: H + 20) if band else (lambda x: top_b(x) + 30)
            sole = [(x, foot(x)) for x in range(int(r_foot), int(l_foot) - 1, -8)]
            shape = poly([(l_foot, foot(l_foot))] + crest + [(r_foot, foot(r_foot))] + sole)
            ground, plate = FIELD[m]
            ref = press.put([(p, t * (.5 + .5 * weight)) for p, t in ground], f'<path d="{shape}"/>')
            slope = math.degrees(math.atan2(top(r_top) - top(l_top), r_top - l_top))
            kind = "dots" if m in (3, 4, 5) else rng.choice(("rows", "rows", "hatch"))
            angle = slope + (rng.uniform(-25, 25) if kind == "rows" else 30)
            size = 5 + 6 * (1 - weight) + 2 * band + 4 * (m in (12, 1, 2))   # frost furrows run sparse
            press.raw(plate, f'<use href="{ref}" fill="{press.texture(plate, kind, angle, size, .25 + .3 * weight)}"/>')
            if i:                                     # a hedge line where two fields meet
                press.put([("yellow", 1), ("blue", 1)], f'<path d="M{l_top:.0f} {top(l_top) + 2:.0f}L{l_foot:.0f} {foot(l_foot):.0f}" '
                                                        f'fill="none" stroke-width="{2 + band * 1.2:.1f}"/>', knock=False, paint="stroke")
        trees(press, top, -20, W + 20, .8 + band * .35, rng, int(months[-1][0][5:7]), wave)


def river(press, near, top_a, top_b, rng, period):
    """A river from the gap in the mountains, widening as it comes down to the meadow."""
    sx = min(range(620, 900, 4), key=lambda x: -near(x))
    pts = [(sx, near(sx) + 6), (sx + 34, top_a(sx + 34) + 16), (sx - 24, 520), (sx + 70, top_b(sx + 70) + 20),
           (sx + 20, 600), (sx + 150, 660), (sx + 260, 760)]
    segs, toks = [], [float(v) for v in re.findall(r"-?\d+\.?\d*", spline(pts))]
    cur = (toks[0], toks[1])
    for i in range(2, len(toks), 6):
        p = [(toks[i], toks[i + 1]), (toks[i + 2], toks[i + 3]), (toks[i + 4], toks[i + 5])]
        segs.append((cur, *p))
        cur = p[2]
    centre = samples(segs, 3)
    total = centre[-1][4]
    left, right = [], []
    for x, y, tx, ty, s in centre:
        w = 2 + 70 * (s / total) ** 1.7
        left.append((x - ty * w / 2, y + tx * w / 2))
        right.append((x + ty * w / 2, y - tx * w / 2))
    shape = poly(left + right[::-1])
    press.defs.append(f'<clipPath id="river"><path d="{shape}"/></clipPath>')
    press.put([("blue", .62)], f'<path d="{shape}"/>')
    ripples = []
    for lane in (-.3, 0, .3):
        lane_pts = [(x + ty * lane * (2 + 70 * (s / total) ** 1.7), y - tx * lane * (2 + 70 * (s / total) ** 1.7)) for x, y, tx, ty, s in centre]
        ripples.append(f'<path class="flow" style="{tempo(period * rng.uniform(.3, .45))}" d="{poly(lane_pts, False)}"/>')
    press.raw("blue", f'<g clip-path="url(#river)" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round">{"".join(ripples)}</g>')


# ---------- the print ----------

def garden(days, total, last, now):
    rng = random.Random(days[-1][0])                  # the drawing holds still through a day
    pull = random.Random(now.isoformat())             # registration changes every print
    counts = [c for _, c in days]
    active = sorted(c for c in counts if c)
    cap = active[int(len(active) * 0.9)] if active else 1
    tone = lambda c: math.sqrt(min(c, cap) / cap)
    period = gust_period(days, total, last, now)
    period = beat(period / 4) * 4 / FPS                           # a gust in four equal beats
    wave = lambda x: f"--d:{beat((0.5 * x / W - 1) * period) / FPS:.4f}s"   # gusts roll left to right
    today, week = counts[-1], sum(counts[-7:])
    press = Press()

    edge, normals, flaps = tear(rng)
    tear_d = poly(edge)

    # Land: mountains from weekly totals; fields from monthly; a meadow bank in front.
    weeks = [sum(counts[i:i + 7]) for i in range(0, len(counts), 7)]
    months = {}
    for date, c in days:
        months[date[:7]] = months.get(date[:7], 0) + c
    months = list(months.items())[-12:]
    ph = [rng.uniform(0, 6.3) for _ in range(6)]
    top_a = lambda x: 478 - 26 * math.sin(x / 210 + ph[0]) - 12 * math.sin(x / 93 + ph[1])
    top_b = lambda x: 560 - 22 * math.sin(x / 250 + ph[2]) - 10 * math.sin(x / 81 + ph[3])
    bank = lambda x: 648 - 14 * math.sin(x / 170 + ph[4]) - 7 * math.sin(x / 61 + ph[5])

    # the sky first, so the ridges can be cut out of it
    ranges = ranges_for(weeks, random.Random(rng.random()))
    far_y, near = (lambda x: ridge(ranges[0], x)), (lambda x: ridge(ranges[1], x))
    skyline = [(x, far_y(x)) for x in range(-20, W + 21, 8)]
    horizon = poly([(-20, -20), (W + 20, -20)] + [(x, y + 40) for x, y in reversed(skyline)])
    press.defs.append(f'<clipPath id="sky"><path d="{horizon}"/></clipPath>')
    fortnight = sum(1 for c in counts[-14:] if c)
    name_pts, cross_pts, tend_pts = samples(place(NAME)), samples(place(CROSS)), samples(place(TENDRIL))
    mood, light = sky(press, now, far_y, rng, fortnight, name_pts + cross_pts + tend_pts)
    mountains(press, ranges, random.Random(rng.random()), light[0], mood)
    fields(press, months, top_a, top_b, rng, wave)
    river(press, near, top_a, top_b, rng, period)
    if mood == "night":
        press.raw("black", f'<rect y="200" width="{W}" height="{H}" fill="{press.ink("black", .22)}" clip-path="url(#land)"/>')
    elif mood == "dusk":
        press.raw("pink", f'<rect y="200" width="{W}" height="{H}" fill="{press.ink("pink", .2)}" clip-path="url(#land)"/>')
    press.defs.append(f'<clipPath id="land"><path d="M-20 {H + 20}L{poly(skyline)[1:-1]}L{W + 20} {H + 20}Z"/></clipPath>')
    bank_d = poly([(-20, H + 20)] + [(x, bank(x)) for x in range(-20, W + 21, 10)] + [(W + 20, H + 20)])
    press.put([("yellow", .9), ("blue", .32)], f'<path d="{bank_d}"/>')
    tufts = "".join(blade(x, bank(x) + rng.uniform(6, 30), rng.uniform(5, 12), rng.uniform(-4, 4), 1.6) for x in range(0, W, 9))
    press.put([("blue", .7)], f'<path d="{tufts}"/>', knock=False)

    # Meadow: a stem per day; gusts roll through it a fortnight at a time. Every
    # fortnight bends on the ground, the same point on each drum, so a flower stays on
    # its stem.
    pitch = (W - 120) / len(days)
    budding = active[int(len(active) * .7)] if active else 1
    for wk in range(0, len(days), 14):
        gx = 60 + pitch * (wk + 7)
        week_art = {p: [] for p in INK}
        for di in range(wk, min(wk + 14, len(days))):
            x = 60 + pitch * (di + 0.5) + rng.uniform(-1, 1)
            c = counts[di]
            h = 34 + 116 * tone(c) + rng.uniform(0, 10)
            lean = rng.uniform(-10, 10)
            month = int(days[di][0][5:7])
            art = {p: [] for p in INK}
            for p, t in rng.choice(LEAF[month]):
                art[p].append(f'<path fill="{press.ink(p, min(1.0, t * 1.3))}" d="{blade(x, 704, h, lean, 2.6 + 1.8 * tone(c))}"/>')
            fx, fy = x + lean, 704 - h
            if c and c >= cap:
                r = rng.uniform(6, 8.5)
                parts = [(press.ref(f'<g transform="translate({fx:.1f} {fy:.1f})">{petals(r, 5, rng.uniform(0, 72))}</g>'), FLOWER[month], True),
                         (press.ref(f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="{r * .32:.1f}"/>'),
                          [("pink", .8)] if FLOWER[month][0][0] == "yellow" else [("yellow", 1)], True)]
            elif c and c >= budding:
                parts = [(press.ref(f'<ellipse cx="{fx:.1f}" cy="{fy:.1f}" rx="2.3" ry="3.6"/>'), [("yellow", 1), ("pink", .3)], False)]
            else:
                parts = []
            for ref, recipe, knock in parts:
                for p in press.knocks if knock else ():
                    art[p].append(f'<use href="{ref}" fill="#fff"/>')
                for p, t in recipe:
                    art[p].append(f'<use href="{ref}" fill="{press.ink(p, t, True)}"/>')
            for p, items in art.items():
                week_art[p] += items
        for p, items in week_art.items():
            if items:
                press.raw(p, f'<g class="gust" style="--o:{gx:.0f}px 704px;{wave(gx)}">{"".join(items)}</g>')

    # The name, black over a blue hit for a rich inky black, cut clean out of the
    # landscape and written in on load.
    body = (ribbon(name_pts, pen(name_pts, 3.2, 19), rng) + ribbon(cross_pts, pen(cross_pts, 3, 10), rng)
            + ribbon(tend_pts, pen(tend_pts, 2.4, 5.5), rng))
    reveal = "".join(f'<path class="write" pathLength="1" d="{line(p)}" style="{tempo(dur, at)}"/>'
                     for p, at, dur in ((name_pts, .6, 2.8), (cross_pts, 3.3, .5), (tend_pts, 3.7, .9)))
    press.defs.append(f'<mask id="written" maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}">{reveal}</mask>')
    press.clear(f'<path d="{body}" stroke="#fff" stroke-width="7" stroke-linejoin="round" mask="url(#written)"/>')
    press.put([("blue", .85), ("black", 1)], f'<path d="{body}" mask="url(#written)"/>', knock=False)
    press.knocks = tuple(INK)                          # from here on things sit over the name

    total_len = name_pts[-1][4]
    day_at = lambda length: round(min(1, max(0, length / total_len)) * (len(days) - 1))

    # Leaves: one node every ~13px of vine, oldest day at the root; size and season from that day.
    side = 1
    for i in range(0, len(name_pts), 8):
        x, y, tx, ty, length = name_pts[i]
        if length < 24 or length > total_len - 20:
            continue
        di = day_at(length)
        t = tone(sum(counts[max(0, di - 3):di + 4]) / 7)
        if t < 0.12 and rng.random() > 0.3:
            continue
        size = 7 + 17 * t
        side = -side
        ang = math.degrees(math.atan2(ty, tx)) + side * rng.uniform(38, 62)
        at = f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.0f})"><g class="sprout" style="--d:{beat(1 + 2.6 * length / total_len) / FPS:.4f}s">'
        vein = f'<path d="M{size * .12:.1f} 0Q{size * .5:.1f} {-size * .05:.1f} {size * .86:.1f} 0" fill="none" stroke="#fff" stroke-width=".9"/>' if size > 10 else ""
        # the paper is cut once, a little wide, and holds still; only the ink flutters in
        # it, and only on the leaves of busier days
        press.clear(f'{at}<path d="{leaf(size)}" stroke="#fff" stroke-width="3" stroke-linejoin="round"/></g></g>')
        flutter = f'class="lf" style="{tempo(rng.uniform(1.6, 2.8), -rng.uniform(0, 3))}"' if size > 15 else ""
        press.put(rng.choice(LEAF[int(days[di][0][5:7])]), f'{at}<g {flutter}><path d="{leaf(size)}"/>{vein}</g></g></g>',
                  knock=False, fine=True)

    # The biggest weeks bloom on the vine, where their days fall along it.
    blooms = []
    top_week = max(weeks) or 1
    for rank, k in enumerate(sorted(range(len(weeks)), key=lambda k: -weeks[k])[:7]):
        target = total_len * (k * 7 + 3) / (len(days) - 1)
        x, y, *_ = min(name_pts[30:-20], key=lambda p: abs(p[4] - target))
        month = int(days[min(len(days) - 1, k * 7 + 3)][0][5:7])
        blooms.append((x, y))
        bloom(press, x, y, 9 + 8 * math.sqrt(weeks[k] / top_week), FLOWER[month], 4.2 + .15 * rank, rng)

    # Today: the tendril's tip. A bud until there is work today, then a flower.
    tip = (tend_pts[-1][0], tend_pts[-1][1])
    if today:
        bloom(press, tip[0], tip[1], 7 + 6 * tone(today), [("pink", 1)], 4.7, rng, pulse=True)
    else:
        bloom(press, tip[0], tip[1], 4.5, [("yellow", 1), ("blue", .3)], 4.7, rng, pulse=True)

    # Big leaves close to the eye in the bottom corners, and fireflies after dark.
    for cx, direction in ((70, 1), (W - 70, -1)):
        for k in range(4):
            size = rng.uniform(90, 150)
            ang = -90 + direction * rng.uniform(15, 70)
            veins = f'<path d="M{size * .08:.0f} 0L{size * .9:.0f} 0' + "".join(
                f'M{size * f:.0f} 0l{size * .12:.0f} {s * size * .13:.0f}' for f in (.25, .42, .59, .74) for s in (-1, 1)) + '" fill="none" stroke="#fff" stroke-width="1.6"/>'
            recipe = rng.choice([DEEP, LEAF[int(days[-1][0][5:7])][0], [("blue", .9), ("yellow", 1)]])
            press.put(recipe, f'<g transform="translate({cx + direction * rng.uniform(0, 60):.0f} {rng.uniform(700, 730):.0f}) rotate({ang:.0f})">'
                              f'<g class="bl" style="{tempo(rng.uniform(4, 6.5), -rng.uniform(0, 5))}"><path d="{leaf(size, .3)}"/>{veins}</g></g>',
                      knock=False)                    # overprinted: a cut this size could not keep up with the sway
    if mood == "night":
        flies = []
        for _ in range(16):
            x, y = rng.uniform(80, W - 80), rng.uniform(420, 680)
            loop = spline([(x + rng.uniform(-40, 40), y + rng.uniform(-30, 30)) for _ in range(4)], closed=True)
            flies.append(f'<g class="blink" style="{tempo(rng.uniform(1.4, 3), -rng.uniform(0, 3))}">'
                         f'<circle r="2.6" class="glide" style="{glide(loop, rng.uniform(9, 16), -rng.uniform(0, 16))}"/></g>')
        press.glow(f'<g fill="{on_paper(INK["yellow"])}">{"".join(flies)}</g>')

    # ---- loose in front of the page ----
    press.layer = "free"

    # grass and a cosmos flopping out over the bottom of the tear
    n = len(edge)
    lip = [edge[k] for k in range(n) if edge[k][1] > CY + RY * .82]
    for side_x, direction, count in ((190, -1, 14), (1040, 1, 8)):
        root = min(lip, key=lambda p: abs(p[0] - side_x))
        clumps = [[] for _ in range(3)]                # each clump of blades bends as one
        for k in range(count):
            bx = root[0] + rng.uniform(-50, 50)
            by = root[1] - rng.uniform(6, 30)
            reach, rise, droop = rng.uniform(50, 150) * direction, rng.uniform(60, 160), rng.uniform(0, 60)
            clumps[k % 3].append(arch((bx, by), (bx + reach * .1, by - rise * .7), (bx + reach * .6, by - rise), (bx + reach, by - rise * .55 + droop), rng.uniform(3, 5.5)))
        for blades in clumps:
            recipe = rng.choice([DEEP, [("yellow", 1), ("blue", .5)], [("yellow", 1), ("blue", .75)], [("yellow", 1), ("blue", .6)]])
            press.put(recipe, f'<g class="bl" style="--o:{root[0]:.0f}px {root[1] - 18:.0f}px;{tempo(rng.uniform(2.6, 4), -rng.uniform(0, 4))}">'
                              f'<path d="{"".join(blades)}"/></g>', knock=False)
    root = min(lip, key=lambda p: abs(p[0] - 1110))
    fx, fy = root[0] + 70, root[1] + 32
    stem = arch((root[0] - 20, root[1] - 30), (root[0], root[1] - 140), (fx + 20, root[1] - 150), (fx, fy), 4)
    sway = f'class="bl" style="--o:{root[0] - 20:.0f}px {root[1] - 30:.0f}px;{tempo(5.5, -2)}"'
    press.put(DEEP, f'<g {sway}><path d="{stem}"/></g>', knock=False)
    press.put([("pink", 1)], f'<g {sway}><g transform="translate({fx:.0f} {fy:.0f}) scale(1 .6)">{petals(22, 8, 10)}</g></g>')
    press.put([("yellow", 1), ("pink", .4)], f'<g {sway}><ellipse cx="{fx:.0f}" cy="{fy - 2:.0f}" rx="7" ry="4.5"/></g>')

    # ivy: the streak, climbing out of the tear and along the page, a pair of leaves a day
    run = min(streak(counts), 60)
    first = len(days) - run - (counts[-1] == 0)
    if run:
        start = min(range(n), key=lambda k: abs(math.remainder(math.atan2(edge[k][1] - CY, edge[k][0] - CX) + 1.95, 2 * math.pi)))
        guide, length, k = [], 0.0, start
        wander = noise(rng, 2000, [(140, 12), (45, 5)])
        while length < run * 12 and len(guide) < n // 2:
            (x, y), (nx, ny) = edge[k % n], normals[k % n]
            out = min(1, length / 60) * (12 + wander(length)) - 12 * (1 - min(1, length / 60))
            guide.append((x + nx * out, y + ny * out))
            if len(guide) > 1:
                length += math.dist(guide[-1], guide[-2])
            k += 3
        vine = spline(guide[::4])
        press.put([("yellow", 1), ("blue", 1)], f'<path class="grow" pathLength="1" d="{vine}" fill="none" stroke-width="4.5" stroke-linecap="round"/>',
                  knock=False, paint="stroke")
        for d in range(run):
            i = min(len(guide) - 2, int((d + .7) / run * (len(guide) - 1)))
            (x0, y0), (x1, y1) = guide[i], guide[i + 1]
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) + (d % 2 * 2 - 1) * rng.uniform(35, 75)
            recipe = rng.choice(LEAF[int(days[first + d][0][5:7])])
            flutter = f'class="lf" style="{tempo(rng.uniform(1.6, 2.6), -rng.random() * 2)}"' if rng.random() < .5 else ""
            press.put(recipe, f'<g transform="translate({x0:.1f} {y0:.1f}) rotate({ang:.0f})">'
                              f'<g class="sprout" style="--d:{beat(1.2 + 2.4 * d / run) / FPS:.4f}s"><g {flutter}>'
                              f'<path d="{leaf(rng.uniform(13, 19), .5)}"/></g></g></g>', knock=False, fine=True)

    # this week's petals, blowing out through the tear on the wind
    gone = []
    for k in range(min(14, 4 + week // 40)):
        x0, y0 = rng.uniform(260, 960), rng.uniform(300, 620)
        if k % 2:                                     # out over the right edge
            route = [(x0, y0), (x0 + 250, y0 + rng.uniform(-80, 40)), (1180, y0 + rng.uniform(-60, 60)), (1300, y0 + rng.uniform(-40, 80))]
        else:                                         # tumbling down onto the page below
            route = [(x0, y0), (x0 + 160, y0 + 60), (x0 + 300, 690), (x0 + 380 + rng.uniform(0, 120), 738)]
        n = beat(period * rng.uniform(1.1, 1.8))
        begin = -beat(rng.uniform(0, n / FPS)) / FPS
        spin = f'class="spin" style="{tempo(rng.uniform(1.2, 3))}"'
        shape = rng.choice([f'<ellipse rx="5.5" ry="2.8"/>', f'<path d="{leaf(11, .38)}" transform="translate(-5 0)"/>'])
        recipe = rng.choice([[("pink", 1)], [("pink", .8), ("yellow", .4)], [("yellow", 1), ("blue", .4)], [("yellow", 1), ("pink", .6)]])
        # in and out over three frames each, like ink thinning on the drum
        fade = f"fade{k}"
        press.keyframes.append(f"@keyframes {fade}{{" + "".join(
            f"{100 * i / n:.3f}%{{opacity:{v:g}}}" for i, v in ((0, 0), (1, .35), (2, .7), (3, 1), (n - 3, .7), (n - 2, .35), (n - 1, 0))) + "}")
        press.put(recipe, f'<g class="loose" style="{glide(spline(route), n / FPS, begin)};'
                          f'animation:glide var(--t) steps(var(--k)) var(--d) infinite,{fade} var(--t) steps(1) var(--d) infinite">'
                          f'<g {spin}>{shape}</g></g>', knock=False, fine=True)

    # today's fallen petals, lying on the page under the tear
    for k in range(min(10, today // 2)):
        x = rng.uniform(300, 1000)
        root = min(lip, key=lambda p: abs(p[0] - x))
        y = root[1] + rng.uniform(9, 28)
        gone.append((x, y, rng.uniform(0, 180)))
        press.put(rng.choice([[("pink", 1)], [("pink", .8), ("yellow", .4)]]), f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="5.5" ry="2.8" transform="rotate({gone[-1][2]:.0f} {x:.0f} {y:.0f})"/>', knock=False, fine=True)

    # butterflies: none on a quiet day, up to three on a big one, visiting blooms and the page
    wings = [[("pink", 1), ("yellow", .45)], [("yellow", 1), ("blue", .5)], [("blue", .9), ("pink", .3)]]
    stops = blooms + [tip]
    for b in range(0 if not today else 1 + (today >= active[len(active) // 2]) + (today >= cap)):
        route = rng.sample(stops, min(4, len(stops)))
        route = [(x + rng.uniform(-40, 40), y - rng.uniform(20, 70)) for x, y in route]
        # it rests on the page, wings going, until it takes off
        route.insert(0, rng.choice([(1250, rng.uniform(60, 300)), (rng.uniform(300, 900), 26), (30, rng.uniform(80, 400))]))
        fly = f'<g class="bfly glide" style="{glide(spline(route, closed=True), rng.uniform(26, 36), 4 + b * 1.5, turn=True)}"><g transform="scale({rng.uniform(1, 1.3):.2f})">'
        wing = (f'<ellipse cx="1" cy="-6" rx="6" ry="7.5" transform="rotate(-20)"/><ellipse cx="-4" cy="-4" rx="4.2" ry="5.2" transform="rotate(25)"/>'
                f'<ellipse cx="1" cy="6" rx="6" ry="7.5" transform="rotate(20)"/><ellipse cx="-4" cy="4" rx="4.2" ry="5.2" transform="rotate(-25)"/>')
        press.put(rng.choice(wings), f'{fly}<g class="wing" style="{tempo(2 / FPS)}">{wing}</g></g></g>', knock=False)
        press.put([("black", 1)], f'{fly}<rect x="-6" y="-1.2" width="12" height="2.4" rx="1.2"/></g></g>', knock=False)

    defs, layers = press.run(pull)
    grain, mottle, pinholes = paper_tiles(random.Random(7))
    sx, sy = pull.uniform(0, 128), pull.uniform(0, 128)
    # Every motion steps on the shared clock: loops hold each pose one frame (`--k` frames
    # a pass, ends held so a sway settles before it turns), gusts move in four equal beats
    # of `q` frames, and one-off entrances count out their frames segment by segment.
    q = round(period * FPS / 4)
    loop = "steps(var(--k),jump-none) var(--d) infinite alternate"
    style = (
        "<style>"
        f".gust{{transform-box:view-box;transform-origin:var(--o);animation:gust {period:.4f}s steps({q}) var(--d) infinite}}"
        "@keyframes gust{0%,100%{transform:skewX(0)}25%{transform:skewX(-8deg)}50%{transform:skewX(2.5deg)}75%{transform:skewX(-1.5deg)}}"
        f".sway{{transform-box:fill-box;transform-origin:50% 100%;animation:sway {period:.4f}s steps({q}) var(--d) infinite}}"
        "@keyframes sway{0%,100%{transform:skewX(0)}25%{transform:skewX(-4deg)}50%{transform:skewX(1.2deg)}75%{transform:skewX(-.5deg)}}"
        f".bl{{transform-box:view-box;transform-origin:var(--o,0 0);animation:bl var(--t) {loop}}}"
        "@keyframes bl{from{transform:rotate(-3.5deg)}to{transform:rotate(3.5deg)}}"
        f".lf{{animation:lf var(--t) {loop}}}"
        "@keyframes lf{from{transform:rotate(-7deg) scaleY(.9)}to{transform:rotate(7deg) scaleY(1.05)}}"
        f".fl{{animation:lf var(--t) {loop}}}"
        f".rays{{transform-box:view-box;animation:spin 150s steps({150 * FPS}) infinite}}"
        ".spin{animation:spin var(--t) steps(var(--k)) infinite}"
        "@keyframes spin{to{transform:rotate(360deg)}}"
        ".cloud{animation:drift var(--t) steps(var(--k)) var(--d) infinite}"
        "@keyframes drift{from{transform:translateX(-360px)}to{transform:translateX(1640px)}}"
        f".star,.blink{{animation:star var(--t) {loop}}}"
        "@keyframes star{from{opacity:1}to{opacity:.1}}"
        f".bird{{transform-box:fill-box;transform-origin:50% 100%;animation:bird var(--t) {loop}}}"
        "@keyframes bird{to{transform:scaleY(-.5)}}"
        ".flow{stroke-dasharray:4 22;animation:flow var(--t) steps(var(--k)) infinite}"
        "@keyframes flow{to{stroke-dashoffset:-26}}"
        ".glide{animation:glide var(--t) steps(var(--k)) var(--d) infinite}"
        "@keyframes glide{from{offset-distance:0%}to{offset-distance:100%}}"
        + "".join(press.keyframes) +
        f".wing{{transform-box:view-box;transform-origin:0 0;animation:flap var(--t) {loop}}}"
        "@keyframes flap{to{transform:scaleY(.2)}}"
        f".flap{{transform-box:view-box;transform-origin:0 0;animation:open 1.25s backwards,lift {period:.4f}s steps({q}) calc(var(--d) + 1.25s) infinite}}"
        "@keyframes open{0%{transform:scaleY(-1);animation-timing-function:steps(9)}60%{transform:scaleY(1.08);animation-timing-function:steps(6)}}"
        "@keyframes lift{0%,100%{transform:none}25%{transform:scaleY(1.1) skewX(-3deg)}50%{transform:scaleY(.95)}75%{transform:scaleY(.98)}}"
        ".write{fill:none;stroke:#fff;stroke-width:40;stroke-linecap:round;stroke-dasharray:1 1;"
        "animation:write var(--t) steps(var(--k)) var(--d) backwards}"
        "@keyframes write{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        f".grow{{stroke-dasharray:1 1;animation:write 2.5s steps({beat(2.5)}) 1s backwards}}"
        ".sprout{animation:sprout 1s var(--d) backwards}"
        "@keyframes sprout{0%{transform:scale(0);animation-timing-function:steps(6)}50%{transform:scale(1.2);animation-timing-function:steps(3)}"
        "75%{transform:scale(.94);animation-timing-function:steps(3)}100%{transform:none}}"
        ".bloom{transform-box:fill-box;transform-origin:center;animation:sprout 1s var(--d) backwards}"
        f".now{{transform-box:fill-box;transform-origin:center;animation:now 2.5s steps({beat(1.25)}) infinite}}"
        "@keyframes now{50%{transform:scale(1.22)}}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}.bfly,.loose{display:none}}"
        "</style>")
    tiles = (f'<pattern id="grain" width="96" height="96" patternUnits="userSpaceOnUse">'
             f'<image width="96" height="96" href="data:image/png;base64,{grain}"/></pattern>'
             f'<pattern id="mottle" width="420" height="420" patternUnits="userSpaceOnUse">'
             f'<image width="420" height="420" href="data:image/png;base64,{mottle}"/></pattern>'
             f'<pattern id="pinholes" width="160" height="160" patternUnits="userSpaceOnUse" patternTransform="translate({sx:.0f} {sy:.0f})">'
             f'<image width="160" height="160" style="image-rendering:pixelated" href="data:image/png;base64,{pinholes}"/></pattern>'
             f'<path id="tear" d="{tear_d}"/><clipPath id="hole"><use href="#tear"/></clipPath>'
             f'<path id="paper-page" fill-rule="evenodd" d="M-80 -80H{W + 80}V{H + 80}H-80Z{tear_d}"/>')
    paper = "#%02X%02X%02X" % PAPER
    out = {}
    for theme in PAGE:
        shade, torn = page(theme, edge, normals, flaps, period, random.Random(11))
        out[theme] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>{total:,} contributions in the last year, printed as a garden behind a tear in the page</title>{style}'
            f'<defs>{defs}{tiles}</defs>'
            # isolated, or Safari multiplies the loose inks into GitHub's dark page behind the image
            f'<g style="isolation:isolate">'
            f'<g clip-path="url(#hole)"><rect width="{W}" height="{H}" fill="{paper}"/>{layers["world"]}'
            f'<rect width="{W}" height="{H}" fill="url(#mottle)"/><rect width="{W}" height="{H}" fill="url(#pinholes)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#grain)" style="mix-blend-mode:multiply" opacity=".3"/>{shade}</g>'
            f'{torn}{layers["free"]}</g></svg>')
    return out


def bloom(press, x, y, r, recipe, at, rng, pulse=False):
    """Six-petal flower that opens at `at` seconds and then nods in the breeze; today's keeps breathing."""
    turn = rng.uniform(0, 60)
    opens = f'<g transform="translate({x:.1f} {y:.1f})"><g class="bloom" style="--d:{beat(at) / FPS:.4f}s">'
    nod = f'class="fl" style="{tempo(rng.uniform(2.2, 3.4))}"'
    wrap = lambda art: f'{opens}<g {nod}>' + (f'<g class="now">{art}</g>' if pulse else art) + "</g></g></g>"
    if not pulse:                                     # the paper is cut once; only the ink nods in it
        press.clear(f'{opens}<g stroke="#fff" stroke-width="2.5">{petals(r, 6, turn)}</g></g></g>')
    press.put(recipe, wrap(petals(r, 6, turn)), knock=pulse, fine=True)
    if r > 5:
        centre = [("yellow", 1), ("pink", .5)] if recipe[0][0] != "yellow" else [("pink", .7)]
        press.put(centre, wrap(f'<circle r="{r * .3:.1f}"/>'), knock=pulse, fine=True)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    login = os.environ.get("PROFILE_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "scryst"
    now = dt.datetime.fromisoformat(os.environ["PRINT_AT"]) if os.environ.get("PRINT_AT") else dt.datetime.now(dt.timezone.utc)
    days, total, last = activity(login, os.environ["GH_TOKEN"])
    out.mkdir(parents=True, exist_ok=True)
    for theme, svg in garden(days, total, last, now).items():
        path = out / f"garden-{theme}.svg"
        path.write_text(svg + "\n")
        print(f"{path} {path.stat().st_size} bytes")
