"""RESULTS_v19m.md + compare_v19_v19m.csv + flags_v19m.json from the v19 and v19m exports (read only).
py -3.11 make_results.py <run_checks.json>"""
import json, os, sys, csv
V = r"C:\Sofistik workflow\26016-design-report"
A, B = os.path.join(V, "v19_export"), os.path.join(V, "v19m_export")
J = lambda *p: json.load(open(os.path.join(*p)))
RUN = J(sys.argv[1])
s19, s19m = J(A, "summary_v19.json"), J(B, "summary_v19m.json")
r19, r19m = J(A, "ring_L2.json"), J(B, "ring_L2.json")
b19, b19m = J(A, "reactions_basic_sums.json"), J(B, "reactions_basic_sums.json")
a3_19, a3_19m = J(A, "A_followup", "partA3.json"), J(B, "A_followup", "partA3.json")
l19, l19m = J(B, "compare_v19", "l1_detail_v19.json"), J(B, "l1_detail_v19m.json")
e19, e19m = J(B, "compare_v19", "erg_parsed.json"), J(B, "scripts", "erg_parsed.json")
model = J(B, "scripts", "model.json")
bsln = {int(k): v.get("sln") for k, v in model["beams"].items()}
f3 = lambda x: "-" if x is None else f"{x:.3f}"
d3 = lambda a, b: "-" if a is None or b is None else f"{b - a:+.3f}"
out = []
P = out.append
P("# 26016 v19m results: MZ released at the L1 r 8.5 ring ends of the A/B joints")
P("")
P("v19m = v19 with FIXA/FIXE 'MY' -> 'MYMZ' at the 18 Level 1 ring ends (group 15, r 8.5 m) that frame into the radial web "
  "at the 9 A/B joints (0, 40, 80, 120, 160, 200, 240, 280, 320 deg; flange plates removed, Wing 13 Nov 2026). "
  "Nothing else changed (diff to v19 = 18 lines + 2 header comment lines). Plan of the released ends: `v19m_released_ends_plan.png`.")
P("")
P("Joint types in the v19 geometry: since v17a (Wing, 6 Nov 2026) the L1-L2 column at r 8.5 stands at 40 deg (SLN 121) and 60 deg (SLN 131), "
  "no longer at 60 and 80 deg. So the joint with a column above (B layout) is at 40 and 280 deg, and 80 deg is an A layout (column below only). "
  "The v15 names (A_040, B_080) are older than that move. The released ends are the same 18 either way.")
P("")
P("## Run checks")
P("")
P("| item | v19 | v19m |")
P("|---|---|---|")
for k, (x, y) in RUN["table"].items():
    P(f"| {k} | {x} | {y} |")
P("")
P("## Global")
P("")
P("| item | v19 | v19m | change |")
P("|---|---|---|---|")
for plc in ("102", "119"):
    t1, t2 = s19["buckling"][plc]["title"], s19m["buckling"][plc]["title"]
    v1, v2 = float(t1.split()[-1]), float(t2.split()[-1])
    P(f"| alpha_cr PLC {plc} (lowest mode, LC {s19m['buckling'][plc]['lowest_lc']}) | {v1:.2f} | {v2:.2f} | {v2 - v1:+.2f} |")
P(f"| sum reactions LC 102 px, py, pz (kN) | {a3_19['tot102']} | {a3_19m['tot102']} | |")
P(f"| sum reactions LC 201 pz (kN) | {a3_19['tot201']} | {a3_19m['tot201']} | {a3_19m['tot201'] - a3_19['tot201']:+.1f} |")
P(f"| SOFiSTiK stored sum LC 102 / 201 | {a3_19.get('stored102')} / {a3_19.get('stored201')} | {a3_19m.get('stored102')} / {a3_19m.get('stored201')} | |")
for k, lab in (("max", "ULS STR max pz (kN, node, LC)"), ("min", "ULS STR min pz (kN, node, LC)"), ("hmax", "ULS STR max horizontal (kN, node, LC)")):
    fa = [round(x, 1) if isinstance(x, float) else x for x in a3_19["A7"][k][:3]]
    fb = [round(x, 1) if isinstance(x, float) else x for x in a3_19m["A7"][k][:3]]
    P(f"| {lab} | {fa} | {fb} | |")
P("")
P("Basic load case reaction sums, sum Fz (kN):")
P("")
x1 = {v["lc"]: v["sum_Fz"] for v in b19["load_cases"]}
x2 = {v["lc"]: v["sum_Fz"] for v in b19m["load_cases"]}
P("| LC | v19 | v19m |")
P("|---|---|---|")
for k in x1:
    P(f"| {k} | {x1[k]:.1f} | {x2.get(k, float('nan')):.1f} |")
P("")
P("## Maximum BDK and AQB per group")
P("")
P("| group | BDK v19 (SLN, LC) | BDK v19m (SLN, LC) | change | AQB v19 (SLN, LC) | AQB v19m (SLN, LC) | change |")
P("|---|---|---|---|---|---|---|")
for g in sorted(set(s19["groups"]) | set(s19m["groups"]), key=int):
    a, b = s19["groups"].get(g, {}), s19m["groups"].get(g, {})
    P(f"| {g} | {f3(a.get('bdk_max'))} ({a.get('bdk_sln')}, {a.get('bdk_lc')}) | {f3(b.get('bdk_max'))} ({b.get('bdk_sln')}, {b.get('bdk_lc')}) "
      f"| {d3(a.get('bdk_max'), b.get('bdk_max'))} | {f3(a.get('aqb_max'))} ({a.get('aqb_sln')}, {a.get('aqb_lc')}) "
      f"| {f3(b.get('aqb_max'))} ({b.get('aqb_sln')}, {b.get('aqb_lc')}) | {d3(a.get('aqb_max'), b.get('aqb_max'))} |")
P("")


def l1rows(kind):
    for s in sorted(l19m["slns"], key=lambda s: (min(l19m["slns"][s]["th"]), int(s))):
        if l19m["slns"][s]["kind"] == kind:
            yield s, l19["slns"].get(s, {}), l19m["slns"][s]


def U(v, k):
    return (v.get(k) or {}).get("util")


for kind, title in (("ring85", "L1 ring r 8.5 (group 15, UB 254, 20 deg segments)"), ("radial", "L1 radials (group 15)")):
    P(f"## {title}")
    P("")
    P("Max |My|, |Mz| over ULS 101-154 (kNm, LC). BDK = max(nm-y, nm-z) per input SLN (radials: BDK id per member as in v19, '-' = no BDK id). "
      "AQB = max station utilisation of the SLN's beams. SLS = largest deflection relative to the line between the SLN end nodes, SLS 201-221 (mm, L/x).")
    P("")
    P("| SLN | deg | r m | My v19 | My v19m | Mz v19 | Mz v19m | BDK v19 | BDK v19m | AQB v19 | AQB v19m | SLS v19 | SLS v19m |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s, a, b in l1rows(kind):
        sa, sb = a.get("sls") or {}, b.get("sls") or {}
        P(f"| {s} | {b['th'][0]:.0f}-{b['th'][1]:.0f} | {b['r'][0]}-{b['r'][1]} | {abs(a['My'][0]):.1f} ({a['My'][1]}) | {abs(b['My'][0]):.1f} ({b['My'][1]}) "
          f"| {abs(a['Mz'][0]):.2f} ({a['Mz'][1]}) | {abs(b['Mz'][0]):.2f} ({b['Mz'][1]}) | {f3(U(a, 'bdk'))} | {f3(U(b, 'bdk'))} "
          f"| {f3(U(a, 'aqb'))} | {f3(U(b, 'aqb'))} | {sa.get('rel')} (L/{sa.get('L_over')}) | {sb.get('rel')} (L/{sb.get('L_over')}) |")
    P("")
P("## Ring r 8.5: Mz at the ring ends at each joint (max |Mz| over ULS 101-154, kNm, local ring axes)")
P("")
P("| joint deg | joint | ring SLN | v19 Mz (LC) | v19m Mz (LC) |")
P("|---|---|---|---|---|")
m19 = {(r["sln"], r["joint_deg"]): r for r in l19["ring_end_Mz"]}
for r in l19m["ring_end_Mz"]:
    j = r["joint_deg"]
    t = "B, released" if j in (40, 280) else ("A, released" if j % 40 == 0 else "S/T, unchanged")
    a = m19.get((r["sln"], j), {})
    P(f"| {j:03d} | {t} | {r['sln']} | {a.get('Mz', 0):+.2f} ({a.get('lc')}) | {r['Mz']:+.2f} ({r['lc']}) |")
P("")
P("## L2 outer ring r 12, SLN 56 / 57 / 62")
P("")
P("| SLN | BDK v19 (LC) | BDK v19m (LC) | AQB v19 (LC) | AQB v19m (LC) | node-end My v19 | node-end My v19m | My at 300 mm v19 | My at 300 mm v19m |")
P("|---|---|---|---|---|---|---|---|---|")
M19 = {m["sln"]: m for m in r19["members"]}
M19m = {m["sln"]: m for m in r19m["members"]}
for s in (56, 57, 62):
    a, b = M19.get(s, {}), M19m.get(s, {})
    na, nb = a.get("node_end") or {}, b.get("node_end") or {}
    ma, mb = (a.get("My_at_300mm_from_node") or {}).get("value"), (b.get("My_at_300mm_from_node") or {}).get("value")
    P(f"| {s} | {f3(a['bdk']['util'])} ({a['bdk']['lc']}) | {f3(b['bdk']['util'])} ({b['bdk']['lc']}) | {f3(a['aqb']['util'])} ({a['aqb']['lc']}) "
      f"| {f3(b['aqb']['util'])} ({b['aqb']['lc']}) | {na.get('My')} | {nb.get('My')} | {ma} | {mb} |")
P("")
rows = []
B1, B2 = {int(k): v for k, v in e19["bdk"].items()}, {int(k): v for k, v in e19m["bdk"].items()}
for i in sorted(set(B1) | set(B2)):
    rows.append(("BDK", i, i, (B1.get(i) or {}).get("util"), (B2.get(i) or {}).get("util"), (B1.get(i) or {}).get("lc"), (B2.get(i) or {}).get("lc")))


def amax(d):
    o = {}
    for b, recs in d.items():
        best = max((r for r in recs if r["util"] is not None), key=lambda r: r["util"], default=None)
        if best:
            o[int(b)] = best
    return o


Q1, Q2 = amax(e19["aqb"]), amax(e19m["aqb"])
for b in sorted(set(Q1) | set(Q2)):
    rows.append(("AQB", b, bsln.get(b), (Q1.get(b) or {}).get("util"), (Q2.get(b) or {}).get("util"), (Q1.get(b) or {}).get("lc"), (Q2.get(b) or {}).get("lc")))
with open(os.path.join(B, "compare_v19_v19m.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "id (BDK: SLN, AQB: beam)", "sln", "util_v19", "util_v19m", "delta", "lc_v19", "lc_v19m"])
    for r in rows:
        w.writerow(list(r[:5]) + [None if r[3] is None or r[4] is None else round(r[4] - r[3], 3)] + list(r[5:]))
worse = sorted([r for r in rows if r[3] is not None and r[4] is not None and r[4] - r[3] > 0.02], key=lambda r: -(r[4] - r[3]))
better = sorted([r for r in rows if r[3] is not None and r[4] is not None and r[3] - r[4] > 0.02], key=lambda r: (r[4] - r[3]))
missing = [r for r in rows if (r[3] is None) != (r[4] is None)]
P("## Flags: utilisation worse by more than 0.02 (whole model: BDK per SLN, AQB per beam)")
P("")
if not worse:
    P("None. No BDK or AQB utilisation in the model went up by more than 0.02.")
else:
    P(f"{len(worse)} entries (full list: compare_v19_v19m.csv):")
    P("")
    P("| check | id | SLN | v19 (LC) | v19m (LC) | change |")
    P("|---|---|---|---|---|---|")
    for r in worse[:40]:
        P(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.3f} ({r[5]}) | {r[4]:.3f} ({r[6]}) | {r[4] - r[3]:+.3f} |")
P("")
P(f"For information: {len(better)} entries went down by more than 0.02"
  + (": " + ", ".join(f"{r[0]} {r[1]} (SLN {r[2]}) {r[3]:.3f} -> {r[4]:.3f}" for r in better[:15]) if better else "") + ".")
if missing:
    P(f"Entries present in only one model: {len(missing)} (" + ", ".join(f"{r[0]} {r[1]}" for r in missing[:10]) + ").")
P("")
P("Members above 0.90 in v19m (summary_v19m.json):")
P("")
for x in s19m["above_0_90"]:
    P(f"- {x['check']} SLN {x['sln']} group {x['group']}: {x['util']:.3f} LC {x['lc']} ({x.get('title', '')})")
open(os.path.join(B, "RESULTS_v19m.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
json.dump(dict(worse=worse, better=better, missing=missing), open(os.path.join(B, "flags_v19m.json"), "w"), indent=1)
print("worse", len(worse), "better", len(better), "missing", len(missing))
