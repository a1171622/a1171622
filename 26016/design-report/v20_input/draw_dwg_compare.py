"""External stair (group 62) from the v20 model geometry, coloured by how the model section compares with the latest
drawings 970027-S01-ST rev 04 (1301-1306): red = drawing smaller/different, green = same, grey = treads."""
import json, os, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__))
SL = json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']
DAT = open(os.path.join(H, "26016_check_v20.dat"), encoding="latin-1").read()
SNO = {int(m[1]): int(m[2]) for m in re.finditer(r"^SLN\s+(\d+) GRP 62 STYP .N. SNO (\d+)", DAT, re.M)}
F = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)
COL = {5: ((210, 30, 30), 6, "RHS 200x100x6 in model -> RHS 160x80x5 on drawings (stringers + landing edge beams)"),
       8: ((235, 140, 0), 6, "SHS 100x100x5 ring supports in model -> 80x80x6.3 stubs on 200x150x10 plates, M20 (drg 1304)"),
       9: ((30, 150, 60), 5, "SHS 80x80x6.3 legs / leg beams: same on drawings (80x80x6.3 RHS, M16 connections)"),
       7: ((170, 170, 170), 2, "treads (model 300x5 plate; drawings 300x50x30x4 lipped channel, 50x50x5 landing joists)")}
W, Hh = 3000, 1750
im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im)
def view(vdir, ox, oy, sc, ctr):
    v = np.array(vdir, float); v /= np.linalg.norm(v); r = np.cross(v, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, v)
    return lambda p: (ox + (np.array(p) - ctr) @ r * sc, oy - (np.array(p) - ctr) @ u * sc)
def draw(P, near, title, tx):
    d.text((tx, 150), title, fill=(0, 0, 0), font=F(30, True))
    for s in sorted(SL, key=lambda s: SNO.get(s['sln'], 0) == 7, reverse=True):
        if s['grp'] != 62 or np.linalg.norm(np.array(s['x1'][:2]) - near) > 5.5: continue
        c, w, _ = COL.get(SNO.get(s['sln']), ((120, 120, 120), 2, ""))
        d.line([P(s['x1']), P(s['x2'])], fill=c, width=w)
ctrR = np.array([12.9, 0.4, 2.2]); ctrL = np.array([9.6, -8.4, 2.2])
draw(view((-1, 0.35, -0.45), 760, 950, 120, ctrR), ctrR[:2], "Right arm (v20 model geometry)", 60)
draw(view((-0.55, -0.85, -0.45), 2250, 950, 120, ctrL), ctrL[:2], "Left arm (v20 model geometry)", 1560)
d.text((60, 30), "26016 external stair: v20 model sections vs latest drawings 970027-S01-ST rev 04 (sheets 1301-1306, 13.11.2026)", fill=(0, 0, 0), font=F(42, True))
d.text((60, 90), "My reading of the drawing text (the PDF graphics could not be rendered on this PC). Colour = how the model member compares.", fill=(60, 60, 60), font=F(25))
y = 1440
for k in (5, 8, 9, 7):
    c, w, t = COL[k]; d.line([(60, y + 14), (140, y + 14)], fill=c, width=8); d.text((160, y), t, fill=(0, 0, 0), font=F(25)); y += 40
d.text((60, y + 10), "Stringer-to-landing connection on drawings: 160x90x16 plate welded to the stringer, 2 x M16 8.8 = simple (pinned) connection -> consistent with the v20 My hinges.",
       fill=(0, 0, 0), font=F(25, True))
im.save(os.path.join(H, "v20_vs_drawings_external_stair.png"), dpi=(150, 150)); im.resize((1500, 875)).save(os.path.join(H, "dwg_preview.jpg"))
