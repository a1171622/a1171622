"""v21 = v20 updated to drawings 970027-S01-ST (issue 13.11.2026), only:
 1. new SECT 10 RHS 160x80x5: external stair (group 62) stringers, stringer seats, landing edge / middle beams (all SNO 5 lines of
    group 62) and the internal stair stringers (sloped SNO 5 lines of group 60); group 60 landing beams / posts stay RHS 200x100x6.
 2. SECT 4 L2 radials UB 457x191x89 -> UB 457x191x98.
 3. external stair landing supports on the L1 ring (group 62, SNO 8: SLN 724, 725, 769, 770) -> SECT 9 SHS 80x80x6.3 (end releases kept).
Everything else as v20 (qp 0.5 kPa, 12 stringer My hinges, pinned feet, loads, combinations, BDK/AQB/buckling).
py -3.11 make_v21.py"""
import re, os
SRC = r"C:\Sofistik workflow\26016-member-check\v20\26016_check_v20.dat"
DST = r"C:\Sofistik workflow\26016-member-check\v21\26016_check_v21.dat"
t = open(SRC, encoding="cp1252").read()
G62_5 = [701, 702, 703, 704, 705, 706, 711, 712, 713, 714, 715, 716, 717, 718, 719, 720, 721,
         746, 747, 748, 749, 750, 751, 756, 757, 758, 759, 760, 761, 762, 763, 764, 765, 766]
G60_STR = [79, 90, 136, 137, 461, 472, 489, 490]
G62_8 = [724, 725, 769, 770]
n = 0
def sno(sln, grp, old, new):
    global t, n
    pat = re.compile(rf"^(SLN\s+{sln} GRP {grp} STYP 'N' SNO ){old}( )", re.M)
    t2, k = pat.subn(rf"\g<1>{new}\g<2>", t); assert k == 1, (sln, k); t = t2; n += 1
for s in G62_5: sno(s, 62, 5, 10)
for s in G60_STR: sno(s, 60, 5, 10)
for s in G62_8: sno(s, 62, 8, 9)
old4 = "PROF TYPE 'UB' Z1 457 Z2 191 Z3 89 MNO 3"
assert t.count(old4) == 1; t = t.replace(old4, "PROF TYPE 'UB' Z1 457 Z2 191 Z3 98 MNO 3")
s9 = re.search(r"SECT 9 MNO 3 [^\n]*\nPROF TYPE 'RHS' Z1 80 Z2 80 Z3 6.3[^\n]*\n", t)
t = t[:s9.end()] + ("SECT 10 MNO 3 MRF 0 BTYP BEAM BCY 'A' BCZ 'A' TITL \"RHS 160x80x5 stair stringers + ext. stair landing beams (v21, drg 1201/1302/1303)\"\n"
                    "PROF TYPE 'RHS' Z1 160 Z2 80 Z3 5 MNO 3 ALPH 0 YM 0 ZM 0 DTYP    S REF    C\n") + t[s9.end():]
hdr = ("$ v21 (13 Nov 2026, Wing): v20 updated to drawings 970027-S01-ST (issue 13.11.2026), only: (1) new SECT 10 RHS 160x80x5 for the external\n"
       "$   stair stringers, stringer seats and landing edge/middle beams (group 62 SNO 5 -> 10, 34 SLN) and the internal stair stringers (group 60\n"
       "$   sloped SLN 79 90 136 137 461 472 489 490 -> 10; group 60 landing beams stay RHS 200x100x6); (2) SECT 4 L2 radials UB 457x191x89 -> 98;\n"
       "$   (3) external stair landing supports on the L1 ring SLN 724 725 769 770 SHS 100x100x5 -> SHS 80x80x6.3 (SECT 9), releases unchanged.\n"
       "$   Stair wind depth parameter #D5 left at 0.20 m (conservative for 160 mm). Everything else as v20.\n")
t = hdr + t
os.makedirs(os.path.dirname(DST), exist_ok=True)
open(DST, "w", encoding="cp1252", newline="").write(t)
print("SLN changed", n, "-> written", DST)
