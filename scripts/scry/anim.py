"""Render loop frames: python anim.py W H N outdir part nparts [json params]"""
import sys, os, json
import numpy as np
from scry import Scene
from common import lamp_tint, grade, grain, save, vignette
from PIL import Image, ImageDraw

W, H, N = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
outdir, part, nparts = sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
kw = json.loads(sys.argv[7]) if len(sys.argv) > 7 else {}
gain = kw.pop('gain', 1.85)
gamt = kw.pop('grain', 0.025)
os.makedirs(outdir, exist_ok=True)
sc = Scene(W, H, **kw)
g = grain(H, W, 3, gamt)  # static grain: the print's tooth, not flicker
e = np.maximum(vignette(H, W, 2.5, 0.5), sc.letter_mask())  # the floor fades in an oval; the name stays lit
ev = np.clip(0.30 + 0.70 * vignette(H, W, 4.0, 0.55), 0, 1)
m4 = Image.new('L', (W * 4, H * 4), 0)
ImageDraw.Draw(m4).rounded_rectangle((0, 0, W * 4 - 1, H * 4 - 1), radius=int(H * 4 * 0.03), fill=255)
alpha = m4.resize((W, H), Image.LANCZOS)
for k in range(part, N, nparts):
    I0 = sc.render(k / N) * gain
    for m in ('dark', 'plate'):
        if m == 'dark':   # dissolves into GitHub's dark page
            save(lamp_tint(grade(I0 * e, g, e), H, W, sc.p['light']), f'{outdir}/dark{k:03d}.png')
        else:             # a plate with crisp rounded corners for the light page
            im = Image.fromarray((lamp_tint(grade(I0 * ev, g), H, W, sc.p['light']) * 255 + 0.5).astype(np.uint8)).convert('RGBA')
            im.putalpha(alpha)
            im.save(f'{outdir}/plate{k:03d}.png')
    print(k, flush=True)
