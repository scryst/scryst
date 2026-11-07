"""The scrying pool: a still night pond printed in riso. The water shows a vision
instead of a reflection: under each thing on the bank its letter of "scryst".
usage: pool.py OUTDIR  -> pool-light.svg, pool-dark.svg (+ .html wrappers)
"""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import garden as g
from garden import Press, INK, W, H, samples, pen, ribbon, poly, noise, blade, arch, bands, tempo, on_paper, tear, page, paper_tiles

WL = 352                       # the waterline
S = 1.3                        # letter scale: x-height 130px
TOP = WL + 30                  # where the x-height letters hang from
BASE = TOP + 100 * S

# Each letter in strokes: baseline 0, x-height -100. Its object stands on the bank above it.
LETTERS = {
    's': ["M72 -86 C60 -102 22 -104 14 -80 C6 -56 66 -52 70 -24 C74 4 26 8 4 -12"],
    'c': ["M76 -82 C62 -104 10 -102 6 -52 C2 -2 54 8 80 -18"],
    'r': ["M16 -102 C16 -60 14 -28 16 6", "M18 -62 C28 -92 50 -104 72 -92"],
    'y': ["M4 -100 C14 -62 26 -32 42 -6", "M84 -100 C72 -50 52 22 32 74 C24 94 6 96 -6 82"],
    't': ["M34 -128 C36 -90 30 -40 36 -12 C40 4 58 4 74 -10", "M4 -98 C26 -100 48 -102 72 -100"],
}
WORD = [('s', 282), ('c', 424), ('r', 556), ('y', 694), ('s', 842), ('t', 982)]   # letter, object x


def at(d, ox, oy, sc=1.0):
    g.OX, g.OY, g.SCALE = ox, oy, sc
    return g.place(d)


def brush(d, ox, oy, sc, wmin, wmax, rng):
    pts = samples(at(d, ox, oy, sc))
    return ribbon(pts, pen(pts, wmin, wmax), rng)


def tube(d, ox, oy, w0, w1, sc=1.0):
    """A stroke tapering from w0 to w1: a neck, a limb, a post."""
    pts = samples(at(d, ox, oy, sc))
    total = pts[-1][4] or 1
    left, right = [], []
    for x, y, tx, ty, s in pts:
        w = (w0 + (w1 - w0) * s / total) / 2
        left.append((x - ty * w, y + tx * w))
        right.append((x + ty * w, y - tx * w))
    return poly(left + right[::-1])


def swan(x, k, rng):
    """A swan on the water facing left; its neck is the s."""
    body = f'<path transform="translate({x} {WL}) scale({k})" d="M-36 2C-36 -16 -6 -30 26 -24C40 -21 50 -30 60 -40C62 -20 54 -2 36 2Z"/>'
    neck = tube("M-24 -10 C-46 -18 -50 -44 -34 -56 C-20 -66 -22 -82 -36 -86", x, WL, 11 * k, 6 * k, k)
    hx, hy = x - 38 * k, WL - 86 * k
    head = f'<ellipse cx="{hx:.1f}" cy="{hy:.1f}" rx="{8 * k:.1f}" ry="{5.5 * k:.1f}"/>'
    beak = poly([(hx - 5 * k, hy - 3 * k), (hx - 20 * k, hy + 3 * k), (hx - 5 * k, hy + 3 * k)])
    return body + f'<path d="{neck}{beak}"/>' + head


def reeds(x, rng):
    """Reeds on the bank, one leaf peeling off to the right: the r."""
    art = []
    for _ in range(9):
        bx = x + rng.uniform(-26, 18)
        art.append(blade(bx, WL + 2, rng.uniform(40, 120), rng.uniform(-10, 6), rng.uniform(2.4, 4)))
    art.append(blade(x - 2, WL + 2, 150, -3, 5))
    art.append(arch((x - 1, WL - 92), (x + 4, WL - 126), (x + 28, WL - 140), (x + 56, WL - 128), 7))
    tops = "".join(f'<rect x="{x + dx - 3:.0f}" y="{WL - h:.0f}" width="6" height="22" rx="3"/>' for dx, h in ((-14, 132), (10, 112)))
    return f'<path d="{"".join(art)}"/>{tops}'


def tree(x, rng):
    """A bare tree forking low, the right limb reaching furthest: the y."""
    trunk = tube(f"M0 0 C2 -40 6 -80 10 -112", x, WL, 22, 13)
    left = tube("M10 -110 C0 -150 -20 -190 -40 -224", x, WL, 13, 3)
    right = tube("M10 -112 C26 -160 44 -210 64 -252", x, WL, 14, 3)
    twigs = "".join(tube(d, x, WL, 4, 1) for d in (
        "M-14 -170 C-28 -182 -36 -186 -50 -186", "M-26 -198 C-24 -214 -22 -224 -16 -236",
        "M30 -170 C44 -176 54 -186 62 -198", "M46 -212 C38 -228 34 -238 34 -252", "M56 -234 C70 -240 78 -248 86 -262"))
    roots = poly([(x - 22, WL + 2), (x - 6, WL - 14), (x + 12, WL - 14), (x + 30, WL + 2)])
    return f'<path d="{trunk}{left}{right}{twigs}{roots}"/>'


def post(x):
    """A lantern post with a crossarm, the lantern hung off its right end: the t."""
    stem = tube("M0 0 C0 -60 1 -120 2 -172", x, WL, 9, 7)
    arm = tube("M-34 -146 C-10 -148 20 -150 46 -150", x, WL, 5, 5)
    hook = tube("M44 -150 C48 -146 48 -140 46 -134", x, WL, 2.4, 2.4)
    cap = poly([(x + 38, WL - 132), (x + 46, WL - 138), (x + 54, WL - 132)])
    return f'<path d="{stem}{arm}{hook}{cap}"/>', (x + 46, WL - 120)


def lantern(x, y):
    return f'<rect x="{x - 7}" y="{y - 12}" width="14" height="22" rx="2"/>'


def pool(rng, pull):
    press = Press()
    press.defs.append(f'<clipPath id="sky"><rect x="-20" y="-20" width="{W + 40}" height="{WL + 20}"/></clipPath>')
    press.defs.append(f'<clipPath id="water"><rect x="-20" y="{WL}" width="{W + 40}" height="{H - WL + 20}"/></clipPath>')
    # night sky, thinning toward the horizon
    bands(press, "blue", 40, WL, 1, .7, "sky")
    bands(press, "black", 40, WL, .5, .12, "sky")
    bands(press, "pink", 240, WL, 0, .1, "sky")
    # the crescent moon, low over the c
    mx, my = WORD[1][1] + 8, 150
    for i in range(7):
        t = i / 6
        press.put([("blue", .96 - .4 * t), ("black", .42 - .36 * t)], f'<circle cx="{mx}" cy="{my}" r="{190 - 130 * t:.0f}" clip-path="url(#sky)"/>')
    box = f'maskUnits="userSpaceOnUse" x="-20" y="-20" width="{W + 40}" height="{H + 40}"'
    press.defs.append(f'<mask id="crescent" {box}><circle cx="{mx}" cy="{my}" r="40" fill="#fff"/><circle cx="{mx + 22}" cy="{my - 8}" r="36"/></mask>')
    press.put([("yellow", 1), ("pink", .1)], f'<circle cx="{mx}" cy="{my}" r="40" mask="url(#crescent)"/>')
    # stars: paper left bare, a few twinkling as light over the ink
    stars, twinkling = [], []
    for _ in range(90):
        x, y = rng.uniform(50, W - 50), rng.uniform(60, WL - 40)
        if math.dist((x, y), (mx, my)) < 110:
            continue
        dot = f'cx="{x:.0f}" cy="{y:.0f}" r="{rng.uniform(1, 2.1):.1f}"'
        if rng.random() < .3:
            twinkling.append(f'<circle class="star" style="{tempo(rng.uniform(1.6, 4.5), -rng.uniform(0, 5))}" {dot}/>')
        else:
            stars.append(f'<circle {dot}/>')
    press.clear("".join(stars))
    press.glow(f'<g fill="{on_paper("#FFFFFF")}">{"".join(twinkling)}</g>')

    # the pond: dark and still, deepening toward the viewer
    press.clear(f'<rect x="-20" y="{WL}" width="{W + 40}" height="{H - WL + 20}"/>')
    bands(press, "blue", WL, H, .78, 1, "water", n=12)
    bands(press, "black", WL, H, .2, .55, "water", n=12)
    streaks = []
    for _ in range(46):
        row = WL + 4 + (H - WL) * rng.random() ** 1.6
        streaks.append(f'<rect x="{rng.uniform(-20, W):.0f}" y="{row:.1f}" width="{rng.uniform(20, 120):.0f}" height="{rng.uniform(.7, 1.6):.1f}"/>')
    press.put([("blue", .35)], f'<g clip-path="url(#water)">{"".join(streaks)}</g>')

    # the far bank: a low ragged strip of land, the things on it in silhouette
    lip = noise(rng, W + 40, [(160, 3), (40, 1.6), (9, .8)])
    bank = poly([(x, WL - 7 - abs(lip(x + 20)) * 2.2) for x in range(-20, W + 21, 4)] + [(W + 20, WL + 2), (-20, WL + 2)])
    sil = [("blue", .95), ("black", .92)]
    lamp_post, lamp = post(WORD[5][1])
    things = (f'<path d="{bank}"/>' + swan(WORD[0][1] + 6, 1.0, rng) + reeds(WORD[2][1], rng)
              + tree(WORD[3][1] - 14, rng) + swan(WORD[4][1] + 4, .62, rng) + lamp_post)
    press.put(sil, things)
    # the lantern burns yellow, a halo of screened light round it
    lx, ly = lamp
    for r, t in ((46, .14), (32, .22), (20, .34)):
        press.put([("yellow", t)], f'<circle cx="{lx}" cy="{ly}" r="{r}" clip-path="url(#sky)"/>', knock=False)
    press.put([("yellow", 1), ("pink", .3)], lantern(lx, ly))

    # the vision: each letter under its thing, light on the dark water, broken into bands
    # that sway apart and back like the surface
    word = []
    for (ch, x) in WORD:
        ox = x - 40 * S
        for d in LETTERS[ch]:
            word.append((ch, brush(d, ox, BASE, S, 5, 30, rng)))
    deep = int(BASE + 100 * S)
    rows = [(y, min(y + 6, deep)) for y in range(WL, deep, 6)]
    for side in (0, 1):
        press.defs.append(f'<clipPath id="rip{side}">' + "".join(
            f'<rect x="-40" y="{a}" width="{W + 80}" height="{b - a:.0f}"/>' for i, (a, b) in enumerate(rows) if i % 2 == side) + "</clipPath>")
    moon = press.ref(f'<path d="{"".join(d for ch, d in word if ch == "c")}"/>')
    rest = press.ref(f'<path d="{"".join(d for ch, d in word if ch != "c")}"/>')
    glow = press.ref(f'<circle cx="{lx}" cy="{BASE - 100 * S + 2:.0f}" r="13"/>')
    inks = {moon: {"yellow": INK["yellow"], "pink": press.ink("pink", .12)},
            rest: {"yellow": press.ink("yellow", .22)},
            glow: {"yellow": INK["yellow"], "pink": press.ink("pink", .3)}}
    for p in INK:
        art = "".join(f'<use href="{ref}" fill="{fills.get(p, "#fff")}"/>' for ref, fills in inks.items())
        press.raw(p, f'<g clip-path="url(#water)">' + "".join(
            f'<g class="rip" style="--x:{3 if side else -3}px;{tempo(2.2, -side * .7)}"><g clip-path="url(#rip{side})">{art}</g></g>'
            for side in (0, 1)) + "</g>")
    return press


def build():
    rng, pull = random.Random(2611), random.Random(5)
    press = pool(rng, pull)
    defs, world = press.run(pull)
    edge, normals, flaps = tear(random.Random(61))
    grain, mottle, pinholes = paper_tiles(random.Random(7))
    tear_d = poly(edge)
    period = 4.0
    q = round(period * g.FPS / 4)
    loop = "steps(var(--k),jump-none) var(--d) infinite alternate"
    style = ("<style>"
             f".star{{animation:star var(--t) {loop}}}@keyframes star{{from{{opacity:1}}to{{opacity:.1}}}}"
             f".rip{{animation:rip var(--t) {loop}}}@keyframes rip{{from{{transform:translateX(calc(-1 * var(--x)))}}to{{transform:translateX(var(--x))}}}}"
             f".flap{{transform-box:view-box;transform-origin:0 0;animation:open 1.25s backwards,lift {period:.4f}s steps({q}) calc(var(--d) + 1.25s) infinite}}"
             "@keyframes open{0%{transform:scaleY(-1);animation-timing-function:steps(9)}60%{transform:scaleY(1.08);animation-timing-function:steps(6)}}"
             "@keyframes lift{0%,100%{transform:none}25%{transform:scaleY(1.1) skewX(-3deg)}50%{transform:scaleY(.95)}75%{transform:scaleY(.98)}}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    tiles = (f'<pattern id="grain" width="96" height="96" patternUnits="userSpaceOnUse"><image width="96" height="96" href="data:image/png;base64,{grain}"/></pattern>'
             f'<pattern id="mottle" width="420" height="420" patternUnits="userSpaceOnUse"><image width="420" height="420" href="data:image/png;base64,{mottle}"/></pattern>'
             f'<pattern id="pinholes" width="160" height="160" patternUnits="userSpaceOnUse"><image width="160" height="160" style="image-rendering:pixelated" href="data:image/png;base64,{pinholes}"/></pattern>'
             f'<path id="tear" d="{tear_d}"/><clipPath id="hole"><use href="#tear"/></clipPath>'
             f'<path id="paper-page" fill-rule="evenodd" d="M-80 -80H{W + 80}V{H + 80}H-80Z{tear_d}"/>')
    paper = "#%02X%02X%02X" % g.PAPER
    out = {}
    for theme in g.PAGE:
        shade, torn = page(theme, edge, normals, flaps, period, random.Random(11))
        out[theme] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"><title>scryst</title>{style}'
                      f'<defs>{defs}{tiles}</defs><g style="isolation:isolate"><g clip-path="url(#hole)"><rect width="{W}" height="{H}" fill="{paper}"/>{world}'
                      f'<rect width="{W}" height="{H}" fill="url(#mottle)" opacity=".55"/><rect width="{W}" height="{H}" fill="url(#pinholes)"/>'
                      f'<rect width="{W}" height="{H}" fill="url(#grain)" style="mix-blend-mode:multiply" opacity=".3"/>{shade}</g>{torn}</g></svg>')
    return out


if __name__ == "__main__":
    OUT = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    for th, s in build().items():
        open(os.path.join(OUT, f'pool-{th}.svg'), 'w').write(s)
        bg = '#ffffff' if th == 'light' else '#0d1117'
        open(os.path.join(OUT, f'pool-{th}.html'), 'w').write(
            f'<!doctype html><title>pool {th}</title><style>body{{margin:0;background:{bg}}}'
            f'main{{max-width:1012px;margin:24px auto;padding:0 16px}}img{{display:block;width:100%;height:auto}}</style>'
            f'<main><h1 hidden data-render-check-ignore>scryst</h1><img src="pool-{th}.svg" alt="scryst"></main>')
        print(th, len(s) // 1024, 'KB')
