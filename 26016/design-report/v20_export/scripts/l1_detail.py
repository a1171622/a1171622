"""L1 group 15 detail (ring r 8.5, ring r 12, ring r 3, radials) for one model: BDK/AQB per input SLN, max |My|,|Mz| over ULS,
Mz at the ring ends at r 8.5 per joint angle, SLS relative deflection of ring and radial spans.
Run: py -3.11 l1_detail.py <cdb> <dat> <erg_parsed.json> <out.json>    (read only)"""
import sys, json, math, re, collections
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
CDB, DAT, ERGP, OUT = sys.argv[1:5]
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st)
d = cdbio.load_daten(info.get("daten")); cdb = cdbio.Cdb(CDB, info)
E = json.load(open(ERGP)); BDK = {int(k): v for k, v in E["bdk"].items()}; AQB = {int(k): v for k, v in E["aqb"].items()}
xyz = R._node_coords(cdb, d); ctx = R._beam_ctx(cdb, d); idx = ctx["idx"]
LCS = {l["lc"]: l for l in R.load_cases(cdb, d)}
have = lambda lc: lc in LCS and "nodes" in (LCS[lc].get("has_results") or [])
ULS = [lc for lc in range(101, 155) if have(lc)]; SLS = [lc for lc in range(201, 222) if have(lc)]
pol = lambda p: (math.hypot(p[0], p[1]), math.degrees(math.atan2(p[1], p[0])) % 360, p[2])
# input SLN geometry (group 15)
sl = {}; cur = None
for l in open(DAT, encoding="latin-1"):
    m = re.match(r"SLN\s+(\d+)\s+GRP\s+(\d+)", l)
    if m: cur = (int(m[1]), int(m[2])); continue
    if l.startswith("SLNB") and cur and cur[1] == 15:
        t = l.split(); a = [float(t[t.index("X1") + k]) for k in (1, 2, 3)]; b = [float(t[t.index("X2") + k]) for k in (1, 2, 3)]
        sl[cur[0]] = (a, b); cur = None
def onseg(p, a, b, tol=0.01):
    ab = [b[i] - a[i] for i in range(3)]; L2 = sum(v * v for v in ab); t = sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2
    return -1e-3 <= t <= 1.001 and math.dist([a[i] + t * ab[i] for i in range(3)], p) < tol
def kind(a, b):
    ra, rb = pol(a)[0], pol(b)[0]
    if abs(ra - rb) < 0.05:
        return {True: "ring85"}.get(abs(ra - 8.5) < 0.1) or ("ring12" if abs(ra - 12) < 0.2 else ("ring3" if abs(ra - 3) < 0.1 else "ring_other"))
    return "radial"
SLK = {s: kind(*ab) for s, ab in sl.items() if abs(ab[0][2] - 4.054) < 0.02 and abs(ab[1][2] - 4.054) < 0.02}
# beams of each input SLN
B = collections.defaultdict(list)
for bnr, v in idx.items():
    n1, n2 = v["nodes"]
    if n1 not in xyz or n2 not in xyz: continue
    p1, p2 = xyz[n1], xyz[n2]
    if abs(p1[2] - 4.054) > 0.02 or abs(p2[2] - 4.054) > 0.02: continue
    s = v["sln"] if v["sln"] in SLK else next((k for k, (a, b) in sl.items() if k in SLK and onseg(p1, a, b) and onseg(p2, a, b)), None)
    if s: B[s].append(bnr)
allb = sorted(b for bl in B.values() for b in bl); ws = set(allb)
# ULS envelopes per SLN and per ring end at r 8.5
env = {s: dict(My=(0, None), Mz=(0, None), N=(0, None)) for s in SLK}
endMz = {}   # (sln, end node) -> (|Mz| max, Mz, lc)
bsl = {b: s for s, bl in B.items() for b in bl}
for lc in ULS:
    rows = R.beam_forces(cdb, d, lc, beams=",".join(map(str, allb)), max_rows=10 ** 7)["rows"]
    by = collections.defaultdict(list)
    for r in rows:
        if r["beam"] not in ws: continue
        s = bsl[r["beam"]]; by[r["beam"]].append(r)
        for k in ("My", "Mz", "N"):
            if abs(r[k]) > abs(env[s][k][0]): env[s][k] = (r[k], lc)
    for bnr, rs in by.items():
        s = bsl[bnr]
        if SLK[s] != "ring85": continue
        rs.sort(key=lambda r: r["x"])
        for n, r in ((idx[bnr]["nodes"][0], rs[0]), (idx[bnr]["nodes"][1], rs[-1])):
            th = pol(xyz[n])[1]
            if abs(th / 20 - round(th / 20)) > 0.01: continue   # only ends at a joint (every 20 deg)
            k = (s, n)
            if k not in endMz or abs(r["Mz"]) > endMz[k][0]: endMz[k] = (abs(r["Mz"]), r["Mz"], r["My"], lc, round(th) % 360)
# SLS: relative deflection of each input SLN (span = SLN between its end points, all beams in it)
defl = {}
for lc in SLS:
    U = {r["node"]: r for r in R._node_rows(cdb, d, lc, None)}
    for s, bl in B.items():
        ns = sorted({n for b in bl for n in idx[b]["nodes"]}, key=lambda n: math.dist(xyz[n], sl[s][0]))
        a, b = ns[0], ns[-1]; L = math.dist(xyz[a], xyz[b])
        for n in ns[1:-1]:
            t = math.dist(xyz[n], xyz[a]) / L
            rel = U[n]["uz"] - ((1 - t) * U[a]["uz"] + t * U[b]["uz"])
            if s not in defl or abs(rel) > abs(defl[s]["rel"]):
                defl[s] = dict(rel=round(rel, 2), abs=round(U[n]["uz"], 2), node=n, lc=lc, L=round(L, 3), L_over=round(L * 1000 / abs(rel)) if rel else None)
aqbs = {}
for s, bl in B.items():
    best = None
    for b in bl:
        for r in AQB.get(b, []):
            if r["util"] is not None and (best is None or r["util"] > best["util"]): best = dict(r, beam=b)
    aqbs[s] = best
out = dict(cdb=CDB, ULS=ULS, SLS=SLS, slns={})
for s in sorted(SLK):
    a, b = sl[s]
    out["slns"][s] = dict(kind=SLK[s], th=[round(pol(a)[1], 1), round(pol(b)[1], 1)], r=[round(pol(a)[0], 2), round(pol(b)[0], 2)], beams=len(B[s]),
                          bdk=BDK.get(s), aqb=aqbs.get(s), My=env[s]["My"], Mz=env[s]["Mz"], N=env[s]["N"], sls=defl.get(s))
out["ring_end_Mz"] = [dict(sln=k[0], node=k[1], absMz=v[0], Mz=v[1], My=v[2], lc=v[3], joint_deg=v[4]) for k, v in sorted(endMz.items(), key=lambda kv: (kv[1][4], kv[0][0]))]
json.dump(out, open(OUT, "w"), indent=1, default=str)
print("slns", collections.Counter(SLK.values()), "ends", len(endMz), "unmapped beams?", sum(len(v) for v in B.values()))
cdb.close()
