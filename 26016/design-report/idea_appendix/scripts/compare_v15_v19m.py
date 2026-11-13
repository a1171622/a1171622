"""Per joint position: IDEA results on v15 forces (current detail, as-is) vs v19m forces. Writes compare_v15_v19m.csv.
Joints are matched by level and angle (the joint TYPE can differ: v19 moved the L1-L2 columns at r 8.5 to 40 / 60 deg)."""
import csv, glob, os, re
A = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); I = r"C:\Sofistik workflow\idea-statica"


def rows(pattern):
    out = {}
    for f in glob.glob(pattern):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            j = re.sub(r"(\.xml|_joint)$", "", r["joint"]); out[j] = r
    return out


def key(j): return j[:5] + "_" + j[-3:]          # level + angle


V15 = {}
for p in (r"\v15\xml_A_noflange_asis\joint_check_summary.csv", r"\v15\xml_B_noflange_asis\joint_check_summary.csv",
          r"\v15\xml_strut_10deg_asis\joint_check_summary.csv", r"\v15\xml_L2haunch_flush_asis\part*\joint_check_summary.csv"):
    V15.update(rows(I + p))
V19 = {}
for p in (r"C:\Sofistik workflow\26016-design-report\v19m_export\idea_L1_noflange\joint_check_summary_v19m.csv",
          I + r"\v19m\xml_strut_10deg\joint_check_summary.csv", I + r"\v19m\xml_L2haunch_flush_M20\joint_check_summary.csv"):
    V19.update(rows(p))
TR = rows(I + r"\v19m\xml_strut_10deg_v15tr\joint_check_summary.csv")
b15 = {key(j): j for j in V15}
out = []
for j in sorted(V19, key=lambda s: (s[:2], s[6], int(s[-3:]))):
    r19 = V19[j]; j15 = b15.get(key(j)); r15 = V15.get(j15, {})
    row = dict(joint_v19m=j, joint_v15_same_position=j15 or "", type_changed="yes" if j15 and j15[6] != j[6] else "")
    worst = 0.0
    for lab, src in (("v15", r15), ("v19m", r19)) + ((("v19m_v15transform", TR[j]),) if j in TR else ()):
        for k in ("Plates", "Bolts", "Welds"):
            row[f"{lab}_{k.lower()}_pct"] = src.get(f"{k} max %", "")
            row[f"{lab}_{k.lower()}_lc"] = src.get(f"{k} governing", "")
        row[f"{lab}_status"] = src.get("passed", "")
    for k in ("plates", "bolts", "welds"):
        try:
            d = float(row[f"v19m_{k}_pct"]) - float(row[f"v15_{k}_pct"]); row[f"delta_{k}"] = round(d, 1); worst = max(worst, abs(d))
        except ValueError:
            row[f"delta_{k}"] = ""
    row["flag"] = "; ".join(x for x in (
        "FAIL" if row["v19m_status"] != "PASS" else "",
        "change > 2 points" if worst > 2 else "",
        ">= 90 %" if max(float(row["v19m_bolts_pct"] or 0), float(row["v19m_welds_pct"] or 0)) >= 90 else "",
        "joint type changed (v19 column positions)" if row["type_changed"] else "") if x)
    out.append(row)
cols = list(dict.fromkeys(k for r in out for k in r))
with open(os.path.join(A, "compare_v15_v19m.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, restval=""); w.writeheader(); w.writerows(out)
for r in out:
    print(f"{r['joint_v19m']:12s} v15 {r['joint_v15_same_position']:12s} P {r['v15_plates_pct']:>5}->{r['v19m_plates_pct']:>5}  B {r['v15_bolts_pct']:>5}->{r['v19m_bolts_pct']:>5}"
          f"  W {r['v15_welds_pct']:>5}->{r['v19m_welds_pct']:>5}  {r['v19m_status']:4s} tr W {r.get('v19m_v15transform_welds_pct',''):>5} | {r['flag']}")
