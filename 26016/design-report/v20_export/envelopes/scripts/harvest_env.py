"""26016 v20 envelopes: read beam forces of the 47 ULS combinations and of the MAXIMA envelope cases from the COPY
26016_env_v20.cdb (read only), build the per-group envelope table with governing beam / x / combination, and the
sanity check (MAXIMA envelope LC vs scan of the combinations at every station).
Run: py -3.11 harvest_env.py
Writes: ../env_table_ULS.csv/.json, ../env_table_SLS.csv/.json, ../sanity_check.json, ../model_beams.json"""
import sys, os, json, csv, math
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config

CDB = r"C:\Sofistik workflow\26016-member-check\v20\envelopes\26016_env_v20.cdb"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ULS = list(range(101, 131)) + [135] + list(range(141, 149)) + list(range(151, 155))
SLS = list(range(201, 222))
COMPS = ["N", "Vy", "Vz", "Mt", "My", "Mz"]
ENV_ULS = {c: (4321 + 2 * i, 4322 + 2 * i) for i, c in enumerate(COMPS)}   # MAXD / MIND
ENV_SLS = {c: (4421 + 2 * i, 4422 + 2 * i) for i, c in enumerate(COMPS)}

st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json")
info = install.find(st)
d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(CDB, info)
ctx = R._beam_ctx(cdb, d)
idx = ctx["idx"]
SECT = {s["nr"]: s["title"] for s in R.sections(cdb, d)}
import re
DAT = r"C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.dat"
SLN_SNO = {}
for l in open(DAT, encoding="latin-1"):
    m = re.match(r"SLN\s+(\d+)\s.*?GRP\s+(\d+).*?SNO\s+(\d+)", l)
    if m: SLN_SNO[int(m[1])] = (int(m[2]), int(m[3]))
GRP_SECT = {}
for s, (g, n) in SLN_SNO.items(): GRP_SECT.setdefault(g, set()).add(n)
DESC = {11: "V-column rakers, ground to L1", 12: "rakers, ground to L1", 13: "vertical columns (ground-L1, L1-L2)",
        14: "vertical columns, ground to L1", 15: "Level 1 framing (radials + rings)", 21: "V-column rakers, L1 to L2",
        23: "vertical columns, L1 to L2", 24: "vertical columns, L1 to L2", 25: "Level 2 framing (radials + rings)",
        31: "V-column rakers, L2 to roof", 35: "roof framing (radials + rings)", 60: "internal stair (stringers, landing, treads)",
        61: "internal stair landing posts", 62: "external stair ground to L1"}
xyz = R._node_coords(cdb, d)
grp = {nr: R._group_of(nr, ctx["groups"], ctx["gdiv"], ctx["sln_groups"].get(v.get("sln"))) for nr, v in idx.items()}
if any(g is None for g in grp.values()):
    grp = {nr: (g if g is not None else R._range_group(nr, ctx["groups"])) for nr, g in grp.items()}


def read_lc(lc):
    rows = {}
    for rec in cdb.records(102, lc):
        if R.first_int(rec) <= 0:
            continue
        f = R.as_rec(d, "CBEAM_FOR", rec)
        key = (int(f.m_nr), round(float(f.m_x), 4))
        rows[key] = [float(f.m_n), float(f.m_vy), float(f.m_vz), float(f.m_mt), float(f.m_my), float(f.m_mz)]
    if hasattr(cdb, "forget"):
        cdb.forget(102, lc)
    return rows


def scan(lcs):
    """per station: max/min value and governing LC of each component over lcs"""
    mx, mn = {}, {}
    for lc in lcs:
        rows = read_lc(lc)
        print("read", lc, len(rows), flush=True)
        for k, v in rows.items():
            a = mx.setdefault(k, [(-1e30, 0)] * 6); b = mn.setdefault(k, [(1e30, 0)] * 6)
            for i in range(6):
                if v[i] > a[i][0]: a[i] = (v[i], lc)
                if v[i] < b[i][0]: b[i] = (v[i], lc)
    return mx, mn


def table(mx, mn, env, tag):
    # sanity: envelope LC value at each station vs scan
    envv = {}
    worst = {c: 0.0 for c in COMPS}
    for i, c in enumerate(COMPS):
        lmax, lmin = env[c]
        rmax, rmin = read_lc(lmax), read_lc(lmin)
        envv[c] = (rmax, rmin)
        for k in mx:
            if k in rmax: worst[c] = max(worst[c], abs(rmax[k][i] - mx[k][i][0]))
            if k in rmin: worst[c] = max(worst[c], abs(rmin[k][i] - mn[k][i][0]))
    groups = sorted({grp[b] for b, _ in mx})
    out = []
    for g in groups:
        keys = [k for k in mx if grp[k[0]] == g]
        bl = sorted({k[0] for k in keys})
        secs = [SECT.get(n, str(n)) for n in sorted(GRP_SECT.get(g, []))]
        slns = sorted({idx[b]["sln"] for b in bl if idx[b]["sln"]})
        row = {"group": g, "description": DESC.get(g, ""), "sections": "; ".join(secs), "n_beam_elements": len(bl), "n_sln": len(slns)}
        for i, c in enumerate(COMPS):
            kmax = max(keys, key=lambda k: mx[k][i][0]); kmin = min(keys, key=lambda k: mn[k][i][0])
            for tagm, k, rec in (("max", kmax, mx[kmax][i]), ("min", kmin, mn[kmin][i])):
                row[f"{c}_{tagm}"] = round(rec[0], 2)
                row[f"{c}_{tagm}_beam"] = k[0]
                row[f"{c}_{tagm}_sln"] = idx[k[0]]["sln"]
                row[f"{c}_{tagm}_x"] = k[1]
                row[f"{c}_{tagm}_lc"] = rec[1]
                e = envv[c][0 if tagm == "max" else 1].get(k)
                row[f"{c}_{tagm}_maxima_lc_value"] = None if e is None else round(e[i], 2)
        out.append(row)
    with open(os.path.join(OUT, f"env_table_{tag}.json"), "w") as f:
        json.dump({"source": CDB, "load_cases": env, "combinations": ULS if tag == "ULS" else SLS,
                   "units": "N, Vy, Vz kN; Mt, My, Mz kNm; x m from beam start; local beam axes, N > 0 tension",
                   "max_abs_diff_maxima_vs_scan_all_stations": worst, "groups": out}, f, indent=1)
    with open(os.path.join(OUT, f"env_table_{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    return out, worst, envv


mxU, mnU = scan(ULS)
tabU, worstU, envU = table(mxU, mnU, ENV_ULS, "ULS")
print("ULS worst diff", worstU)

# sanity check members: SLN 56 (L2 r 12 ring), one column, one stair stringer
def member_check(sln_or_beams, label):
    bl = [b for b in idx if idx[b]["sln"] == sln_or_beams] if isinstance(sln_or_beams, int) else sln_or_beams
    keys = [k for k in mxU if k[0] in bl]
    res = {"label": label, "beams": sorted(bl), "group": grp[bl[0]], "section": SECT.get(SLN_SNO.get(idx[bl[0]]["sln"], (0, 5 if grp[bl[0]] == 60 else 0))[1])}
    for c in ("My", "N"):
        i = COMPS.index(c)
        km = max(keys, key=lambda k: mxU[k][i][0]); kn = min(keys, key=lambda k: mnU[k][i][0])
        em = max(envU[c][0][k][i] for k in keys); en = min(envU[c][1][k][i] for k in keys)
        res[c] = {"scan_max": round(mxU[km][i][0], 3), "scan_max_lc": mxU[km][i][1], "scan_max_at": [km[0], km[1]],
                  "maxima_max": round(em, 3),
                  "scan_min": round(mnU[kn][i][0], 3), "scan_min_lc": mnU[kn][i][1], "scan_min_at": [kn[0], kn[1]],
                  "maxima_min": round(en, 3)}
    return res

def sln_of_group(g, pick):
    s = sorted({idx[b]["sln"] for b in idx if grp[b] == g and idx[b]["sln"]})
    return pick(s)

checks = [member_check(56, "SLN 56 (named in the brief: group 25, L2 outer ring r 12)"), member_check(227, "SLN 227 (L1 ring r 8.5, 340-360 deg, group 15)")]
col_sln = 0
for g in (13, 14):
    s = sorted({idx[b]["sln"] for b in idx if grp[b] == g and idx[b]["sln"]})
    if s: col_sln = s[0]; break
checks.append(member_check(col_sln, f"column SLN {col_sln}"))
# stair stringer: SLN 722 (group 62, BDK 1.013) per RESULTS_v20
checks.append(member_check([b for b in idx if idx[b]["sln"] in range(1454, 1464)], "internal stair upper-flight stringer, z 6.28-8.05 m, y about -9.4 (analysis lines 1454-1463, group 60)"))
json.dump({"ULS_worst_station_diff": worstU, "members": checks}, open(os.path.join(OUT, "sanity_check.json"), "w"), indent=1)
print(json.dumps(checks, indent=1))

mxS, mnS = scan(SLS)
tabS, worstS, _ = table(mxS, mnS, ENV_SLS, "SLS")
print("SLS worst diff", worstS)

# model data for drawing / labels
beams = {b: {"sln": v["sln"], "group": grp[b], "section": v["section"], "nodes": v["nodes"]} for b, v in idx.items()}
json.dump({"beams": beams, "nodes": {n: xyz[n] for b in idx.values() for n in b["nodes"] if n in xyz},
           "sections": SECT}, open(os.path.join(OUT, "scripts", "model_beams.json"), "w"))
print("done")



