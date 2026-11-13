"""Labelled picture of L2-R12-E1 as built in IDEA (v21), from the IDEA scene renders r12_under.png / r12_top.png."""
from PIL import Image, ImageDraw, ImageFont
import os
D = r"C:\Sofistik workflow\idea-statica\v21\R12\final"
A, B = Image.open(os.path.join(D, "r12_under.png")).convert("RGB"), Image.open(os.path.join(D, "r12_top.png")).convert("RGB")
W = A.width + B.width; H = max(A.height, B.height) + 430
im = Image.new("RGB", (W, H), "white"); im.paste(A, (0, 70)); im.paste(B, (A.width, 70)); d = ImageDraw.Draw(im)
def F(s):
    try: return ImageFont.truetype("arial.ttf", s)
    except Exception: return ImageFont.load_default()
f, fb, fs = F(18), F(24), F(16)
d.text((20, 15), "26016 L2-R12-E1_000 (node 1485, r 12, 0 deg), IDEA StatiCa model as built on v21 forces - Wing to check the geometry", fill="black", font=fb)
def lab(xy, txt, to, col=(170, 0, 0)):
    d.multiline_text(xy, txt, fill=col, font=f, spacing=2); d.line([xy[0], xy[1] + 10, to[0], to[1] + 70], fill=col, width=2)
lab((30, 120), "ring UB 254x146x43 (SLN 55 + 56)\ncontinuous, bearing member", (150, 400))
lab((700, 110), "bracket in the ring web plane: 10 web,\n20 top plate, 20 inclined stiffeners", (470, 230))
lab((760, 640), "395x145x20 fin plates both sides of the\nradial web, 6 x M24 10.9 (3 rows x 2)", (560, 420))
lab((30, 700), "20 ring stiffener at 315\n(full width, welded to both flanges)", (320, 420))
lab((380, 840), "radial UB 457x191x98 (SLN 73), bottom flange\ncut over the ring, web passes the ring web", (420, 640))
d.text((A.width + 20, 75), "view from above (radial towards the centre at left)", fill="black", font=f)
d.text((20, 75), "view from below / outside", fill="black", font=f)
y = max(A.height, B.height) + 85
notes = ["Read from drawing 970027-S01-ST-1103 rev 04 sections D1 / E (reading picture L2-R12-E1_reading_v21.png, option (a) as agreed).",
         "Assumptions (not readable from the drawing or simplified for IDEA):",
         " - Radial web passes the ring web (slot); in IDEA the ring web stays whole and overlaps the radial web (slightly stiff). Radial bottom flange cut back over the ring.",
         " - Bolt positions: rows 105 / 230 / 330 below the fin top (98 above the bottom of steel), columns +-39 from the ring web; M24 10.9, bearing, holes 26.",
         " - Welds: throat a = 7.0 (10 mm leg) to flanges, a = 4.2 (6 mm leg) to webs, double fillets; plates S275.",
         " - Ring stiffeners at 315 modelled full width (a half-plate on one side did not connect in IDEA 26.0).",
         " - Left out: the 20 x 295 plates above the ring bottom flange (they made the IDEA model a mechanism), the 205x70x20 stiffener and 185x70x20 plate (section E).",
         " - Fin plates split around the ring top flange and web (upper piece + 2 lower halves each side), each welded to the ring.",
         " - Built at 0 deg (node 1485): radial end Vz 89.8 / My 47.2 kNm; the other r 12 ends are within +3 % Vz (160 deg) and +1.5 % My (240 deg)."]
for t in notes: d.text((20, y), t, fill="black", font=fs); y += 26
im.save(os.path.join(D, "L2-R12-E1_as_built_v21.png")); print("ok")
