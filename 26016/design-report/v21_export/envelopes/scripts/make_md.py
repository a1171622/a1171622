"""ENVELOPES.md for v21 from the harvest / picture JSONs (same content as the v20 note, numbers from v21)."""
import json, os
E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(E, "sanity_check.json"))); P = json.load(open(os.path.join(E, "pictures_final.json")))
T = {g["group"]: g for g in json.load(open(os.path.join(E, "env_table_ULS.json")))["groups"]}
V = r"C:\Sofistik workflow\26016-member-check\v20\envelopes\env_table_ULS.json"
T19 = {g["group"]: g for g in json.load(open(V))["groups"]}
o = []; A = o.append
A("# 26016 v21 - ULS member force envelopes (WinGRAF pictures + table)")
A("")
A("Model: `26016-member-check\\v21\\26016_check_v21` = v20 + drawing 970027-S01-ST sections (stair RHS 160x80x5, L2 radials UB 457x191x98, landing supports SHS 80x80x6.3) (run 13 Nov 2026, exit 0, 0 errors).")
A("Read from a COPY (`v21\\envelopes\\26016_env_v21.cdb`); nothing re-analysed. Same recipe, views, scales logic and file names as the v20 envelopes.")
A("Standalone PDF: `26016_v21_ULS_envelopes.pdf` (A4, cover, 2 table pages, one picture per page with a caption).")
A("")
A("## Load cases")
A("")
A("Model MAXIMA COMB 3 (EXTR NONL, TYPE DESI, BASE 4300): the 43 ULS STR combinations 101-130, 135, 141-148, 151-154 as exclusive alternatives (TYPE AG1, factor 1.00). "
  "Beam envelope LCs: N 4321/4322, Vy 4323/4324, Vz 4325/4326, Mt 4327/4328, My 4329/4330, Mz 4331/4332 (max/min); SLS 201-221: 4421-4432. EQU 131-134 not included.")
A("")
A("## Sanity check (MAXIMA vs scan of the 43 combinations)")
A("")
w = S["ULS_worst_station_diff"]
A("Largest difference at any station of any beam: " + ", ".join(f"{k} {v:.1e}" for k, v in w.items()) + " (kN / kNm). They match.")
A("")
A("| member | My max (LC) | My min (LC) | N max (LC) | N min (LC) | MAXIMA |"); A("|---|---|---|---|---|---|")
for m in S["members"]:
    my, n = m["My"], m["N"]
    same = all(abs(my[a] - my[b]) < 1e-3 and abs(n[a] - n[b]) < 1e-3 for a, b in (("scan_max", "maxima_max"), ("scan_min", "maxima_min")))
    A(f"| {m['label']} | {my['scan_max']:.3f} ({my['scan_max_lc']}) | {my['scan_min']:.3f} ({my['scan_min_lc']}) | {n['scan_max']:.3f} ({n['scan_max_lc']}) | {n['scan_min']:.3f} ({n['scan_min_lc']}) | {'identical' if same else 'DIFFERS'} |")
A("")
A("## Pictures (`png/`, 300 dpi; print 170 mm wide, result text about 2.6 mm)")
A("")
A("Red = max envelope LC, blue = min envelope LC. Floor My/Vz/N in a steep isometric (My acts in the vertical plane; a true top view had to rotate the diagram into the plan and "
  "flips side with member direction), Mz of Level 1 in true plan. Columns per storey (SEL by element). Scale = 1 cm on the 25.5 cm WinGRAF sheet.")
A("")
A("| file | groups | quantity | scale 1 cm = | labels above | envelope max / min |"); A("|---|---|---|---|---|---|")
U = {"N": "kN", "VY": "kN", "VZ": "kN", "MT": "kNm", "MY": "kNm", "MZ": "kNm"}
for it in P:
    p = it.get("picture")
    if not p: A(f"| {it['file']} | all beam groups | key | - | - | - |"); continue
    A(f"| {it['file']} | {', '.join(map(str, p['groups']))} | {p['q']} {U[p['q']]} | {p['unit']:g} | {p['thr']:g} | {p['max']:g} / {p['min']:g} |")
A("")
A("## Group extremes v20 -> v21 (My and N, kNm / kN)")
A("")
A("| group | My max | My min | N max | N min |"); A("|---|---|---|---|---|")
for g in sorted(T):
    a, b = T19.get(g, {}), T[g]
    A(f"| {g} | {a.get('My_max')} -> {b['My_max']} | {a.get('My_min')} -> {b['My_min']} | {a.get('N_max')} -> {b['N_max']} | {a.get('N_min')} -> {b['N_min']} |")
A("")
A("Kingpost: shell elements, no beam diagram. Table with Vy, Vz, Mt, Mz and governing beam / x / LC: env_table_ULS.csv / .json (SLS: env_table_SLS.*).")
A("")
A("Inputs: `26016_env_wing.dat` (WinGRAF + PLBCONVERTER, from scripts/make_wing.py), scripts/harvest_env.py, storey_ext.py, finalize.py, make_md.py; envelope LCs from the model run (maxima_comb3_excerpt.dat in the v20 envelopes, unchanged).")
open(os.path.join(E, "ENVELOPES.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("\n".join(o[14:22]))
