"""Model updated to drawings 970027-S01-ST (13.11.2026): results and sections on top of edit_v21.py -> edit_v22.py
Q deflections of Table 13 (Level 2, roof, internal stair) come from v21_export/A_followup/partA4_report_deflections.json (QD below)."""
import json, os
s = open('edit_v21.py').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:70])
    s = s.replace(a, b)
def block(start, endmark, new):
    global s
    i = s.index(start); j = s.index("])\n", i) + 3 if endmark is None else s.index(endmark, i)
    s = s[:i] + new + s[j:]
QD = dict(L2Q='24.9', RFQ='9.5', L1Q='7.9', INT='4.1')
if os.path.exists('qd.json'): QD.update(json.load(open('qd.json')))
rep("v20_export/')", "v21_export/')")
# description
rep("The stringers and the landing frame are RHS 200x100x6, and each middle landing", "The stringers are RHS 160x80x5 and the landing frames are RHS 200x100x6, and each middle landing")
rep("The stringers and the landing beams are RHS 200x100x6. The landings stand on SHS 80x80x6.3 legs", "The stringers and the landing beams are RHS 160x80x5. The landings stand on SHS 80x80x6.3 legs")
rep("set_row(tr, ['5 / 6 / 7', 'RHS 200x100x6 / RHS 50x50x5 / tray 300x5', 'Stair stringers and landing frames / landing joists / treads (60, 62)'])",
    "set_row(tr, ['5 / 6 / 7', 'RHS 200x100x6 / RHS 50x50x5 / tray 300x5', 'Landing frames of the internal stairs (60) / landing joists / treads (60, 62)'])")
rep("tr8 = add_row(ch[232], tr, ['8', 'SHS 100x100x5', 'Landing posts of the internal stairs (61), ring brackets of the external staircase (62)'])\nadd_row(ch[232], tr8, ['9', 'SHS 80x80x6.3', 'Legs and transverse beams of the external staircase (62)'])",
    "tr8 = add_row(ch[232], tr, ['8', 'SHS 100x100x5', 'Landing posts of the internal stairs (61)'])\ntr9 = add_row(ch[232], tr8, ['9', 'SHS 80x80x6.3', 'Legs, transverse beams and ring brackets of the external staircase (62)'])\nadd_row(ch[232], tr9, ['10', 'RHS 160x80x5', 'Stair stringers (60, 62), landing beams of the external staircase (62)'])")
# Table 13
block("fill(249, [", None, '''fill(249, [
 ['Level 1 deck, outer ring between diagonal nodes (L = 8.2 m)', 'G + Q + 0.5W', '15.8', '221', '32.8 (L/250)', 'OK'],
 ['Level 1 deck, same, imposed load only', 'Q', '%(L1Q)s', '11', '22.8 (L/360)', 'OK'],
 ['Level 2 deck, radial kingpost to r 12 (L = 11.3 m)', 'G + Q', '32.2', '201', '45.4 (L/250)', 'OK'],
 ['Level 2 deck, same, imposed load only', 'Q', '%(L2Q)s', '11 + 12 + 13', '31.5 (L/360)', 'OK'],
 ['Roof, radial kingpost to r 12, downward (L = 11.3 m)', 'G + Q', '15.9', '201', '45.4 (L/250)', 'OK'],
 ['Roof, same, imposed load only', 'Q roof', '%(RFQ)s', '12', '31.5 (L/360)', 'OK'],
 ['Roof, upward under wind uplift', 'G + W', '18.8 (up)', '206', '45.4 (L/250)', 'OK'],
 ['Horizontal, Level 2 (h = 8.1 m) / roof (h = 12.1 m)', 'G + W (+ Q)', '1.3 / 1.3', '202 / 204', '27 / 40 (h/300)', 'OK'],
 ['Internal stairs, stringer Level 1 to middle landing (L = 4.0 m)', 'G + Q', '%(INT)s', '201', '15.9 (L/250)', 'OK'],
 ['External staircase, flight between its ends (L = 3.1 m)', 'G + Q', '2.9', '201', '12.3 (L/250)', 'OK'],
 ['External staircase, landing at Level 1, horizontal (h = 4.43 m)', 'G + Q / G + Q + 0.5W', '23.4 / 26.7', '201 / 218', '14.8 (h/300)', 'See 7.2.3'],
])
''' % QD)
# Table 14
block("fill(256, [", None, '''fill(256, [
 ['11', 'Facade diagonals, ground to Level 1', 'SHS 150x150x10', '0.38', 'SLN 25 / LC 147', 'OK'],
 ['21', 'Facade diagonals, Level 1 to Level 2', 'SHS 150x150x10', '0.39', 'SLN 17 / LC 145', 'OK'],
 ['31', 'Facade diagonals, Level 2 to roof', 'SHS 150x150x10', '0.24', 'SLN 380 / LC 147', 'OK'],
 ['12', 'Raking struts', 'SHS 150x150x10', '0.09', 'SLN 448 / LC 121', 'OK'],
 ['13', 'Columns r 8.5 m, ground to Level 1', 'SHS 150x150x10', '0.25', 'SLN 41 / LC 121', 'OK'],
 ['23', 'Columns r 8.5 m, Level 1 to Level 2', 'SHS 150x150x10', '0.14', 'SLN 96 / LC 119', 'OK'],
 ['14', 'Inner columns, ground to Level 1', 'SHS 150x150x10', '0.37', 'SLN 399 / LC 145', 'OK'],
 ['24', 'Inner columns, Level 1 to Level 2', 'SHS 150x150x10', '0.29', 'SLN 417 / LC 122', 'OK'],
 ['15', 'Level 1 beams', 'UB 254x146x43', '0.66', 'SLN 223 / LC 153', 'OK'],
 ['25', 'Level 2 beams', 'UB 457 / UB 254', '0.89', 'SLN 56 / LC 120', 'OK'],
 ['35', 'Roof beams', 'UB 254x146x43', '0.38', 'SLN 318 / LC 107', 'OK'],
 ['60', 'Internal stairs', 'RHS 160x80x5 / RHS 200x100x6', '0.43', 'SLN 490 / LC 122', 'OK'],
 ['61', 'Landing posts of the internal stairs', 'SHS 100x100x5', '0.11', 'SLN 602 / LC 120', 'OK'],
 ['62', 'External staircase, stringers and landing beams', 'RHS 160x80x5', '0.38', 'SLN 746 / LC 135', 'OK'],
 ['62', 'External staircase, legs', 'SHS 80x80x6.3', '0.90', 'SLN 767 / LC 121', 'OK'],
])
''')
rep("the program check at the node centreline gives 1.06. The UB 457x191x89 radials of Level 2 reach 0.73 (SLN 73, combination 147).",
    "the program check at the node centreline gives 1.07 for this member and 1.01 for the adjacent members SLN 57 and SLN 62, which are covered by the same direct check. The UB 457x191x98 radials of Level 2 reach 0.65 (SLN 73, combination 147).")
rep("(Appendix B); the program check at the node centreline gives 1.06.')", "(Appendix B); the program check at the node centreline gives 1.07.')")
# Table 15
block("fill(259, [", None, '''fill(259, [
 ['1', 'SHS 150x150x10', '0.39', 'beam 110113 (GRP 21) / LC 146', 'OK'],
 ['2', 'UB 254x146x43', '0.79', 'beam 140020 (GRP 25) / LC 120', 'OK'],
 ['4', 'UB 457x191x98', '0.61', 'beam 140389 (GRP 25) / LC 145', 'OK'],
 ['5', 'RHS 200x100x6', '0.47', 'beam 170305 (GRP 60) / LC 120', 'OK'],
 ['6', 'RHS 50x50x5', '0.22', 'beam 170128 (GRP 60) / LC 120', 'OK'],
 ['7', 'Tread tray 300x5 (elastic)', '0.72', 'beam 170105 (GRP 60) / LC envelope, elastic', 'OK'],
 ['8', 'SHS 100x100x5', '0.10', 'beam 180010 (GRP 61) / LC 120', 'OK'],
 ['9', 'SHS 80x80x6.3', '0.29', 'beam 190493 (GRP 62) / LC 152', 'OK'],
 ['10', 'RHS 160x80x5', '0.48', 'beam 170403 (GRP 60) / LC 122', 'OK'],
])
''')
# Table 16
rep("cellsub(265, '7.09', '6.95'); cellsub(265, '7.46', '7.32')", "cellsub(265, '7.09', '6.95'); cellsub(265, '7.46', '7.15')")
rep("The first 20 modes lie between 6.95 and 9.51 (combination 102) and between 7.32 and 10.11 (combination 119).", "The first 20 modes lie between 6.95 and 9.50 (combination 102) and between 7.15 and 10.07 (combination 119).")
rep("with a maximum utilisation of 0.67. In the first mode of either combination the external staircase moves less than 5% of the governing member.')",
    "with a maximum utilisation of 0.66. The external staircase does not govern any of the first 20 modes of either combination: its largest displacement in these modes is 12% of the displacement of the governing member.')")
rep("'For the columns, struts and diagonals the amplified utilisation is 0.40 x 1.168 = 0.46.'", "'For the columns, struts and diagonals the amplified utilisation is 0.39 x 1.168 = 0.46.'")
# stair table
block("rows = [\n ['Stringers', 'RHS 200x100x6'", "for k, tx in enumerate(rows):", '''rows = [
 ['Stringers', 'RHS 160x80x5', '0.38 / 0.34', 'SLN 746 / LC 135, SLN 758 / LC 121', 'OK'],
 ['Stringer seats of the upper flights on the first landing', 'RHS 160x80x5', '0.32 / 0.42', 'SLN 711 / LC 135, SLN 756 / LC 135', 'OK'],
 ['Landing beams', 'RHS 160x80x5', '0.29 / 0.40', 'SLN 764 / LC 135, SLN 763 / LC 121', 'OK'],
 ['Legs', 'SHS 80x80x6.3', '0.90 / 0.29', 'SLN 767 / LC 121, SLN 768 / LC 152', 'OK'],
 ['Transverse beams between the legs', 'SHS 80x80x6.3', '0.01 / 0.05', 'SLN 793 / LC 119', 'OK'],
 ['Brackets on the Level 1 ring', 'SHS 80x80x6.3', '0.04 / 0.04', 'SLN 724 / LC 122', 'OK'],
 ['Treads', '5 mm plate (elastic)', '0.57', 'SLN 728 / LC envelope', 'OK'],
]
''')
rep("and a design compression of 32 kN (combination 122). They are verified conservatively with a buckling length of twice their height, which gives 0.98.", "and a design compression of 28 kN (combination 121). They are verified conservatively with a buckling length of twice their height, which gives 0.90.")
rep("the EN 1993-1-1 interaction check gives 0.33.'", "the EN 1993-1-1 interaction check gives 0.32.'")
rep("each foot carries up to 40 kN downward and up to 21 kN uplift, with a horizontal force of up to 48 kN (combination 111)", "each foot carries up to 40 kN downward and up to 22 kN uplift, with a horizontal force of up to 47 kN (combination 111)")
rep("The brackets on the Level 1 outer ring carry an axial force between 2 kN tension and 20 kN compression.", "The brackets on the Level 1 outer ring carry an axial force between 2 kN tension and 21 kN compression.")
rep("moves horizontally by 18.8 mm, and by 21.0 mm with wind (combination 218), while the Level 1 deck moves less than 2 mm. The first landing moves by 2.9 mm and 5.9 mm. The vertical deflection of the flights between their ends is 1.3 mm.",
    "moves horizontally by 23.4 mm, and by 26.7 mm with wind (combination 218), while the Level 1 deck moves less than 2 mm. The first landing moves by 4.0 mm and 7.8 mm. The vertical deflection of the flights between their ends is 2.9 mm.")
rep("427.8 kN compression (node 2, combination 146), 53.6 kN uplift (node 12, combination 133) and 113.5 kN horizontal (node 27, combination 105).", "428.3 kN compression (node 2, combination 146), 53.2 kN uplift (node 12, combination 133) and 112.7 kN horizontal (node 27, combination 105).")
rep("The members of the internal stairs reach 0.70 and the members of the external staircase reach 0.98.'", "The members of the internal stairs reach 0.72 and the members of the external staircase reach 0.90.'")
rep("'with a maximum weld utilisation of 87%.', 'with a maximum weld utilisation of 94%.'", "'with a maximum weld utilisation of 87%.', 'with a maximum weld utilisation of 99%.'")
# Appendix B
rep("The hogging moment at the 340 degree node centreline is 163.3 kNm", "The hogging moment at the 340 degree node centreline is 163.8 kNm")
rep("' = 163.3 - 91 × 0.3 + 0.1 = 136 '", "' = 163.8 - 91 × 0.3 + 0.1 = 137 '")
rep("setcell(c(1, 1), '18.4 kN')", "setcell(c(1, 1), '16.5 kN')")
rep("'136 kNm (163.3 kNm at the node centreline)'", "'137 kNm (163.8 kNm at the node centreline)'")
rep("' = 0.012 below 0.25'", "' = 0.011 below 0.25'")
rep("msub(ch[405], '131', '136')", "msub(ch[405], '131', '137')"); rep("' = 0.763 + 0.026 = 0.79 ≤ 0.90'", "' = 0.766 + 0.026 = 0.79 ≤ 0.90'")
rep("'The axial force is a tension of 18.4 kN.", "'The axial force is a tension of 16.5 kN.")
rep("msub(ch[421], '131', '136')", "msub(ch[421], '131', '137')"); rep("' = 0.349 + 0.009 = 0.36 ≤ 0.90'", "' = 0.350 + 0.009 = 0.36 ≤ 0.90'")
rep("msub(ch[422], '131', '136')", "msub(ch[422], '131', '137')"); rep("' = 0.873 + 0.016 = 0.89 ≤ 0.90'", "' = 0.877 + 0.016 = 0.89 ≤ 0.90'")
# sections in Wing's own text and tables
gen = r"""
# --- sections to the drawings of 13.11.2026
_n = 0
for _t in body.iter(qn('w:t')):
    if _t.text and '457x191x89' in _t.text: _t.text = _t.text.replace('457x191x89', '457x191x98'); _n += 1
print('UB 457x191x98 replacements', _n)
"""
rep("\n# ------------------------------------------------------------------ figure and table numbers in document order", gen + "\n# ------------------------------------------------------------------ figure and table numbers in document order")
open('edit_v22.py', 'w').write(s)
