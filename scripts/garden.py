"""Prints the profile's living risograph, stdlib only.

  GH_TOKEN=... python3 scripts/garden.py dist/

Four drums, as on a real riso: yellow, fluorescent pink, blue and black. Every
colour in the picture is one of those inks or two of them overprinted, and each
drum lands a little out of register, differently on every print.

Everything is measured, nothing is decoration:
  meadow   one stem per day of the last year, height = contributions that day
  hills    weekly totals, smoothed into ridges
  name     "scryst", hand-drawn as one inked vine; its leaves are the year's days,
           left to right, in the season's overprint; the biggest weeks flower
  tendril  today: a bud that opens once there is work today
  sky      the sun, or the moon in its real phase, where it is over Los Angeles
  wind     gusts quicken when this week outpaces the year and just after a push
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

W, H = 1280, 600
PAPER = (236, 235, 230)
INK = {"yellow": "#FFE800", "pink": "#FF48B0", "blue": "#0078BF", "black": "#2A2627"}
ANGLE = {"yellow": 0, "pink": 75, "blue": 15, "black": 45}
LA = ZoneInfo("America/Los_Angeles")

# Leaf recipes per month: (plate, tone) pairs overprinted. Winter blue, spring lime,
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

# "scryst" as one cursive vine: baseline y=0, x-height -100, ascender -176. Drawn by hand.
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
SCALE, OX, OY = 1.38, 306, 316


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
    """Collects artwork per drum; a shape inked on two drums overprints."""

    def __init__(self):
        self.plates = {p: [] for p in INK}
        self.screens = {}

    def ink(self, plate, tone):
        if tone >= 0.97:
            return INK[plate]
        pid = f"{plate}{round(tone * 100)}"
        if pid not in self.screens:
            pitch = 5.2
            r = pitch * math.sqrt(tone / math.pi)
            self.screens[pid] = (f'<pattern id="{pid}" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse" '
                                 f'patternTransform="rotate({ANGLE[plate]})"><circle cx="{pitch / 2}" cy="{pitch / 2}" '
                                 f'r="{r:.2f}" fill="{INK[plate]}"/></pattern>')
        return f"url(#{pid})"

    def put(self, recipe, draw):
        """draw(fill) -> svg; placed once on every drum in the recipe."""
        for plate, tone in recipe:
            self.plates[plate].append(draw(self.ink(plate, tone)))

    def run(self, rng):
        out = []
        for plate, parts in self.plates.items():
            reach = 1.0 if plate == "black" else 2.6
            dx, dy = rng.uniform(-reach, reach), rng.uniform(-reach, reach)
            out.append(f'<g transform="translate({dx:.1f} {dy:.1f})" style="mix-blend-mode:multiply">{"".join(parts)}</g>')
        return "".join(self.screens.values()), "".join(out)


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


def line(pts):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y, *_ in pts[::3])


def smooth(values, sigma):
    r = int(3 * sigma)
    out = []
    for i in range(len(values)):
        ws = [(math.exp(-(j * j) / (2 * sigma * sigma)), values[i + j]) for j in range(-r, r + 1) if 0 <= i + j < len(values)]
        out.append(sum(w * v for w, v in ws) / sum(w for w, _ in ws))
    return out


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
            row += bytes((*PAPER, 255 if rng.random() < 0.018 else 0))
        holes.append(bytes(row))
    pinholes = png(128, 128, holes, 6)
    return grain, mottle, pinholes


# ---------- sky ----------

def sky(press, now, horizon):
    """Sun or moon for this moment over Los Angeles, set behind the hills (clipped to the sky
    above `horizon`), with a halftone wash at twilight and at night."""
    local = now.astimezone(LA)
    n = local.timetuple().tm_yday
    decl = math.radians(-23.44) * math.cos(2 * math.pi * (n + 10) / 365)
    day_len = 2 * math.degrees(math.acos(-math.tan(math.radians(34.05)) * math.tan(decl))) / 15
    h = now.hour + now.minute / 60
    f = ((h - (19.88 - day_len / 2)) % 24) / day_len  # solar noon 19:53 UTC; 0 sunrise .. 1 sunset
    defs = f'<clipPath id="sky"><path d="{horizon}"/></clipPath>'
    if f <= 1:
        x, y = 150 + f * 980, 360 - math.sin(math.pi * f) * 270
        low = min(f, 1 - f)
        if low < .07:
            wash(press, "pink", 200, 480, up=False)
        recipe = [("yellow", .9)] + ([("pink", .75)] if low < .07 else [("pink", .3)] if low < .18 else [])
        press.put(recipe, lambda fill: f'<circle cx="{x:.0f}" cy="{y:.0f}" r="88" fill="{fill}" clip-path="url(#sky)"/>')
    else:
        g = (f - 1) / ((24 - day_len) / day_len)      # 0 dusk .. 1 dawn
        x, y = 150 + g * 980, 330 - math.sin(math.pi * g) * 240
        age = ((now - dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)).total_seconds() / 86400) % 29.530589
        lit = 1 - abs(2 * age / 29.530589 - 1)       # 0 new .. 1 full
        off = 2 * 66 * lit * (-1 if age < 14.77 else 1)
        disc = f'<circle cx="{x:.0f}" cy="{y:.0f}" r="66"'
        shade = f'<circle cx="{x + off:.0f}" cy="{y:.0f}" r="66"'
        box = f'maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}"'
        # The lit moon is paper: knocked out of the night wash, then touched with a little yellow.
        defs += (f'<mask id="moonlit" {box}>{disc} fill="#fff"/>{shade} fill="#000"/></mask>'
                 f'<mask id="night" {box}><rect x="-20" y="-20" width="{W + 40}" height="{H + 40}" fill="#fff"/>'
                 f'{disc} fill="#000"/>{shade} fill="#fff"/></mask>')
        wash(press, "blue", 0, 480, up=True, mask="night")
        press.put([("yellow", .3)], lambda fill: f'{disc} fill="{fill}" mask="url(#moonlit)"/>')
    return defs


def wash(press, plate, y0, y1, up, mask=None):
    """Halftone gradient in bands of shrinking dots, clipped to the sky."""
    bands, attr = 9, f' mask="url(#{mask})"' if mask else ""
    rows = []
    for b in range(bands):
        tone = (0.42 * (1 - b / bands) + 0.04) if up else 0.32 * (b + 1) / bands
        top = y0 + (y1 - y0) * b / bands
        rows.append((tone, f'x="-10" y="{top:.0f}" width="{W + 20}" height="{(y1 - y0) / bands + 1:.0f}"'))
    press.put([(plate, 1)], lambda _: f'<g clip-path="url(#sky)"{attr}>' + "".join(
        f'<rect {box} fill="{press.ink(plate, tone)}"/>' for tone, box in rows) + "</g>")


# ---------- the print ----------

def garden(days, total, last, now):
    rng = random.Random(days[-1][0])                  # the drawing holds still through a day
    pull = random.Random(now.isoformat())             # registration changes every print
    counts = [c for _, c in days]
    active = sorted(c for c in counts if c)
    cap = active[int(len(active) * 0.9)] if active else 1
    tone = lambda c: math.sqrt(min(c, cap) / cap)
    period = gust_period(days, total, last, now)
    delay = lambda x: f"--d:{(0.55 * x / W - 1) * period:.2f}s"   # gusts cross left to right
    press = Press()

    # Hills from weekly totals: a far blue ridge, a near pale green one.
    weeks = [sum(counts[i:i + 7]) for i in range(0, len(counts), 7)]
    top = max(weeks) or 1

    def ridge(vals, base, amp, sigma):
        v = smooth(vals, sigma)
        return [(W * i / (len(v) - 1), base - amp * math.sqrt(x / top)) for i, x in enumerate(v)]

    def land(pts):
        return f"M-10 {H} L-10 {pts[0][1]:.1f} L" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + f" L{W + 10} {pts[-1][1]:.1f} L{W + 10} {H}Z"
    far_pts = ridge(weeks, 468, 210, 1.6)
    far = land(far_pts)
    near = land(ridge([sum(weeks[max(0, i - 3):i + 1]) / 4 for i in range(len(weeks))], 524, 120, 2.5))
    horizon = (f"M-20 -20 L{W + 20} -20 L{W + 20} {far_pts[-1][1] + 2:.1f} L"
               + " L".join(f"{x:.1f} {y + 2:.1f}" for x, y in reversed(far_pts)) + f" L-20 {far_pts[0][1] + 2:.1f}Z")
    defs = sky(press, now, horizon)
    press.put([("blue", .45)], lambda fill: f'<path d="{far}" fill="{fill}"/>')
    press.put([("yellow", .55), ("blue", .16)], lambda fill: f'<path d="{near}" fill="{fill}"/>')

    # Meadow: a stem per day; the best days flower.
    pitch = (W - 24) / len(days)
    for wk in range(0, len(days), 7):
        stems = {p: [] for p in INK}
        for di in range(wk, min(wk + 7, len(days))):
            x = 12 + pitch * (di + 0.5) + rng.uniform(-1, 1)
            c = counts[di]
            h = 8 + 92 * tone(c) + rng.uniform(0, 6)
            lean = rng.uniform(-7, 7)
            month = int(days[di][0][5:7])
            d = (f"M{x - 2.2:.1f} {H + 4}Q{x + lean * .2:.1f} {H - h * .6:.1f} {x + lean:.1f} {H - h:.1f}"
                 f"Q{x + lean * .2 + 1:.1f} {H - h * .6:.1f} {x + 2.2:.1f} {H + 4}Z")
            for plate, t in rng.choice(LEAF[month]):   # grass prints a shade deeper than leaves
                t = min(1.0, t * 1.4)
                stems[plate].append(f'<path fill="{press.ink(plate, t)}" d="{d}"/>')
            if c and c >= cap:
                r = rng.uniform(2.8, 4.2)
                for plate, t in FLOWER[month]:
                    stems[plate].append(f'<circle cx="{x + lean:.1f}" cy="{H - h:.1f}" r="{r:.1f}" fill="{press.ink(plate, t)}"/>')
        for plate, items in stems.items():
            if items:
                press.plates[plate].append(f'<g class="gust" style="{delay(12 + pitch * wk)}">{"".join(items)}</g>')

    # The name: black key over a blue hit for a rich, inky black, written in on load.
    name_pts = samples(place(NAME))
    cross_pts, tend_pts = samples(place(CROSS)), samples(place(TENDRIL))
    body = (ribbon(name_pts, pen(name_pts, 3.2, 19), rng) + ribbon(cross_pts, pen(cross_pts, 3, 10), rng)
            + ribbon(tend_pts, pen(tend_pts, 2.4, 5.5), rng))
    # Pen timing: the name, then the crossbar, then the tendril out to today.
    reveal = "".join(f'<path class="write" pathLength="1" d="{line(p)}" style="animation-delay:{at}s;animation-duration:{dur}s"/>'
                     for p, at, dur in ((name_pts, 0, 2.4), (cross_pts, 2.3, .5), (tend_pts, 2.7, .9)))
    defs += f'<mask id="written" maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}">{reveal}</mask>'
    press.put([("blue", .85), ("black", 1)], lambda fill: f'<path d="{body}" fill="{fill}" mask="url(#written)"/>')

    x0, x1 = name_pts[0][0], tend_pts[-1][0]

    def day_at(x):
        return round(min(1, max(0, (x - x0) / (x1 - x0))) * (len(days) - 1))

    # Leaves: one node every ~12px of vine; the day beneath sets size and season.
    side, total_len = 1, name_pts[-1][4]
    for i in range(0, len(name_pts), 8):
        x, y, tx, ty, length = name_pts[i]
        if length < 30 or length > total_len - 20:
            continue
        di = day_at(x)
        t = tone(sum(counts[max(0, di - 3):di + 4]) / 7)
        if t < 0.12 and rng.random() > 0.25:
            continue
        size = 5 + 17 * t
        side = -side
        ang = math.degrees(math.atan2(ty, tx)) + side * rng.uniform(40, 65)
        grow = 2.2 + 1.8 * (x - x0) / (x1 - x0)
        shape = (f'M0 0C{size * .3:.1f} {-size * .38:.1f} {size * .75:.1f} {-size * .36:.1f} {size:.1f} 0'
                 f'C{size * .75:.1f} {size * .36:.1f} {size * .3:.1f} {size * .38:.1f} 0 0Z')
        press.put(rng.choice(LEAF[int(days[di][0][5:7])]), lambda fill: (
            f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.0f})"><g class="sprout" style="animation-delay:{grow:.2f}s">'
            f'<path class="sway" style="{delay(x)}" fill="{fill}" d="{shape}"/></g></g>'))

    # Flowers where the biggest weeks fall on the vine.
    for rank, k in enumerate(sorted(range(len(weeks)), key=lambda k: -weeks[k])[:7]):
        target = x0 + (x1 - x0) * (k * 7 + 3) / (len(days) - 1)
        x, y, *_ = min(name_pts[20:-20], key=lambda p: abs(p[0] - target) + 0.05 * abs(p[1] - OY + 60))
        month = int(days[min(len(days) - 1, k * 7 + 3)][0][5:7])
        bloom(press, x, y, 7 + 7 * math.sqrt(weeks[k] / top), FLOWER[month], 4.8 + 0.12 * rank, rng)

    # Today: the tendril's tip. A bud until there is work today, then a flower.
    tx_, ty_ = tend_pts[-1][:2]
    if counts[-1]:
        bloom(press, tx_, ty_, 6 + 6 * tone(counts[-1]), [("pink", 1)], 3.6, rng, pulse=True)
    else:
        bloom(press, tx_, ty_, 4.5, [("yellow", 1), ("blue", .3)], 3.6, rng, pulse=True)

    screens, plates = press.run(pull)
    grain, mottle, pinholes = paper_tiles(random.Random(7))
    sx, sy = pull.uniform(0, 128), pull.uniform(0, 128)
    style = (
        "<style>"
        f".gust{{transform-box:fill-box;transform-origin:50% 100%;animation:gust {period:.2f}s ease-in-out infinite;animation-delay:var(--d)}}"
        "@keyframes gust{0%,46%,100%{transform:skewX(0)}12%{transform:skewX(-9deg)}26%{transform:skewX(3deg)}36%{transform:skewX(-2deg)}}"
        f".sway{{animation:sway {period:.2f}s ease-in-out infinite;animation-delay:var(--d)}}"
        "@keyframes sway{0%,46%,100%{transform:rotate(0)}12%{transform:rotate(-14deg)}26%{transform:rotate(5deg)}}"
        ".write{fill:none;stroke:#fff;stroke-width:40;stroke-linecap:round;stroke-dasharray:1 1;"
        "animation:write 2.4s cubic-bezier(.45,0,.3,1) backwards}"
        "@keyframes write{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        ".sprout{animation:sprout .9s cubic-bezier(.3,1.5,.5,1) backwards}"
        "@keyframes sprout{from{transform:scale(0)}}"
        ".bloom{transform-box:fill-box;transform-origin:center;animation:sprout 1.2s cubic-bezier(.3,1.6,.5,1) backwards}"
        ".now{transform-box:fill-box;transform-origin:center;animation:now 2.4s ease-in-out infinite}"
        "@keyframes now{50%{transform:scale(1.25)}}"
        "@media (prefers-reduced-motion:reduce){.gust,.sway,.write,.sprout,.bloom,.now{animation:none}}"
        "</style>")
    tiles = (f'<pattern id="grain" width="96" height="96" patternUnits="userSpaceOnUse">'
             f'<image width="96" height="96" href="data:image/png;base64,{grain}"/></pattern>'
             f'<pattern id="mottle" width="420" height="420" patternUnits="userSpaceOnUse">'
             f'<image width="420" height="420" href="data:image/png;base64,{mottle}"/></pattern>'
             f'<pattern id="pinholes" width="160" height="160" patternUnits="userSpaceOnUse" patternTransform="translate({sx:.0f} {sy:.0f})">'
             f'<image width="160" height="160" style="image-rendering:pixelated" href="data:image/png;base64,{pinholes}"/></pattern>'
             f'<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>')
    paper = "#%02X%02X%02X" % PAPER
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
            f'<title>{total:,} contributions in the last year, printed as a garden</title>{style}'
            f'<defs>{screens}{tiles}{defs}</defs>'
            f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{paper}"/>{plates}'
            f'<rect width="{W}" height="{H}" fill="url(#mottle)"/><rect width="{W}" height="{H}" fill="url(#pinholes)"/>'
            f'<rect width="{W}" height="{H}" fill="url(#grain)" style="mix-blend-mode:multiply" opacity=".3"/></g></svg>')


def bloom(press, x, y, r, recipe, at, rng, pulse=False):
    """Five-petal flower that opens at `at` seconds; today's keeps breathing afterwards."""
    turn = rng.uniform(0, 72)
    petals = "".join(f'<ellipse cx="{r * .55:.1f}" cy="0" rx="{r * .56:.1f}" ry="{r * .34:.1f}" transform="rotate({turn + 72 * p:.0f})"/>'
                     for p in range(5))
    wrap = lambda art: (f'<g transform="translate({x:.1f} {y:.1f})"><g class="bloom" style="animation-delay:{at:.1f}s">'
                        + (f'<g class="now">{art}</g>' if pulse else art) + "</g></g>")
    press.put(recipe, lambda fill: wrap(f'<g fill="{fill}">{petals}</g>'))
    if r > 5:
        centre = [("yellow", 1), ("pink", .5)] if recipe[0][0] != "yellow" else [("pink", .7)]
        press.put(centre, lambda fill: wrap(f'<circle r="{r * .3:.1f}" fill="{fill}"/>'))


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    login = os.environ.get("PROFILE_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "scryst"
    now = dt.datetime.fromisoformat(os.environ["PRINT_AT"]) if os.environ.get("PRINT_AT") else dt.datetime.now(dt.timezone.utc)
    days, total, last = activity(login, os.environ["GH_TOKEN"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "garden.svg").write_text(garden(days, total, last, now) + "\n")
    print(f"{out / 'garden.svg'} {(out / 'garden.svg').stat().st_size} bytes")
