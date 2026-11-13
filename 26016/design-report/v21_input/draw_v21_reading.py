"""v21 reading picture: members whose section changed (from the v21 .dat and the model geometry), coloured by new section.
Left: whole model 3D with L2 radials UB 457x191x98 (blue) and both stairs; right: close-ups of the external stair and internal stair."""
import json, os, re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__))
SL = json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']
D21 = open(os.path.join(H, "26016_check_v21.dat"), encoding="cp1252").read()
D20 = open(r"C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.dat", encoding="cp1252").read()
sno = lambda t: {int(m[1]): (int(m[2]), int(m[3])) for m in re.finditer(r"^SLN\s+(\d+) GRP (\d+) STYP .N. SNO (\d+)", t, re.M)}
N21, N20 = sno(D21), sno(D20)
F = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)
def style(sln):
    g, s = N21.get(sln, (0, 0)); o = N20.get(sln, (0, 0))[1]
    if s == 4: return (30, 80, 220), 5            # L2 radials, section 4 now UB 457x191x98
    if s == 10: return (220, 30, 30), 5            # new RHS 160x80x5
    if s == 9 and o == 8: return (240, 140, 0), 6  # ext stair ring supports SHS 100 -> 80x80x6.3
    if s == 5 and g == 60: return (130, 60, 160), 4  # internal stair landing beams kept RHS 200x100x6
    return (200, 200, 200), 1
W, Hh = 3200, 1900
im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im)
def view(vdir, ox, oy, sc, ctr):
    v = np.array(vdir, float); v /= np.linalg.norm(v); r = np.cross(v, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, v)
    return lambda p: (ox + (np.array(p) - ctr) @ r * sc, oy - (np.array(p) - ctr) @ u * sc)
def draw(P, filt, labels=()):
    order = sorted(SL, key=lambda s: style(s['sln'])[1])
    for s in order:
        if not filt(s): continue
        c, w = style(s['sln']); d.line([P(s['x1']), P(s['x2'])], fill=c, width=w)
    for sln, txt in labels:
        s = next(x for x in SL if x['sln'] == sln); m = P((np.array(s['x1']) + np.array(s['x2'])) / 2)
        d.text((m[0] + 8, m[1] - 28), txt, fill=style(sln)[0], font=F(22, True))
P1 = view((1, 1.4, -0.8), 820, 1080, 52, np.array([0, 0, 5.0]))
draw(P1, lambda s: True, [(79, "79"), (90, "90"), (136, "136"), (137, "137"), (461, "461"), (472, "472"), (489, "489"), (490, "490")])
d.text((60, 170), "Whole model (v21 geometry = v20)", fill=(0, 0, 0), font=F(30, True))
near = lambda c, r: (lambda s: math.dist(s['x1'][:2], c) < r)
P2 = view((-1, 0.35, -0.45), 2450, 900, 70, np.array([11.5, -4.2, 2.2]))
draw(P2, lambda s: s['grp'] == 62 or (near((12.5, -4.0), 6)(s) and s['x1'][2] < 4.5 and s['grp'] in (15,)),
     [(701, "701"), (702, "702"), (713, "713"), (714, "714"), (746, "746"), (747, "747"), (758, "758"), (759, "759"), (724, "724"), (769, "769")])
d.text((1720, 170), "External stair (group 62), from outside", fill=(0, 0, 0), font=F(30, True))
d.text((60, 30), "26016 v21 - members changed to drawings 970027-S01-ST (issue 13.11.2026), coloured by NEW section", fill=(0, 0, 0), font=F(44, True))
leg = [((30, 80, 220), "UB 457x191x98: 18 Level 2 radials (section 4, was UB 457x191x89; drg 1101/1102)"),
       ((220, 30, 30), "RHS 160x80x5 (new section 10, was RHS 200x100x6): external stair stringers 701 702 713 714 746 747 758 759, seats 711 712 756 757,"),
       (None, "     landing edge / middle beams 703-706 715-721 748-751 760-766; internal stair stringers 79 90 136 137 461 472 489 490 (drg 1201/1302/1303)"),
       ((240, 140, 0), "SHS 80x80x6.3 (section 9, was SHS 100x100x5): external stair landing supports on the L1 ring 724 725 769 770 (drg 1304), Z-only as before"),
       ((130, 60, 160), "kept RHS 200x100x6: internal stair landing beams and short posts at +6.04 (only the stringers change per the brief)"),
       ((200, 200, 200), "unchanged")]
y = 1660
for c, t in leg:
    if c: d.line([(60, y + 14), (130, y + 14)], fill=c, width=8)
    d.text((150, y), t, fill=(0, 0, 0), font=F(24)); y += 36
im.save(os.path.join(H, "v21_changed_members_reading.png"), dpi=(150, 150)); im.resize((1600, 950)).save(os.path.join(H, "v21_preview.jpg"))

