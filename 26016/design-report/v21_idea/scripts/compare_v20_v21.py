"""Per joint position: IDEA results on v15 forces (current detail, as-is) vs v20 forces. Writes compare_v15_v20.csv.
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


V15 = {}   # here: the v20 results (baseline)
for p in (I + r"\v20\xml_A_noflange\joint_check_summary.csv", I + r"\v20\xml_B_noflange\joint_check_summary.csv",
          I + r"\v20\xml_strut_10deg\joint_check_summary.csv", I + r"\v20\xml_L2haunch_flush_M20\joint_check_summary.csv"):
    V15.update(rows(p))
V19 = {}   # here: v21
for p in (I + r"\v21\xml_A_noflange\joint_check_summary.csv", I + r"\v21\xml_B_noflange\joint_check_summary.csv",
          I + r"\v21\xml_strut_10deg\joint_check_summary.csv", I + r"\v21\xml_L2haunch_flush_M20\joint_check_summary.csv"):
    V19.update(rows(p))
TR = {}
b15 = {key(j): j for j in V15}
out = []
for j in sorted(V19, key=lambda s: (s[:2], s[6], int(s[-3:]))):
    r19 = V19[j]; j15 = b15.get(key(j)); r15 = V15.get(j15, {})
    row = dict(joint_v21=j, joint_v20_same_position=j15 or "", type_changed="yes" if j15 and j15[6] != j[6] else "")
    worst = 0.0
    for lab, src in (("v20", r15), ("v21", r19)) + ((("v20_v15transform", TR[j]),) if j in TR else ()):
        for k in ("Plates", "Bolts", "Welds"):
            row[f"{lab}_{k.lower()}_pct"] = src.get(f"{k} max %", "")
            row[f"{lab}_{k.lower()}_lc"] = src.get(f"{k} governing", "")
        row[f"{lab}_status"] = src.get("passed", "")
    for k in ("plates", "bolts", "welds"):
        try:
            d = float(row[f"v21_{k}_pct"]) - float(row[f"v20_{k}_pct"]); row[f"delta_{k}"] = round(d, 1); worst = max(worst, abs(d))
        except ValueError:
            row[f"delta_{k}"] = ""
    row["flag"] = "; ".join(x for x in (
        "FAIL" if row["v21_status"] != "PASS" else "",
        "change > 2 points" if worst > 2 else "",
        ">= 90 %" if max(float(row["v21_bolts_pct"] or 0), float(row["v21_welds_pct"] or 0)) >= 90 else "",
        "joint type changed (v19 column positions)" if row["type_changed"] else "") if x)
    out.append(row)
cols = list(dict.fromkeys(k for r in out for k in r))
with open(os.path.join(A, "compare_v20_v21.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, restval=""); w.writeheader(); w.writerows(out)
for r in out:
    print(f"{r['joint_v21']:12s} P {r['v20_plates_pct']:>5}->{r['v21_plates_pct']:>5}  B {r['v20_bolts_pct']:>5}->{r['v21_bolts_pct']:>5}  W {r['v20_welds_pct']:>5}->{r['v21_welds_pct']:>5}  {r['v21_status']:4s} | {r['flag']}")