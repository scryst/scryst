"""Print the profile poster: python3 scripts/poster.py <out-dir> [--at 2026-11-06T20:00Z]

Writes poster-light.svg and poster-dark.svg: paper and black ink, the wordmark and the ink kid on
one ground line, and a halftone moon behind her in tonight's real phase. The vector art comes from
scripts/art.json (made once from art/mascot.png and Bricolage Grotesque). Standard library only.
"""
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1200, 440
SYNODIC = 29.530589
NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
THEMES = {
    "light": {"paper": "#F1EFEA", "ink": "#111110", "grain": (0, 0.6, 0.34)},
    "dark": {"paper": "#111110", "ink": "#ECE8DF", "grain": (1, 0.6, 0.28)},
}


def moon(now):
    """(age in days, lit fraction, name) for the moon at `now`."""
    age = ((now - NEW_MOON).total_seconds() / 86400) % SYNODIC
    lit = (1 - math.cos(2 * math.pi * age / SYNODIC)) / 2
    names = ["new moon", "waxing crescent", "first quarter", "waxing gibbous",
             "full moon", "waning gibbous", "last quarter", "waning crescent"]
    return age, lit, names[int((age / SYNODIC) * 8 + 0.5) % 8]


def lit_shape(cx, cy, r, age, steps=48):
    """The sunlit part of the disk as seen from the north: right limb waxing, left limb waning."""
    phi = 2 * math.pi * age / SYNODIC
    side = 1 if age < SYNODIC / 2 else -1
    ys = [r * math.cos(math.pi * i / steps) for i in range(steps + 1)]  # top to bottom
    limb = [(cx + side * math.sqrt(max(r * r - y * y, 0)), cy - y) for y in ys]
    term = [(cx + side * math.cos(phi) * math.sqrt(max(r * r - y * y, 0)), cy - y) for y in reversed(ys)]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in limb + term) + "Z"


def poster(theme, art, now):
    t = THEMES[theme]
    wm, m = art["wordmark"], art["mascot"]
    age, lit, name = moon(now)

    # wordmark: 740 wide, standing on the same ground line as the kid
    x0, top, x1, _ = wm["bounds"]
    s = 740 / (x1 - x0)
    word = f"translate({56 - x0 * s:.2f} 414) scale({s:.5f})"

    # mascot: 372 tall, feet on the baseline at y 414, centered on x 952
    bx0, by0, bx1, by1 = m["bbox"]
    ms = 372 / (by1 - by0)
    mx, my = 952 - (bx0 + bx1) / 2 * ms, 414 - by1 * ms
    potrace = f'translate(0 {m["h"]}) scale(0.1 -0.1)'

    def part(d, cls=""):
        return f'<path{f" class={chr(34)}{cls}{chr(34)}" if cls else ""} d="{d}" transform="{potrace}"/>'

    sway = lambda p, delay: (  # noqa: E731
        f'<animateTransform attributeName="transform" type="rotate" dur="3.6s" begin="{delay}s" repeatCount="indefinite" '
        f'values="-5 {p[0]} {p[1]};5 {p[0]} {p[1]};-5 {p[0]} {p[1]}" keyTimes="0;.5;1" calcMode="spline" '
        f'keySplines=".45 0 .55 1;.45 0 .55 1"/>')
    # she is printed as a die-cut sticker: in the dark theme the plate is cream and her ink stays dark,
    # so she never turns into a photo negative
    plate, kid_ink = (t["paper"], t["ink"]) if theme == "light" else (t["ink"], t["paper"])
    lids = "".join(
        f'<ellipse cx="{e["cx"]}" cy="{e["cy"]}" rx="{e["rx"] + 6}" ry="{e["ry"] + 7}" fill="{plate}"/>'
        f'<path d="M{e["cx"] - e["rx"]} {e["cy"] - 2} Q{e["cx"]} {e["cy"] + 14} {e["cx"] + e["rx"]} {e["cy"] - 2}" '
        f'fill="none" stroke="{kid_ink}" stroke-width="9" stroke-linecap="round"/>'
        for e in m["eyes"])
    sparkles = "".join(
        f'<g class="tw tw{i}">{part(sp["d"])}</g>' for i, sp in enumerate(m["sparkles"]))

    # moon: behind her head
    mcx, mcy, mr = 952, 150, 128
    lit_d = lit_shape(mcx, mcy, mr, age)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="scryst">
<title>scryst</title>
<desc>An ink kid with antennae holds a crystal ball in front of a halftone moon, drawn in tonight's real phase ({name}, {round(lit * 100)}% lit).</desc>
<style>
.kid{{animation:breathe 4.2s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%}}
@keyframes breathe{{50%{{transform:scale(1.006,1.014)}}}}
.blink{{opacity:0;animation:blink 7s steps(1) infinite 2.2s}}
@keyframes blink{{0%{{opacity:1}}2.2%{{opacity:0}}100%{{opacity:0}}}}
.tw{{transform-box:fill-box;transform-origin:center;animation:tw 2.8s ease-in-out infinite}}
.tw1{{animation-delay:1.4s}}
@keyframes tw{{0%,100%{{transform:scale(1) rotate(0)}}40%{{transform:scale(.35) rotate(45deg);opacity:.5}}60%{{transform:scale(1.15) rotate(90deg)}}}}
.moon{{animation:glow 9s ease-in-out infinite}}
@keyframes glow{{50%{{opacity:.82}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
<pattern id="ht" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><circle cx="3.5" cy="3.5" r="2.3" fill="{t["ink"]}"/></pattern>
<pattern id="ht2" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><circle cx="3.5" cy="3.5" r=".75" fill="{t["ink"]}"/></pattern>
<filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="11" stitchTiles="stitch"/>
<feColorMatrix values="0 0 0 0 {t["grain"][0]} 0 0 0 0 {t["grain"][0]} 0 0 0 0 {t["grain"][0]} 0 0 0 {t["grain"][1]} -{t["grain"][2]}"/>
</filter>
</defs>
<rect width="{W}" height="{H}" fill="{t["paper"]}"/>
<g class="moon"><circle cx="{mcx}" cy="{mcy}" r="{mr}" fill="url(#ht2)"/><path d="{lit_d}" fill="url(#ht)"/>
<circle cx="{mcx}" cy="{mcy}" r="{mr}" fill="none" stroke="{t["ink"]}" stroke-width="1.5" stroke-dasharray="2 5"/></g>
<path d="{wm["d"]}" transform="{word}" fill="{t["ink"]}"/>
<line x1="56" y1="416" x2="{W - 56}" y2="416" stroke="{t["ink"]}" stroke-width="3"/>
<g transform="translate({mx:.2f} {my:.2f}) scale({ms:.5f})" fill="{t["ink"]}">
<g class="kid"><g fill="{plate}">{part(m["silhouette"])}</g><g fill="{kid_ink}">{part(m["body"])}</g>
<g>{part(m["antenna_l"])}{sway(m["pivot_l"], 0)}</g>
<g>{part(m["antenna_r"])}{sway(m["pivot_r"], -1.1)}</g>
<g class="blink">{lids}</g>
{sparkles}</g></g>
<rect width="{W}" height="{H}" filter="url(#grain)"/>
</svg>
'''


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    art = json.load(open(os.path.join(HERE, "art.json")))
    now = (dt.datetime.fromisoformat(sys.argv[sys.argv.index("--at") + 1].replace("Z", "+00:00"))
           if "--at" in sys.argv else dt.datetime.now(dt.timezone.utc))
    for theme in THEMES:
        with open(os.path.join(out, f"poster-{theme}.svg"), "w") as f:
            f.write(poster(theme, art, now))
    age, lit, name = moon(now)
    print(f"{name}, {lit:.0%} lit, age {age:.1f} d")


if __name__ == "__main__":
    main()
