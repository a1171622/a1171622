"""Report deflection table numbers (read only on the v21 cdb, and v20 for comparison).
1 L2 framing set (env_node_SLS_L2.json nodes): min uz for LC 11+12+13; uz of nodes 5568 / 5569 for that sum and LC 201.
2 Roof set (env_node_SLS_RF.json): min uz LC 12.   3 L1 set (env_node_SLS_L1.json): min uz LC 11.
4 Stair stringers: uz relative to the straight line between the stringer's end nodes, LC 201 (internal stair SLN 79 90 136 137 461 472
  489 490; external stair flight stringers SLN 701 702 713 714 746 747 758 759). The PART A (f) line used SNO 5 to find the internal
  stringers; v21 moved them to SNO 10, so it found none (rel 0.0). Here the stringers are taken by SLN.
py -3.11 partA4_report.py  -> ../partA4_report_deflections.json"""
import sys, json, math, collections
sys.path.insert(0, r"C:\Sofistik workflow\26016-design-report\v21_export\scripts")
from cdbx import open_cdb, R
E = r"C:\Sofistik workflow\26016-design-report\v21_export"
SETS = {k: [n["node"] for n in json.load(open(fr"{E}\env_node_SLS_{k}.json"))["nodes"]] for k in ("L1", "L2", "RF")}
INT = [79, 90, 136, 137, 461, 472, 489, 490]; EXT = [701, 702, 713, 714, 746, 747, 758, 759]


import re


def sln_beams_geo(dat, slns, xyz, idx):
    txt = open(dat, encoding="latin-1").read(); out = {}
    for s in slns:
        i = re.search(r"^SLN\s+" + str(s) + r"\s", txt, re.M).start()
        m = re.compile(r"SLNB X1\s+(\S+)\s+(\S+)\s+(\S+) X2\s+(\S+)\s+(\S+)\s+(\S+)").search(txt, i)
        a = [float(m[i]) for i in (1, 2, 3)]; b = [float(m[i]) for i in (4, 5, 6)]
        ab = [b[i] - a[i] for i in range(3)]; L2 = sum(v * v for v in ab)
        def on(p):
            tt = sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2
            return -1e-3 <= tt <= 1.001 and math.dist([a[i] + tt * ab[i] for i in range(3)], p) < 0.01
        out[s] = [bb for bb, v in idx.items() if all(on(xyz[n]) for n in v["nodes"])]
    return out


def run(cdb_path):
    cdb, d = open_cdb(cdb_path)
    xyz = R._node_coords(cdb, d); idx = R._beam_ctx(cdb, d)["idx"]
    U = {}
    def u(lc):
        if lc not in U: U[lc] = {r["node"]: r for r in R._node_rows(cdb, d, lc, None)}
        return U[lc]
    def uz_sum(n, lcs): return sum(u(lc)[n]["uz"] for lc in lcs)
    def mn(ns, lcs):
        n = min((n for n in ns if n in u(lcs[0])), key=lambda n: uz_sum(n, lcs))
        return dict(uz_mm=round(uz_sum(n, lcs), 2), node=n, xyz=[round(v, 3) for v in xyz[n]])
    o = {}
    o["1_L2_LC11+12+13_min"] = mn(SETS["L2"], (11, 12, 13))
    o["1_nodes_5568_5569"] = {str(n): dict(xyz=[round(v, 3) for v in xyz[n]], uz_LC11_12_13=round(uz_sum(n, (11, 12, 13)), 2), uz_LC201=round(u(201)[n]["uz"], 2)) for n in (5568, 5569) if n in xyz}
    o["2_RF_LC12_min"] = mn(SETS["RF"], (12,))
    o["3_L1_LC11_min"] = mn(SETS["L1"], (11,))
    dat = cdb_path.replace(".cdb", ".dat")
    by_sln = sln_beams_geo(dat, INT + EXT, xyz, idx)
    def rel(s, lc):
        bl = by_sln.get(s)
        if not bl: return None
        cnt = collections.Counter(n for b in bl for n in idx[b]["nodes"]); ends = [n for n, c in cnt.items() if c == 1]
        if len(ends) != 2: return dict(sln=s, note=f"not a simple chain ({len(ends)} ends)")
        a, b = sorted(ends, key=lambda n: xyz[n][2]); ns = list(cnt)
        L = math.dist(xyz[a], xyz[b]); ua, ub = u(lc)[a]["uz"], u(lc)[b]["uz"]; best = None
        for n in ns:
            tt = sum((xyz[n][i] - xyz[a][i]) * (xyz[b][i] - xyz[a][i]) for i in range(3)) / L ** 2
            v = u(lc)[n]["uz"] - (ua + (ub - ua) * tt)
            if best is None or v < best[0]: best = (v, n)
        return dict(sln=s, rel_uz_mm=round(best[0], 2), node=best[1], L_m=round(L, 3), L_over=round(L * 1000 / abs(best[0])) if abs(best[0]) > 1e-6 else None,
                    ends=[a, b], z_ends=[round(xyz[a][2], 2), round(xyz[b][2], 2)], n_beams=len(bl))
    for lab, sl in (("4_internal_stair_LC201", INT), ("4_external_stair_flights_LC201", EXT)):
        rr = [r for r in (rel(s, 201) for s in sl) if r]
        o[lab] = dict(worst=min((r for r in rr if "rel_uz_mm" in r), key=lambda r: r["rel_uz_mm"], default=None), all=rr)
    cdb.close()
    return o


out = dict(what="Report deflection table, read only. uz in mm (down negative), unfactored basic LCs 11/12/13, SLS characteristic LC 201.",
           v21=run(r"C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.cdb"),
           v20=run(r"C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.cdb"))
json.dump(out, open(fr"{E}\A_followup\partA4_report_deflections.json", "w"), indent=1)
for v in ("v21", "v20"):
    o = out[v]; print(v)
    for k, x in o.items():
        print(" ", k, json.dumps(x.get("worst") if isinstance(x, dict) and "worst" in x else x))
