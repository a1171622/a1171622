"""PART_A_v19m.md: the Part A follow-up numbers for v19m, with the v19 value beside each (same sections as PART_A_v19.md).
Run from v19m_export/A_followup:  py -3.11 scripts/part_a_md.py"""
import json, os
A = r"C:\Sofistik workflow\26016-design-report\v19_export\A_followup"
B = r"C:\Sofistik workflow\26016-design-report\v19m_export\A_followup"
J = lambda d, f: json.load(open(os.path.join(d, f)))
a1, b1 = J(A, "partA1.json"), J(B, "partA1.json")
a2, b2 = J(A, "partA2.json"), J(B, "partA2.json")
a3, b3 = J(A, "partA3.json"), J(B, "partA3.json")
s19 = json.load(open(r"C:\Sofistik workflow\26016-design-report\v19_export\reactions_basic_sums.json"))
s19m = json.load(open(r"C:\Sofistik workflow\26016-design-report\v19m_export\reactions_basic_sums.json"))
o = []
P = o.append
P("# 26016 v19m - Part A follow-up numbers (read-only, 13 Nov 2026)")
P("Source: 26016_check_v19m.cdb / .erg (v19 + MZ released at the 18 L1 r 8.5 ring ends of the A/B joints). Read only, no calculation started.")
P("Each line: v19m value, then [v19 value]. Same scripts as the v19 Part A (partA.py, partA2.py, partA3.py), paths moved to v19m. Units kN, kNm, mm, m.")
P("")
P("## A1 BDK max per group - util | SLN | LC  [v19]")
for g in sorted(b1["A1"], key=lambda k: (len(k), k)):
    x, y = b1["A1"][g], a1["A1"].get(g, {})
    P(f"{g}: {x['util']:.3f} | {x['sln']} | {x['lc']} {x['check'] if x['util'] > 1 else ''}  [{y.get('util')} | {y.get('sln')} | {y.get('lc')}]")
P("")
P("## A2 AQB max per section - util | beam | group | SLN | LC  [v19]")
for s in sorted(b2_ := b1["A2"], key=int):
    x, y = b1["A2"][s], a1["A2"].get(s, {})
    P(f"SNO {s}: {x['util']:.3f} | {x['beam']} | {x['group']} | {x['sln']} | {x['lc']}  [{y.get('util')} | {y.get('beam')} | {y.get('lc')}]")
P("")
P("## A3 Buckling (lowest eigenmodes)")
for lc in ("9201", "9220", "9221", "9240"):
    x, y = b1["A3"].get(lc), a1["A3"].get(lc)
    if not isinstance(x, dict):
        continue
    P(f"LC {lc} ({b1['A3titles'].get(lc)}) [v19: {a1['A3titles'].get(lc)}]: max node {x['node']} r {x['r_theta_z'][0]:.2f} at {x['r_theta_z'][1]:.1f} deg z {x['r_theta_z'][2]:.2f} "
          f"[v19 node {y['node']}]; groups with > 10 % of the max: " + ", ".join(f"{g} {v}" for g, v in x["gmax_rel"].items() if v > 0.1))
P("")
P("## A4 SLS deflections ('rel' = relative to the straight line between span ends, 'abs' = global uz; down negative)  [v19]")
def dl(k, lab):
    x, y = b2.get(k), a2.get(k)
    if isinstance(x, list):
        x, y = x[0], (y or [{}])[0]
    if not x:
        return
    P(f"{lab}: rel {x.get('rel')} at node {x.get('rel_node')} / abs {x.get('uz_abs_at_rel')} (span {x.get('span')}, L {x.get('L')}, LC {x.get('lc')})"
      f"  [{(y or {}).get('rel')} / {(y or {}).get('uz_abs_at_rel')}]")
dl("a_201", "(a) L1 ring r 12, LC 201"); dl("a_GQpsiW", "(a) L1 ring r 12, G+Q+0.5W worst"); dl("a_LC11", "(a) L1 ring r 12, LC 11 only")
dl("b_201", "(b) L2 radial, LC 201"); dl("b_Q", "(b) L2 radial, LC 11+12+13"); dl("b_abs201", "(b) L2 radial largest abs, LC 201")
dl("c_201", "(c) roof radial, LC 201"); dl("c_Q12", "(c) roof radial, LC 12"); dl("c_up_GW", "(c) roof radial upward G+W")
for k in ("d_L1", "d_L2", "d_RF"):
    x, y = b2[k], a2[k]
    P(f"(d) max horizontal {k[2:]}: {x['uh']} mm node {x['node']} LC {x['lc']}  [{y['uh']} node {y['node']} LC {y['lc']}]")
dl("e_280_201_spans", "(e) L1 radial 280 deg r 8.5-12 under the landing posts, LC 201"); dl("e_40_201_spans", "(e) L1 radial 40 deg r 8.5-12, LC 201")
dl("f_stringers_SLSenv_worst", "(f) internal stair stringer, SLS envelope worst")
P("")
P("## A5 Support reactions (force of the support on the structure, pz + = compression)")
P("node | r (m) angle (deg) | 102 px | py | pz [v19 pz] | 201 pz | EQU min pz (LC)")
R19 = {r["node"]: r for r in a3["rows"]}
for r in b3["rows"]:
    y = R19.get(r["node"], {})
    loc = f"{r['r']:.2f} {r['th']:.1f}" if r["node"] < 900 or r["node"] > 1000 else f"x {r['x']:.2f} y {r['y']:.2f}"
    P(f"{r['node']} | {loc} | {r['px']:.1f} | {r['py']:.1f} | {r['pz']:.1f} [{y.get('pz', float('nan')):.1f}] | {r['pz201']:.1f} | {r['eq'][0]:.1f} ({r['eq'][1]})")
P(f"Grand total 102: {b3['tot102']} [v19 {a3['tot102']}]; SOFiSTiK stored {b3.get('stored102')}. Grand total 201 pz: {b3['tot201']} [v19 {a3['tot201']}].")
P("")
P("## A6 reactions_basic_sums (sum Fx, Fy, Fz)  [v19 Fz]")
y = {r["lc"]: r for r in s19["load_cases"]}
for r in s19m["load_cases"]:
    P(f"LC {r['lc']} {r['title']}: {r['sum_Fx']:.1f}, {r['sum_Fy']:.1f}, {r['sum_Fz']:.1f}  [{y[r['lc']]['sum_Fz']:.1f}]")
P("")
P("## A7 ULS reaction envelope, STR only (101-154 without 131-134)  [v19]")
for k, lab in (("max", "max pz"), ("min", "min pz"), ("hmax", "max horizontal resultant")):
    x, yy = b3["A7"][k], a3["A7"][k]
    P(f"{lab}: {x[0]:.1f} node {x[1]} LC {x[2]}  [{yy[0]:.1f} node {yy[1]} LC {yy[2]}]")
P("")
P("## A8 L2 outer ring SLN 56, LC 120, forces at the radial nodes  [v19]")
for n in ("1460", "1485"):
    for x in b3["A8_nodes"].get(n, []):
        yy = next((z for z in a3["A8_nodes"].get(n, []) if z["sln"] == x["sln"]), {})
        P(f"node {n} beam SLN {x['sln']}: N {x['N']:+.1f}, Vz {x['Vz']:+.1f}, My {x['My']:+.1f}, Mz {x['Mz']:+.2f}  [My {yy.get('My')}, Mz {yy.get('Mz')}]")
open(os.path.join(B, "PART_A_v19m.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("\n".join(o[:40]))
