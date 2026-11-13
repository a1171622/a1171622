s = open('edit_report.py').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:70])
    s = s.replace(a, b)
rep("v19m_export/')", "v20_export/')")
# end conditions
rep("clone_after(ch[225], ch[225], 'The stair stringers are pinned at the foot and at the top. The brackets",
    "clone_after(ch[225], ch[225], 'The stringers of the internal stairs are pinned at the foot and at the top. The stringers of the external staircase are released for bending about the major axis at both ends of each flight, and their feet stand on pinned supports. The brackets")
rep("sub(ch[241], '7.09', '6.94')", "sub(ch[241], '7.09', '6.95')")
# Table 13
i = s.index("fill(249, ["); j = s.index("])\n", i) + 3
s = s[:i] + '''fill(249, [
 ['Level 1 deck, outer ring between diagonal nodes (L = 8.2 m)', 'G + Q + 0.5W', '14.8', '221', '32.8 (L/250)', 'OK'],
 ['Level 1 deck, same, imposed load only', 'Q', '8.0', '11', '22.8 (L/360)', 'OK'],
 ['Level 2 deck, radial kingpost to r 12 (L = 11.3 m)', 'G + Q', '33.1', '201', '45.4 (L/250)', 'OK'],
 ['Level 2 deck, same, imposed load only', 'Q', '24.9', '11 + 12 + 13', '31.5 (L/360)', 'OK'],
 ['Roof, radial kingpost to r 12, downward (L = 11.3 m)', 'G + Q', '15.9', '201', '45.4 (L/250)', 'OK'],
 ['Roof, same, imposed load only', 'Q roof', '9.5', '12', '31.5 (L/360)', 'OK'],
 ['Roof, upward under wind uplift', 'G + W', '18.8 (up)', '206', '45.4 (L/250)', 'OK'],
 ['Horizontal, Level 2 (h = 8.1 m) / roof (h = 12.1 m)', 'G + W (+ Q)', '1.4 / 1.3', '210 / 204', '27 / 40 (h/300)', 'OK'],
 ['Internal stairs, stringer Level 1 to middle landing (L = 4.0 m)', 'G + Q', '4.1', '201', '15.9 (L/250)', 'OK'],
 ['External staircase, flight between its ends (L = 3.1 m)', 'G + Q', '1.3', '201', '12.3 (L/250)', 'OK'],
 ['External staircase, landing at Level 1, horizontal (h = 4.43 m)', 'G + Q / G + Q + 0.5W', '18.8 / 21.0', '201 / 218', '14.8 (h/300)', 'See 7.2.3'],
])
''' + s[j:]
# Table 14
i = s.index("fill(256, ["); j = s.index("])\n", i) + 3
s = s[:i] + '''fill(256, [
 ['11', 'Facade diagonals, ground to Level 1', 'SHS 150x150x10', '0.38', 'SLN 36 / LC 147', 'OK'],
 ['21', 'Facade diagonals, Level 1 to Level 2', 'SHS 150x150x10', '0.40', 'SLN 17 / LC 145', 'OK'],
 ['31', 'Facade diagonals, Level 2 to roof', 'SHS 150x150x10', '0.24', 'SLN 380 / LC 147', 'OK'],
 ['12', 'Raking struts', 'SHS 150x150x10', '0.10', 'SLN 448 / LC 121', 'OK'],
 ['13', 'Columns r 8.5 m, ground to Level 1', 'SHS 150x150x10', '0.25', 'SLN 41 / LC 121', 'OK'],
 ['23', 'Columns r 8.5 m, Level 1 to Level 2', 'SHS 150x150x10', '0.14', 'SLN 96 / LC 119', 'OK'],
 ['14', 'Inner columns, ground to Level 1', 'SHS 150x150x10', '0.36', 'SLN 399 / LC 145', 'OK'],
 ['24', 'Inner columns, Level 1 to Level 2', 'SHS 150x150x10', '0.29', 'SLN 417 / LC 122', 'OK'],
 ['15', 'Level 1 beams', 'UB 254x146x43', '0.67', 'SLN 223 / LC 153', 'OK'],
 ['25', 'Level 2 beams', 'UB 457 / UB 254', '0.89', 'SLN 56 / LC 120', 'OK'],
 ['35', 'Roof beams', 'UB 254x146x43', '0.38', 'SLN 318 / LC 107', 'OK'],
 ['60', 'Internal stairs', 'RHS 200x100x6', '0.31', 'SLN 490 / LC 122', 'OK'],
 ['61', 'Landing posts of the internal stairs', 'SHS 100x100x5', '0.11', 'SLN 602 / LC 120', 'OK'],
 ['62', 'External staircase, stringers and landing beams', 'RHS 200x100x6', '0.23', 'SLN 756 / LC 135', 'OK'],
 ['62', 'External staircase, legs', 'SHS 80x80x6.3', '0.98', 'SLN 722 / LC 122', 'OK'],
])
''' + s[j:]
rep("The UB 457x191x89 radials of Level 2 reach 0.73 (SLN 73, combination 148).", "The UB 457x191x89 radials of Level 2 reach 0.73 (SLN 73, combination 147).")
# Table 15
i = s.index("fill(259, ["); j = s.index("])\n", i) + 3
s = s[:i] + '''fill(259, [
 ['1', 'SHS 150x150x10', '0.39', 'beam 110113 (GRP 21) / LC 146', 'OK'],
 ['2', 'UB 254x146x43', '0.79', 'beam 140020 (GRP 25) / LC 120', 'OK'],
 ['4', 'UB 457x191x89', '0.66', 'beam 140389 (GRP 25) / LC 145', 'OK'],
 ['5', 'RHS 200x100x6', '0.41', 'beam 170305 (GRP 60) / LC 120', 'OK'],
 ['6', 'RHS 50x50x5', '0.21', 'beam 170128 (GRP 60) / LC 120', 'OK'],
 ['7', 'Tread tray 300x5 (elastic)', '0.70', 'beam 170105 (GRP 60) / LC envelope, elastic', 'OK'],
 ['8', 'SHS 100x100x5', '0.10', 'beam 180010 (GRP 61) / LC 120', 'OK'],
 ['9', 'SHS 80x80x6.3', '0.26', 'beam 190493 (GRP 62) / LC 152', 'OK'],
])
''' + s[j:]
rep("the program check at the node centreline gives 1.08.')", "the program check at the node centreline gives 1.06.')")
# Table 16
rep("cellsub(265, '7.09', '6.94'); cellsub(265, '7.46', '7.31')", "cellsub(265, '7.09', '6.95'); cellsub(265, '7.46', '7.32')")
rep("The first 20 modes lie between 6.94 and 9.57 (combination 102) and between 7.31 and 10.21 (combination 119).", "The first 20 modes lie between 6.95 and 9.51 (combination 102) and between 7.32 and 10.11 (combination 119).")
rep("with a maximum utilisation of 0.65. No mode of the external staircase appears among the first 20 modes of either combination.')", "with a maximum utilisation of 0.67. In the first mode of either combination the external staircase moves less than 5% of the governing member.')")
rep("msub(ch[269], '1 - 1/7.09', '1 - 1/6.94'); msub(ch[269], ' = 1.164', ' = 1.168')", "msub(ch[269], '1 - 1/7.09', '1 - 1/6.95'); msub(ch[269], ' = 1.164', ' = 1.168')")
# stair table
i = s.index("rows = [\n ['Stringers', 'RHS 200x100x6'"); j = s.index("]\n", s.index("['Treads'", i)) + 2
s = s[:i] + '''rows = [
 ['Stringers', 'RHS 200x100x6', '0.21 / 0.23', 'SLN 701 / LC 135, SLN 713 / LC 122', 'OK'],
 ['Stringer seats of the upper flights on the first landing', 'RHS 200x100x6', '0.23 / 0.27', 'SLN 756 / LC 135', 'OK'],
 ['Landing beams', 'RHS 200x100x6', '0.16 / 0.22', 'SLN 764 / LC 135, SLN 763 / LC 121', 'OK'],
 ['Legs', 'SHS 80x80x6.3', '0.98 / 0.26', 'SLN 722 / LC 122, SLN 768 / LC 152', 'OK'],
 ['Transverse beams between the legs', 'SHS 80x80x6.3', '0.01 / 0.04', 'SLN 793 / LC 123', 'OK'],
 ['Brackets on the Level 1 ring', 'SHS 100x100x5', '0.04 / 0.04', 'SLN 724 / LC 122', 'OK'],
 ['Treads', '5 mm plate (elastic)', '0.52', 'SLN 727 / LC envelope', 'OK'],
]
''' + s[j:]
rep("'The legs are SHS 80x80x6.3 with a height of 4.43 m at the Level 1 landing and a design compression of 34 kN (combination 122). The landings are held in position by the flights, which act as raking struts to their pinned feet, and the buckling analysis of section 7.2.2 shows no mode of the external staircase below a factor of 9.5. The legs are therefore verified with a buckling length equal to their height, which gives 0.33 with the EN 1993-1-1 interaction check.'",
    "'The stringers are pinned at both ends of each flight and carry the stair load as simply supported beams. The legs are SHS 80x80x6.3 with a height of 4.43 m at the Level 1 landing and a design compression of 32 kN (combination 122). They are verified conservatively with a buckling length of twice their height, which gives 0.98. The landings are held in position by the flights, which act as raking struts to their pinned feet, and with a buckling length equal to the height the EN 1993-1-1 interaction check gives 0.33.'")
rep("each foot carries up to 40 kN downward and up to 31 kN uplift, with a horizontal force of up to 61 kN (combination 111), and is anchored to the foundation for these forces. The leg bases carry up to 63 kN downward, up to 13 kN uplift and less than 1 kN horizontally. The brackets on the Level 1 outer ring carry an axial force between 7 kN tension and 17 kN compression.",
    "each foot carries up to 40 kN downward and up to 21 kN uplift, with a horizontal force of up to 48 kN (combination 111), and is anchored to the foundation for these forces. The leg bases carry up to 32 kN downward, up to 6 kN uplift and about 1 kN horizontally. The brackets on the Level 1 outer ring carry an axial force between 2 kN tension and 20 kN compression.")
rep("moves horizontally by 17.2 mm, and by 20.7 mm with wind (combination 218), while the Level 1 ring moves less than 1 mm. The first landing moves by 2.8 mm and 7.9 mm. The vertical deflection of the flights between their ends is 1.1 mm.",
    "moves horizontally by 18.8 mm, and by 21.0 mm with wind (combination 218), while the Level 1 deck moves less than 2 mm. The first landing moves by 2.9 mm and 5.9 mm. The vertical deflection of the flights between their ends is 1.3 mm.")
rep("429.3 kN compression (node 2, combination 146), 120.6 kN uplift (node 12, combination 133) and 117.0 kN horizontal (node 27, combination 105).", "427.8 kN compression (node 2, combination 146), 53.6 kN uplift (node 12, combination 133) and 113.5 kN horizontal (node 27, combination 105).")
rep("300 to 318 kN horizontal and 931 to 997 kN uplift per direction", "196 to 208 kN horizontal and 608 to 651 kN uplift per direction")
rep("The members of the internal stairs and of the external staircase reach 0.67.'", "The members of the internal stairs reach 0.70 and the members of the external staircase reach 0.98.'")
rep("sub(ch[298], '7.09', '6.94')", "sub(ch[298], '7.09', '6.95')")
# Appendix B
rep("The hogging moment at the 340 degree node centreline is 163.2 kNm", "The hogging moment at the 340 degree node centreline is 163.3 kNm")
rep("' = 163.2 - 91 × 0.3 + 0.1 = 136 '", "' = 163.3 - 91 × 0.3 + 0.1 = 136 '")
rep("setcell(c(1, 1), '13.5 kN')", "setcell(c(1, 1), '18.4 kN')")
rep("'136 kNm (163.2 kNm at the node centreline)'", "'136 kNm (163.3 kNm at the node centreline)'")
rep("setcell(c(4, 1), '1.4 kNm')", "setcell(c(4, 1), '1.0 kNm')")
rep("' = 0.009 below 0.25'", "' = 0.012 below 0.25'")
rep("msub(ch[405], '1.2', '1.4'); msub(ch[405], ' = 0.708 + 0.031 = 0.74 ≤ 0.90', ' = 0.763 + 0.036 = 0.80 ≤ 0.90')", "msub(ch[405], '1.2', '1.0'); msub(ch[405], ' = 0.708 + 0.031 = 0.74 ≤ 0.90', ' = 0.763 + 0.026 = 0.79 ≤ 0.90')")
rep("'The axial force is a tension of 13.5 kN.", "'The axial force is a tension of 18.4 kN.")
rep("msub(ch[421], '1.2', '1.4'); msub(ch[421], ' = 0.015 + 0.337 + 0.012 = 0.36 ≤ 0.90', ' = 0.349 + 0.013 = 0.36 ≤ 0.90')", "msub(ch[421], '1.2', '1.0'); msub(ch[421], ' = 0.015 + 0.337 + 0.012 = 0.36 ≤ 0.90', ' = 0.349 + 0.009 = 0.36 ≤ 0.90')")
rep("msub(ch[422], '1.2', '1.4'); msub(ch[422], ' = 0.034 + 0.822 + 0.019 = 0.88 ≤ 0.90', ' = 0.873 + 0.022 = 0.89 ≤ 0.90')", "msub(ch[422], '1.2', '1.0'); msub(ch[422], ' = 0.034 + 0.822 + 0.019 = 0.88 ≤ 0.90', ' = 0.873 + 0.016 = 0.89 ≤ 0.90')")
# wind basis (inserted before the figure renumbering)
wind = r"""
# --- wind pressure 0.50 kPa
sub(ch[125], 'The wind pressure is 0.766 kPa,', 'The wind pressure is 0.50 kPa,')
settext(139, 'The basic velocity pressure is calculated in accordance with EN 1991-1-4 clause 4.5 with a basic wind velocity of 25 m/s:')
_w = clone_after(ch[141], ch[139], 'The design wind pressure is taken as 0.50 kPa, which is the pressure adopted on the cladded area in the original design (1.3 x 0.383 kPa).')
remove(141)
for old, new in (('2.30 kN/m', '1.50 kN/m'), ('0.167 kN/m', '0.109 kN/m'), ('0.84 kN/m', '0.55 kN/m'), ('1.16 kN/m', '0.75 kN/m'), ('0.46 / 0.39 kN/m', '0.30 / 0.25 kN/m'), ('0.766 kPa average', '0.50 kPa average'), ('0.766 kPa', '0.50 kPa'), ('0.153 kPa', '0.10 kPa')):
    cellsub(144, old, new)
"""
rep("# ------------------------------------------------------------------ figure and table numbers in document order", wind + "\n# ------------------------------------------------------------------ figure and table numbers in document order")
open('edit_v20.py', 'w').write(s)
