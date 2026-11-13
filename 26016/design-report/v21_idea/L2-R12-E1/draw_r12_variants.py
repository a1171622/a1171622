"""Before/after strain picture for L2-R12-E1 (v21): variant 0, V1 (20 x 295 plates), V2 (185x70x20 plates). py -3.11 draw_r12_variants.py"""
from PIL import Image, ImageDraw, ImageFont
R = r"C:\Sofistik workflow\idea-statica\v21\R12"
srcs = [(R + r"\final\report\crop_2.png", "Variant 0 (current): no 20 x 295 plates",
         ["plate strain 6.6 % (LC 153), ring bottom flange below the radial web / lower fins",
          "max weld 109.1 % stiffener at 315 to ring top flange (a 7.0, LC 121)",
          "bolts 60.7 %"], (650, 630)),
        (R + r"\var_V1\report\strain.png", "Variant 1: + 20 x 295 plates on the ring bottom flange",
         ["(140 wide, radial web face to the 315 stiffener; edges welded to the flange,",
          " end to the stiffener, lower fins welded onto them)",
          "plate strain 7.1 % (LC 120), ring bottom flange at the end of the new plate",
          "max weld 102.8 % 295 plate to ring bottom flange (SLN 55 side, a 7.0, LC 119)",
          "bolts 59.1 %"], (470, 712)),
        (R + r"\var_V2\report\strain.png", "Variant 2: + E-section 185x70x20 plates under the fins",
         ["(2 x 70 + web, 185 along the ring, edges welded to the flange; radial web sits on it)",
          "plate strain 8.0 % (LC 119), ring bottom flange at the plate ends (under the plate)",
          "max weld 105.3 % ring top flange welds; 185 plate to flange 104.9 % (LC 120)",
          "bolts 60.4 %"], (650, 630))]
ims = [Image.open(s).convert("RGB") for s, *_ in srcs]
sc = 0.62; ims = [im.resize((int(im.width * sc), int(im.height * sc))) for im in ims]
W = sum(im.width for im in ims); H = ims[0].height + 330
out = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(out)
def F(s):
    try: return ImageFont.truetype("arial.ttf", s)
    except Exception: return ImageFont.load_default()
x = 0
d.text((15, 8), "26016 L2-R12-E1 (v21 forces): plastic strain in IDEA without and with the extra plates of drawing 1103 (limit 5 %)", fill="black", font=F(24))
for im, (s, title, notes, spot) in zip(ims, srcs):
    out.paste(im, (x, 50)); cx, cy = x + int(spot[0] * sc), 50 + int(spot[1] * sc)
    d.ellipse([cx - 32, cy - 24, cx + 32, cy + 24], outline=(200, 0, 0), width=4)
    d.text((x + 12, 55), title, fill="black", font=F(18))
    y = 50 + im.height + 5
    for t in notes: d.text((x + 12, y), t, fill="black", font=F(15)); y += 21
    x += im.width
d.multiline_text((15, H - 95), "In both variants the extra plates connect and work, but the strain peak moves to the end of the new plate / weld on the existing ring\n"
                 "bottom flange and rises (7.1 % / 8.0 %). The ring flange is close to yield over the joint (ring My 136 kNm vs M_el 138.6 kNm), so every\n"
                 "plate or weld end on it becomes a local peak. Red circles: location of the peak in each plot.", fill=(150, 0, 0), font=F(17), spacing=4)
out.save(R + r"\final\L2-R12-E1_variants_v21.png"); print(out.size)
