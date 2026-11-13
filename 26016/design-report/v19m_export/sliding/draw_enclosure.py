"""Picture of the enclosure assumption in 26016 v19m, drawn from the model geometry (slns_v19.json):
left 3D view with the clad ground drum (r 8.5, z 0-4.05) and the clad core (r 3, L1-L2), everything else open;
right: plan of the wind load as modelled (3 m strip per windward column, cf 1.0) and as proposed (cylinder, projected width)."""
import json, math, os
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__))
SL = json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']
F = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)
W, Hh = 3000, 1700
im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im, "RGBA")
# ---------- left: 3D view, wind -Y comes from +Y (back right) ----------
ox, oy, s = 820, 1250, 44
def P3(x, y, z):
    u = (x * 0.87 - y * 0.50); v = (x * 0.25 + y * 0.43) + z * 1.0
    return (ox + u * s, oy - v * s)
GREY = (175, 175, 175)
for l in SL:
    a, b = l['x1'], l['x2']
    if max(abs(a[0]), abs(b[0]), abs(a[1]), abs(b[1])) > 13.5: continue        # skip external stair for clarity
    d.line([P3(*a), P3(*b)], fill=GREY, width=2)
def ring_pts(r, z, n=72): return [P3(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z) for k in range(n + 1)]
# clad ground drum r 8.5 z 0..4.05 : draw as 18 facets, shaded
def facets(r, z0, z1, col):
    for k in range(18):
        a0, a1 = math.radians(20 * k), math.radians(20 * (k + 1))
        p = [P3(r * math.cos(a0), r * math.sin(a0), z0), P3(r * math.cos(a1), r * math.sin(a1), z0),
             P3(r * math.cos(a1), r * math.sin(a1), z1), P3(r * math.cos(a0), r * math.sin(a0), z1)]
        d.polygon(p, fill=col, outline=(col[0], col[1], col[2], 255))
facets(8.5, 0, 4.05, (70, 130, 220, 70))
facets(3.0, 4.05, 8.05, (240, 150, 40, 90))
for z, lab in ((4.05, "Level 1  +4.05"), (8.05, "Level 2  +8.05"), (12.06, "Roof  +12.06")):
    d.line(ring_pts(12.0, z), fill=(90, 90, 90), width=3)
    d.text(P3(12.6, -1.5, z), lab, fill=(60, 60, 60), font=F(26, True))
d.text((60, 140), "Enclosure assumed in the model (v19m)", fill=(0, 0, 0), font=F(38, True))
d.rectangle([60, 200, 100, 230], fill=(70, 130, 220, 110)); d.text((115, 200), "ground storey 0-4.05 m: CLAD all round, 18-sided drum, r 8.5 m (17 m across), 3 m strip per column",
                                                                   fill=(20, 60, 150), font=F(24))
d.rectangle([60, 245, 100, 275], fill=(240, 150, 40, 140)); d.text((115, 245), "core r 3 m, Level 1 to Level 2 only: CLAD (6 m across)", fill=(170, 90, 0), font=F(24))
d.text((60, 290), "everything else OPEN: L1-L2 and L2-roof outside the core (open balustrade only), roof = canopy", fill=(80, 80, 80), font=F(24))
d.text(P3(-3, -12, 2.0), "OPEN under L1 deck\noutside the drum (r 8.5-12)", fill=(80, 80, 80), font=F(22))
d.text(P3(-16, 1, 10.0), "OPEN storey\n(L2 to roof)", fill=(80, 80, 80), font=F(22))
d.text(P3(-16, 1, 6.0), "OPEN storey\n(L1 to L2,\noutside core)", fill=(80, 80, 80), font=F(22))
# wind arrow from +Y
for dz in (1.0, 3.0):
    a, b = P3(0, 19, dz), P3(0, 14, dz); d.line([a, b], fill=(0, 0, 0), width=7)
    d.polygon([b, (b[0] - 14, b[1] - 18), (b[0] + 14, b[1] - 4)], fill=(0, 0, 0))
d.text(P3(0, 19.5, 4.4), "wind -Y (from +Y)", fill=(0, 0, 0), font=F(28, True))
# ---------- right: plans ----------
def plan(cx, cy, sc, title, proposed):
    Pp = lambda x, y: (cx + x * sc, cy - y * sc)
    d.text((cx - 330, cy - 15.2 * sc), title, fill=(0, 0, 0), font=F(30, True))
    d.ellipse([Pp(-12, 12), Pp(12, -12)], outline=(200, 200, 200), width=2)
    d.ellipse([Pp(-3, 3), Pp(3, -3)], outline=(240, 150, 40), width=4)
    pts = [Pp(8.5 * math.cos(math.radians(a)), 8.5 * math.sin(math.radians(a))) for a in range(0, 361, 20)]
    d.line(pts, fill=(70, 130, 220), width=5)
    for a in range(0, 360, 20):
        x, y = 8.5 * math.cos(math.radians(a)), 8.5 * math.sin(math.radians(a))
        d.rectangle([Pp(x - .2, y + .2), Pp(x + .2, y - .2)], fill=(40, 40, 40))
        if not proposed and y > -0.01:          # windward half: 3 m strip, full qp in the wind direction
            th = math.atan2(y, x); tx, ty = -math.sin(th), math.cos(th)
            d.line([Pp(x - 1.5 * tx, y - 1.5 * ty), Pp(x + 1.5 * tx, y + 1.5 * ty)], fill=(220, 30, 30), width=11)
            d.line([Pp(x, y + 2.2), Pp(x, y + 0.5)], fill=(220, 30, 30), width=4)
            d.polygon([Pp(x - .35, y + .9), Pp(x + .35, y + .9), Pp(x, y + .35)], fill=(220, 30, 30))
    if not proposed:
        for a in (75, 105, 135, 165):           # core columns (approx. positions, 3 windward)
            pass
        d.text((cx - 330, cy + 12.6 * sc), "qp x 3 m x 4.05 m on EACH windward column, cf 1.0, in the wind direction\n"
                                           "even where the cladding is almost parallel to the wind\n"
                                           "= 30 m loaded width on a 17 m drum (+ 9 m on 6 m core)  ->  121 kN",
               fill=(200, 20, 20), font=F(23))
    else:
        y0 = 11.0
        for x in (-8.5, 8.5): d.line([Pp(x, -y0), Pp(x, y0)], fill=(20, 90, 200), width=2)
        for yy in (y0 + 0.3, y0 + 1.3, y0 + 2.3):
            for xx in (-7, -4, -1, 2, 5, 7.5):
                d.line([Pp(xx, yy + 1.0), Pp(xx, yy)], fill=(20, 90, 200), width=3)
        d.line([Pp(-8.5, -y0), Pp(8.5, -y0)], fill=(20, 90, 200), width=5)
        d.text(Pp(-4.5, -y0 + 0.3), "projected width 17 m", fill=(20, 90, 200), font=F(24, True))
        d.text((cx - 330, cy + 12.6 * sc), "closed cylinder (EN 1991-1-4 7.9): qp x cf x 17 m x 4.05 m\n"
                                           "cf 1.0 profiled / 0.8 smooth cladding (+ core 6 m x 4.0 m)\n"
                                           "->  71 kN (cf 1.0)  /  57 kN (cf 0.8)",
               fill=(20, 70, 170), font=F(23))
    a, b = Pp(13.5, 9), Pp(13.5, 6); d.line([a, b], fill=(0, 0, 0), width=6)
    d.polygon([b, (b[0] - 10, b[1] - 16), (b[0] + 10, b[1] - 16)], fill=(0, 0, 0)); d.text(Pp(12.2, 10.6), "wind", fill=(0, 0, 0), font=F(22))
plan(2150, 560, 21, "Plan, ground storey - wind load AS MODELLED", False)
plan(2150, 1250, 21, "Plan, ground storey - PROPOSED", True)
d.text((60, 30), "26016 v19m - ground storey enclosure and core: what the model assumes, and how the wind is put on them", fill=(0, 0, 0), font=F(44, True))
d.text((60, 1610), "To confirm (Wing): is the ground storey really closed all round?  Is the core clad L1-L2 only?  Cladding profiled or smooth (cf 1.0 or 0.8)?",
       fill=(0, 0, 0), font=F(28, True))
im.save(os.path.join(H, "enclosure_assumption.png"), dpi=(150, 150))
im.resize((1500, 850)).save(os.path.join(H, "enclosure_preview.jpg"))

