"""Group 62 (external stair) participation in all 20 buckling modes of PLC 102 (LC 9201-9220) and PLC 119 (LC 9221-9240), v21 (read only).
Per mode: factor (from the LC title), node with the largest |u| (group, r, angle, z), group 62 max |u| / global max |u| (same measure as PART A 'gmax_rel'),
and group 62 share of sum |u|^2 over all nodes (a node counts for group 62 if any beam of group 62 meets it).
Run from v21_export/A_followup/scripts:  py -3.11 buckling_g62.py  -> ../../buckling_group62_participation.json"""
import json, math, re, collections
from geo import *
from cdbx import open_cdb, R
cdb, d = open_cdb()
T = {l["lc"]: l["title"] for l in R.load_cases(cdb, d)}
ngr = collections.defaultdict(set)
for b, v in beams.items():
    for n in v["nodes"]: ngr[n].add(eg(b))
out = {}
for plc, lcs in ((102, range(9201, 9221)), (119, range(9221, 9241))):
    modes = []
    for i, lc in enumerate(lcs, 1):
        rows = R._node_rows(cdb, d, lc, None)
        if not rows: modes.append(dict(mode=i, lc=lc, missing=True)); continue
        u = {r["node"]: math.sqrt(r["ux"] ** 2 + r["uy"] ** 2 + r["uz"] ** 2) for r in rows}
        nmax = max(u, key=u.get); umax = u[nmax]
        g62 = [n for n in u if 62 in ngr.get(n, ())]
        e_all = sum(v * v for v in u.values()); e62 = sum(u[n] ** 2 for n in g62)
        gmax = collections.defaultdict(float)
        for n, v in u.items():
            for g in ngr.get(n, ()): gmax[g] = max(gmax[g], v)
        top = sorted(((g, v / umax) for g, v in gmax.items()), key=lambda t: -t[1])[:4]
        m = re.search(r"fact\s+([-\d.Ee+]+)", T.get(lc, "") or "")
        r_, th, z = pol(nmax) if nmax in xyz else (None, None, None)
        modes.append(dict(mode=i, lc=lc, title=T.get(lc), factor=float(m[1]) if m else None,
                          max_node=nmax, max_node_groups=sorted(ngr.get(nmax, ())), r=round(r_, 2) if r_ else None, angle_deg=round(th, 1) if th else None, z=round(z, 2) if z is not None else None,
                          g62_max_rel=round(gmax.get(62, 0) / umax, 3), g62_energy_share=round(e62 / e_all, 4),
                          top_groups_max_rel={str(g): round(v, 3) for g, v in top}))
    out[str(plc)] = modes
cdb.close()
res = dict(what="Group 62 (external stair) participation in the 20 buckling modes of PLC 102 and PLC 119, model v21",
           measures={"g62_max_rel": "max |u| over group 62 nodes / max |u| over all nodes (1.0 = the mode peaks in the stair)",
                     "g62_energy_share": "sum |u|^2 over group 62 nodes / sum |u|^2 over all nodes"}, modes=out)
json.dump(res, open(r"C:\Sofistik workflow\26016-design-report\v21_export\buckling_group62_participation.json", "w"), indent=1)
for plc, ms in out.items():
    print("PLC", plc)
    for m in ms: print(" ", m.get("mode"), m.get("factor"), "g62 max_rel", m.get("g62_max_rel"), "share", m.get("g62_energy_share"), "peak grp", m.get("max_node_groups"))
