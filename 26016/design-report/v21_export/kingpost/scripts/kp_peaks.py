"""Local peaks: distance of each high element to the nearest node where a beam element meets the kingpost shells (point load introduction)."""
import sys, json, math, collections
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st); d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(r"C:\Sofistik workflow\26016-member-check\v21\envelopes\26016_env_v21.cdb", info)
xyz = R._node_coords(cdb, d); idx = R._beam_ctx(cdb, d)["idx"]
Q = json.load(open("quads.json"))
qn = set(n for q in Q.values() for n in q["nodes"])
att = collections.defaultdict(list)
for k in json.load(open("kin_kingpost.json"))["constraints"]:     # kinematic constraints: shell node k[1] tied to beam-end node k[2][0]
    if k[2][0] and k[1] in qn: att[k[1]].append(k[2][0])
sup = [r["node"] for r in R.support_reactions(cdb, d, 102, max_rows=10 ** 6)["rows"] if r["node"] in qn]
cdb.close()
P = list(att)
print("shell nodes tied to beam ends (kinematic constraints):", len(P), "support nodes on shells:", len(sup))
zs = collections.Counter(round(xyz[n][2], 2) for n in P); print(zs.most_common(10))
pe = json.load(open("per_element_max_ULS.json"))
def cen(e): ns = Q[e]["nodes"]; ps = [xyz[n] for n in ns if n in xyz]; return [sum(p[i] for p in ps) / len(ps) for i in range(3)]
def dist(e): c = cen(e); return min(math.dist(c, xyz[n]) for n in P + sup)
rows = []
for e, v in pe.items():
    rows.append((v, e, Q[e]["grp"], dist(e), cen(e)))
rows.sort(reverse=True)
print("top 12 elements: sigma_v, el, grp, dist to beam/support node (mm), z")
for r in rows[:12]: print(round(r[0], 1), r[1], r[2], round(r[3] * 1000), round(r[4][2], 3))
out = {}
for lim in (0.0, 0.020, 0.040, 0.060, 0.100, 0.150):
    m = max((r for r in rows if r[3] >= lim), key=lambda r: r[0])
    c = m[4]
    out[f"min_dist_{int(lim * 1000)}mm"] = dict(sigma_v=round(m[0], 1), element=m[1], group=m[2], dist_mm=round(m[3] * 1000), z=round(c[2], 3),
                                                angle=round(math.degrees(math.atan2(c[1], c[0])) % 360, 1), r=round(math.hypot(c[0], c[1]), 3))
    print(lim, out[f"min_dist_{int(lim * 1000)}mm"])
json.dump(dict(attached_nodes=len(P), note="max ULS element-centre sigma_v excluding elements whose centre is closer than the limit to a shell node that is tied by a kinematic constraint to a beam end (each radial end is tied to 4 shell nodes) or to a support node", coupled_shell_nodes=sorted(att), zs=dict(collections.Counter(round(xyz[n][2], 3) for n in att)), by_distance=out), open("../kingpost_peaks_v21.json", "w"), indent=1)

# per zone, ULS element-centre maxima at increasing distance from the coupled nodes
def zone(e, c):
    g = Q[e]["grp"]; z = c[2]
    if g in ("6", "7", 6, 7):
        return "tube wall, base" if z < 0.5 else "tube wall, Level 2 zone" if 7.4 <= z <= 8.7 else "tube wall, roof zone" if z >= 11.5 else "tube wall, between levels"
    return ("collar / cap plates, " if g in (1, "1") else "radial fin plates, ") + ("Level 2" if z < 10 else "roof")
ZT = collections.defaultdict(dict)
for lim in (0.0, 0.05, 0.10, 0.15):
    for v, e, g, dd, c in rows:
        if dd < lim: continue
        zn = zone(e, c); k = f"{int(lim * 1000)}mm"
        if k not in ZT[zn] or v > ZT[zn][k]["sigma_v"]:
            ZT[zn][k] = dict(sigma_v=round(v, 1), util=round(v / 275, 3), element=e, dist_mm=round(dd * 1000), z=round(c[2], 3),
                            angle=round(math.degrees(math.atan2(c[1], c[0])) % 360, 1), r=round(math.hypot(c[0], c[1]), 3))
for zn, v in sorted(ZT.items()):
    print("%-30s" % zn, "  ".join(f"{k}: {x['sigma_v']} (r {x['r']}, {x['angle']} deg)" for k, x in v.items()))
res = json.load(open("../kingpost_peaks_v21.json")); res["by_zone"] = ZT
json.dump(res, open("../kingpost_peaks_v21.json", "w"), indent=1)
