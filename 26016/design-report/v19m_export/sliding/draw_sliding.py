"""Plan sketch from the v19m model geometry: how the enclosure cladding wind is applied now (qp x 3 m on every windward
column, wind -Y) and the refined reading (closed 17 m enclosure, cf on the projected width), plus the FoS table."""
import json, math, csv, os
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__))
S = {s['sln']: s for s in json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']}
R = list(csv.DictReader(open(os.path.join(H, "sliding_refine.csv"))))
W, Hh = 2800, 1500
im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im)
def F(s): return ImageFont.truetype("arial.ttf", s)
def F_b(s): return ImageFont.truetype("arialbd.ttf", s)
cx, cy, sc = 620, 760, 40                           # plan centre, px per m
P = lambda x, y: (cx + x * sc, cy - y * sc)
# rings for orientation
for r, col in ((12, (200, 200, 200)), (8.5, (150, 150, 150)), (3, (170, 170, 170))):
    d.ellipse([P(-r, r), P(r, -r)], outline=col, width=2)
d.text(P(9.0, -10.3), "r 12 ring (deck edge)", fill=(120, 120, 120), font=F(22))
# ground columns r 8.5 (group 13 below L1) and core columns r 3
clad_g = [38, 39, 40, 41, 42, 43, 44, 45, 46, 47]
for a in range(0, 360, 20):
    x, y = 8.5 * math.cos(math.radians(a)), 8.5 * math.sin(math.radians(a))
    d.rectangle([P(x - 0.15, y + 0.15), P(x + 0.15, y - 0.15)], fill=(60, 60, 60))
for n in clad_g + [410, 423, 420]:
    x, y = S[n]['x1'][:2]
    th = math.atan2(y, x); tx, ty = -math.sin(th), math.cos(th)      # tangent
    d.line([P(x - 1.5 * tx, y - 1.5 * ty), P(x + 1.5 * tx, y + 1.5 * ty)], fill=(220, 30, 30), width=9)
    d.line([P(x, y + 1.6), P(x, y + 0.4)], fill=(220, 30, 30), width=3)          # load arrow -Y
    d.polygon([P(x - 0.25, y + 0.6), P(x + 0.25, y + 0.6), P(x, y + 0.25)], fill=(220, 30, 30))
    d.text(P(x - 0.6, y + 2.6), f"{n}", fill=(220, 30, 30), font=F(18))
# projected width of the enclosure
y0 = -11.2
d.line([P(-8.5, y0), P(8.5, y0)], fill=(20, 90, 200), width=5)
for x in (-8.5, 8.5): d.line([P(x, y0 - 0.5), P(x, y0 + 0.5)], fill=(20, 90, 200), width=5); d.line([P(x, y0), P(x, 0)], fill=(20, 90, 200), width=1)
d.text(P(-5.3, y0 - 0.5), "projected width 17.0 m (refined: cf x 17.0 m x 4.05 m)", fill=(20, 90, 200), font=F(24))
# wind arrow
d.line([P(-13.5, 14.0), P(-13.5, 10.0)], fill=(0, 0, 0), width=8); d.polygon([P(-14.2, 10.6), P(-12.8, 10.6), P(-13.5, 9.4)], fill=(0, 0, 0))
d.text(P(-15.0, 15.2), "wind -Y (LC 73)", fill=(0, 0, 0), font=F_b(26))
d.text((30, 20), "26016 v19m - overall sliding: how the enclosure cladding wind is applied (plan, ground storey)", fill=(0, 0, 0), font=F_b(34))
d.text((30, 70), "Red: modelled now = qp x 3 m on each windward column, cf 1.0, in the wind direction (10 ground columns r 8.5 + 3 core columns r 3, SLN shown)",
       fill=(220, 30, 30), font=F(24))
d.text((30, 102), "= 30 m + 9 m of loaded width on an enclosure that is 17 m + 6 m wide across the wind: about 1.7 x the projected area, before any cf.",
       fill=(220, 30, 30), font=F(24))
# right panel: table
x0, yt = 1290, 230
d.text((x0, yt - 60), "Sliding FoS = 0.40 x (DL - wind uplift) / H     (unfactored DL + WL)", fill=(0, 0, 0), font=F_b(26))
hdr = ["wind", "H now", "FoS now", "A: clad cf1.0", "A+B", "A(cf0.8)+B", "A+B+C"]
cw = [90, 110, 120, 170, 110, 160, 120]
xx = x0
for h, w in zip(hdr, cw): d.text((xx, yt), h, fill=(0, 0, 0), font=F_b(22)); xx += w
for i, r in enumerate(R):
    y = yt + 40 + 38 * i; xx = x0
    vals = [r['direction'], r['H'], *[f"{float(r[k]):.2f}" for k in ('FoS_model', 'FoS_clad_cf10', 'FoS_drag_both_cf10', 'FoS_drag_both_cf08', 'FoS_drag_cf10_roof05')]]
    for v, w in zip(vals, cw):
        col = (200, 0, 0) if xx == x0 + 200 and float(v) < 1.5 else (0, 0, 0)
        d.text((xx, y), v, fill=col, font=F(22)); xx += w
notes = ["DL = 1920.1 kN (LC 1-4).  Wind uplift 931-997 kN: roof 331 kN (cf 1.0) + L1/L2 decks 625 kN (cf 1.0, deck rule) + stairs.",
         "A  cladding: closed 17 m enclosure (ground) + 6 m core, cf 1.0 on projected width (profiled cladding;",
         "    EN 1991-1-4 7.9 circular cylinder, Re about 4e7, psi_lambda 1.0 kept): 120.8 -> 71.1 kN.  cf 0.8 if smooth: 56.9 kN.",
         "B  rakers / struts: cross-flow principle, force from the wind component normal to each inclined member",
         "    (q sin^2 theta), cf 1.45 kept: 60.1 -> 39.7 kN.  Not explicit in EN 1991-1-4: engineer's judgement.",
         "C  roof uplift cf 1.0 -> 0.5 (EN Table 7.6, alpha 0, phi 0, open below roof): uplift -165.5 kN (not a drag change).",
         "Unchanged: deck edges + balustrade 79 kN, stairs 55-58 kN, deck uplift (cf 1.0) 625 kN.",
         "DL + 0.7 LL + 0.5 WL and DL + LL + 0.5 WL: FoS 11 or more (no change needed).",
         "Target FoS 1.5 assumed (to be confirmed by Wing)."]
for i, t in enumerate(notes): d.text((x0, yt + 240 + 34 * i), t, fill=(40, 40, 40), font=F(21))
# small bar chart of the minimum FoS
labels = [("now", min(float(r['FoS_model']) for r in R)), ("A", min(float(r['FoS_clad_cf10']) for r in R)),
          ("A+B", min(float(r['FoS_drag_both_cf10']) for r in R)), ("A(0.8)+B", min(float(r['FoS_drag_both_cf08']) for r in R)),
          ("A+B+C", min(float(r['FoS_drag_cf10_roof05']) for r in R))]
bx, by, bh = x0 + 40, 1440, 360
for i, (lab, v) in enumerate(labels):
    x = bx + i * 190; top = by - v / 2.0 * bh
    d.rectangle([x, top, x + 120, by], fill=(220, 30, 30) if v < 1.5 else (40, 150, 70))
    d.text((x + 20, top - 32), f"{v:.2f}", fill=(0, 0, 0), font=F_b(24)); d.text((x + 10, by + 6), lab, fill=(0, 0, 0), font=F(20))
yl = by - 1.5 / 2.0 * bh
d.line([bx - 20, yl, bx + 5 * 190, yl], fill=(0, 0, 0), width=2); d.text((bx + 5 * 190 + 10, yl - 12), "FoS 1.5", fill=(0, 0, 0), font=F(20))
d.text((bx - 20, by - bh - 40), "minimum FoS over the 4 wind directions", fill=(0, 0, 0), font=F_b(22))
im.save(os.path.join(H, "sliding_wind_refine.png"), dpi=(150, 150))

