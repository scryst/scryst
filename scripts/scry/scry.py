"""scryst: the floor of a black scrying bowl.
One light above the water; the water surface carries the name and refracts the light into caustics on
the floor. Each letter is the same water behaving differently:
  s swell, c chop, r rain, y current, s wind, t still.
render(W, H, phase) -> intensity field (photon density on the floor), phase in [0,1) loops seamlessly."""
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, rotate
from common import layout, fields, bloom

TAU = 2 * np.pi
P = dict(
    ridge_w=0.095,      # lens ridge half-width, x-height units
    focal=0.50,         # floor depth (refraction strength), x-height units
    floor_base=0.97,    # photon density subtracted as the dark floor (0..1 of the light pool)
    floor_keep=0.06,    # how much of the undisturbed floor light stays
    light=(0.40, 0.27, 0.36, 0.72),  # the one lamp: (x, y) as frame fractions, radii as fractions of W and H
    lamp_k=0.5,         # letters take this power of the lamp falloff (the open floor takes all of it)
    xh_frac=0.355, gap=0.26,          # x-height as a fraction of H, letter gap in x-heights
    taper=0.14,                       # stroke ends sink to flat water over this fraction of the stroke
    swell_amp=2.2, swell_w=0.9, swell_mod=0.45,           # s: one long slow wave along the stroke
    chop=0.22, chop_s=0.06, glint=0.10,                   # c: short facets, a caustic net inside the stroke
    rain_base=1.0, rain=0.10, rain_r=0.32,                # r: drops ring outwards
    ytaper=0.22, yfade=0.85,                              # y: streaks die out down the tail
    wind=0.17, wind_s=0.035, wind_an=6.0, wind_rot=95,    # s: ripples blown one way across the stroke
    tbar=1.1, ttaper=0.14,                                # t: still water
    near_amp=0.02,                                        # the faint drift shared by the whole bowl
    bg_amp=0.8, bg_gain=0.30, bg_scale=0.12, clear=0.40,  # the open water's own dim caustic web
)

class Scene:
    def __init__(self, W, H, pad=None, **kw):
        # the water is simulated on a canvas larger than the frame, so no light is lost or gained at
        # the frame's edge; render() crops back to W x H
        self.W0, self.H0 = W, H
        self.pad = pd = int(round(0.08 * H)) if pad is None else pad
        W, H = W + 2 * pd, H + 2 * pd
        self.W, self.H = W, H
        self.p = dict(P, **kw)
        p = self.p
        self.Ls = layout(W, H, xh_frac=p['xh_frac'] * self.H0 / H, base_frac=(0.635 * self.H0 + pd) / H, gap=p['gap'])
        self.xh = self.Ls[0]['xh']
        self.yy, self.xx = np.mgrid[0:H, 0:W].astype(float)
        self.F = [fields(W, H, L) for L in self.Ls]
        self.waves = {}
        self.drops = []
        L = self.Ls[2]
        # three drops, placed by hand on the r (x-height units from its origin): arm tip, shoulder, stem
        xh, x0, by = self.xh, L['x0'], L['base']
        for j, (u, v) in enumerate([(0.62, 0.93), (0.30, 0.86), (0.12, 0.30)]):
            self.drops.append((np.array([x0 + u * xh, by - v * xh]), j / 3, 1))

    def letter_mask(self, reach=0.35):
        """1 on the letters, falling to 0 a little way off them (frame coordinates)."""
        pd = self.pad
        d = np.min([F[0] for F in self.F], 0)[pd:pd + self.H0, pd:pd + self.W0]
        return np.exp(-(d / (self.xh * reach)) ** 2)

    def gnoise(self, scale, seed, t, aniso=None, rot=20):
        """Blurred-noise field looping on a circle in noise space: smooth, seamless, constant variance."""
        key = (scale, seed, aniso, rot)
        if key not in self.waves:
            r = np.random.default_rng(seed)
            fs = []
            for _ in range(4):
                z = r.standard_normal((self.H, self.W))
                if aniso is None:
                    z = gaussian_filter(z, scale, mode='wrap')
                else:
                    big = r.standard_normal((self.H + self.W, self.H + self.W))
                    big = gaussian_filter(big, (scale * aniso, scale), mode='wrap')
                    big = rotate(big, rot, reshape=False, order=1)
                    o = (big.shape[0] - self.H) // 2, (big.shape[1] - self.W) // 2
                    z = big[o[0]:o[0] + self.H, o[1]:o[1] + self.W]
                fs.append(z / z.std())
            self.waves[key] = fs
        A, B, C, D = self.waves[key]
        c1, s1, c2, s2 = np.cos(TAU * t), np.sin(TAU * t), np.cos(2 * TAU * t), np.sin(2 * TAU * t)
        return (A * c1 + B * s1) * 0.8 + (C * c2 + D * s2) * 0.6

    def surface(self, t):
        xh, xx, yy, p = self.xh, self.xx, self.yy, self.p
        h = np.zeros((self.H, self.W))
        for i, (L, (d, tan, par, sid)) in enumerate(zip(self.Ls, self.F)):
            w = xh * p['ridge_w']
            te = p['ytaper'] if i == 3 else p['ttaper'] if i == 5 else p['taper']
            taper = np.clip(par / te, 0, 1) * np.clip((1 - par) / te, 0, 1)
            taper = taper * taper * (3 - 2 * taper)
            if i == 0:
                w = w * p['swell_w']
            ridge = np.exp(-(d / w) ** 2) * taper
            if i == 0:    # swell: one long slow wave traveling along the stroke
                h += p['swell_amp'] * ridge * (1 + p['swell_mod'] * np.cos(TAU * (par * 2.5 - t)))
            elif i == 1:  # chop: the ridge broken by short isotropic waves
                h += ridge * (1 + p['chop'] * self.gnoise(xh * p['chop_s'], 5, t))
                if p['glint'] > 0:  # short choppy facets inside the stroke: glitter, not spurs
                    h += p['glint'] * np.exp(-(d / (w * 1.5)) ** 2) * taper * self.gnoise(xh * 0.016, 6, t)
            elif i == 2:  # rain: drops land on the stroke and ring outwards
                h += p['rain_base'] * ridge
                for (px, py), ph0, cyc in self.drops:
                    ph = (ph0 + t * cyc) % 1
                    rr = ph * xh * p['rain_r']
                    r = np.hypot(xx - px, yy - py)
                    h += p['rain'] * (1 - ph) ** 2.2 * np.cos(TAU * (r - rr) / (xh * 0.05)) \
                        * np.exp(-((r - rr) / (xh * 0.045)) ** 2) * np.exp(-(d / (xh * 0.45)) ** 2) * (1 - np.exp(-(d / (xh * 0.13)) ** 2))
            elif i == 3:  # current: streaks drawn out along the stroke, drifting with it
                u = xx * tan[..., 0] + yy * tan[..., 1]
                v = -xx * tan[..., 1] + yy * tan[..., 0]
                st = np.cos(TAU * v / (xh * 0.05) + 1.4 * np.sin(TAU * (u / (xh * 0.5) - t)))
                fade = np.where(sid == 1, np.clip((p['yfade'] - par) / 0.25, 0, 1), 1.0)  # streaks die out down the tail
                h += ridge * (1 + 0.13 * st * fade)
            elif i == 4:  # wind: cat's-paw ripples all lying one way, running downwind
                h += ridge * (1 + p['wind'] * self.gnoise(xh * p['wind_s'], 8, t, aniso=p['wind_an'], rot=p['wind_rot']))
            else:         # still: the water settles; only the faint drift shared by the whole bowl moves it
                h += ridge * np.where(sid == 1, p['tbar'], 1.0)
        h += p['near_amp'] * self.gnoise(xh * 0.06, 98, t)
        return h

    def photons(self, h, ss=5):
        W, H, xh, p = self.W, self.H, self.xh, self.p
        gy, gx = np.gradient(gaussian_filter(h, 0.7 * xh / 126))
        f = xh * p['focal'] * (xh / 126)  # focus is resolution-independent: tuned at x-height 126 px
        if not hasattr(self, '_samp'):
            sy, sx = np.mgrid[0:H * ss, 0:W * ss] / ss
            jr = np.random.default_rng(1)
            self._samp = (sy.ravel() + jr.uniform(0, 1 / ss, sy.size), sx.ravel() + jr.uniform(0, 1 / ss, sx.size))
        sy, sx = self._samp
        dx = map_coordinates(gx, [sy, sx], order=1, mode='nearest') * f
        dy = map_coordinates(gy, [sy, sx], order=1, mode='nearest') * f
        I, _, _ = np.histogram2d(sy + dy, sx + dx, bins=[H, W], range=[[0, H], [0, W]])
        return gaussian_filter(I / (ss * ss), 0.55 * xh / 126)

    def render(self, t):
        W, H, xh, p = self.W, self.H, self.xh, self.p
        lx, ly, rx, ry = p['light']
        yy, xx = self.yy, self.xx
        pd, W0, H0 = self.pad, self.W0, self.H0
        lf = 1.0 / (1.0 + ((xx - pd - lx * W0) / (rx * W0)) ** 2 + ((yy - pd - ly * H0) / (ry * H0)) ** 2) ** 1.5
        ll = lf ** p['lamp_k']  # the letters take less of the lamp's falloff than the open floor
        I = self.photons(self.surface(t)) * ll
        I = np.clip(I - p['floor_base'] * ll, 0, None) + p['floor_keep'] * I
        if p['bg_amp'] > 0:
            # the open water around the name: its own caustic web, dimmer, and drawn away from the
            # letters (their lenses gather the light around them, leaving a dark clearing)
            B = self.photons(p['bg_amp'] * self.gnoise(xh * p['bg_scale'], 99, t)) * lf
            B = gaussian_filter(np.clip(B - p['floor_base'] * lf, 0, None), 0.8)
            if not hasattr(self, '_clear'):
                dmin = np.min([F[0] for F in self.F], 0)
                self._clear = 1 - np.exp(-(dmin / (xh * p['clear'])) ** 2)
            I = I + p['bg_gain'] * B * self._clear
        I = bloom(I, 1.6, 18, 0.22, 0.16)
        return I[pd:pd + H0, pd:pd + W0]
