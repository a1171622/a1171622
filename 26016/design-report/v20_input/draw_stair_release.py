"""v20 reading of Wing's sketch: external stair (group 62) from the model geometry, the 16 released stringer ends
(My, FIXA/FIXE 'MY') circled in orange with SLN number. Two views (both arms)."""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
H = os.path.dirname(os.path.abspath(__file__))
SL = json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']
G62 = [s for s in SL if s['grp'] == 62]
REL = {701: "right flight 1 inner", 702: "right flight 1 outer", 713: "right flight 2 inner", 714: "right flight 2 outer",
       746: "left flight 1 inner", 747: "left flight 1 outer", 758: "left flight 2 inner", 759: "left flight 2 outer"}
F = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)
W, Hh = 3000, 1750
im = Image.new("RGB", (W, Hh), "white"); d = ImageDraw.Draw(im)


def view(vdir, ox, oy, sc, ctr):
    v = np.array(vdir, float); v /= np.linalg.norm(v)
    r = np.cross(v, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, v)
    return lambda p: (ox + (np.array(p) - ctr) @ r * sc, oy - (np.array(p) - ctr) @ u * sc)


def draw(P, title, tx, ty, near):
    d.text((tx, ty), title, fill=(0, 0, 0), font=F(30, True))
    for s in SL:                                  # context: platform members near the stair, light grey
        a, b = np.array(s['x1']), np.array(s['x2'])
        if s['grp'] != 62 and min(np.linalg.norm(a[:2] - near), np.linalg.norm(b[:2] - near)) < 6 and max(a[2], b[2]) < 4.6:
            d.line([P(a), P(b)], fill=(205, 205, 205), width=2)
    for s in G62:
        a, b = s['x1'], s['x2']
        if np.linalg.norm(np.array(a[:2]) - near) > 5.5: continue
        sn = s['sln']
        col, w = ((30, 90, 210), 7) if sn in REL else ((120, 120, 120), 3)
        d.line([P(a), P(b)], fill=col, width=w)
    for sn in REL:
        s = next(x for x in G62 if x['sln'] == sn)
        if np.linalg.norm(np.array(s['x1'][:2]) - near) > 5.5: continue
        for e, p in (("start", s['x1']), ("end", s['x2'])):
            x, y = P(p)
            d.ellipse([x - 26, y - 26, x + 26, y + 26], outline=(255, 120, 0), width=6)
        m = P((np.array(s['x1']) + np.array(s['x2'])) / 2)
        d.text((m[0] + 14, m[1] - 34), f"SLN {sn}", fill=(30, 90, 210), font=F(26, True))


ctrR = np.array([12.9, 0.4, 2.2]); ctrL = np.array([9.6, -8.4, 2.2])
draw(view((-1, 0.35, -0.45), 760, 980, 120, ctrR), "Right arm (SLN 701/702 flight 1, 713/714 flight 2), seen from outside", 60, 150, ctrR[:2])
draw(view((-0.55, -0.85, -0.45), 2250, 980, 120, ctrL), "Left arm (SLN 746/747 flight 1, 758/759 flight 2), seen from outside", 1560, 150, ctrL[:2])
d.text((60, 30), "26016 v20 - external stair (group 62): stringer ends released for My (pinned in the plane of the flight)", fill=(0, 0, 0), font=F(44, True))
d.text((60, 90), "Orange circle = My released (FIXA 'MY' at the start, FIXE 'MY' at the end of the SLN). N, Vy, Vz, Mt, Mz stay connected. Blue = the 8 stringers (RHS 200x100x6). Grey = landings, legs, brackets, treads (unchanged).",
       fill=(60, 60, 60), font=F(25))
notes = ["Released ends (16): each stringer SLN is one line from flight end to flight end; tread nodes inside the flight stay continuous.",
         "  right arm: 701, 702 (flight 1: foot on the ground supports +0.64 -> landing 1 +2.43);  713, 714 (flight 2: landing 1 +2.64 -> top +4.43 at L1)",
         "  left arm : 746, 747 (flight 1);  758, 759 (flight 2)",
         "Reading of Wing's sketch: it shows ONE flight with its two stringers circled at both ends. I applied the same release to all 8 stringers",
         "(both arms, both flights) as the stringer-to-landing connection type. If only the drawn flight is meant, tell me which one (the sketch view does not",
         "show the arm unambiguously) and I will rerun with that flight only."]
for i, t in enumerate(notes):
    d.text((60, 1530 + 34 * i), t, fill=(0, 0, 0) if i in (0, 3) else (40, 40, 40), font=F(25, i in (0, 3)))
im.save(os.path.join(H, "v20_stair_release_reading.png"), dpi=(150, 150))
im.resize((1500, 875)).save(os.path.join(H, "v20_stair_preview.jpg"))


