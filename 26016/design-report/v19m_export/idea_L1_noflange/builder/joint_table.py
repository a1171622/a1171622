"""Joint results table for the v19m no-flange IDEA batch: per joint plates (strain % of 5 %), bolts %, welds %, governing case,
pass/fail, max |ring-end Mz| that went in; v15 no-flange (as-is and Mz = 0) beside it from the repo csv.
py -3.11 joint_table.py <out_dir>"""
import csv, json, os, sys
V = r"C:\Sofistik workflow\idea-statica\v19m"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(os.path.join(V, "xml_A_noflange", "joint_check_summary.csv"), encoding="utf-8-sig")))
F = json.load(open(os.path.join(V, "forces_v19m.json")))
old = list(csv.DictReader(open(r"C:\Sofistik workflow\repo_a1171622\26016\design-report\idea_summary\L1_noflange\L1_noflange_results.csv", encoding="utf-8-sig")))
OLDNAME = {"L1-R8-B_040": "L1-R8-A_040", "L1-R8-A_080": "L1-R8-B_080"}  # same angle, v15 type
RINGS = {185, 227, 264, 265, 189, 192, 195, 198, 210, 213, 214, 217, 218, 221, 425, 426, 225, 226}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


out = []
for r in rows:
    j = r["joint"].replace(".xml", "")
    f = F[j]["forces_kN_kNm_IDEA_axes"]
    ring = [n for n in f if n.startswith("SLN") and int(n[3:]) in RINGS]
    mz = max(abs(v["Mz"]) for n in ring for v in f[n].values())
    oj = OLDNAME.get(j, j)
    oa = next((o for o in old if o["joint"] == oj and o["forces"] == "as-is"), {})
    oz = next((o for o in old if o["joint"] == oj and o["forces"] == "Mz = 0"), {})
    gov = r.get("Welds governing") if r["passed"] == "PASS" else r.get("Plates governing")
    out.append(dict(joint=j, template=F[j]["template"] + (f" rotated {F[j]['rotation_deg']} deg" if F[j]["rotation_deg"] else ""),
                    load_effects=r.get("load_effects"), result=r["passed"], plates_pct=num(r.get("Plates max %")), bolts_pct=num(r.get("Bolts max %")),
                    welds_pct=num(r.get("Welds max %")), analysis_pct=num(r.get("Analysis max %")), governing_case=gov,
                    plates_gov=r.get("Plates governing"), bolts_gov=r.get("Bolts governing"), welds_gov=r.get("Welds governing"),
                    max_ring_end_Mz_kNm=round(mz, 3), ring_members=" ".join(ring),
                    v15_name=oj, v15_asis=f"{oa.get('result')} P{oa.get('plates %')} B{oa.get('bolts %')} W{oa.get('welds %')}" if oa else "",
                    v15_mz0=f"{oz.get('result')} P{oz.get('plates %')} B{oz.get('bolts %')} W{oz.get('welds %')}" if oz else "",
                    error=r.get("error", "")))
with open(os.path.join(OUT, "L1_noflange_v19m_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
L = ["| joint | result | plates % | bolts % | welds % | governing case | max ring-end Mz in (kNm) | v15 same angle as-is | v15 Mz = 0 |",
     "|---|---|---|---|---|---|---|---|---|"]
for o in out:
    L.append(f"| {o['joint']} | {o['result']} | {o['plates_pct']} | {o['bolts_pct']} | {o['welds_pct']} | {o['governing_case']} | {o['max_ring_end_Mz_kNm']} "
             f"| {o['v15_name']}: {o['v15_asis']} | {o['v15_mz0']} |")
open(os.path.join(OUT, "joint_table.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
