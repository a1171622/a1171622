"""26016 v21 kingpost von Mises check (read only on the COPY 26016_env_v21.cdb; nothing re-analysed).
Shell groups 6 + 7 (tube wall, r 0.305, t 20), 1 (horizontal collar / cap plates), 2 (vertical radial fin plates), S275, t 20.
For each element and each load case: stresses from the ASE shell forces (key 210/LC, CQUAD_FOR):
  membrane  s = n / t,  bending s = 6 m / t^2,  top / bottom = membrane +- bending, mid = membrane;
  sigma_v = sqrt(sx^2 + sy^2 - sx sy + 3 txy^2)   (transverse shear vx, vy neglected: zero at the faces).
'element' = forces at the element centre (averaged over the element); 'gauss' = largest of the 4 Gauss points (raw peak, m_sg).
fy = 275 MPa (S275, t = 20 <= 40 mm, EN 10025-2), gamma_M0 = 1.0.
py -3.11 kp_vonmises.py  -> ../kingpost_von_mises_v21.json / .csv"""
import sys, os, json, math, csv, collections, bisect
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
from sofistik_mcp.results import as_rec
CDB = r"C:\Sofistik workflow\26016-member-check\v21\envelopes\26016_env_v21.cdb"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ULS = list(range(101, 131)) + [135] + list(range(141, 149)) + list(range(151, 155))
SLS = [201]
FY = 275.0
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st); d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(CDB, info)
xyz = R._node_coords(cdb, d)
G = sorted({(g["min_element"], g["group"]) for g in R.groups(cdb, d) if g["min_element"] > 0}); starts = [s for s, _ in G]
eg = lambda nr: G[bisect.bisect_right(starts, nr) - 1][1]
TITLE = {l["lc"]: l["title"] for l in R.load_cases(cdb, d)}
Q = {}
for rec in cdb.records(200, 0):
    o = as_rec(d, "CQUAD", rec)
    if o.m_nr > 0 and eg(o.m_nr) in (1, 2, 6, 7):
        ps = [xyz[n] for n in o.m_node if n in xyz]
        c = [sum(p[i] for p in ps) / len(ps) for i in range(3)]
        Q[o.m_nr] = dict(grp=eg(o.m_nr), t=float(o.m_thick[0]), c=c, nodes=list(o.m_node))


def zone(e):
    q = Q[e]; z = q["c"][2]; g = q["grp"]
    if g in (6, 7):
        if z < 0.5: return "tube wall, base zone (z 0-0.5)"
        if 7.4 <= z <= 8.7: return "tube wall, Level 2 connection zone (z 7.4-8.7)"
        if z >= 11.5: return "tube wall, roof connection zone (z > 11.5)"
        return "tube wall, between levels"
    lev = "Level 2" if z < 10 else "roof"
    return ("horizontal collar / cap plates, " if g == 1 else "vertical radial fin plates, ") + lev


def vm(sx, sy, t): return math.sqrt(max(sx * sx + sy * sy - sx * sy + 3 * t * t, 0.0))


def surf(mxx, myy, mxy, nx, ny, nxy, t):
    sm = (nx / t, ny / t, nxy / t); sb = (6 * mxx / t ** 2, 6 * myy / t ** 2, 6 * mxy / t ** 2)
    top = vm(sm[0] + sb[0], sm[1] + sb[1], sm[2] + sb[2]); bot = vm(sm[0] - sb[0], sm[1] - sb[1], sm[2] - sb[2]); mid = vm(*sm)
    return {"top": top / 1e3, "bottom": bot / 1e3, "mid": mid / 1e3}   # forces in kN/m, kNm/m (CDB units) -> kN/m2 -> MPa


best = {}            # (zone, kind) -> record
per_el = collections.defaultdict(lambda: dict(v=0.0))   # element max (element-centre), ULS
lc_max = {}
for lc in ULS + SLS:
    if cdb.kexist(210, lc) < 2: print("no quad forces for", lc); continue
    lmax = (0, None)
    for rec in cdb.records(210, lc):
        o = as_rec(d, "CQUAD_FOR", rec)
        e = o.m_nr
        if e not in Q: continue
        t = Q[e]["t"]
        s = surf(o.m_mxx, o.m_myy, o.m_mxy, o.m_nx, o.m_ny, o.m_nxy, t)
        gs = []
        for gp in range(4):
            v = [o.m_sg[gp][k] for k in range(8)]     # mxx myy mxy vx vy nx ny nxy at the Gauss point
            gs.append(max(surf(v[0], v[1], v[2], v[5], v[6], v[7], t).values()))
        gpk = max(gs)
        kind = "SLS" if lc in SLS else "ULS"
        zn = zone(e)
        sk, sv = max(s.items(), key=lambda kv: kv[1])
        for key, val, srf in (("element", sv, sk), ("gauss", gpk, "max of top/bottom/mid at a Gauss point")):
            k = (zn, kind, key)
            if k not in best or val > best[k]["sigma_v_MPa"]:
                c = Q[e]["c"]
                best[k] = dict(zone=zn, check=kind, value=key, sigma_v_MPa=round(val, 1), element=e, group=Q[e]["grp"], t_mm=round(t * 1000, 1),
                               surface=srf, z_m=round(c[2], 3), angle_deg=round(math.degrees(math.atan2(c[1], c[0])) % 360, 1),
                               r_m=round(math.hypot(c[0], c[1]), 3), lc=lc, lc_title=TITLE.get(lc), fy_MPa=FY, util=round(val / FY, 3),
                               surfaces_MPa={kk: round(vv, 1) for kk, vv in s.items()} if key == "element" else None)
        if kind == "ULS" and sv > per_el[e]["v"]: per_el[e] = dict(v=sv, lc=lc, surface=sk)
        if sv > lmax[0]: lmax = (sv, e)
    lc_max[lc] = dict(max_element_sigma_v=round(lmax[0], 1), element=lmax[1])
    print(lc, lc_max[lc], flush=True)
cdb.close()
rows = sorted(best.values(), key=lambda r: (r["check"], r["zone"], r["value"]))
gov = max((r for r in rows if r["check"] == "ULS" and r["value"] == "element"), key=lambda r: r["sigma_v_MPa"])
above = sorted(((e, v) for e, v in per_el.items() if v["v"] > FY), key=lambda kv: -kv[1]["v"])
res = dict(what="26016 v21 kingpost shells, von Mises equivalent stress from the ASE shell forces of the 43 ULS STR combinations (101-130, 135, 141-148, "
                "151-154) and SLS 201; read only from 26016_env_v21.cdb (copy of 26016_check_v21.cdb).",
           method=__doc__, fy_MPa=FY, gamma_M0=1.0, governing_ULS=gov,
           elements_above_fy_ULS=[dict(element=e, sigma_v=round(v["v"], 1), lc=v["lc"], surface=v["surface"], z=round(Q[e]["c"][2], 3),
                                       group=Q[e]["grp"]) for e, v in above[:50]],
           n_elements={g: sum(1 for q in Q.values() if q["grp"] == g) for g in (1, 2, 6, 7)}, rows=rows, lc_max=lc_max)
json.dump(res, open(os.path.join(OUT, "kingpost_von_mises_v21.json"), "w"), indent=1)
with open(os.path.join(OUT, "kingpost_von_mises_v21.csv"), "w", newline="") as f:
    cols = ["check", "zone", "value", "sigma_v_MPa", "util", "fy_MPa", "t_mm", "element", "group", "surface", "z_m", "angle_deg", "r_m", "lc", "lc_title"]
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
print("governing", gov); print("above fy (element centre):", len(above))
json.dump({str(e): round(v["v"], 1) for e, v in per_el.items()}, open(os.path.join(OUT, "scripts", "per_element_max_ULS.json"), "w"))
