"""Append the v20-specific sections to RESULTS_v20.md (read only on 26016_check_v20.cdb and the export JSONs):
status changes v19m -> v20, sliding + overturning from the real v20 reactions, L2 ring SLN 56, leg 722, alpha_cr modes,
max SLS deflections, max reactions, stair landing sway. Writes sliding_overturning_v20.json too.
py -3.11 results_extra_v20.py"""
import csv, json, os, sys, re
sys.path.insert(0, r"C:\Sofistik workflow\sofistik-mcp")
from sofistik_mcp import cdbio, results as R, install, config
V = r"C:\Sofistik workflow\26016-design-report"; B = os.path.join(V, "v20_export"); A = os.path.join(V, "v19m_export")
J = lambda *p: json.load(open(os.path.join(*p), encoding="utf-8"))
out = []; P = out.append
# ---------- status changes ----------
rows = list(csv.DictReader(open(os.path.join(B, "compare_v19m_v20.csv"))))
ch = [r for r in rows if r["util_v19m"] and r["util_v20"] and (float(r["util_v19m"]) > 1.0) != (float(r["util_v20"]) > 1.0)]
P("## Status changes v19m -> v20 (utilisation crossing 1.00, BDK per SLN and AQB per beam)")
P("")
if ch:
    P("| check | id | SLN | v19m (LC) | v20 (LC) | status |"); P("|---|---|---|---|---|---|")
    for r in sorted(ch, key=lambda r: -float(r["util_v19m"])):
        st = "FAIL -> PASS" if float(r["util_v20"]) <= 1.0 else "PASS -> FAIL"
        P(f"| {r['check']} | {r['id (BDK: SLN, AQB: beam)']} | {r['sln']} | {float(r['util_v19m']):.3f} ({r['lc_v19m']}) | {float(r['util_v20']):.3f} ({r['lc_v20']}) | {st} |")
else:
    P("None.")
P("")
s20 = J(B, "summary_v20.json")
P("Members above 1.00 in v20: " + (", ".join(f"{x.get('check')} SLN {x.get('sln')} {x.get('util')} LC {x.get('lc')}" for x in s20["above_0_90"] if float(x.get("util", 0)) > 1.0) or "none"))
P("")
# ---------- L2 ring SLN 56 ----------
r56 = [m for m in J(B, "ring_L2.json")["members"] if m["sln"] == 56][0]
q56 = [m for m in J(A, "ring_L2.json")["members"] if m["sln"] == 56][0]
P("## Governing L2 ring check, SLN 56 (L2 outer ring r 12, UB 254, LC %s)" % r56["governing_lc"])
P("")
P("| item | v19m | v20 |"); P("|---|---|---|")
P(f"| BDK (LC) | {q56['bdk']['util']} ({q56['bdk']['lc']}) | {r56['bdk']['util']} ({r56['bdk']['lc']}) {r56['bdk']['check']} |")
P(f"| AQB (LC) | {q56['aqb']['util']} ({q56['aqb']['lc']}) | {r56['aqb']['util']} ({r56['aqb']['lc']}) |")
for k in ("N", "Vz", "My"):
    P(f"| node end {k} (node {r56['node_end']['node']}) | {q56['node_end'][k]:.2f} | {r56['node_end'][k]:.2f} |")
P(f"| My at 300 mm from the node | {q56['My_at_300mm_from_node']['value']:.2f} | {r56['My_at_300mm_from_node']['value']:.2f} |")
P("")
P("Units kN, kNm; SOFiSTiK local axes. LC 120 = ULS G+Q+psiW -X down (wind as the accompanying action, so the qp change hardly moves it).")
P("")
# ---------- stair ----------
st20, st19 = J(B, "stair_ext.json"), J(A, "stair_ext.json")
P("## External stair (group 62)")
P("")
P("| member | v19m BDK / AQB (LC) | v20 BDK / AQB (LC) |"); P("|---|---|---|")
m19 = {m["sln"]: m for m in st19["members"]}
for m in st20["members"]:
    o = m19.get(m["sln"], {})
    if m["sln"] in (722, 767, 701, 702, 713, 714, 746, 747, 758, 759) or (m.get("bdk") or {}).get("util", 0) >= 0.8:
        f = lambda x: "-" if not x else f"{x.get('util')} ({x.get('lc')})"
        P(f"| SLN {m['sln']} {m['title']} | {f(o.get('bdk'))} / {f(o.get('aqb'))} | {f(m.get('bdk'))} / {f(m.get('aqb'))} |")
P("")
P("Landing horizontal movement (mm):")
P("")
P("| landing | LC 201 v19m | LC 201 v20 | worst wind SLS v19m (LC) | worst wind SLS v20 (LC) |"); P("|---|---|---|---|---|")
for k, v in st20["landing_horizontal_movement"].items():
    o = st19["landing_horizontal_movement"].get(k, {})
    P(f"| {k} | {o.get('lc201', {}).get('value', 0):.1f} | {v['lc201']['value']:.1f} | {o.get('worst_wind_SLS', {}).get('value', 0):.1f} ({o.get('worst_wind_SLS', {}).get('lc')}) | "
      f"{v['worst_wind_SLS']['value']:.1f} ({v['worst_wind_SLS']['lc']}) |")
P("")
P("Stair support reactions (foot / leg bases, ULS envelope): see stair_ext.json 'supports' and env_support_ULS.json.")
P("")
# ---------- alpha_cr, deflections, reactions from PART A ----------
pa = open(os.path.join(B, "A_followup", "PART_A_v20.md"), encoding="utf-8").read()
def sect(tag):
    m = re.search(r"## " + tag + r"[^\n]*\n(.*?)(?=\n## |\Z)", pa, re.S); return m.group(1).strip() if m else ""
P("## alpha_cr (lowest buckling factors) and mode description [v19m in brackets]")
P(""); P(sect("A3")); P("")
P("PLC 102: lowest mode = local ground-floor raking column (group 11) at about 171 deg, as in v19m. "
  "PLC 119: lowest mode = Level 1 pinwheel (inner core turns, radials r 3-8.5 bend about the weak axis), as in v19m. Both < 10 (same class as before).")
P("")
P("## Max SLS deflections [v19m in brackets]")
P(""); P(sect("A4")); P("")
P("## Max reactions [v19m in brackets]")
P(""); P(sect("A7")); P("")
# ---------- sliding + overturning from the real v20 reactions ----------
st = config.load_settings(r"C:\Sofistik workflow\sofistik-mcp\settings.json"); info = install.find(st); d = cdbio.load_daten(info.get("daten"))
cdb = cdbio.Cdb(r"C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.cdb", info)
RX = {lc: {r["node"]: r for r in R.support_reactions(cdb, d, lc, max_rows=10 ** 6)["rows"]} for lc in (1, 2, 3, 4, 11, 13, 14, 71, 72, 73, 74)}
nodes = sorted(RX[1])
g = lambda n, k, lcs: sum((RX[lc].get(n, {}).get(k) or 0) for lc in lcs)
DLc, LLc = (1, 2, 3, 4), (11, 13, 14)
res = []
P("## Sliding and overturning from the real v20 reactions (unfactored, mu 0.40, as the original report)")
P("")
P("FoS sliding = 0.40 x sum Fz / sum H. Overturning: no support may lift off (min support Fz > 0), as the original report; "
  "plus the EQU 0.9G + 1.5W uplift per support for the anchors (reactions_EQU.json).")
P("")
P("| combination | wind | sum Fz (kN) | H (kN) | FoS sliding | min support Fz (kN, node) |"); P("|---|---|---|---|---|---|")
for name, fd, fl, fw in (("DL + WL", 1, 0, 1.0), ("DL + 0.7LL + 0.5WL", 1, 0.7, 0.5), ("DL + LL + 0.5WL", 1, 1.0, 0.5)):
    for w, lab in ((71, "+X"), (72, "-X"), (73, "-Y"), (74, "+Y")):
        fz = {n: g(n, "pz", DLc) * fd + g(n, "pz", LLc) * fl + g(n, "pz", (w,)) * fw for n in nodes}
        fx = sum(g(n, "px", (w,)) for n in nodes) * fw; fy = sum(g(n, "py", (w,)) for n in nodes) * fw
        H = (fx ** 2 + fy ** 2) ** 0.5; S = sum(fz.values()); fos = 0.4 * S / H
        mn = min(fz, key=fz.get)
        res.append(dict(combination=name, wind=lab, sum_Fz=round(S, 1), H=round(H, 1), FoS=round(fos, 2), min_support_Fz=round(fz[mn], 1), node=mn))
        P(f"| {name} | {lab} | {S:.1f} | {H:.1f} | {fos:.2f} | {fz[mn]:.1f} ({mn}) |")
P("")
mins = min(r["FoS"] for r in res if r["combination"] == "DL + WL")
P(f"Minimum sliding FoS (DL + WL): {mins:.2f}. Prediction by scaling v19m to qp 0.5 kPa: 2.48 -> {'matches' if abs(mins - 2.48) < 0.01 else 'differs'}.")
neg = [r for r in res if r["min_support_Fz"] < 0]
P("Overturning (unfactored): " + ("no support lifts off in any combination." if not neg else
  "supports with uplift: " + "; ".join(f"{r['combination']} {r['wind']} node {r['node']} {r['min_support_Fz']} kN" for r in neg) + " (anchors needed, see EQU)."))
eq = J(B, "reactions_EQU.json")
P("EQU 0.9G + 1.5W (131-134): " + "; ".join(f"LC {c['lc']} max uplift {c['max_uplift']['pz']:.1f} kN at node {c['max_uplift']['node']} ({len(c['uplift_nodes'])} supports in uplift)" for c in eq["combinations"]))
eq19 = J(A, "reactions_EQU.json")
P("[v19m: " + "; ".join(f"LC {c['lc']} {c['max_uplift']['pz']:.1f} kN node {c['max_uplift']['node']}" for c in eq19["combinations"]) + "]")
P("")
json.dump(dict(rows=res, min_FoS_DL_WL=mins), open(os.path.join(B, "sliding_overturning_v20.json"), "w"), indent=1)
with open(os.path.join(B, "RESULTS_v20.md"), "a", encoding="utf-8") as f:
    f.write("\n" + "\n".join(out) + "\n")
print("\n".join(out[:12])); print("...sliding min", mins)
