"""Fit the cdb -> IOM force mapping for the v14 L2-R12-E1_000 template (its forces came from the v14 cdb)."""
import sys, json, math
sys.path.insert(0, r"C:\Sofistik workflow\idea-statica\v21\builder")
from iomx import load
from calib import geom, match, IC, CAND
from cdbend import Model
X = r"C:\Sofistik workflow\idea-statica\v14\xml_E1\L2-R12-E1_000.xml"
m = Model(r"C:\Sofistik workflow\26016-member-check\v14\26016_v14_idea_forces.cdb")
els, cp, lcs, res = geom(load(X)); node = m.node_at(cp, 0.1); mt = match(m, node, els, cp)
print("node", node, cp, {e: (els[e]["name"], mt[e]) for e in els})
lcn = {k: int(v.split('_')[1]) for k, v in lcs.items()}
F = m.end_forces(node, sorted(set(lcn.values())))
out = {}
for eid in els:
    b = mt[eid]['beam']; mp = {}
    if not any((eid, k) in res for k in lcn): print(eid, "no results"); continue
    for c in IC:
        xs = [res[(eid, k)][c] for k in lcn]; best = None
        for sc in CAND[c]:
            for sg in (1, -1):
                ys = [sg * F[(b, lcn[k])][sc] * 1000 for k in lcn]
                err = math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys)) / len(xs)); mag = max(abs(x) for x in xs) + 1e-9
                if best is None or err < best[0]: best = (err, sc, sg, mag)
        mp[c] = [best[1], best[2]]; mp[c + "_relerr"] = round(best[0] / best[3], 4)
    out[eid] = dict(name=els[eid]["name"], beam=b, sln=m.idx[b]["sln"], start_at_node=m.idx[b]["nodes"][0] == node, map=mp)
    print(eid, els[eid]["name"], b, out[eid]["start_at_node"], mp)
json.dump(dict(node=node, cp=cp, els=out), open("calib_e1.json", "w"), indent=1)
m.cdb.close()
