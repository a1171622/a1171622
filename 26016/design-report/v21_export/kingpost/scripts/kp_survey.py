"""Kingpost shells in the v21 cdb (read only on the envelope COPY): groups, element counts, thickness, material, geometry."""
import sys, json, math, collections, bisect
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
from sofistik_mcp.results import as_rec
CDB = r"C:\Sofistik workflow\26016-member-check\v21\envelopes\26016_env_v21.cdb"
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st); d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(CDB, info)
xyz = R._node_coords(cdb, d)
G = sorted({(g["min_element"], g["group"]) for g in R.groups(cdb, d) if g["min_element"] > 0}); starts = [s for s, _ in G]
eg = lambda nr: G[bisect.bisect_right(starts, nr) - 1][1]
Q = {}
for rec in cdb.records(200, 0):
    o = as_rec(d, "CQUAD", rec)
    if o.m_nr <= 0: continue
    Q[o.m_nr] = dict(nodes=list(o.m_node), mat=o.m_mat, t=float(o.m_thick[0]), grp=eg(o.m_nr), T=[[float(o.m_t[i][j]) for j in range(3)] for i in range(3)])
agg = collections.defaultdict(lambda: dict(n=0, t=collections.Counter(), mat=collections.Counter(), z=[], r=[], nrm=collections.Counter()))
for e, q in Q.items():
    a = agg[q["grp"]]; a["n"] += 1; a["t"][round(q["t"] * 1000, 1)] += 1; a["mat"][q["mat"]] += 1
    ps = [xyz[n] for n in q["nodes"] if n in xyz]
    a["z"] += [p[2] for p in ps]; a["r"] += [math.hypot(p[0], p[1]) for p in ps]
    a["nrm"][tuple(round(x, 2) for x in q["T"][2])] += 1
for g, a in sorted(agg.items()):
    print(g, a["n"], dict(a["t"]), dict(a["mat"]), "z %.2f..%.2f r %.3f..%.3f" % (min(a["z"]), max(a["z"]), min(a["r"]), max(a["r"])), a["nrm"].most_common(4))
json.dump({str(k): v for k, v in Q.items()}, open("quads.json", "w"))
print(R.materials(cdb, d) if hasattr(R, "materials") else "")
cdb.close()
