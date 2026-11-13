"""Reading of drawing 970027-S01-ST-1103 rev 04 sections D1 / E (ring to radial joint at r 12, Level 2) and the
idealisation planned for IDEA StatiCa (L2-R12-E1, v21). Dimensions mm. PIL only. py -3.11 draw_r12_reading.py"""
from PIL import Image, ImageDraw, ImageFont
W, H = 2300, 1560
im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
def F(s): 
    try: return ImageFont.truetype("arial.ttf", s)
    except Exception: return ImageFont.load_default()
f, fs, fb = F(19), F(16), F(26)
RH, RB, Rtw, Rtf = 259.6, 147.3, 7.2, 12.7
BH, BB, Btw, Btf = 467.2, 192.8, 11.4, 19.6
PT = 20; ztp = 428; zbp = ztp - 395; rows = [ztp - 105, ztp - 230, ztp - 330]
RING, RAD, PL, BR, ST, BO = (185, 195, 207), (227, 201, 160), (217, 83, 79), (91, 141, 239), (58, 163, 107), (240, 220, 0)
class V:
    def __init__(s, ox, oy, k): s.ox, s.oy, s.k = ox, oy, k
    def p(s, x, z): return (s.ox + x * s.k, s.oy - z * s.k)
    def rect(s, x, z, w, h, c, o="black"):
        a, b = s.p(x, z + h), s.p(x + w, z); d.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], fill=c, outline=o)
    def poly(s, pts, c): d.polygon([s.p(*q) for q in pts], fill=c, outline="black")
    def line(s, a, b, c="black", w=2): d.line([s.p(*a), s.p(*b)], fill=c, width=w)
    def circ(s, x, z, r, c): (cx, cy) = s.p(x, z); d.ellipse([cx - r * s.k, cy - r * s.k, cx + r * s.k, cy + r * s.k], fill=c, outline="black")
def note(xy, txt, to=None, col="black", font=f):
    d.multiline_text(xy, txt, fill=col, font=font, spacing=3)
    if to: d.line([xy, to], fill=col, width=2); d.ellipse([to[0] - 4, to[1] - 4, to[0] + 4, to[1] + 4], fill=col)
d.text((30, 18), "26016 L2-R12-E1 (v21): how I read drawing 970027-S01-ST-1103 rev 04, sections D1 and E, and what goes into IDEA (Wing to confirm)", fill="black", font=fb)
# ---- view 1 (D1): looking along the radial, ring runs left-right
v = V(700, 820, 1.0); L = 620
d.text((60, 70), "View 1 = section D1: looking along the radial; ring runs left-right", fill="black", font=f)
v.rect(-L, Rtf, 2 * L, RH - 2 * Rtf, (225, 230, 236)); v.rect(-L, RH - Rtf, 2 * L, Rtf, RING); v.rect(-L, 0, 2 * L, Rtf, RING)
for s in (-1, 1):
    x1, x2 = 155, 155 + 210 * 0.7071
    v.poly([(s * (Btw / 2 + PT), RH), (s * x2, RH), (s * x1, BH - Btf - PT), (s * (Btw / 2 + PT), BH - Btf - PT)], (190, 210, 250))
    v.line((s * x1, BH - Btf - PT), (s * x2, RH), BR, 9)
    v.rect(min(s * (Btw / 2 + PT), s * x1), BH - Btf - PT, abs(x1 - Btw / 2 - PT), PT, BR)
    v.rect(s * 315 - PT / 2, Rtf, PT, RH - 2 * Rtf, ST)
    v.rect(min(s * (Btw / 2 + PT), s * 315), Rtf + 10, abs(315 - Btw / 2 - PT), PT, ST)
    v.rect(Btw / 2 if s > 0 else -Btw / 2 - PT, zbp, PT, 395, PL)
v.rect(-BB / 2, BH - Btf, BB, Btf, RAD); v.rect(-BB / 2, 0, BB, Btf, RAD); v.rect(-Btw / 2, Btf, Btw, BH - 2 * Btf, RAD)
for z in rows: v.line((-65, z), (65, z), "black", 9); v.line((-65, z), (65, z), BO, 4)
v.line((-L, 0), (L, 0), (150, 150, 150), 1)
note((60, 880), "ring UB 254x146x43 (SLN 55 / 56), continuous", v.p(-480, 120))
note((60, 110), "radial UB 457x191x98 (SLN 73) ends at the ring;\nbottom flanges flush (read from D1 / E)", v.p(-40, BH - 8))
note((700, 160), "395x145x20 plates (2 Nos) each side of\nthe radial web, welded to the ring;\n6 x M24 10.9 through plate + web + plate", v.p(Btw / 2 + PT, 380))
note((880, 920), "bracket in the ring web plane: 20 plate under the radial\ntop flange (155 each side), 20 stiffener 210 long at 135 deg,\n10 web plate", v.p(230, 330))
note((1100, 600), "20 ring web stiffeners\nat +-315 (2 Nos)", v.p(315, 140))
note((60, 960), "20 plates 295 long, 10 above the\nring bottom flange (2 Nos)", v.p(-200, 30))
# ---- view 2 (E): looking along the ring, radial runs right (towards the centre)
u = V(1650, 820, 1.0); L2 = 520
d.text((1360, 70), "View 2 = section E: looking along the ring", fill="black", font=f)
u.poly([(-RB / 2, BH - Btf), (L2, BH - Btf), (L2, Btf), (RB / 2 + 5, Btf), (RB / 2 + 5, RH + 5), (-RB / 2, RH + 5)], RAD)
u.rect(-RB / 2, BH - Btf, L2 + RB / 2, Btf, RAD); u.rect(RB / 2 + 5, 0, L2 - RB / 2 - 5, Btf, RAD)
u.rect(-72.5, zbp, 145, 395, (236, 160, 158))
u.rect(-RB / 2, RH - Rtf, RB, Rtf, RING); u.rect(-RB / 2, 0, RB, Rtf, RING); u.rect(-Rtw / 2, Rtf, Rtw, RH - 2 * Rtf, RING)
for z in rows:
    for c in (-39, 39): u.circ(c, z, 13, BO)
u.line((-150, 0), (L2, 0), (150, 150, 150), 1)
note((1330, 110), "radial top flange + web tongue run over the ring\nto its outer flange tip; radial web and bottom flange\ncoped over the ring (RH + 5) back to the inner tip", u.p(-40, 400))
note((1890, 560), "bolt rows 105 / 125 / 100\n(98 to bottom), columns\n+-39 from the ring web", u.p(39, rows[1]))
note((1360, 880), "ring section; the lower 2 bolt rows sit inside the ring\ndepth: the drawing slots the ring web for the plates.\nIDEA: ring web kept whole, plates welded to it (open point 1)", u.p(-5, 90), col=(170, 0, 0))
d.multiline_text((30, 1110), "Welds: 10 mm fillets to flanges, 6 mm to webs (drawing note), 10 mm where shown. Plates S275 (as the other 26016 joints). Bolts M24 10.9, bearing.\n"
                 "Forces: v21 database, 43 ULS STR cases at the SLN 73 end node (r 12). Open points for Wing: (1) the radial web / ring web crossing (slot vs cope);\n"
                 "(2) the 205x70x20 stiffener and 185x70x20 plate at the ring flanges (E) are left out unless they carry load in your reading.", fill="black", font=fs, spacing=4)

# ---- insets: the two readings of the radial web at the ring (plan view at mid ring depth)
def inset(ox, oy, title, slotted):
    k = 0.9; q = V(ox, oy, k)
    d.text((ox - 210, oy - 230), title, fill="black", font=f)
    # plan: ring web runs left-right (x along ring), radial runs up (y = towards centre). use q.p(x, y) with y up
    q.rect(-240, -3.6, 480, 7.2, RING)                      # ring web
    q.rect(-240, -73.6, 480, 3, RING); q.rect(-240, 70.6, 480, 3, RING)   # ring flange tips (outline only)
    for s in (-1, 1): q.rect(s * 5.7 if s > 0 else -25.7, -72.5, 20, 145, PL)   # 395 plates (plan, 20 thick)
    if slotted:
        q.rect(-5.7, -73.6, 11.4, 147.2 + 130, RAD)          # radial web passes the ring web (slot in ring web or radial web)
    else:
        q.rect(-5.7, 73.6 + 5, 11.4, 125, RAD)               # radial web stops at the inner flange tip + 5
    for c in (-39, 39): q.line((-60, c), (60, c), "black", 5); q.line((-60, c), (60, c), BO, 2)
    q.rect(-240, -3.6, 480, 7.2, RING)
inset(1500, 1440, "(a) radial web passes the ring web (slot)\nlower bolts: plate + radial web + plate\n= planned IDEA model", True)
inset(1980, 1440, "(b) radial web coped over the ring\nlower bolts clamp the 2 plates only", False)
d.text((1290, 1528), "insets: plan at mid ring depth; grey = ring web, red = 395x145x20 plates, tan = radial web, yellow = M24 bolts", fill="black", font=fs)

im.save("L2-R12-E1_reading_v21.png"); print("ok")
