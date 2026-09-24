"""Prints the profile's living risograph, stdlib only.

  GH_TOKEN=... python3 scripts/garden.py dist/

The page is torn open on a lake printed behind it, the name written across the
mountains and mirrored in the water. Four drums, as on a real riso: yellow,
fluorescent pink, blue and black. Every colour in it is one of those inks or two
of them overprinted, and each drum lands a little out of register, differently on
every print. The torn page is GitHub's own, so the print comes in a light and a
dark copy.

What the picture measures:
  ranges   the year's weekly totals in six ranges, the oldest furthest away;
           a busier stretch stands taller
  reeds    one stem per day of the last year along the shore, height =
           contributions that day; the best days go to seed
  water    today's work, as light glittering under the sun or moon
  mist     settles in the valleys when the week is quiet, lifts when it is busy
  birds    the days worked in the last fortnight, leaving through the tear
  sky      the sun where it is over Los Angeles; by night the moon, in its real phase
  wind     quickens when this week outpaces the year and just after a push
  boat     out on the lake within an hour of a push, with a lantern after dark
  cabin    smoke from the chimney on a day with work in it; from dusk its window
           is lit for six hours after a push
  fireworks  over the lake on the night of the year's best day
The season shows too: larches gold in autumn and green in spring, snow on the
ranges in winter, fireflies on summer evenings. A heron, rising fish, a plane and
meteors come and go by chance. Only aggregate counts and the latest push time
are read.
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


def stepped(name, stops):
    """@keyframes whose every change lands on the shared clock. A timing function
    steps within each keyframe segment, not across the loop, so steps(--k) over
    uneven segments ticks far faster than FPS and redraws the whole image each
    screen frame. Here each segment steps once a frame, or once if it holds still.
    `stops` are (frame, declarations); the last frame is the loop's length."""
    frames = stops[-1][0]
    at = lambda f: f"{100 * f / frames:.5g}%"
    segs = "".join(f"{at(f)}{{{css};animation-timing-function:steps({1 if css == nxt else g - f})}}"
                   for (f, css), (g, nxt) in zip(stops, stops[1:]))
    return f"@keyframes {name}{{{segs}100%{{{stops[-1][1]}}}}}"


# Loop lengths in frames for motions with uneven keyframes, which must be fixed to step on the clock.
RING, STRIKE, SMOKE, METEOR, FLY, TRAIL, BURST, ROW, FLOCK = 144, 120, 62, 180, 36, 768, 66, 1080, 360


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

LAKE = 510                                        # the far shore
SIL = [("blue", .95), ("black", .92)]             # a backlit silhouette: near-black, never #000
# Range inks at the ridge, far (0) to near (5); each thins toward its foot into the valley haze.
RANGE = {
    "day": [[("blue", .12), ("pink", .1)], [("blue", .2), ("pink", .12)], [("blue", .32), ("pink", .14)],
            [("blue", .48), ("pink", .15)], [("blue", .66), ("pink", .14), ("black", .12)], [("blue", .88), ("yellow", .5), ("black", .34)]],
    "dusk": [[("blue", .1), ("pink", .4)], [("blue", .2), ("pink", .44)], [("blue", .32), ("pink", .46)],
             [("blue", .48), ("pink", .46), ("black", .06)], [("blue", .68), ("pink", .4), ("black", .2)], [("blue", .95), ("pink", .2), ("black", .72)]],
    "night": [[("blue", .7), ("black", .16)], [("blue", .76), ("black", .24)], [("blue", .84), ("black", .34)],
              [("blue", .9), ("black", .46)], [("blue", .96), ("black", .6)], [("blue", 1), ("black", .86)]],
}
RIM = {"day": [("yellow", 1), ("pink", .25)], "dusk": [("yellow", 1), ("pink", .6)], "night": [("blue", .5)]}   # light along each ridge

# "scryst" in one connected hand: baseline y=0, x-height -100, ascender -176.
NAME = (
    "M-40 12 C-20 10 0 -40 48 -102 C40 -84 30 -66 44 -50 C62 -32 74 -14 60 0 C48 12 20 10 14 -4 "
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
SCALE, OX, OY = 1.0, 392, 352
REFLECT = .34                                     # the water seen from above: reflections foreshortened


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


# ---------- the press ----------

class Press:
    """Collects artwork per drum; a shape inked on two drums overprints.

    Artwork is defined once and placed on each drum by reference. `knock` clears
    paper through every drum first, so a subject prints clean over what is behind it.
    """

    def __init__(self):
        self.plates = {p: [] for p in INK}
        self.over = []
        self.knocks = tuple(INK)
        self.screens, self.defs = {}, []

    def ink(self, plate, tone):
        """A drum's ink at a tone: solid, or a dot screen."""
        if tone >= 0.97:
            return INK[plate]
        pid = f"{plate}{round(tone * 100)}"
        if pid not in self.screens:
            r = 4.6 * math.sqrt(tone / math.pi)
            self.screens[pid] = (f'<pattern id="{pid}" width="4.6" height="4.6" patternUnits="userSpaceOnUse" '
                                 f'patternTransform="rotate({ANGLE[plate]})"><circle cx="2.3" cy="2.3" '
                                 f'r="{r:.2f}" fill="{INK[plate]}"/></pattern>')
        return f"url(#{pid})"

    def veil(self, tone):
        """A reverse screen: paper dots knocked through the ink, for thin mist."""
        pid = f"veil{round(tone * 100)}"
        if pid not in self.screens:
            r = 4.6 * math.sqrt(tone / math.pi)
            self.screens[pid] = (f'<pattern id="{pid}" width="4.6" height="4.6" patternUnits="userSpaceOnUse" '
                                 f'patternTransform="rotate(30)"><circle cx="2.3" cy="2.3" r="{r:.2f}" fill="#fff"/></pattern>')
        return f"url(#{pid})"

    def raw(self, plate, svg):
        self.plates[plate].append(svg)

    def glow(self, svg):
        """Light laid over every drum, for small bright things that move: a knockout
        would have to move on every drum with them."""
        self.over.append(svg)

    def ref(self, svg):
        if svg.startswith("#"):
            return svg
        self.defs.append(f'<g id="a{len(self.defs)}">{svg}</g>')
        return f"#a{len(self.defs) - 1}"

    def put(self, recipe, svg, knock=True, paint="fill"):
        ref = self.ref(svg)
        if knock:
            self.clear(ref, paint=paint)
        for plate, tone in recipe:
            self.raw(plate, f'<use href="{ref}" {paint}="{self.ink(plate, tone)}"/>')
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
        world = "".join(f'<g transform="translate({offs[p][0]:.1f} {offs[p][1]:.1f})" style="mix-blend-mode:multiply">'
                        f'{"".join(parts)}</g>' for p, parts in self.plates.items() if parts) + "".join(self.over)
        return "".join(self.screens.values()) + "".join(self.defs), world


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
    """A tapered stroke along one cubic: a leaf arching off a reed."""
    pts = [bez((p0, p1, p2, p3), k / 24) for k in range(25)]
    left = [(x - ty * w * (1 - k / 24) ** .8 / 2, y + tx * w * (1 - k / 24) ** .8 / 2) for k, (x, y, tx, ty) in enumerate(pts)]
    right = [(x + ty * w * (1 - k / 24) ** .8 / 2, y - tx * w * (1 - k / 24) ** .8 / 2) for k, (x, y, tx, ty) in enumerate(pts)]
    return poly(left + right[::-1])


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


def bands(press, plate, y0, y1, t0, t1, clip, n=20, ease=1.0):
    """Halftone gradient in bands of shrinking dots."""
    rows = "".join(f'<rect x="-20" y="{y0 + (y1 - y0) * b / n:.1f}" width="{W + 40}" height="{(y1 - y0) / n + 1:.1f}" '
                   f'fill="{press.ink(plate, max(.02, t0 + (t1 - t0) * (b / (n - 1)) ** ease))}"/>' for b in range(n))
    press.raw(plate, f'<g clip-path="url(#{clip})">{rows}</g>')


def sky(press, now, rng, edge):
    day, f, low, age = sun_or_moon(now)
    mood = "night" if not day else "dusk" if low < .08 else "day"
    press.defs.append(f'<clipPath id="sky"><rect x="-20" y="-20" width="{W + 40}" height="{LAKE + 20}"/></clipPath>')
    if mood == "day":
        bands(press, "blue", 40, LAKE, .55, .05, "sky")
        bands(press, "yellow", 200, LAKE, .0, .3, "sky", ease=1.6)
        bands(press, "pink", 320, LAKE, .0, .12, "sky")
    elif mood == "dusk":
        bands(press, "blue", 40, LAKE, .62, .03, "sky", ease=.7)
        bands(press, "pink", 60, LAKE, .04, .62, "sky")
        bands(press, "yellow", 220, LAKE, .02, .8, "sky", ease=1.4)
    else:
        bands(press, "blue", 40, LAKE, 1, .62, "sky")
        bands(press, "black", 40, LAKE, .48, .06, "sky")
        bands(press, "pink", 320, LAKE, 0, .12, "sky")
    sx, sy = 170 + f * 940, 420 - math.sin(math.pi * f) * 320
    if not day:
        # The sun sets behind the ranges, but the moon keeps clear of them (a crescent cut
        # by a ridge reads as a shard) and of the torn edge above it. Over the name it rides
        # above the letters even if the page hides its top: a stem into the disc reads as a lollipop.
        rim = max((py for px, py in edge if abs(px - sx) < 55 and py < CY), default=0)
        letters = [p[1] for p in samples(place(NAME)) + samples(place(CROSS)) if abs(p[0] - sx) < 60]
        sy = min(max(245 - math.sin(math.pi * f) * 140, rim + 62), min(letters, default=1e9) - 72)
    if day:
        # rays: broad wedges of thin yellow fanned from the sun, turning very slowly
        warm = [("pink", .35)] if mood == "dusk" else []
        wedges = []
        for k in range(18):
            a = 2 * math.pi * k / 18 + rng.uniform(-.05, .05)
            half = rng.uniform(.035, .075)
            wedges.append(f"M{sx:.0f} {sy:.0f}L{sx + 1100 * math.cos(a - half):.0f} {sy + 1100 * math.sin(a - half):.0f}"
                          f"L{sx + 1100 * math.cos(a + half):.0f} {sy + 1100 * math.sin(a + half):.0f}Z")
        # they thin with distance: rings round the sun, which turn with it unchanged
        rings = ((0, 180, 1), (180, 290, .78), (290, 400, .58), (400, 540, .4), (540, 1100, .24))
        circle = lambda r: f"M{sx - r:.0f} {sy:.0f}a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0Z"
        for i, (r0, r1, _) in enumerate(rings):
            press.defs.append(f'<clipPath id="ray{i}"><path clip-rule="evenodd" d="{circle(r1)}{circle(r0) if r0 else ""}"/></clipPath>')
        fan = press.ref(f'<path d="{"".join(wedges)}"/>')
        for plate, tone in [("yellow", .4 if mood == "day" else .55)] + [(p, t * .5) for p, t in warm]:
            art = "".join(f'<use href="{fan}" clip-path="url(#ray{i})" fill="{press.ink(plate, tone * fade)}"/>' for i, (*_, fade) in enumerate(rings))
            press.raw(plate, f'<g clip-path="url(#sky)"><g class="rays" style="transform-origin:{sx:.0f}px {sy:.0f}px">{art}</g></g>')
        for r, t in ((170, .1), (140, .16), (116, .23), (96, .3), (80, .38)):
            press.put([("yellow", t)] + [(p, v * t) for p, v in warm], f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r}" clip-path="url(#sky)"/>', knock=False)
        press.put([("yellow", 1), ("pink", .8 if mood == "dusk" else .12)], f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="62"/>')
    else:
        lit = 1 - abs(2 * age / 29.530589 - 1)       # 0 new .. 1 full
        off = 2 * 50 * lit * (-1 if age < 14.77 else 1)
        disc = f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="50"'
        box = f'maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}"'
        press.defs.append(f'<mask id="moonlit" {box}>{disc} fill="#fff"/><circle cx="{sx + off:.0f}" cy="{sy:.0f}" r="50"/></mask>')
        for i in range(8):                                # moonlight thins the sky round it
            t = i / 7
            press.put([("blue", .96 - .42 * t), ("black", .4 - .36 * t)], f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{250 - 170 * t:.0f}" clip-path="url(#sky)"/>')
        press.put([("yellow", .35)], f'{disc} mask="url(#moonlit)"/>')
        # Most stars are paper left bare. A quarter twinkle: they are drawn as light over
        # the ink instead, which is cheaper than knocking a hole through every drum.
        stars, twinkling = [], []
        for _ in range(110):
            x, y = rng.uniform(40, W - 40), rng.uniform(50, 380)
            if math.dist((x, y), (sx, sy)) > 130:
                if rng.random() < .25:
                    twinkling.append(f'<circle class="star" style="{tempo(rng.uniform(1.6, 4.5), -rng.uniform(0, 5))}" cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(1.2, 2.2):.1f}"/>')
                else:
                    stars.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(1, 2.2):.1f}"/>')
        press.clear("".join(stars))
        press.glow(f'<g fill="{on_paper("#FFFFFF")}">{"".join(twinkling)}</g>')

    # long stratus streaks drifting on the wind: paper knocked out of every drum, a shaded belly
    lit = {"day": [], "dusk": [("yellow", .22)], "night": [("blue", .5)]}[mood]
    belly = {"day": ("pink", .18), "dusk": ("pink", .45), "night": ("blue", .75)}[mood]
    for k in range(3):
        cy = rng.uniform(110, 250)
        span = rng.uniform(260, 460)
        puffs = "".join(f'<ellipse cx="{rng.uniform(-span / 2, span / 2):.0f}" cy="{rng.uniform(-5, 2):.0f}" '
                        f'rx="{rng.uniform(40, 110):.0f}" ry="{rng.uniform(5, 11):.0f}"/>' for _ in range(6))
        puffs += f'<rect x="{-span / 2:.0f}" y="-2" width="{span:.0f}" height="7" rx="3.5"/>'
        body = press.ref(puffs)
        press.defs.append(f'<clipPath id="st{k}">{puffs}</clipPath>')      # a clip may not <use> a group
        dur = rng.uniform(220, 320)
        wrap = f'<g clip-path="url(#sky)"><g class="cloud" style="{tempo(dur, -dur * (k + rng.random()) / 3)}"><g transform="translate(0 {cy:.0f})">'
        for plate in INK:
            art = f'<use href="{body}" fill="#fff"/>' + "".join(f'<use href="{body}" fill="{press.ink(p, t)}"/>' for p, t in lit if p == plate)
            if plate == belly[0]:
                art += f'<rect x="{-span:.0f}" y="1" width="{span * 2:.0f}" height="20" clip-path="url(#st{k})" fill="{press.ink(*belly)}"/>'
            press.raw(plate, wrap + art + "</g></g></g>")
    return mood, (sx, sy), day


# ---------- land and water ----------

def ridges(weeks, rng):
    """Six ranges of the year's weeks, the oldest furthest away, each a function
    x -> ridge y. The far ranges are the great ones, the near ones foothills."""
    top = math.sqrt(max(weeks) or 1)
    out = []
    n = len(weeks)
    span = W + 240
    for k in range(6):
        vals = weeks[round(n * k / 6):round(n * (k + 1) / 6)]
        depth = 1 - .13 * k
        base = 330 + 36 * k
        # the weeks set the height of the land along the range, eased between them; a range
        # of quiet weeks is lower overall, but every range keeps some relief
        rmax = math.sqrt(max(vals) or 1)
        relief = 60 + 80 * rmax / top
        env = [depth * (52 + relief * math.sqrt(v) / rmax) * rng.uniform(.9, 1.08) for v in vals]
        step = span / len(env)

        def envelope(s, env=env, step=step):
            u = min(max(s / step - .5, 0), len(env) - 1.001)
            i, f = int(u), (1 - math.cos(math.pi * (u % 1))) / 2
            return env[i] * (1 - f) + env[min(i + 1, len(env) - 1)] * f
        # peaks stand at uneven intervals, each as tall as the land there allows, with
        # flanks of their own steepness; the skyline is the highest of them
        # the newest range comes down to the water as a headland at either side, opening
        # the view in the middle
        frame = (lambda x: .35 + 2.6 * (abs(x - W / 2) / (W / 2)) ** 2.4) if k == 5 else (lambda _: 1)
        peaks, x = [], -140.0
        while x < W + 140:
            x += rng.uniform(80, 280) * (1.25 - .07 * k)
            h = envelope(x + 120) * rng.uniform(.3, 1) ** .7 * frame(x)
            peaks.append((x, h, h * rng.uniform(1.1, 3.2), h * rng.uniform(1.1, 3.2)))
        jag = noise(rng, span, [(90, 3 + k), (34, 2.5 + .8 * k), (12, 1.2 + .5 * k), (4.5, .5 + .25 * k)])

        def y(x, peaks=peaks, jag=jag, base=base):
            m = max(h * max(0.0, 1 - (px - x) / wl if x < px else 1 - (x - px) / wr) ** 1.3 for px, h, wl, wr in peaks)
            return base - m - jag(x + 120)
        out.append((y, base, max(h for _, h, *_ in peaks) + 8, peaks))
    return out


def mist(press, y, rng, mood):
    """A wisp of valley mist drifting along the foot of a range: a paper core
    feathered out through a reverse screen; only a thin veil by moonlight."""
    span = rng.uniform(700, 1100)
    blobs = [(rng.uniform(-span / 2, span / 2), rng.uniform(-3, 3), rng.uniform(70, 170), rng.uniform(4, 10)) for _ in range(9)]
    puffs = lambda grow: "".join(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx * grow:.0f}" ry="{ry * grow:.1f}"/>' for cx, cy, rx, ry in blobs)
    dur = rng.uniform(320, 440)
    reach = span / 2 + 200
    wrap = (f'<g class="mist" style="--a:{-reach:.0f}px;--b:{W + reach:.0f}px;{tempo(dur, -dur * rng.random())}">'
            f'<g transform="translate(0 {y:.0f})">')
    layers = ((2.2, .15), (1.6, .3), (1.15, .45)) if mood == "night" else ((2.2, .25), (1.6, .5), (1.15, .75), (.8, 1))
    art = "".join(f'<g fill="{press.veil(t) if t < 1 else "#fff"}">{puffs(grow)}</g>' for grow, t in layers)
    for plate in INK:
        press.raw(plate, wrap + art + "</g></g>")


SHADE = {"day": [("blue", .5), ("black", .14)], "dusk": [("blue", .5), ("pink", .1), ("black", .18)], "night": [("blue", .2), ("black", .32)]}


def faces(y, peaks, sx, foot, rng):
    """The flank of each skyline peak turned from the sun, as one path: along the
    ridge from the summit to the valley, then down a wavering crease."""
    out = []
    for px, h, wl, wr in peaks:
        if not -60 < px < W + 60:
            continue
        top = lambda x, px=px, h=h, wl=wl, wr=wr: h * max(0.0, 1 - (px - x) / wl if x < px else 1 - (x - px) / wr) ** 1.3
        owner = lambda x: max(peaks, key=lambda q: q[1] * max(0.0, 1 - (q[0] - x) / q[2] if x < q[0] else 1 - (x - q[0]) / q[3]) ** 1.3)[0]
        if owner(px) != px:                              # hidden behind a taller neighbour
            continue
        way = 1 if px > sx else -1
        edge, x = [], px
        while abs(x - px) < 400 and owner(x) == px and top(x) > 0:
            edge.append((x, y(x)))
            x += 3 * way
        if len(edge) < 4:
            continue
        ay = y(px)
        crease = [(px + way * (t * (foot - ay) * .2) + rng.uniform(-2.5, 2.5), ay + t * (foot - ay)) for t in (i / 10 for i in range(11))]
        out.append(poly(edge + [(edge[-1][0], foot)] + crease[::-1]))
    return "".join(out)


# Larches among the pines keep the calendar: soft green in spring, gold in autumn.
LARCH = {
    "spring": {"day": [("yellow", .75), ("blue", .35)], "dusk": [("yellow", .6), ("blue", .45), ("pink", .2)]},
    "autumn": {"day": [("yellow", 1), ("pink", .1), ("black", .24)], "dusk": [("yellow", .85), ("pink", .18), ("black", .32)]},
}


def season(now):
    md = (lambda d: d.month * 100 + d.day)(now.astimezone(LA))
    return "winter" if md >= 1221 or md < 320 else "spring" if md < 621 else "summer" if md < 922 else "autumn"


def pines(press, y, base, mood, wave, rng, when, clearing=None):
    """Dark pines along the headlands, in stands that lean together in a gust; a
    larch among them now and then, in its season's colour."""
    larch = LARCH.get(when, {}).get(mood)
    stands, x = {}, -10.0
    while x < W + 10:
        land = base - y(x)
        if land > 40 and not (clearing and abs(x - clearing) < 24):
            kind = "larch" if larch and rng.random() < .3 else "pine"
            s = rng.uniform(.6, 1) * min(1.6, land / 70)
            h, w, n, cut = (44 * s, 13 * s, rng.randint(4, 6), .45) if kind == "pine" else (47 * s, 12.5 * s, rng.randint(5, 7), .5)
            tx, ty = x, y(x) + 6
            left = [(tx, ty - h)]
            for i in range(1, n + 1):
                f = i / n
                left += [(tx - w * f * rng.uniform(.9, 1.15), ty - h + h * f * .92), (tx - w * f * cut, ty - h + h * f * .92 - h * .05)]
            right = [(2 * tx - a, b + rng.uniform(-1, 1)) for a, b in left[1:]][::-1]
            stands.setdefault((int(x // 260), kind), []).append(poly(left + [(tx - w * .12, ty), (tx + w * .12, ty)] + right))
            x += rng.uniform(.35, .8) * w * 2
        else:
            x += 12
    inks = {"pine": SIL if mood != "day" else [("blue", .9), ("yellow", .6), ("black", .5)], "larch": larch}
    for (key, kind), parts in stands.items():
        ref = press.ref(f'<path d="{"".join(parts)}"/>')
        gx = key * 260 + 130
        fills = {p: press.ink(p, t) for p, t in inks[kind]}
        for p in INK:
            press.raw(p, f'<g class="gust" style="--o:{gx:.0f}px {y(gx):.0f}px;{wave(gx)}"><use href="{ref}" fill="{fills.get(p, "#fff")}"/></g>')


def clearing(y, base, rng):
    """A level spot on a headland's slope for the cabin, or None."""
    side = rng.choice((0, 1))
    xs = range(130, 330, 4) if side == 0 else range(W - 330, W - 130, 4)
    spots = [x for x in xs if 45 < base - y(x) < 110]
    return min(spots, key=lambda x: abs(y(x + 8) - y(x - 8)) + rng.uniform(0, 3)) if spots else None


def cabin(press, x, y, mood, today, idle, drift):
    """A cabin in the clearing. Smoke rises from its chimney on days with work in
    them; after dark its window is lit if there was a push in the last six hours."""
    s, bx, by = 1.15, x, y(x) + 13
    walls = f'<path transform="translate({bx:.0f} {by:.0f}) scale({s})" d="M-12 0V-12H12V0Z"/>'
    roof = f'<path transform="translate({bx:.0f} {by:.0f}) scale({s})" d="M-15.5 -11L0 -22.5L15.5 -11ZM6 -16V-26H10V-14Z"/>'
    press.put(SIL if mood != "day" else [("yellow", .55), ("pink", .4), ("black", .5)], walls)
    press.put(SIL, roof)
    if mood != "day" and idle < 6:
        warm = on_paper(INK["yellow"])
        press.glow(f'<g fill="{warm}"><circle cx="{bx - 4 * s:.1f}" cy="{by - 6 * s:.1f}" r="9" opacity=".22"/>'
                   f'<rect x="{bx - 7 * s:.1f}" y="{by - 8 * s:.1f}" width="{6 * s:.1f}" height="{4.5 * s:.1f}"/></g>')
    if today:
        colour = {"day": "#A3B2BF", "dusk": "#8E8FA6", "night": "#8FA3B6"}[mood]
        puffs = "".join(f'<circle class="smoke" style="--wx:{drift:.0f}px;{tempo(SMOKE / FPS, -i * SMOKE / FPS / 5)}" cx="{bx + 8 * s:.1f}" cy="{by - 27 * s:.1f}" r="{3.4 + i * .3:.1f}"/>'
                        for i in range(5))
        press.glow(f'<g fill="{colour}">{puffs}</g>')


def ranges(press, rs, mood, fog, sun, wave, rng, when, home):
    """The ranges back to front, each thinning into haze at its foot, shadowed on
    the flanks turned from the sun and lit along its ridge; mist lies in more of
    the valleys the quieter the week."""
    floor = .82 if mood == "night" else .52 - .3 * fog
    wisps = rng.sample(range(1, 5), 1 + round(2 * fog))
    for k, (y, base, tallest, peaks) in enumerate(rs):
        ridge = [(x, y(x)) for x in range(-20, W + 21, 3)]
        shape = poly([(-20, H + 20)] + ridge + [(W + 20, H + 20)])
        press.clear(f'<path d="{shape}"/>')
        press.defs.append(f'<clipPath id="r{k}"><path d="{shape}"/></clipPath>')
        top, foot = base - tallest, base + 36
        for plate, tone in RANGE[mood][k]:
            bands(press, plate, top, foot, tone, tone * floor, f"r{k}", n=14, ease=.8)
            press.raw(plate, f'<rect x="-20" y="{foot:.0f}" width="{W + 40}" height="{H - foot + 20:.0f}" fill="{press.ink(plate, tone * floor)}" clip-path="url(#r{k})"/>')
        if k < 5:
            press.defs.append(f'<clipPath id="f{k}"><path d="{faces(y, peaks, sun[0], foot, rng)}"/></clipPath>')
            for plate, tone in SHADE[mood]:
                bands(press, plate, top, foot, tone * (.7 + .06 * k), tone * floor * .5, f"f{k}", n=10, ease=.8)
        if when == "winter" and 1 <= k <= 4:             # snow on the blue middle ranges; the far ones are pale already
            line = noise(rng, W + 40, [(60, 6), (18, 3), (6, 1.4)])
            level = base - tallest * .6                  # snow lies above an altitude, not a depth
            snow = poly(ridge + [(x, max(y(x), level + line(x + 20))) for x in range(W + 20, -21, -3)])
            press.clear(f'<path d="{snow}"/>')
            press.put([("blue", .2 if mood != "night" else .5)], f'<path d="{snow}" clip-path="url(#f{k})"/>', knock=False)
        rim = poly(ridge, False)
        if k > 3:                                        # the near ranges are lit only where the sun catches them
            if k == 5:
                spot = clearing(y, base, rng)
                pines(press, y, base, mood, wave, rng, when, spot)
                if spot:
                    home(spot, y)
            if k in wisps:
                mist(press, base + 14, rng, mood)
            continue
        press.clear(f'<path d="{rim}" fill="none" stroke="#fff" stroke-width="{1.8 + .2 * k:.1f}" stroke-linejoin="round"/>', paint="stroke")
        press.put(RIM[mood], f'<path d="{rim}" fill="none" stroke-width="{1 + .15 * k:.1f}" stroke-linejoin="round"/>', knock=False, paint="stroke")
        if k in wisps:                                   # in the valley, behind the next range
            mist(press, base + 14, rng, mood)


def reflection(press, hand, mood):
    """The name upside down in the water, foreshortened, in bands that sway apart
    and back like a lake's surface."""
    flip = f"translate(0 {LAKE * (1 + REFLECT):.1f}) scale(1 {-REFLECT})"
    deep = LAKE + REFLECT * (LAKE - (OY - 176 * SCALE)) + 6
    rows = [(y, min(y + 5, deep)) for y in range(LAKE, int(deep), 5)]
    for side in (0, 1):
        press.defs.append(f'<clipPath id="rip{side}">' + "".join(
            f'<rect x="-40" y="{a}" width="{W + 80}" height="{b - a:.0f}"/>' for i, (a, b) in enumerate(rows) if i % 2 == side) + "</clipPath>")
    ink = {"day": [("blue", .4), ("black", .3)], "dusk": [("blue", .45), ("pink", .15), ("black", .38)], "night": [("yellow", .6)]}[mood]
    fills = {p: press.ink(p, t) for p, t in ink}
    if mood == "night":                              # yellow reads on dark water only through a knockout
        fills = {p: fills.get(p, "#fff") for p in INK}
    for p, fill in fills.items():
        art = f'<use href="{hand}" transform="{flip}" mask="url(#written)" fill="{fill}"/>'
        press.raw(p, f'<g clip-path="url(#lake)">' + "".join(
            f'<g class="rip" style="--x:{3 if side else -3}px;{tempo(1.9, -side * .6)}"><g clip-path="url(#rip{side})">{art}</g></g>'
            for side in (0, 1)) + "</g>")


def lake(press, rs, mood, sun, today, hand, rng):
    press.defs.append(f'<clipPath id="lake"><rect x="-20" y="{LAKE}" width="{W + 40}" height="{H - LAKE + 20}"/></clipPath>')
    press.clear(f'<rect x="-20" y="{LAKE}" width="{W + 40}" height="{H - LAKE + 20}"/>')
    # the water holds the sky just above the horizon, darkening toward the viewer
    if mood == "day":
        bands(press, "blue", LAKE, H, .1, .55, "lake", n=10)
        bands(press, "yellow", LAKE, H, .3, .04, "lake", n=10)
    elif mood == "dusk":
        bands(press, "yellow", LAKE, H, .85, .08, "lake", n=10, ease=.7)
        bands(press, "pink", LAKE, H, .4, .22, "lake", n=10)
        bands(press, "blue", LAKE, H, .08, .66, "lake", n=10)
    else:
        bands(press, "blue", LAKE, H, .5, .85, "lake", n=10)
        bands(press, "black", LAKE, H, .04, .28, "lake", n=10)
    # the near range upside down in the water, seen from above so foreshortened, broken by ripples
    y = rs[-1][0]
    mirror = [(x, LAKE + (LAKE - y(x)) * REFLECT) for x in range(-20, W + 21, 4)]
    press.put([(p, t * .5) for p, t in RANGE[mood][-1]], f'<path d="{poly([(-20, LAKE)] + mirror + [(W + 20, LAKE)])}" clip-path="url(#lake)"/>')
    reflection(press, hand, mood)
    streaks = []
    for _ in range(70):
        row = LAKE + 3 + (H - LAKE) * rng.random() ** 1.4
        streaks.append(f'<rect x="{rng.uniform(-20, W):.0f}" y="{row:.1f}" width="{rng.uniform(30, 160):.0f}" height="{rng.uniform(.8, 2):.1f}"/>')
    press.clear(f'<g clip-path="url(#lake)">{"".join(streaks)}</g>')
    # the far shore: a low ragged strip of dark land where the range meets the water
    lip = noise(rng, W + 40, [(140, 2.2), (40, 1.2), (11, .6)])
    press.put([(p, t * .8) for p, t in RANGE[mood][-1]], f'<path d="{poly([(x, LAKE - .5 - abs(lip(x + 20)) * 1.2) for x in range(-20, W + 21, 5)] + [(W + 20, LAKE + .8), (-20, LAKE + .8)])}"/>')
    # the road of light the sun or moon lays across the water, widening toward the viewer
    road = []
    for i in range(34):
        d = i / 33
        w = (14 + 130 * d) * rng.uniform(.35, 1)
        road.append(f'<rect x="{sun[0] + rng.gauss(0, 4 + 20 * d) - w / 2:.0f}" y="{LAKE + 3 + (H - LAKE - 8) * d ** 1.25:.1f}" '
                    f'width="{w:.0f}" height="{1.2 + 2.4 * d:.1f}" rx="1"/>')
    road = f'<g clip-path="url(#lake)">{"".join(road)}</g>'
    if mood == "day":
        press.clear(road)
    else:
        press.put([("yellow", 1), ("pink", .25)] if mood == "dusk" else [("yellow", .55)], road)
    # today's work, as light glittering on the water under the sun or moon
    glints = []
    for k in range(min(60, today)):
        d = rng.random()
        gx = sun[0] + rng.gauss(0, 10 + 70 * d)
        glints.append((k % 3, f'<rect x="{gx - 3 - 9 * d:.0f}" y="{LAKE + 4 + (H - LAKE - 10) * d:.1f}" '
                              f'width="{6 + 18 * d * rng.uniform(.5, 1.2):.0f}" height="{1.2 + 1.4 * d:.1f}" rx="1"/>'))
    colour = on_paper("#FFF6C8" if mood == "night" else "#FFFFFF")
    for group in range(3):
        art = "".join(a for k, a in glints if k == group)
        if art:
            press.glow(f'<g class="star" style="{tempo(rng.uniform(.8, 1.6), -rng.uniform(0, 2))}" fill="{colour}" clip-path="url(#lake)">{art}</g>')


def bay(rng):
    """The near shore round a bay: banks in the corners, shallows across the middle,
    where things stand further off and smaller."""
    ph = [rng.uniform(0, 6.3) for _ in range(2)]
    ground = lambda x: 704 - 62 * (1 - (2 * x / W - 1) ** 2) - 5 * math.sin(x / 150 + ph[0]) - 3 * math.sin(x / 47 + ph[1])
    near = lambda x: .42 + .58 * abs(2 * x / W - 1) ** 1.3
    return ground, near


def reeds(press, days, counts, tone, cap, budding, wave, shore, rng):
    """A stem per day along the near shore, the year left to right; gusts roll
    through them four weeks at a time."""
    ground, near = shore
    # banks only in the corners; across the middle the reeds stand out in the shallows
    bank = lambda x: ground(x) + 400 * max(0.0, .72 - near(x))
    press.put(SIL, f'<path d="{poly([(-20, H + 20)] + [(x, bank(x)) for x in range(-20, W + 21, 8)] + [(W + 20, H + 20)])}"/>')
    pitch = (W - 120) / len(days)
    for wk in range(0, len(days), 28):
        gx = 60 + pitch * (wk + 14)
        art = []
        for di in range(wk, min(wk + 28, len(days))):
            x = 60 + pitch * (di + 0.5) + rng.uniform(-1.2, 1.2)
            c = counts[di]
            base = ground(x) + 6
            h = ((8 + 150 * tone(c) + rng.uniform(0, 12)) if c else rng.uniform(4, 14)) * near(x)
            lean = (rng.uniform(-8, 8) + h * .04) * near(x)
            art.append(blade(x, base, h, lean, (1.3 + 1.7 * tone(c)) * near(x)))
            if c and near(x) > .72 and rng.random() < .55:   # a leaf arching off the stems on the banks
                side, l = rng.choice((-1, 1)), h * rng.uniform(.35, .7)
                art.append(arch((x, base), (x + side * l * .1, base - l * .8), (x + side * l * .5, base - l), (x + side * l * .75, base - l * .7), 2.6))
            for _ in range(2 if near(x) > .72 else 0):   # and low grass on the banks
                tx = x + rng.uniform(-pitch, pitch)
                art.append(blade(tx, ground(tx) + 6, rng.uniform(6, 20) * near(tx), rng.uniform(-6, 6), 1.6 * near(tx)))
            if c and c >= budding:                        # the busier days go to seed
                fx, fy = x + lean, base - h
                size = (9 if c >= cap else 5.5) * near(x)
                ang = math.degrees(math.atan2(lean, h))
                art.append(f'M{fx:.1f} {fy + 2:.1f}m-2.2 0a2.2 {size:.1f} {ang:.0f} 1 0 4.4 0a2.2 {size:.1f} {ang:.0f} 1 0 -4.4 0Z')
        ref = press.ref(f'<path d="{"".join(art)}"/>')
        # cut out of the warm drums as they bend, so the lit water never tints them
        fills = {"yellow": "#fff", "pink": "#fff", **{p: press.ink(p, t) for p, t in SIL}}
        for p, fill in fills.items():
            press.raw(p, f'<g class="gust" style="--o:{gx:.0f}px {ground(gx):.0f}px;{wave(gx)}"><use href="{ref}" fill="{fill}"/></g>')


def pen_hand(press, rng):
    """The name's outline and the mask that writes it in on load, shared by the
    name and its reflection."""
    k = SCALE / 1.16
    pts, cross, tend = samples(place(NAME)), samples(place(CROSS)), samples(place(TENDRIL))
    body = (ribbon(pts, pen(pts, 4.6 * k, 36 * k), rng) + ribbon(cross, pen(cross, 3.6 * k, 13 * k), rng)
            + ribbon(tend, pen(tend, 3 * k, 8 * k), rng))
    reveal = "".join(f'<path class="write" pathLength="1" d="{line(p)}" style="{tempo(dur, at)}"/>'
                     for p, at, dur in ((pts, .6, 2.6), (cross, 3.1, .4), (tend, 3.4, .8)))
    press.defs.append(f'<mask id="written" maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}">{reveal}</mask>')
    return press.ref(f'<path d="{body}"/>')


def name(press, hand, mood):
    """The name: black over a blue hit for a rich ink, cut clean out of the
    landscape, the pink drum slipping at its edge."""
    written = f'<use href="{hand}" mask="url(#written)"/>'
    press.clear(f'<use href="{hand}" stroke="#fff" stroke-width="3" stroke-linejoin="round" mask="url(#written)"/>')
    press.put([("pink", 1)], f'<g transform="translate(2.2 1.6)">{written}</g>', knock=False)
    press.clear(written, plates=["pink"])              # pink only where it slipped
    ink = [("yellow", 1), ("pink", .12)] if mood == "night" else [("blue", .9), ("black", 1)]   # by night, in the moon's yellow
    press.put(ink, written, knock=False)


def birds(fortnight, rng, theme):
    """The days worked in the last fortnight: a flock rising out of the distance,
    growing as it nears, and leaving over the torn page. Past the tear it is drawn
    in the page's own light, or it would vanish into GitHub's dark."""
    if not fortnight:
        return ""
    flock = []
    for b in range(fortnight):
        bx, by = -b * rng.uniform(14, 22) + rng.uniform(-6, 6), (b % 2 * 2 - 1) * b * rng.uniform(3, 7) + rng.uniform(-5, 5)
        flock.append(f'<g transform="translate({bx:.0f} {by:.0f}) scale({rng.uniform(.8, 1.2):.2f})"><path class="bird" style="{tempo(rng.choice((.25, .33)), -rng.random())}" '
                     f'd="M-8 0Q-4 -5 0 0Q4 -5 8 0"/></g>')
    route, length, begin = "M960 420C1030 300 1100 170 1250 -70", FLOCK / FPS, -rng.uniform(4, 20)
    art = lambda colour: (f'<g class="glide" style="{glide(route, length, begin)}"><g class="away" style="{tempo(length, begin)}">'
                          f'<g fill="none" stroke="{colour}" stroke-width="1.6" stroke-linecap="round">{"".join(flock)}</g></g></g>')
    beyond = PAGE[theme]["rim"] if theme == "dark" else INK["black"]
    return f'<g clip-path="url(#hole)">{art(INK["black"])}</g><g clip-path="url(#outside)">{art(beyond)}</g>'


# ---------- life ----------

def dark(press, svg, recipe=SIL):
    """A dark shape on its own inks, without a knockout: it prints dark over
    anything. Drawn inline rather than by reference, so its parts can move."""
    for p, t in recipe:
        c = press.ink(p, t)
        press.raw(p, f'<g fill="{c}" stroke="{c}">{svg}</g>')


HERON = ('<path stroke-width=".6" d="M12 -19C6 -16 -4 -20 -8 -28C-9 -33 -4 -36 2 -34C8 -31 11 -25 12 -19Z"/>'
         '<path fill="none" stroke-width="1.3" d="M1 -21L0 0M4 -21L4.6 0"/>'
         '<g class="{cls}" style="transform-origin:-6px -31px;{t}"><path fill="none" stroke-width="2.8" stroke-linecap="round" d="M-6 -31C-11 -35 -4 -41 -8 -47"/>'
         '<circle stroke-width=".4" cx="-8.5" cy="-48" r="2.6"/><path stroke-width=".4" d="M-10 -49.6L-21 -47.6L-9.6 -46.2Z"/></g>')


def heron(press, shore, rng):
    """A heron in the shallows, facing into the bay; now and then it strikes."""
    ground, near = shore
    side = rng.choice((-1, 1))
    x = W / 2 + side * rng.uniform(170, 250)           # out in open water, clear of the reed beds
    sc, base = 2.3 * near(x), ground(x) + 3
    face = f"translate({x:.0f} {base:.0f}) scale({sc * side:.2f} {sc:.2f})"
    dark(press, f'<g transform="translate({x:.0f} {base:.0f}) scale({sc * side:.2f} {-sc * .5:.2f})">{HERON.format(cls="", t="")}</g>',
         [("blue", .45), ("black", .2)])
    dark(press, f'<g transform="{face}">{HERON.format(cls="strike", t=tempo(STRIKE / FPS, -rng.uniform(0, STRIKE / FPS)))}</g>')
    return x


BOAT = ('<path d="M-24 -1C-16 5 16 5 24 -1L21 -4.5H-21Z"/><path d="M-4 -4.5L-2.5 -16H3L4.5 -4.5Z"/>'
        '<circle cx=".3" cy="-19.2" r="3"/><path fill="none" stroke-width="1.3" d="M-9 -15L7 2"/>')


def boat(press, mood, rng, heron_x=None):
    """A boat out on the lake: someone shipped within the hour. By night it carries a lantern.
    It rows the open water between the reed beds, on the far side of any heron."""
    a, b = 200, W - 200
    if heron_x is not None:
        a, b = (heron_x + 90, b) if heron_x < W / 2 else (a, heron_x - 90)
    route, length, begin = f"M{a:.0f} 598L{b:.0f} 598", ROW / FPS, -rng.uniform(0, ROW / FPS)
    move = f'class="row" style="{glide(route, length, begin)}"'
    dark(press, f'<g {move}><g transform="scale(1.3)">{BOAT}</g></g>')
    dark(press, f'<g {move}><g transform="scale(1.3 -.65)">{BOAT}</g></g>', [("blue", .5), ("black", .25)])
    wake = on_paper("#FFFFFF") if mood != "night" else "#B8C8D6"
    lamp = (f'<circle cx="19" cy="-9" r="8" fill="{on_paper(INK["yellow"])}" opacity=".25"/><circle cx="19" cy="-9" r="2.2" fill="{on_paper(INK["yellow"])}"/>'
            f'<rect x="16" y="3" width="6" height="14" fill="{on_paper(INK["yellow"])}" opacity=".4"/>') if mood == "night" else ""
    press.glow(f'<g {move}><path d="M-25 1L-78 8M-25 1L-72 -4" stroke="{wake}" stroke-width="1.2" opacity=".7"/>{lamp}</g>')


def rises(press, mood, rng):
    """Fish rising: rings spreading on the water here and there."""
    colour, alpha = {"day": (on_paper(INK["blue"]), .7), "dusk": ("#F4EFE6", .85), "night": ("#DCE5EC", .7)}[mood]
    for _ in range(5):
        y = rng.uniform(LAKE + 20, 640)
        x, near = rng.uniform(140, W - 140), .5 + .8 * (y - LAKE) / (640 - LAKE)
        press.glow(f'<g class="ring" style="{tempo(RING / FPS, -rng.uniform(0, RING / FPS))}" fill="none" stroke="{colour}" '
                   f'stroke-width="{.9 + .7 * near:.1f}" opacity="{alpha}"><ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{24 * near:.1f}" ry="{5.5 * near:.1f}"/>'
                   f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{13 * near:.1f}" ry="{3 * near:.1f}"/></g>')


def meteors(press, rng):
    for _ in range(2):
        x0, y0 = rng.uniform(120, W - 420), rng.uniform(70, 125)
        path = f"M{x0:.0f} {y0:.0f}L{x0 + 250:.0f} {y0 + 62:.0f}"
        press.glow(f'<g class="meteor" style="{glide(path, METEOR / FPS, -rng.uniform(0, METEOR / FPS), turn=True)}" fill="{on_paper("#FFFFFF")}">'
                   f'<path d="M0 0L-64 -1.3L-64 1.3Z" opacity=".8"/><circle r="1.6"/></g>')


def fireflies(press, rng):
    warm = on_paper(INK["yellow"])
    for _ in range(4):
        dots = []
        for _ in range(5):
            x = rng.uniform(70, 330) if rng.random() < .5 else rng.uniform(950, 1210)
            y = rng.uniform(560, 668)
            dots.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4.5" opacity=".3"/><circle cx="{x:.0f}" cy="{y:.0f}" r="1.5"/>')
        press.glow(f'<g class="fly" style="{tempo(FLY / FPS, -rng.uniform(0, 2 * FLY / FPS))}" fill="{warm}">{"".join(dots)}</g>')


def contrail(press, rng):
    """A plane crossing high up, drawing its trail."""
    y0, y1 = rng.uniform(95, 150), rng.uniform(80, 140)
    x0, x1 = (rng.uniform(80, 300), rng.uniform(900, 1200))[::rng.choice((1, -1))]
    path, length, begin = f"M{x0:.0f} {y0:.0f}L{x1:.0f} {y1:.0f}", TRAIL / FPS, -rng.uniform(0, 40)
    press.glow(f'<path class="trail" pathLength="1" d="{path}" style="{tempo(length, begin)}" fill="none" stroke="{on_paper("#FFFFFF")}" stroke-width="2.4" stroke-linecap="round"/>'
               f'<circle class="plane" r="1.8" fill="{INK["black"]}" style="{glide(path, length, begin)}"/>')


def fireworks(press, rng):
    """The night of the year's best day: fireworks over the lake, doubled in the water."""
    white, yellow, pink = on_paper("#FFFFFF"), on_paper(INK["yellow"]), on_paper(INK["pink"])
    sites = [(250, 205, 62, yellow), (1050, 180, 70, white), (165, 140, 44, yellow), (1150, 255, 48, pink), (330, 120, 54, white)]
    for cx, cy, r, colour in sites:
        cx, cy = cx + rng.uniform(-20, 20), cy + rng.uniform(-15, 15)
        streaks, tips = [], []
        for k in range(18):
            a = 2 * math.pi * k / 18 + rng.uniform(-.07, .07)
            c, s_ = math.cos(a), math.sin(a)
            reach = r * rng.uniform(.88, 1.06)
            i0, i1 = (cx + c * r * .3, cy + s_ * r * .3), (cx + c * reach, cy + s_ * reach)
            streaks.append(poly([(i0[0] - s_ * .3, i0[1] + c * .3), (i1[0] - s_ * 1.1, i1[1] + c * 1.1),
                                 (i1[0] + s_ * 1.1, i1[1] - c * 1.1), (i0[0] + s_ * .3, i0[1] - c * .3)]))
            tips.append(f'<circle cx="{i1[0]:.1f}" cy="{i1[1]:.1f}" r="2.2"/>')
        loop, begin = BURST / FPS, -rng.uniform(0, BURST / FPS)
        burst = (f'<g class="burst" style="{tempo(loop, begin)}"><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r * 1.3:.0f}" fill="{colour}" opacity=".12"/>'
                 f'<path d="{"".join(streaks)}" fill="{colour}"/><g fill="{white if colour != white else yellow}">{"".join(tips)}</g></g>')
        rocket = f"M{cx + rng.uniform(-12, 12):.0f} {LAKE - 30}L{cx:.0f} {cy:.0f}"
        press.glow(burst + f'<circle class="rocket" r="1.8" fill="{yellow}" style="{glide(rocket, loop, begin)}"/>')
        press.glow(f'<g clip-path="url(#lake)" opacity=".5"><g transform="translate(0 {LAKE * (1 + REFLECT):.1f}) scale(1 {-REFLECT})">{burst}</g></g>')

# ---------- the print ----------

def garden(days, total, last, now):
    rng = random.Random(days[-1][0])                  # the drawing holds still through a day
    pull = random.Random(now.isoformat())             # registration changes every print
    counts = [c for _, c in days]
    active = sorted(c for c in counts if c)
    cap = active[int(len(active) * 0.9)] if active else 1
    budding = active[int(len(active) * .7)] if active else 1
    tone = lambda c: math.sqrt(min(c, cap) / cap)
    period = gust_period(days, total, last, now)
    period = beat(period / 4) * 4 / FPS                           # a gust in four equal beats
    wave = lambda x: f"--d:{beat((0.5 * x / W - 1) * period) / FPS:.4f}s"   # gusts roll left to right
    today, week = counts[-1], sum(counts[-7:])
    fog = max(.15, min(1.0, 1.25 - .5 * week / max(1, total / 52.14)))
    weeks = [sum(counts[i:i + 7]) for i in range(0, len(counts), 7)]
    fortnight = sum(1 for c in counts[-14:] if c)
    press = Press()

    idle = (now - last).total_seconds() / 3600 if last else 1e9
    record = today > 0 and today >= max(counts[:-1] or [0])
    luck = random.Random(pull.random())               # life moves about from print to print
    when = season(now)

    edge, normals, flaps = tear(rng)
    tear_d = poly(edge)
    mood, sun, day = sky(press, now, random.Random(rng.random()), edge)   # its draws vary with the hour; the land's must not
    rs = ridges(weeks, random.Random(rng.random()))
    drift = 18 + 30 * 8 / period
    home = lambda x, y: cabin(press, x, y, mood, today, idle, drift)
    ranges(press, rs, mood, fog, sun, wave, random.Random(rng.random()), when, home)
    hand = pen_hand(press, random.Random(rng.random()))
    lake(press, rs, mood, sun, today, hand, random.Random(rng.random()))
    shore = bay(random.Random(rng.random()))
    wader = heron(press, shore, luck) if mood != "night" else None
    if idle < 1:
        boat(press, mood, luck, wader)
    reeds(press, days, counts, tone, cap, budding, wave, shore, random.Random(rng.random()))
    name(press, hand, mood)
    rises(press, mood, luck)
    if mood == "night":
        meteors(press, luck)
    if mood != "day" and when == "summer":
        fireflies(press, luck)
    if mood == "day" and luck.random() < .55:
        contrail(press, luck)
    if mood == "night" and record:                   # a bright sky would swallow them
        fireworks(press, luck)

    defs, world = press.run(pull)
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
        "@keyframes gust{0%,100%{transform:skewX(0)}25%{transform:skewX(-7deg)}50%{transform:skewX(2deg)}75%{transform:skewX(-1.2deg)}}"
        f".rays{{transform-box:view-box;animation:spin 240s steps({240 * FPS}) infinite}}"
        "@keyframes spin{to{transform:rotate(360deg)}}"
        ".cloud{animation:drift var(--t) steps(var(--k)) var(--d) infinite}"
        "@keyframes drift{from{transform:translateX(-500px)}to{transform:translateX(1780px)}}"
        ".mist{animation:mist var(--t) steps(var(--k)) var(--d) infinite}"
        "@keyframes mist{from{transform:translateX(var(--a))}to{transform:translateX(var(--b))}}"
        f".star{{animation:star var(--t) {loop}}}"
        "@keyframes star{from{opacity:1}to{opacity:.1}}"
        f".bird{{transform-box:fill-box;transform-origin:50% 100%;animation:bird var(--t) {loop}}}"
        "@keyframes bird{to{transform:scaleY(-.5)}}"
        ".glide{animation:glide var(--t) steps(var(--k)) var(--d) infinite}"
        "@keyframes glide{from{offset-distance:0%}to{offset-distance:100%}}"
        ".row{animation:row var(--t) var(--d) infinite}"
        + stepped("row", [(0, "offset-distance:0%;opacity:0"), (54, "offset-distance:5%;opacity:1"),
                          (ROW - 54, "offset-distance:95%;opacity:1"), (ROW, "offset-distance:100%;opacity:0")]) +
        ".away{transform-origin:0 0;animation:away var(--t) var(--d) infinite}"
        + stepped("away", [(0, "transform:scale(.2);opacity:0"), (22, "transform:scale(.36);opacity:1"), (FLOCK, "transform:scale(2.8);opacity:1")]) +
        f".flap{{transform-box:view-box;transform-origin:0 0;animation:open 1.25s backwards,lift {period:.4f}s steps({q}) calc(var(--d) + 1.25s) infinite}}"
        "@keyframes open{0%{transform:scaleY(-1);animation-timing-function:steps(9)}60%{transform:scaleY(1.08);animation-timing-function:steps(6)}}"
        "@keyframes lift{0%,100%{transform:none}25%{transform:scaleY(1.1) skewX(-3deg)}50%{transform:scaleY(.95)}75%{transform:scaleY(.98)}}"
        f".rip{{animation:rip var(--t) {loop}}}"
        "@keyframes rip{from{transform:translateX(calc(-1 * var(--x)))}to{transform:translateX(var(--x))}}"
        ".ring{transform-box:fill-box;transform-origin:center;animation:ring var(--t) var(--d) infinite}"
        + stepped("ring", [(0, "transform:scale(.15);opacity:0"), (4, "transform:scale(.3);opacity:1"),
                           (36, "transform:scale(1.5);opacity:0"), (RING, "transform:scale(1.5);opacity:0")]) +
        ".strike{transform-box:view-box;animation:strike var(--t) var(--d) infinite}"
        + stepped("strike", [(0, "transform:none"), (101, "transform:none"), (106, "transform:rotate(-62deg)"),
                             (113, "transform:rotate(-62deg)"), (STRIKE, "transform:none")]) +
        ".smoke{transform-box:fill-box;transform-origin:center;animation:smoke var(--t) var(--d) infinite}"
        + stepped("smoke", [(0, "transform:translate(0,0) scale(.4);opacity:0"),
                            (7, "transform:translate(calc(var(--wx) * .113),-5.2px) scale(.65);opacity:.8"),
                            (SMOKE, "transform:translate(var(--wx),-46px) scale(2.6);opacity:0")]) +
        ".meteor{animation:meteor var(--t) var(--d) infinite}"
        + stepped("meteor", [(0, "offset-distance:0%;opacity:0"), (1, "offset-distance:12%;opacity:1"),
                             (9, "offset-distance:100%;opacity:0"), (METEOR, "offset-distance:100%;opacity:0")]) +
        ".fly{animation:fly var(--t) var(--d) infinite alternate}"
        + stepped("fly", [(0, "opacity:0"), (11, "opacity:0"), (22, "opacity:1"), (FLY, "opacity:1")]) +
        ".trail{stroke-dasharray:1 1;animation:trail var(--t) var(--d) infinite}"
        + stepped("trail", [(0, "stroke-dashoffset:1;opacity:.85"), (461, "stroke-dashoffset:0;opacity:.85"),
                            (653, "stroke-dashoffset:0;opacity:0"), (TRAIL, "stroke-dashoffset:0;opacity:0")]) +
        ".plane{animation:plane var(--t) var(--d) infinite}"
        + stepped("plane", [(0, "offset-distance:0%;opacity:1"), (461, "offset-distance:100%;opacity:1"),
                            (462, "offset-distance:100%;opacity:0"), (TRAIL, "offset-distance:100%;opacity:0")]) +
        ".burst{transform-box:fill-box;transform-origin:center;animation:burst var(--t) var(--d) infinite}"
        + stepped("burst", [(0, "transform:scale(.05) translateY(0);opacity:0"), (6, "transform:scale(.05) translateY(0);opacity:0"),
                            (7, "transform:scale(.05) translateY(0);opacity:1"), (16, "transform:scale(1) translateY(3px);opacity:1"),
                            (41, "transform:scale(1.1) translateY(18px);opacity:0"), (BURST, "transform:scale(1.1) translateY(18px);opacity:0")]) +
        ".rocket{animation:rocket var(--t) var(--d) infinite}"
        + stepped("rocket", [(0, "offset-distance:0%;opacity:1"), (6, "offset-distance:86%;opacity:1"),
                             (7, "offset-distance:100%;opacity:0"), (BURST, "offset-distance:100%;opacity:0")]) +
        ".write{fill:none;stroke:#fff;stroke-width:48;stroke-linecap:round;stroke-dasharray:1 1;"
        "animation:write var(--t) steps(var(--k)) var(--d) backwards}"
        "@keyframes write{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        "</style>")
    tiles = (f'<pattern id="grain" width="96" height="96" patternUnits="userSpaceOnUse">'
             f'<image width="96" height="96" href="data:image/png;base64,{grain}"/></pattern>'
             f'<pattern id="mottle" width="420" height="420" patternUnits="userSpaceOnUse">'
             f'<image width="420" height="420" href="data:image/png;base64,{mottle}"/></pattern>'
             f'<pattern id="pinholes" width="160" height="160" patternUnits="userSpaceOnUse" patternTransform="translate({sx:.0f} {sy:.0f})">'
             f'<image width="160" height="160" style="image-rendering:pixelated" href="data:image/png;base64,{pinholes}"/></pattern>'
             f'<path id="tear" d="{tear_d}"/><clipPath id="hole"><use href="#tear"/></clipPath>'
             f'<path id="paper-page" fill-rule="evenodd" d="M-80 -80H{W + 80}V{H + 80}H-80Z{tear_d}"/>'
             f'<clipPath id="outside"><use href="#paper-page" clip-rule="evenodd"/></clipPath>')
    paper = "#%02X%02X%02X" % PAPER
    out = {}
    for theme in PAGE:
        shade, torn = page(theme, edge, normals, flaps, period, random.Random(11))
        out[theme] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>{total:,} contributions in the last year, printed as a landscape behind a tear in the page</title>{style}'
            f'<defs>{defs}{tiles}</defs>'
            # isolated, or Safari multiplies the inks into GitHub's dark page behind the image
            f'<g style="isolation:isolate">'
            f'<g clip-path="url(#hole)"><rect width="{W}" height="{H}" fill="{paper}"/>{world}'
            f'<rect width="{W}" height="{H}" fill="url(#mottle)" opacity=".55"/><rect width="{W}" height="{H}" fill="url(#pinholes)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#grain)" style="mix-blend-mode:multiply" opacity=".3"/>{shade}</g>'
            f'{torn}{birds(fortnight, random.Random(3), theme) if day else ""}</g></svg>')
    return out


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
