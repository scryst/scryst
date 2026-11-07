"""scryst: six ways of seeing, one letter each.

s  smoke curling off an incense ember   (capnomancy)
c  a crescent moon with earthshine      (selenomancy)
r  a candle whose flame leans into the arm (lychnomancy)
y  a forked hazel divining rod          (rhabdomancy)
s  a bead of quicksilver                (catoptromancy, liquid mirror)
t  a quartz point with a twin crossing it (crystallomancy)

Writes scryst-light.svg and scryst-dark.svg into the folder given (banner/). Every animation period divides
12 s, so the whole banner loops seamlessly every 12 s.
"""
import math, os, random, sys

W, H = 1200, 400
BASE = 272
XH = 150
TOP = BASE - XH
X = dict(s1=196, c=338, r=494, y=624, s2=788, t=922)
VB = (146, 10, 900, 360)  # crop to the word so it fills the README column

PAL = {
    'dark': dict(
        page='#0d1117', mid='#151b27', grain=.06,
        smoke='#d9dee8', smoke_core=.32, ember='#ff7a2e',
        moon='#f3ead0', moon_shade='#b9ae90', earthshine='#9fb0d0', earth_op=.035, halo='#f6eccb', halo_op=.22,
        wax_l='#e7d7b8', wax_m='#fff4df', wax_d='#b89f74', glow='#ffae4a', glow_op=.30, glow_r=64, lit_op=.55, wax_edge='none', moon_rim='none',
        bark='#7d5232', bark_d='#4a2d18', bark_l='#b0835a', cut='#e9d3a8', leaf='#6f8a45',
        hg=['#2a303b', '#6d7684', '#c7cfd9', '#ffffff'], hg_warm='#ffcf8a',
        q_l='#e6f2fb', q_m='#a9c8e2', q_d='#5f86ad', q_edge='#ffffff', q_op=.88,
        shadow=None,
    ),
    'light': dict(
        page='#ffffff', mid='#ffffff', grain=.05,
        smoke='#5f6b82', smoke_core=.2, ember='#f05a14',
        moon='#e2e8ef', moon_shade='#8593a5', earthshine='#c6d0dc', earth_op=0, halo='#b8c6d8', halo_op=.18,
        wax_l='#e3d1ae', wax_m='#fbefd8', wax_d='#a88b5c', glow='#ffb347', glow_op=.14, glow_r=40, lit_op=.25, wax_edge='#c9b48c', moon_rim='#8c98a8',
        bark='#7a4c2b', bark_d='#432612', bark_l='#a87b52', cut='#e5cc9c', leaf='#6a8240',
        hg=['#1f2530', '#596272', '#b6bfca', '#ffffff'], hg_warm='#ffb860',
        q_l='#cfe3f3', q_m='#86acd0', q_d='#3f6890', q_edge='#2f5478', q_op=.95,
        shadow='#3a2f20',
    ),
}


def s_path(x, squash=0):
    """Lowercase s skeleton, drawn from the lower-left terminal to the upper-right one."""
    return (f"M{x+4},{BASE-30} C{x+14},{BASE+4} {x+94},{BASE+8} {x+96},{BASE-38} "
            f"C{x+98},{BASE-80+squash} {x+4},{BASE-70-squash} {x+6},{TOP+40} "
            f"C{x+8},{TOP-6} {x+86},{TOP-8} {x+94},{TOP+20}")


def smoke(p):
    x = X['s1']
    wisps = []
    rnd = random.Random(7)
    # strands flow along the s from the ember: each dash pattern moves one period per loop
    for i, (dx, dy, w, op, dash, dur) in enumerate([
        (0, 0, 13, .55, (90, 40), 6), (5, -4, 6, .6, (60, 50), 4), (-6, 5, 4, .5, (40, 70), 3),
        (3, 8, 2.5, .7, (120, 30), 6), (-3, -9, 2, .55, (30, 45), 4), (8, 3, 1.5, .6, (70, 25), 3)]):
        per = dash[0] + dash[1]
        wisps.append(
            f'<path class="wisp" style="--per:-{per}px;animation-duration:{dur}s" d="{s_path(x)}" '
            f'transform="translate({dx},{dy})" fill="none" stroke="{p["smoke"]}" stroke-opacity="{op}" '
            f'stroke-width="{w}" stroke-linecap="round" stroke-dasharray="{dash[0]} {dash[1]}"/>')
    core = f'<path d="{s_path(x)}" fill="none" stroke="{p["smoke"]}" stroke-opacity="{p["smoke_core"]*1.6:.2f}" stroke-width="18" stroke-linecap="round"/>'
    # plume leaving the top terminal and thinning into nothing
    plume = (f'<path class="plume" d="M{x+94},{TOP+20} C{x+104},{TOP-4} {x+84},{TOP-26} {x+100},{TOP-50} '
             f'C{x+112},{TOP-68} {x+96},{TOP-84} {x+108},{TOP-104}" fill="none" stroke="{p["smoke"]}" '
             f'stroke-width="4" stroke-linecap="round" mask="url(#plumefade)"/>')
    ember = (f'<line x1="{x+1}" y1="{BASE-24}" x2="{x-14}" y2="{BASE+36}" stroke="#6b4426" stroke-width="3.5" stroke-linecap="round"/>'
             f'<line x1="{x+1}" y1="{BASE-24}" x2="{x-3}" y2="{BASE-10}" stroke="#3b3b3b" stroke-width="3.6" stroke-linecap="round"/>'
             f'<circle class="ember" cx="{x+2}" cy="{BASE-27}" r="3.6" fill="{p["ember"]}"/>'
             f'<circle class="ember" cx="{x+2}" cy="{BASE-27}" r="9" fill="{p["ember"]}" opacity=".35" filter="url(#soft6)"/>')
    defs = f'''
<filter id="smokeA" x="-40%" y="-40%" width="180%" height="180%"><feTurbulence type="fractalNoise" baseFrequency="0.022 0.035" numOctaves="3" seed="4"/><feDisplacementMap in="SourceGraphic" scale="26"/><feGaussianBlur stdDeviation="1.6"/></filter>
<filter id="smokeB" x="-40%" y="-40%" width="180%" height="180%"><feTurbulence type="fractalNoise" baseFrequency="0.026 0.03" numOctaves="3" seed="11"/><feDisplacementMap in="SourceGraphic" scale="24"/><feGaussianBlur stdDeviation="1.6"/></filter>
<linearGradient id="pf" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<mask id="plumefade" maskUnits="userSpaceOnUse"><rect x="{x+60}" y="{TOP-110}" width="80" height="140" fill="url(#pf)"/></mask>'''
    body = (f'<g id="L-s1">{ember}'
            f'<g filter="url(#smokeA)">{core}</g><g class="boilA" filter="url(#smokeA)">{"".join(wisps)}{plume}</g>'
            f'<g class="boilB" filter="url(#smokeB)">{"".join(wisps)}{plume}</g></g>')
    return defs, body


def moon(p):
    x = X['c']
    cx, cy, R = x + 74, BASE - 75, 75
    kx, ky, kr = cx + 30, cy - 4, 58
    rnd = random.Random(3)
    craters = []
    for _ in range(26):
        a = rnd.uniform(0, 2 * math.pi); d = R * math.sqrt(rnd.random()) * .95
        px, py = cx + d * math.cos(a), cy + d * math.sin(a)
        rr = rnd.choice([2, 2.5, 3, 4, 5, 7])
        craters.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rr}" fill="{p["moon_shade"]}" opacity=".45"/>'
                       f'<path d="M{px-rr*.8:.1f},{py+rr*.5:.1f} a{rr},{rr} 0 0 0 {rr*1.6:.1f},0" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="1"/>')
    defs = f'''
<filter id="maria" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="4" seed="21"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.25"/><feComposite in2="SourceGraphic" operator="in" result="m"/><feFlood flood-color="{p["moon_shade"]}"/><feComposite in2="m" operator="in"/><feComposite in2="SourceGraphic" operator="over"/></filter>
<filter id="pock"><feTurbulence type="fractalNoise" baseFrequency="0.25" numOctaves="2" seed="5"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -1 1.1"/><feComposite in2="SourceGraphic" operator="in"/></filter>
<filter id="term"><feGaussianBlur stdDeviation="3.2"/></filter>
<mask id="crescent" maskUnits="userSpaceOnUse"><circle cx="{cx}" cy="{cy}" r="{R}" fill="#fff"/><circle cx="{kx}" cy="{ky}" r="{kr}" fill="#000" filter="url(#term)"/></mask>
<clipPath id="disc"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath>
<radialGradient id="limb" cx=".38" cy=".45" r=".62"><stop offset=".7" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".28"/></radialGradient>'''
    body = (f'<g id="L-c"><g mask="url(#crescent)"><circle cx="{cx}" cy="{cy}" r="{R}" fill="none"/></g><g class="halo" opacity="{p["halo_op"]}" filter="url(#soft18)"><rect x="{cx-R}" y="{cy-R}" width="{2*R}" height="{2*R}" fill="{p["halo"]}" mask="url(#crescent)"/></g>'
            
            f'<g mask="url(#crescent)"><g clip-path="url(#disc)"><rect x="{cx-R}" y="{cy-R}" width="{2*R}" height="{2*R}" fill="{p["moon"]}" filter="url(#maria)"/>'
            f'{"".join(craters)}<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#limb)"/><circle cx="{cx}" cy="{cy}" r="{R-.6}" fill="none" stroke="{p["moon_rim"]}" stroke-width="1.2"/></g></g></g>')
    return defs, body


def candle(p):
    """The stem is a slim taper; the flame leans out of the wick to make the shoulder and arm."""
    x = X['r']
    l, r_ = x + 4, x + 30
    top = TOP + 40
    drips = ''.join(
        f'<path d="M{l+a},{top} q{w/2},{-3} {w},0 v{h} a{w/2},{w/2} 0 0 1 {-w},0 z" fill="{p["wax_m"]}"/>'
        for a, w, h in [(1, 6, 24), (16, 7, 40)])
    wx, wy = x + 12, top - 7
    flame = (f'<g class="flame">'
             f'<path d="M{wx-5},{wy+3} C{wx-8},{TOP+14} {wx+10},{TOP-6} {wx+40},{TOP-6} C{wx+62},{TOP-6} {wx+76},{TOP+6} {wx+86},{TOP+24} '
             f'C{wx+70},{TOP+14} {wx+52},{TOP+12} {wx+36},{TOP+16} C{wx+20},{TOP+20} {wx+10},{wy-6} {wx+8},{wy+3} Z" fill="url(#flameO)"/>'
             f'<path d="M{wx-2},{wy+1} C{wx-4},{TOP+18} {wx+12},{TOP+3} {wx+34},{TOP+3} C{wx+48},{TOP+3} {wx+58},{TOP+9} {wx+64},{TOP+16} '
             f'C{wx+50},{TOP+14} {wx+34},{TOP+16} {wx+22},{TOP+22} C{wx+12},{TOP+27} {wx+6},{wy-4} {wx+4},{wy+1} Z" fill="url(#flameI)"/>'
             f'<ellipse cx="{wx+1}" cy="{wy}" rx="4" ry="3" fill="#7d9cff" opacity=".45"/></g>')
    defs = f'''
<linearGradient id="wax" x1="0" x2="1"><stop offset="0" stop-color="{p["wax_l"]}"/><stop offset=".45" stop-color="{p["wax_m"]}"/><stop offset="1" stop-color="{p["wax_d"]}"/></linearGradient>
<linearGradient id="waxlit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd38a" stop-opacity=".55"/><stop offset=".5" stop-color="#ffd38a" stop-opacity="0"/></linearGradient>
<linearGradient id="flameO" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#ffd45e"/><stop offset=".55" stop-color="#ff8a24"/><stop offset="1" stop-color="#ff5a10" stop-opacity=".15"/></linearGradient>
<linearGradient id="flameI" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#fffef5"/><stop offset=".7" stop-color="#fff0b0"/><stop offset="1" stop-color="#ffd76a" stop-opacity="0"/></linearGradient>'''
    body = (f'<g id="L-r"><circle class="glow" cx="{x+44}" cy="{TOP+14}" r="{p["glow_r"]}" fill="{p["glow"]}" opacity="{p["glow_op"]}" filter="url(#soft24)"/>'
            f'<path d="M{l},{top} Q{(l+r_)/2},{top+4} {r_},{top} L{r_+1},{BASE} Q{(l+r_)/2},{BASE+3} {l-1},{BASE} Z" fill="url(#wax)" stroke="{p["wax_edge"]}" stroke-width=".8"/>'
            f'<path d="M{l},{top} Q{(l+r_)/2},{top+4} {r_},{top} L{r_},{top+50} L{l},{top+50} Z" fill="url(#waxlit)"/>'
            f'{drips}<ellipse cx="{(l+r_)/2}" cy="{top+1}" rx="{(r_-l)/2}" ry="3.4" fill="{p["wax_m"]}"/>'
            f'<ellipse cx="{(l+r_)/2}" cy="{top+1}" rx="{(r_-l)/2-4}" ry="1.8" fill="{p["wax_l"]}"/>'
            f'<path d="M{wx},{top} q0,-4 1,-7" stroke="#1d1a17" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
            f'{flame}</g>')
    return defs, body


def rod(p):
    x = X['y']
    left = f"M{x+6},{TOP+2} C{x+18},{TOP+48} {x+38},{BASE-44} {x+54},{BASE-14}"
    right = f"M{x+106},{TOP-2} C{x+92},{TOP+70} {x+62},{BASE+10} {x+28},{BASE+72}"
    rnd = random.Random(12)
    lent = ''.join(f'<rect x="{x+rnd.uniform(10,100):.0f}" y="{rnd.uniform(TOP,BASE+60):.0f}" width="{rnd.uniform(2,4):.1f}" height="1.2" fill="{p["bark_l"]}" opacity=".8"/>' for _ in range(60))
    defs = f'''
<filter id="bark" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="0.5 0.03" numOctaves="3" seed="2"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.6 1.1"/><feComposite in2="SourceGraphic" operator="in" result="g"/><feFlood flood-color="{p["bark_d"]}"/><feComposite in2="g" operator="in"/><feComposite in2="SourceGraphic" operator="over"/></filter>
<clipPath id="rodclip"><path d="{left}" stroke-width="12"/></clipPath>
<linearGradient id="rodsh" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>'''
    sw = lambda d, w, c, extra='': f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="butt" {extra}/>'
    wood = (f'<g filter="url(#bark)">{sw(left, 14, p["bark"])}{sw(right, 17, p["bark"])}</g>'
            f'{sw(left, 4, p["bark_l"], "opacity=\".35\" transform=\"translate(-3,0)\"")}'
            f'{sw(right, 5, p["bark_l"], "opacity=\".35\" transform=\"translate(-4,0)\"")}'
            f'<g mask="url(#rodmask)">{lent}</g>'
            # the candle lights the side of the rod that faces it
            f'<g mask="url(#rodmask)" class="lit" opacity="{p["lit_op"]}">{sw(left, 4, p["glow"], "transform=\"translate(-5,0)\"")}{sw(right, 4, p["glow"], "transform=\"translate(-6,0)\"")}</g>'
            # cut ends show pale wood and a pith dot
            f'<ellipse cx="{x+6}" cy="{TOP+1}" rx="6.5" ry="3" fill="{p["cut"]}" transform="rotate(-15 {x+6} {TOP+1})"/><circle cx="{x+6}" cy="{TOP+1}" r="1.2" fill="{p["bark_d"]}"/>'
            f'<ellipse cx="{x+106}" cy="{TOP-2}" rx="8" ry="3.4" fill="{p["cut"]}" transform="rotate(12 {x+106} {TOP-2})"/><circle cx="{x+106}" cy="{TOP-2}" r="1.4" fill="{p["bark_d"]}"/>'
            # knot and a bud with one young leaf
            f'<ellipse cx="{x+84}" cy="{TOP+86}" rx="3.5" ry="5" fill="{p["bark_d"]}" transform="rotate(25 {x+84} {TOP+86})"/>'
            f'<path d="M{x+99},{TOP+42} q8,-11 21,-11 q-5,12 -21,11z" fill="{p["leaf"]}"/><path d="M{x+99},{TOP+42} q9,-6 19,-10" stroke="#fff" stroke-opacity=".35" fill="none"/>')
    defs += f'<mask id="rodmask" maskUnits="userSpaceOnUse">{sw(left, 13, "#fff")}{sw(right, 16, "#fff")}</mask>'
    drop = f'<g class="drop"><path d="M{x+28},{BASE+74} q-4,7 0,10 q4,-3 0,-10z" fill="#9cc7ee"/></g>'
    body = f'<g id="L-y"><g class="dip">{wood}{drop}</g></g>'
    return defs, body


def quicksilver(p):
    x = X['s2']
    d = s_path(x, squash=4)
    hg = p['hg']
    layers = ''.join(f'<path d="{d}" transform="translate({tx},{ty})" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" {o}/>'
                     for tx, ty, w, c, o in [(0, 0, 24, hg[0], ''), (0, -1.5, 18.5, hg[1], ''), (-1, -3.5, 9.5, hg[2], ''),
                                              (-1.5, -6, 3.5, hg[3], 'opacity=".9"'), (1.5, 6, 4, hg[2], 'opacity=".35"')])
    blobs = (f'<circle cx="{x+4}" cy="{BASE-30}" r="13.5" fill="{hg[0]}"/><circle cx="{x+1}" cy="{BASE-35}" r="6" fill="{hg[2]}"/><circle cx="{x}" cy="{BASE-37}" r="2.6" fill="#fff"/>'
             f'<circle cx="{x+94}" cy="{TOP+20}" r="12.5" fill="{hg[0]}"/><circle cx="{x+91}" cy="{TOP+15}" r="5.5" fill="{hg[2]}"/><circle cx="{x+90}" cy="{TOP+13}" r="2.4" fill="#fff"/>')
    bead = (f'<g class="bead"><circle cx="{x+118}" cy="{BASE-6}" r="7" fill="{hg[0]}"/><circle cx="{x+116}" cy="{BASE-8}" r="3.4" fill="{hg[2]}"/><circle cx="{x+115.5}" cy="{BASE-9}" r="1.3" fill="#fff"/></g>')
    warm = f'<path class="warm" d="{d}" transform="translate(-6,-2)" fill="none" stroke="{p["hg_warm"]}" stroke-width="3" stroke-linecap="round" stroke-dasharray="40 90 20 200" opacity=".7"/>'
    defs = '''
<filter id="liquid" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur in="SourceAlpha" stdDeviation="4" result="b"/><feSpecularLighting in="b" surfaceScale="6" specularConstant=".9" specularExponent="30" lighting-color="#fff" result="s"><fePointLight x="560" y="60" z="260"/></feSpecularLighting><feComposite in="s" in2="SourceAlpha" operator="in" result="s2"/><feComposite in="SourceGraphic" in2="s2" operator="arithmetic" k2="1" k3=".7"/></filter>'''
    body = f'<g id="L-s2"><g class="wobble" filter="url(#liquid)">{layers}{blobs}</g>{warm}</g>'
    return defs, body


def quartz(p):
    x = X['t']
    cx, hw = x + 30, 13
    sh, ap = TOP - 44, TOP - 82  # shoulder and apex of the point
    L, C1, C2, R = cx - hw, cx - 6, cx + 7, cx + hw
    stem = [
        (f'{L},{sh} {C1},{sh+5} {C1},{BASE} {L},{BASE-3}', p['q_l']),
        (f'{C1},{sh+5} {C2},{sh+5} {C2},{BASE} {C1},{BASE}', p['q_m']),
        (f'{C2},{sh+5} {R},{sh} {R},{BASE-3} {C2},{BASE}', p['q_d']),
        (f'{L},{sh} {cx-1},{ap} {C1},{sh+5}', p['q_l']),
        (f'{C1},{sh+5} {cx-1},{ap} {C2},{sh+5}', p['q_m']),
        (f'{C2},{sh+5} {cx-1},{ap} {R},{sh}', p['q_d']),
    ]
    # the twin grows through the stem, its own point to the right, a broken end to the left
    by, bh = TOP + 4, 19
    bx0, bx1, btip = cx - 30, cx + 36, cx + 56
    bar = [
        (f'{bx0},{by} {bx1},{by} {btip},{by+bh/2} {bx1},{by+7} {bx0+2},{by+7}', p['q_l']),
        (f'{bx0+2},{by+7} {bx1},{by+7} {btip},{by+bh/2} {bx1},{by+15} {bx0+1},{by+15}', p['q_m']),
        (f'{bx0+1},{by+15} {bx1},{by+15} {btip},{by+bh/2} {bx1},{by+bh} {bx0+3},{by+bh}', p['q_d']),
        (f'{bx0},{by} {bx0-3},{by+6} {bx0+2},{by+11} {bx0-2},{by+17} {bx0+3},{by+bh} {bx0+1},{by+15} {bx0+2},{by+7}', p['q_m']),
    ]
    # a small druse at the foot leaning right, the t's hook
    foot = [
        (f'{cx+4},{BASE} {cx+36},{BASE-20} {cx+44},{BASE-14} {cx+14},{BASE+2}', p['q_m']),
        (f'{cx+36},{BASE-20} {cx+56},{BASE-30} {cx+44},{BASE-14}', p['q_l']),
    ]
    polys = lambda ps, op: ''.join(f'<polygon points="{pt}" fill="{c}" fill-opacity="{op}" stroke="{p["q_edge"]}" stroke-opacity=".55" stroke-width=".8" stroke-linejoin="round"/>' for pt, c in ps)
    allpts = ' '.join(pt for pt, _ in stem + bar + foot)
    clip = ''.join(f'<polygon points="{pt}"/>' for pt, _ in stem + bar + foot)
    inner = (f'<path d="M{cx-3},{sh+20} L{cx-4},{BASE-12}" stroke="#fff" stroke-opacity=".7" stroke-width="1.4"/>'
             f'<path d="M{L+4},{sh+40} L{C1-2},{sh+38} M{L+5},{BASE-50} L{C1-1},{BASE-54}" stroke="#fff" stroke-opacity=".35" stroke-width="1"/>'
             f'<path d="M{C2+1},{sh+8} L{C2+1},{BASE-2}" stroke="url(#spectrum)" stroke-width="2.4" class="fire"/>')
    defs = f'''
<clipPath id="qclip">{clip}</clipPath>
<linearGradient id="spectrum" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff6b8b"/><stop offset=".25" stop-color="#ffd36b"/><stop offset=".5" stop-color="#7cf0a8"/><stop offset=".75" stop-color="#6bb8ff"/><stop offset="1" stop-color="#b48bff"/></linearGradient>
<linearGradient id="glint" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'''
    star = (f'<g class="spark"><path d="M{cx-1},{ap-14} L{cx+1},{ap-2} L{cx+13},{ap} L{cx+1},{ap+2} L{cx-1},{ap+14} L{cx-3},{ap+2} L{cx-15},{ap} L{cx-3},{ap-2} Z" fill="#fff"/></g>')
    body = (f'<g id="L-t">{polys(foot, p["q_op"])}{polys(stem, p["q_op"])}{polys(bar, p["q_op"])}{inner}'
            f'<g clip-path="url(#qclip)"><rect class="sweep" x="{x-20}" y="{TOP-30}" width="140" height="40" fill="url(#glint)" transform="rotate(-18 {cx} {TOP})"/></g>{star}</g>')
    return defs, body


CSS = '''
@keyframes flow { to { stroke-dashoffset: var(--per); } }
.wisp { animation: flow linear infinite; }
@keyframes plume { 0%,100% { transform: translate(0,0) skewX(0deg) } 50% { transform: translate(3px,-4px) skewX(-6deg) } }
.plume { transform-box: fill-box; transform-origin: 0% 100%; animation: plume 6s ease-in-out infinite; }
@keyframes boil { 0%,100% { opacity: 1 } 50% { opacity: .15 } }
@keyframes boil2 { 0%,100% { opacity: .15 } 50% { opacity: 1 } }
.boilA { animation: boil 6s ease-in-out infinite; }
.boilB { animation: boil2 6s ease-in-out infinite; }
@keyframes ember { 0%,100% { opacity: 1 } 40% { opacity: .55 } 70% { opacity: .9 } }
.ember { animation: ember 3s ease-in-out infinite; }
@keyframes halo { 0%,100% { opacity: var(--h0) } 50% { opacity: calc(var(--h0) * 1.6) } }
.halo { animation: halo 12s ease-in-out infinite; }
@keyframes flick {
  0%,100% { transform: scale(1,1) skewX(0deg) } 13% { transform: scale(1.04,.94) skewX(-3deg) }
  27% { transform: scale(.97,1.05) skewX(2deg) } 41% { transform: scale(1.06,.97) skewX(-1deg) }
  58% { transform: scale(.95,1.03) skewX(3deg) } 74% { transform: scale(1.03,.95) skewX(-2deg) } 88% { transform: scale(.99,1.02) }
}
.flame { transform-box: fill-box; transform-origin: 0% 60%; animation: flick 2s ease-in-out infinite; }
@keyframes glow { 0%,100% { opacity: var(--g0) } 23% { opacity: calc(var(--g0)*.8) } 47% { opacity: calc(var(--g0)*1.15) } 71% { opacity: calc(var(--g0)*.9) } }
.glow { animation: glow 2s ease-in-out infinite; }
@keyframes lit { 0%,100% { opacity: var(--l0) } 23% { opacity: calc(var(--l0)*.7) } 47% { opacity: calc(var(--l0)*1.2) } 71% { opacity: calc(var(--l0)*.85) } }
.lit { animation: lit 2s ease-in-out infinite; }
@keyframes dip { 0%,100% { transform: rotate(0deg) } 30% { transform: rotate(2.4deg) } 55% { transform: rotate(-1deg) } 80% { transform: rotate(1.4deg) } }
.dip { transform-box: view-box; transform-origin: 680px 118px; animation: dip 12s ease-in-out infinite; }
@keyframes drop { 0%,62% { transform: translateY(-8px) scale(.2); opacity: 0 } 74% { transform: translateY(0) scale(1); opacity: 1 } 82% { transform: translateY(0) scale(1.1,1); opacity: 1 } 92% { transform: translateY(22px) scale(.9,1.2); opacity: 0 } 100% { opacity: 0 } }
.drop { transform-box: fill-box; transform-origin: 50% 0%; animation: drop 12s ease-in infinite; }
@keyframes wob { 0%,100% { transform: scale(1,1) } 33% { transform: scale(1.02,.985) } 66% { transform: scale(.988,1.015) } }
.wobble { transform-box: fill-box; transform-origin: 50% 100%; animation: wob 4s ease-in-out infinite; }
@keyframes bead { 0%,100% { transform: translate(0,0) scale(1,1) } 20% { transform: translate(-1.5px,0) scale(1.08,.9) } 40% { transform: translate(1px,0) scale(.95,1.05) } 60% { transform: translate(0,0) } }
.bead { transform-box: fill-box; transform-origin: 50% 100%; animation: bead 4s ease-in-out infinite; }
@keyframes warm { 0%,100% { stroke-dashoffset: 0 } 50% { stroke-dashoffset: -36px } }
.warm { animation: warm 2s ease-in-out infinite; }
@keyframes sweep { 0%,55% { transform: translateY(260px) } 80%,100% { transform: translateY(-120px) } }
.sweep { animation: sweep 6s cubic-bezier(.4,0,.2,1) infinite; }
@keyframes spark { 0%,72%,100% { transform: scale(0) rotate(0deg); opacity: 0 } 80% { transform: scale(1) rotate(30deg); opacity: 1 } 90% { transform: scale(.3) rotate(60deg); opacity: 0 } }
.spark { transform-box: fill-box; transform-origin: 50% 50%; animation: spark 6s ease-out infinite; }
@keyframes fire { 0%,100% { opacity: .25 } 50% { opacity: .85 } }
.fire { animation: fire 4s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) { *, *::before { animation: none !important; } .boilB { opacity: .15; } .drop, .spark { opacity: 0; } }
'''


def build(scheme):
    p = PAL[scheme]
    parts = [f(p) for f in (smoke, moon, candle, rod, quicksilver, quartz)]
    defs = ''.join(d for d, _ in parts)
    body = ''.join(b for _, b in parts)
    shadow = ''
    if p['shadow']:
        defs += f'<filter id="lift" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="{p["shadow"]}" flood-opacity=".18"/></filter>'
        body = f'<g filter="url(#lift)">{body}</g>'
    common = f'''
<filter id="soft6" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="soft18" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="18"/></filter>
<filter id="soft24" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="24"/></filter>
<filter id="soft30" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="30"/></filter>
<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="8" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 {p["grain"]*12:.2f} 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>
<radialGradient id="vg" cx=".5" cy=".5" r=".5"><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient><mask id="vig" maskUnits="userSpaceOnUse"><rect x="{VB[0]}" y="{VB[1]}" width="{VB[2]}" height="{VB[3]}" fill="url(#vg)"/></mask>
<radialGradient id="bg" cx=".5" cy=".52" r=".5"><stop offset="0" stop-color="{p["mid"]}"/><stop offset=".92" stop-color="{p["page"]}"/></radialGradient>'''
    style = CSS.replace('var(--h0)', str(p['halo_op'])).replace('var(--g0)', str(p['glow_op'])).replace('var(--l0)', str(p['lit_op']))
    alt = 'scryst'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}" width="{VB[2]}" height="{VB[3]}" role="img" aria-label="{alt}">'
            f'<title>{alt}</title><style>{style}</style><defs>{common}{defs}</defs>'
            f'<rect x="{VB[0]}" y="{VB[1]}" width="{VB[2]}" height="{VB[3]}" fill="url(#bg)"/>'
            f'<rect x="{VB[0]}" y="{VB[1]}" width="{VB[2]}" height="{VB[3]}" fill="#808080" filter="url(#grain)" opacity="{p["grain"]}" mask="url(#vig)"/>'
            f'{body}</svg>')


if __name__ == '__main__':
    out = sys.argv[1]
    for scheme in ('light', 'dark'):
        open(os.path.join(out, f'scryst-{scheme}.svg'), 'w').write(build(scheme))
