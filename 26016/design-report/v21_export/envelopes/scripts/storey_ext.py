"""Per-storey extremes of the vertical members (groups 11-31) from the MAXIMA envelope LCs (read only, COPY cdb)
and of the L1 r 8.5 ring. Writes storey_ext.json: {storey: {Q: [max, min]}} for the label threshold and scale."""
import sys, os, json
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
HERE = os.path.dirname(os.path.abspath(__file__))
CDB = r"C:\Sofistik workflow\26016-member-check\v21\envelopes\26016_env_v21.cdb"
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json")
info = install.find(st); d = cdbio.load_daten(info.get("daten")); cdb = cdbio.Cdb(CDB, info)
m = json.load(open(os.path.join(HERE, "model_beams.json"))); B = m["beams"]; N = m["nodes"]
VERT = {11, 12, 13, 14, 21, 23, 24, 31}
ST = {"G-L1": (-1, 4.10), "L1-L2": (4.00, 8.10), "L2-RF": (8.00, 12.5)}
RING = {185, 264, 265, 189, 192, 195, 198, 210, 213, 214, 217, 218, 221, 426, 425, 225, 226, 227}
def where(b):
    v = B[str(b)]
    if v["sln"] in RING: return ["ring85"]
    if v["group"] not in VERT: return []
    z = [N[str(n)][2] for n in v["nodes"]]
    return [s for s, (a, c) in ST.items() if a <= min(z) and max(z) <= c]
Q = {"N": (4321, 4322, 0), "MY": (4329, 4330, 4), "MZ": (4331, 4332, 5)}
out = {}
for q, (lmax, lmin, i) in Q.items():
    for lc, k in ((lmax, 0), (lmin, 1)):
        for rec in cdb.records(102, lc):
            if R.first_int(rec) <= 0: continue
            f = R.as_rec(d, "CBEAM_FOR", rec)
            v = [f.m_n, f.m_vy, f.m_vz, f.m_mt, f.m_my, f.m_mz][i]
            for s in where(int(f.m_nr)):
                e = out.setdefault(s, {}).setdefault(q, [-1e30, 1e30])
                e[k] = max(e[k], v) if k == 0 else min(e[k], v)
json.dump(out, open(os.path.join(HERE, "storey_ext.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
