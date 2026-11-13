"""L2-R12-E1 as built v21 (corrected = variant 4): IDEA views + true plan view from the model geometry + Wing's three comments.
py -3.11 draw_r12_asbuilt2.py"""
import json, math, re
from PIL import Image, ImageDraw, ImageFont
R = r"C:\Sofistik workflow\idea-statica\v21\R12"; V = R + r"\var_V4s"
A, B, S = [Image.open(V + f).convert("RGB") for f in (r"\r12_under.png", r"\r12_top.png", r"\report\strain.png")]
S = S.resize((int(S.width * 0.62), int(S.height * 0.62)))
geo = json.load(open(V + r"\L2-R12-E1_000_geo.json"))
x14 = open(r"C:\Sofistik workflow\idea-statica\v14\xml_E1\L2-R12-E1_000.xml", "rb").read().decode("utf-16")
pts = {int(m[1]): (float(m[2]), float(m[3])) for m in re.finditer(r"<Point3D><Id>(\d+)</Id><Name>[^<]*</Name><X>([^<]*)</X><Y>([^<]*)</Y>", x14)}
W, H = 2300, 2350
im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
def F(s):
    try: return ImageFont.truetype("arial.ttf", s)
    except Exception: return ImageFont.load_default()
f, fb, fs = F(18), F(26), F(16)
d.text((20, 12), "26016 L2-R12-E1_000 (node 1485, r 12, 0 deg) on v21 forces - CORRECTED model (variant 4) after Wing's 3 comments", fill="black", font=fb)
im.paste(A, (0, 60)); im.paste(B, (A.width, 60))
d.text((20, 62), "view from below / outside", fill="black", font=f); d.text((A.width + 20, 62), "view from above", fill="black", font=f)
# comment markers
def mark(xy, n, col=(0, 140, 0)):
    x, y = xy; d.ellipse([x - 26, y - 26, x + 26, y + 26], outline=col, width=5); d.text((x + 28, y - 30), n, fill=col, font=fb)
mark((795, 60 + 460), "2")        # SLN 56 side 315 stiffener (view from below)
mark((A.width + 705, 60 + 545), "1")  # fin lower plate bottom weld (view from above)
mark((560, 60 + 250), "3")        # bracket now on the straight ring
# ---- plan view (true plan, mm, origin at the node, x = radial outward, y = tangent)
ox, oy, k = 1650, 1450, 0.62
d.text((1200, 1030), "TRUE PLAN from the model geometry (mm; node at the centre; radial runs to the left, towards the platform centre)", fill="black", font=f)
N0 = pts[1]; er = (pts[1][0] - pts[2][0], pts[1][1] - pts[2][1]); l = math.hypot(*er); er = (er[0] / l, er[1] / l); et = (-er[1], er[0])
def loc(p): dx, dy = p[0] - N0[0], p[1] - N0[1]; return (dx * er[0] + dy * er[1]) * 1000, (dx * et[0] + dy * et[1]) * 1000
def scr(s, t): return (ox + s * k, oy - t * k)
for pid in (4, 5):
    s, t = loc(pts[pid]); L = math.hypot(s, t); u = (s / L * 650, t / L * 650)
    d.line([scr(0, 0), scr(*u)], fill=(150, 150, 150), width=3)
    d.text(scr(u[0] + 15, u[1]), f"real ring chord SLN {55 if pid == 4 else 56} (10 deg off the tangent)", fill=(110, 110, 110), font=fs)
d.line([scr(0, -650), scr(0, 650)], fill=(0, 0, 0), width=2)
d.text(scr(25, -560), "IDEA ring centre line (straight, tangent)", fill="black", font=fs)
for s_ in (-73.65, 73.65): d.line([scr(s_, -650), scr(s_, 650)], fill=(120, 140, 200), width=1)
d.rectangle([scr(-700, 96.4), scr(73.6, -96.4)], outline=(200, 150, 80), width=2)
d.text(scr(-690, 120), "radial UB 457x191x98 flange", fill=(160, 110, 40), font=fs)
cols = {"fin": (217, 83, 79), "bracket": (91, 141, 239), "stiffener": (58, 163, 107), "inclined": (40, 90, 200), "top plate": (91, 141, 239)}
for g in geo:
    if "poly" not in g or g.get("neg"): continue
    pp = [loc(p) for p in g["poly"]]
    c = next((v for kk, v in cols.items() if kk in g["name"]), (120, 120, 120))
    if abs(g["normal"][2]) > 0.3:                       # horizontal or inclined plate: footprint
        d.polygon([scr(*p) for p in pp], outline=c, width=2)
    else:                                                # vertical / inclined plate: plan line with thickness
        xs = [p for p in pp]; a = min(xs, key=lambda p: (p[0], p[1])); b = max(xs, key=lambda p: (p[0], p[1]))
        if math.dist(a, b) < 1: continue
        d.line([scr(*a), scr(*b)], fill=c, width=max(2, int(g["th"] * 1000 * k)))
for g in geo:
    if "bolts" in g:
        for p in g["bolts"]:
            s, t = loc(p); d.ellipse([scr(s, t)[0] - 6, scr(s, t)[1] - 6, scr(s, t)[0] + 6, scr(s, t)[1] + 6], fill=(240, 210, 0), outline="black")
d.text(scr(-330, -260), "10 web + 20 inclined + 20 top plate (bracket)\nalong the straight ring, both sides", fill=(40, 90, 200), font=fs)
d.text(scr(330, -360), "20 stiffeners at +-315\n(full width, both faces)", fill=(58, 163, 107), font=fs)
d.text(scr(120, 60), "395x145x20 fin plates", fill=(217, 83, 79), font=fs)
# strain plot
im.paste(S, (0, 1040)); d.text((20, 1040), "IDEA plastic strain, corrected model: 3.0 % (LC 122) < 5 %", fill="black", font=f)
y = 1720
txt = ["Wing's comments and what was found / changed:",
       "1  'missing weld between end plate and bottom flange': TRUE. The lower 395x145x20 fin plates stopped 20 mm above the ring bottom flange",
       "   (gap left for the 20 mm plates that were not modelled) and were welded only to the ring web (a 4.2) and the top flange underside (a 7.0).",
       "   Now taken down to the bottom flange and welded to it (a 7.0) - yellow welds at the plate feet in the view from above.",
       "2  'missing stiffener': the SLN 56 side 315 stiffener WAS in the model (full width, both faces), but IDEA drew the ring as ONE straight line along",
       "   the SLN 55 chord, 20 deg off the SLN 56 chord, so that stiffener and the SLN 56 bracket sat up to ~110 mm off the IDEA ring (hidden in the view).",
       "3  'UB looks straight but the haunch is not': same cause. IDEA models a continuous member straight; my bracket followed the real chords (+-10 deg).",
       "   Fix: the ring is now modelled straight along the tangent at the node (bisector of the two chords) and every bracket / stiffener part sits",
       "   on it (plan above). Error: the real chords are 10 deg off the tangent; at the 315 stiffeners the real ring web is 55 mm inward of the model's.",
       "   Drawing D1 shows the bracket in elevation only; the plan (sheet set) shows straight ring chords between radials. A straight local model is the",
       "   usual CBFEM idealisation; the 10 deg kink is not modelled.",
       "",
       "Results (43 ULS cases): v0 = first model, v0s = first model on the straight ring, V4 = v0s + fin feet welded to the bottom flange, V5 = V4 with 20x295 plates",
       "   v0  6.6 % / welds 109.1 % / bolts 60.7 %     v0s 3.5 % / 101.4 % / 70.2 %     V4 3.0 % / 100.6 % / 69.8 %     V5 7.1 % / 99.2 % / 67.0 %",
       "   V4 max weld: 315 stiffener (SLN 55 side) to ring flange, a 7.0, 100.6 % LC 153; bracket top plates / inclined stiffeners 98-99.5 %. V4 is the corrected model."]
for t in txt: d.text((20, y), t, fill="black", font=fs); y += 24
im.save(R + r"\final\L2-R12-E1_as_built_v21.png"); print(im.size)
