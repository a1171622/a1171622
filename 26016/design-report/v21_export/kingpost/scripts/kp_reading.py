"""kingpost_reading_v21.png: the kingpost shells as read from the v21 cdb (elevation + Level 2 plan), coloured by part, with the
nodes tied to the radial beam ends (kinematic constraints) and the support nodes. All plates t = 20 mm, S275. PIL only."""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st); d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(r"C:\Sofistik workflow\26016-member-check\v21\envelopes\26016_env_v21.cdb", info); xyz = R._node_coords(cdb, d)
sup = [r["node"] for r in R.support_reactions(cdb, d, 102, max_rows=10 ** 6)["rows"]]
cdb.close()
Q = json.load(open("quads.json")); K = json.load(open("kin_kingpost.json"))["constraints"]
tied = {k[1] for k in K if k[2][0]}; qn = {n for q in Q.values() for n in q["nodes"]}
COL = {1: (91, 141, 239), 2: (230, 140, 40), 6: (150, 160, 175), 7: (120, 130, 145)}
W, H = 2000, 1500
im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im)
def F(s):
    try: return ImageFont.truetype("arial.ttf", s)
    except Exception: return ImageFont.load_default()
f, fb, fs = F(18), F(24), F(15)
dr.text((20, 12), "26016 v21 kingpost: shell model as read from the cdb (Wing to confirm)", fill="black", font=fb)
# elevation: x horizontal, z vertical
ox, oz, k = 330, 1360, 100.0
def E(p): return (ox + p[0] * k, oz - p[2] * k)
for e, q in sorted(Q.items(), key=lambda kv: -(xyz[kv[1]["nodes"][0]][1] if kv[1]["nodes"][0] in xyz else 0)):
    ps = [xyz[n] for n in q["nodes"] if n in xyz]
    if len(ps) >= 3: dr.polygon([E(p) for p in ps], fill=COL[q["grp"]])
for n in tied: dr.ellipse([E(xyz[n])[0] - 3, E(xyz[n])[1] - 3, E(xyz[n])[0] + 3, E(xyz[n])[1] + 3], fill=(220, 0, 0))
for n in sup:
    if n in qn: x, y = E(xyz[n]); dr.polygon([(x, y), (x - 6, y + 12), (x + 6, y + 12)], outline=(0, 120, 0))
for z, t in ((0.0, "base, 20 support nodes on the tube end"), (4.054, "Level 1 (no kingpost plates or ties at this level)"), (7.81, "Level 2: collar plate z 7.81 (bottom)"),
             (8.30, "Level 2: collar plate z 8.30 (top) + 18 radial fins"), (11.91, "roof: plate z 11.91"), (12.20, "roof: cap plate z 12.20 + 18 fins")):
    dr.line([(ox + 1.0 * k, oz - z * k), (ox + 1.6 * k, oz - z * k)], fill="black"); dr.text((ox + 1.65 * k, oz - z * k - 9), f"z {z:.2f}  {t}", fill="black", font=fs)
dr.text((40, 70), "ELEVATION (x horizontal, z up; 1 m = 100 px)", fill="black", font=f)
# plan of the Level 2 bottom collar plate
px, py, kp = 1500, 520, 380.0
def Pp(p): return (px + p[0] * kp, py - p[1] * kp)
dr.text((1150, 70), "PLAN, Level 2 (z 7.6-8.4): collar plates, fins, tube", fill="black", font=f)
for e, q in Q.items():
    ps = [xyz[n] for n in q["nodes"] if n in xyz]
    if not ps or not (7.55 < sum(p[2] for p in ps) / len(ps) < 8.45): continue
    if q["grp"] == 1 and abs(ps[0][2] - 7.81) > 0.02: continue
    dr.polygon([Pp(p) for p in ps], fill=COL[q["grp"]] if q["grp"] != 1 else (200, 215, 245), outline=None)
for n in tied:
    if 7.7 < xyz[n][2] < 7.9: dr.ellipse([Pp(xyz[n])[0] - 4, Pp(xyz[n])[1] - 4, Pp(xyz[n])[0] + 4, Pp(xyz[n])[1] + 4], fill=(220, 0, 0))
for a in range(0, 360, 20):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    dr.line([Pp((0.66 * c, 0.66 * s)), Pp((0.95 * c, 0.95 * s))], fill=(120, 80, 20), width=2)
y = 980
for t, col in (("tube wall, groups 6 + 7: r 0.305, t 20, z 0-12.2 (about CHS 610 x 20), 12,117 elements", COL[6]),
               ("horizontal collar / cap plates, group 1: r <= 0.916, t 20, Level 2 z 7.81 / 8.30, roof z 11.91 / 12.20", COL[1]),
               ("vertical radial fin plates, group 2: r 0.304-0.506, t 20, 18 per level (every 20 deg)", COL[2]),
               ("red dots: shell nodes tied by kinematic constraints to a radial beam end (4 nodes per beam end, 288 in total)", (220, 0, 0)),
               ("brown lines (plan): radial beams, ending at r 0.66 (beam end node at the beam axis, tied to the 4 plate nodes)", (120, 80, 20))):
    dr.rectangle([1100, y, 1130, y + 18], fill=col); dr.text((1140, y), t, fill="black", font=fs); y += 30
dr.multiline_text((1100, y + 10), "Material S275 (MNO 3), fy = 275 MPa for t = 20 <= 40 mm, gamma_M0 = 1.0.\nNo beam shares a node with the shells: each radial end is tied to 4 nodes\n(point-like load introduction; the source of the local peaks).", fill="black", font=fs, spacing=4)
im.save(r"C:\Sofistik workflow\26016-design-report\v21_export\kingpost\kingpost_reading_v21.png"); print("ok")
