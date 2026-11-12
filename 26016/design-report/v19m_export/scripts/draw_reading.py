"""Plan of the external stair (group 62) from the v19m model geometry, coloured by max(BDK, AQB), with the reading labelled."""
import json, sys
from PIL import Image, ImageDraw, ImageFont
X = sys.argv[1]
m = json.load(open("model.json")); xyz = {int(k): v for k, v in m["xyz"].items()}; beams = {int(k): v for k, v in m["beams"].items()}
S = json.load(open(X + r"\stair_ext.json")); RG = json.load(open(X + r"\ring_L2.json"))
W, H = 2000, 2650; sc = 108; x0, y1 = 2.2, 6.6
P = lambda p: (int((p[0] - x0) * sc) + 40, int((y1 - p[1]) * sc) + 140)
img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
try:
    F = ImageFont.truetype("arial.ttf", 22); FB = ImageFont.truetype("arialbd.ttf", 26); FS = ImageFont.truetype("arial.ttf", 18)
except Exception:
    F = FB = FS = ImageFont.load_default()
def col(u):
    if u is None: return (150, 150, 150)
    if u >= 1.0: return (200, 0, 0)
    if u >= 0.9: return (240, 120, 0)
    if u >= 0.5: return (230, 190, 0)
    return (40, 140, 60)
# L1 ring r 12: polygon through the ring corner nodes at 0, 20, 40 deg and 280, 300, 320 deg (z 4.05)
import math
for angs in ((-80, -60, -40, -20, 0, 20, 40, 50),):
    pts = [P((12 * math.cos(math.radians(t)), 12 * math.sin(math.radians(t)))) for t in (-80, -60, -40, -20, 0, 20, 40)]
    d.line(pts, fill=(120, 120, 220), width=5)
d.text(P((12.2, -3.3)), "L1 ring r 12 (group 15), z 4.05", fill=(80, 80, 200), font=FS)
mem = S["members"]
for mb in sorted(mem, key=lambda q: q["kind"] == "tread"):
    u = max([(mb[k] or {}).get("util") or 0 for k in ("bdk", "aqb")]) if (mb["bdk"] or mb["aqb"]) else None
    wd = 2 if mb["kind"] == "tread" else (9 if mb["kind"] in ("leg", "ring bracket") else 6)
    for b in mb["beams"]:
        a, c = beams[b]["nodes"]
        pa, pc = P(xyz[a]), P(xyz[c])
        if pa == pc or mb["kind"] in ("leg", "ring bracket"):
            d.ellipse([pa[0] - 9, pa[1] - 9, pa[0] + 9, pa[1] + 9], fill=col(u), outline="black")
        else:
            d.line([pa, pc], fill=col(u), width=wd)
# labels for governing members
lab = {722: (40, -30), 767: (60, 60), 711: (-330, 10), 756: (-330, -10), 768: (-300, 40), 723: (40, 10)}
for mb in mem:
    if mb["sln"] in lab:
        zs = [(xyz[n][2], n) for b in mb["beams"] for n in beams[b]["nodes"]]; p = P(xyz[max(zs)[1]]); dx, dy = lab[mb["sln"]]
        t = "SLN %d %s\nBDK %.3f LC %d" % (mb["sln"], mb["kind"], mb["bdk"]["util"], mb["bdk"]["lc"])
        d.line([p, (p[0] + dx, p[1] + dy)], fill="black", width=1); d.text((p[0] + dx, p[1] + dy), t, fill="black", font=F)
# brackets
for br in S["ring_brackets"]["lc102"]:
    e = S["ring_brackets"]["ULS_envelope"][str(br["sln"])]; p = P(br["ring_xyz"])
    d.rectangle([p[0] - 12, p[1] - 12, p[0] + 12, p[1] + 12], outline=(160, 0, 160), width=4)
    d.text((p[0] - 330 if br["sln"] in (724, 725) else p[0] + 18, p[1] - 30),
           "bracket SLN %d (node %d)\nN ULS %+.1f (LC %d) / %+.1f (LC %d) kN\nonly N reaches the ring" % (br["sln"], br["ring_node"], e["N_max"], e["N_max_lc"], e["N_min"], e["N_min_lc"]),
           fill=(140, 0, 140), font=FS)
# supports
env = S["supports"]["ULS_envelope"]
for n, e in env.items():
    sp = [r for r in S["supports"]["lc102"] if r["node"] == int(n)][0]; p = P((sp["x"], sp["y"]))
    d.polygon([(p[0], p[1] - 14), (p[0] - 12, p[1] + 9), (p[0] + 12, p[1] + 9)], outline="black", fill=(255, 255, 255) if e["pz_min"] > -5 else (255, 200, 200))
    if int(n) in (901, 902, 909, 910):
        d.text((p[0] + 14, p[1] + 4), "SPT %s pz %+.1f / %+.1f kN\nH max %.0f kN" % (n, e["pz_max"], e["pz_min"], max(abs(e["px_max"]), abs(e["px_min"]), abs(e["py_max"]), abs(e["py_min"]))), fill="black", font=FS)
for mb in mem:
    if mb["kind"] in ("leg", "ring bracket"):
        u = max([(mb[k] or {}).get("util") or 0 for k in ("bdk", "aqb")])
        a = beams[mb["beams"][0]]["nodes"][0]; zs = [(xyz[n][2], n) for b in mb["beams"] for n in beams[b]["nodes"]]
        p = P(xyz[max(zs)[1]]); r = 11
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col(u), outline="black", width=2)
# landing sway
for part, v in S["landing_horizontal_movement"].items():
    w = v["worst_wind_SLS"]; p = P(w["xyz"]); k = 10
    q = (p[0] + int(w["ux"] * k * sc / 135), p[1] - int(w["uy"] * k * sc / 135))
    d.line([p, q], fill=(220, 0, 0), width=5); d.ellipse([q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6], fill=(220, 0, 0))
    d.text((q[0] + 8, q[1] + (12 if "left landing 2" in part else -10)), "%s: %.1f mm (LC %d, node %d)" % (part, w["value"], w["lc"], w["node"]), fill=(200, 0, 0), font=FS)
d.text((40, 20), "26016 v19m external stair (group 62), plan from the model geometry: how I read the v19m results", fill="black", font=FB)
d.text((40, 60), "colour = max(BDK, AQB) per member: green < 0.5, yellow 0.5 to 0.9, orange 0.9 to 1.0, red >= 1.0;  dots = legs and brackets seen from above;\n"
       "triangles = pinned supports SPT 901 to 916 (pink = uplift > 5 kN in ULS);  purple squares = ring brackets (N only);  red arrows = horizontal landing movement, worst SLS wind (x10)", fill="black", font=FS)
d.text((40, H - 120), "Legs are checked with Lcr = 2 L (as run). Sway comes from G + Q; the stair is held sideways by the pinned flight 1 feet.\n"
       "Forces are from 26016_check_v19m.cdb / .erg, read by extract_v19m.py (stair_ext.json). Wing to confirm the leg Lcr and the bracket bearing detail.", fill="black", font=F)
img.save(X + r"\R1_external_stair_reading.png")
print("ok")
