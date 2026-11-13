"""Find the r 12 Level 2 radial-to-ring nodes in v21 and the radial end forces (envelope over the 43 ULS STR cases)."""
import sys, math, json
sys.path.insert(0, r"C:\Sofistik workflow\idea-statica\v21\builder")
from cdbend import Model
m = Model(r"C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.cdb")
LCS = list(range(101, 131)) + [135] + list(range(141, 149)) + list(range(151, 155))
cand = [n for n, p in m.xyz.items() if abs(math.hypot(p[0], p[1]) - 12.0) < 0.01 and abs(p[2] - 8.055) < 0.01]
out = []
for n in cand:
    bl = m.beams_at(n)
    rad = []
    for b in bl:
        a, c = m.idx[b]["nodes"]; o = c if a == n else a; p = m.xyz[o]
        if math.hypot(p[0], p[1]) < 11.9 and abs(p[2] - 8.055) < 0.01: rad.append(b)
    if len(rad) != 1 or len(bl) != 3: continue
    F = m.end_forces(n, LCS); b = rad[0]
    vz = max(abs(F[(b, lc)]["Vz"]) for lc in LCS); my = max(abs(F[(b, lc)]["My"]) for lc in LCS)
    ang = math.degrees(math.atan2(m.xyz[n][1], m.xyz[n][0])) % 360
    out.append(dict(node=n, angle=round(ang, 1), beam=b, sln=m.idx[b]["sln"], Vz_max=round(vz, 1), My_max=round(my, 1), nbeams=len(bl)))
for r in sorted(out, key=lambda r: r["angle"]): print(r)
json.dump(out, open("r12_candidates_v21.json", "w"), indent=1)
m.cdb.close()
