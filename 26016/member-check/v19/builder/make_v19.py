"""26016 v19 = v18 + external stair stability set-up (Wing 12 Nov 2026):
 (1) the 4 ring brackets (SLN 724/725/769/770) carry vertical force only at the L1 ring (Z only), so the stair frame must stand
     on its own sideways (portal action of the legs);
 (2) the 12 legs become SHS 80x80x6.3 (drawing 201 '80x80x6.3 RHS column (typ)');
 (3) new transverse SHS 80x80x6.3 beams between the legs, pinned both ends (FIXA/FIXE MYMZ), at the heights in elevation 201:
     landing 1 legs at +1.235 m (inner pair C1-C4 and outer pair C2-C3), landing 2 legs D2-D3 at +1.45 and +2.90 m;
 (4) BDK: legs checked with Lcr = 2 x L (pinned-base sway portal, conservative), new beams fork ends.
Usage: python3 make_v19.py <v18.dat> <v19.dat>"""
import re, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ext_geom
src, dst = sys.argv[1], sys.argv[2]
txt = open(src).read()
cnt = {}
def sub1(old, new, n=1):
    global txt
    c = txt.count(old); assert c == n, (old, c); txt = txt.replace(old, new); cnt[old[:30]] = c

# ---- 1. section 9 SHS 80x80x6.3
sub1('PROF TYPE \'RHS\' Z1 100 Z2 100 Z3 5 MNO 3 ALPH 0 YM 0 ZM 0 DTYP    S REF    C\nEND',
     'PROF TYPE \'RHS\' Z1 100 Z2 100 Z3 5 MNO 3 ALPH 0 YM 0 ZM 0 DTYP    S REF    C\n'
     'SECT 9 MNO 3 MRF 0 BTYP BEAM BCY \'A\' BCZ \'A\' TITL "SHS 80x80x6.3 external stair legs + transverse beams (v19)"\n'
     'PROF TYPE \'RHS\' Z1 80 Z2 80 Z3 6.3 MNO 3 ALPH 0 YM 0 ZM 0 DTYP    S REF    C\nEND')
LEGS = [707, 708, 709, 710, 722, 723, 752, 753, 754, 755, 767, 768]
BRK = [724, 725, 769, 770]
# ---- 2. legs -> section 9; brackets -> Z only at the ring end
for n in LEGS:
    txt, k = re.subn(r"(SLN +%d GRP 62 STYP 'N' SNO )8( )" % n, r"\g<1>9\2", txt); assert k == 1, n
for n in BRK:
    txt, k = re.subn(r"(SLN +%d GRP 62 .*?)FIXE 'MYMZ'" % n, r"\1FIXE 'PYPZMXMYMZ'", txt); assert k == 1, n
# ---- 3. transverse beams
lines, supports, lars, flights = ext_geom.build()
leg = {}
for l in lines:
    if l['kind'] == 'leg': leg[l['title']] = l['a'][:2]
B = []
for side in ('right', 'left'):
    g = lambda nm: leg['%s %s' % (side, nm)]
    B += [(g('landing 1 leg inner-low'), g('landing 1 leg inner-high'), 1.235, f'{side} landing 1 inner legs beam +1.235'),
          (g('landing 1 leg outer-low'), g('landing 1 leg outer-high'), 1.235, f'{side} landing 1 outer legs beam +1.235'),
          (g('landing 2 leg outer-low'), g('landing 2 leg outer-high'), 1.45, f'{side} landing 2 legs beam +1.45'),
          (g('landing 2 leg outer-low'), g('landing 2 leg outer-high'), 2.90, f'{side} landing 2 legs beam +2.90')]
last = max(int(m) for m in re.findall(r"^SLN +(\d+) GRP 62 ", txt, re.M)); assert last < 800
NB = list(range(last + 1, last + 1 + len(B)))
new = ['$ ---- v19: transverse SHS 80x80x6.3 beams between the external stair legs, pinned both ends (Wing 12 Nov 2026, elevation 201)']
for n, (a, b, z, t) in zip(NB, B):
    new += ["SLN     %d GRP 62 STYP 'N' SNO 9 DRX 0 0 -1 FIXA 'MYMZ' FIXE 'MYMZ' TITL \"%s\"" % (n, t),
            'SLNB X1 %12.8f %12.8f %12.8f X2 %12.8f %12.8f %12.8f' % (a[0], a[1], z, b[0], b[1], z)]
iM = txt.index('PROG SOFIMSHC urs:2'); iE = txt.index('\nEND', iM)
txt = txt[:iE] + '\n' + '\n'.join(new) + txt[iE:]
# ---- 4. loads: legs wind width 0.08, EHF area 0.00181; same loads on the new beams
sub1("STO#D8     0.10 ", "STO#D9     0.08       $ m SHS 80x80 (v19 external stair legs + transverse beams)\nSTO#D8     0.10 ")
out = []
for l in txt.split('\n'):
    m = re.match(r"(\s*LINE SLN ')(\d+)(' WIDE 0 TYPE .*)", l)
    if m and int(m.group(2)) in LEGS:
        l2 = l.replace('#D8', '#D9').replace('*0.00187', '*0.00181'); out.append(l2)
        if int(m.group(2)) == LEGS[0]:
            out += [m.group(1) + str(n) + m.group(3).replace('#D8', '#D9').replace('*0.00187', '*0.00181') for n in NB]
            cnt['beam_load_blocks'] = cnt.get('beam_load_blocks', 0) + 1
    else: out.append(l)
txt = '\n'.join(out)
# ---- 5. BDK
for n in LEGS:
    txt, k = re.subn(r"(\$ group 62 SLN %d: .*?), SHS 100x100x5, (.*?), fork ends, Lcr = L \(v17\)" % n,
                     r"\1, SHS 80x80x6.3, \2, fork ends, Lcr = 2 L both axes (v19: pinned-base sway portal, conservative)", txt); assert k == 1, n
    txt, k = re.subn(r"MEMB SLN %d TYPE LTB ID %d\n" % (n, n), "MEMB SLN %d TYPE LTB ID %d SKY 2.0 SKZ 2.0\n" % (n, n), txt); assert k == 1, n
memb = []
for n, (a, b, z, t) in zip(NB, B):
    memb += ['$ group 62 SLN %d: %s, SHS 80x80x6.3, L %.2f m, pinned ends, Lcr = L (v19)' % (n, t, np.linalg.norm(a - b)),
             '  CVA CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0            $ fork support', '  CVE CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0',
             'MEMB SLN %d TYPE LTB ID %d' % (n, n)]
lm = max(int(m) for m in re.findall(r'^MEMB SLN (7\d\d) TYPE LTB ID', txt, re.M))
anchor = re.search(r'MEMB SLN %d TYPE LTB ID %d[^\n]*\n' % (lm, lm), txt).group(0)
assert txt.count(anchor) == 1
txt = txt.replace(anchor, anchor + '\n'.join(memb) + '\n')
hdr = ['$ 26016 member check v19 (12 Nov 2026) = v18 + external stair stability set-up (Wing): ring brackets 724/725/769/770 Z only',
       "$   (FIXE 'PYPZMXMYMZ' at the ring), legs SHS 80x80x6.3 (SECT 9), transverse SHS 80x80x6.3 beams SLN %d-%d pinned both ends" % (NB[0], NB[-1]),
       '$   (landing 1 legs at +1.235, landing 2 legs at +1.45 and +2.90), BDK legs Lcr = 2 L. Built by make_v19.py.']
open(dst, 'w', newline='').write('\n'.join(hdr) + '\n' + txt)
print(cnt, 'beams', NB)
