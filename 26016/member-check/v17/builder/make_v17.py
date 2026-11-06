"""26016 v17 = v16 + (1) stair B moved one bay (-20 deg: foot L1 radial 20, top L2 radial 60, landing posts on the L1
radial at 40), L2 opening 40-80 -> 20-60 (L2 UB457 radial at 40 stops at r 8.5, the one at 60 runs to r 12), deck-load
void moved with it; (2) external stair ground -> L1 from Wing's DXF 'ALS-FAB-0140-REV00 CONCOURSE C-2026 (edited)'
(model = DXF rotated +20 deg about the platform centre (93341, 0), z + 4.004 m), group 62, internal-stair sections
(RHS 200x100x6 sect 5, 300x5 treads sect 7, SHS 100x100x5 sect 8 for legs and ring brackets), confirmed by Wing 6 Nov 2026.
Usage: python3 make_v17.py <v16.dat> <v17.dat>"""
import re, math, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse import parse_sln
from stairwind import stair_wind, sexpr
import ext_geom
src, dst = sys.argv[1], sys.argv[2]
L = open(src).read().split('\n')
iMSH = L.index('PROG SOFIMSHC urs:2'); iMSHend = next(i for i in range(iMSH, len(L)) if L[i] == 'END')
sln = parse_sln(L[:iMSHend], iMSHend)
ROT = -20.0
def rot(p, deg=ROT):
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    return np.array([p[0]*c - p[1]*s, p[0]*s + p[1]*c] + list(p[2:]))
def ang(p): return math.degrees(math.atan2(p[1], p[0])) % 360
def fmt3(p): return '%12.8f %12.8f %12.8f' % tuple(p)
cnt = {}
def bump(k, n=1): cnt[k] = cnt.get(k, 0) + n

# ---------------- 1. stair B (groups 60 and 61, north side) rotated by -20 deg ----------------
B = sorted(n for n, v in sln.items() if v['grp'] in (60, 61) and ang((v['segs'][0][0] + v['segs'][-1][1]) / 2) < 180)
for n in B:
    v = sln[n]
    h = L[v['line']]
    m = re.search(r'DRX\s+(\S+)\s+(\S+)\s+(\S+)', h)
    if m:
        d = rot([float(x) for x in m.groups()])
        h = h[:m.start()] + 'DRX %.6g %.6g %.6g' % tuple(d) + h[m.end():]
    pass
    L[v['line']] = h
    for bl in v['blines']:
        l = L[bl]
        def rp(mm):
            p = rot([float(mm.group(2)), float(mm.group(3)), float(mm.group(4))])
            return '%s %s' % (mm.group(1), fmt3(p))
        L[bl] = re.sub(r'(X[12M])\s+(\S+)\s+(\S+)\s+(\S+)', rp, l)
    bump('stairB_rotated')

# ---------------- 1b. L1-L2 column SLN 121 (under the cut L2 radial end at r 8.5) moves with the opening, 60 -> 40 deg
#      (stair A has the same: column SLN 85 under the cut radial end at 280 deg; independent review 6 Nov 2026)
#      v17a (Wing 6 Nov 2026): both stair-B columns follow the stair, 121 60 -> 40 deg and 131 80 -> 60 deg
for cn in (121, 131):
    v = sln[cn]; assert v['grp'] == 13
    for bl in v['blines']:
        L[bl] = re.sub(r'(X[12M])\s+(\S+)\s+(\S+)\s+(\S+)', lambda mm: '%s %s' % (mm.group(1), fmt3(rot([float(mm.group(2)), float(mm.group(3)), float(mm.group(4))]))), L[bl])
    m = re.search(r'DRX\s+(\S+)\s+(\S+)\s+(\S+)', L[v['line']])
    L[v['line']] = L[v['line']][:m.start()] + 'DRX %.6g %.6g %.6g' % tuple(rot([float(x) for x in m.groups()])) + L[v['line']][m.end():]
    bump('col_rotated')
    # snap the column foot onto the top of the L1 column below (r 8.5, same angle) so SOFIMSHC merges it well inside TOLG
    below = sln[{121: 40, 131: 41}[cn]]
    top = below['segs'][0][0] if below['segs'][0][0][2] > below['segs'][-1][1][2] else below['segs'][-1][1]
    bl = v['blines'][-1]
    L[bl] = re.sub(r'X2\s+\S+\s+\S+\s+(\S+)', lambda mm: 'X2 %12.8f %12.8f %s' % (top[0], top[1], mm.group(1)), L[bl])

# ---------------- 2. L2 radials: 40 deg stops at r 8.5 (opening), 60 deg runs to r 12 ----------------
P85_40 = (6.51186867, 5.46284146, 8.055); P12_60 = (5.99999907, 10.3923016, 8.055)
for n, p in ((81, P85_40), (87, P12_60)):
    bl = sln[n]['blines'][0]
    L[bl] = re.sub(r'X1\s+\S+\s+\S+\s+\S+', 'X1 ' + fmt3(p), L[bl], count=1); bump('L2radial')

# ---------------- 3. external stair, group 62 ----------------
lines, supports, lars, flights = ext_geom.build()
SLN0, SPT0, LAR0 = 701, 901, 605
for k, l in enumerate(lines): l['no'] = SLN0 + k
def drx(l):
    e = l['b'] - l['a']; e = e / np.linalg.norm(e)
    if abs(e[2]) > 0.999: return (1, 0, 0)
    d = np.array([0, 0, -1.0]) - np.dot([0, 0, -1.0], e) * e; d /= np.linalg.norm(d); return tuple(d)
new_sln = ['$ ---- v17: external stair ground -> L1 (group 62), Wing DXF 6 Nov 2026; leg bases and flight feet pinned (SPT 901-916),',
           '$      landing 2 corners on the L1 r12 ring through 4 short SHS brackets, pinned at the ring (FIXE MYMZ), rigid at the landing']
for l in lines:
    rel = " FIXE '%s'" % l['rel'] if l.get('rel') else ''
    d = drx(l)
    new_sln += ["SLN     %d GRP 62 STYP 'N' SNO %d DRX %.6g %.6g %.6g%s TITL \"%s\"" % (l['no'], l['sno'], d[0], d[1], d[2], rel, l['title'][:60]),
                'SLNB X1 %s X2 %s' % (fmt3(l['a']), fmt3(l['b']))]
new_spt = ['$ ---- v17: external stair ground supports (pinned), start platform taken as ground']
for k, (p, t) in enumerate(supports):
    new_spt += ['SPT     %d X %10.5f %10.5f %10.5f NX 0 0 -1 SX 1 0 0 TITL "%s"' % (SPT0 + k, p[0], p[1], p[2], t[:60]), 'SPTP TYPE PP']
iFirstSLN = next(i for i in range(iMSH, iMSHend) if L[i].startswith('SLN '))
iGrp61 = next(i for i in range(iMSH, iMSHend) if L[i] == 'GRP  61')
L = L[:iGrp61 + 1] + ['GRP  62'] + L[iGrp61 + 1:iFirstSLN] + new_spt + L[iFirstSLN:iMSHend] + new_sln + L[iMSHend:]
off = 1 + len(new_spt) + len(new_sln)

# geometry after the change, for the loads
sln2 = parse_sln(L, next(i for i in range(len(L)) if L[i] == 'END' and i > iMSH))
S = {n: (v['segs'][0][0], v['segs'][-1][1], v['sno']) for n, v in sln2.items() if v['grp'] in (60, 62)}
ext = {l['no']: l for l in lines}
rail = [l['no'] for l in lines if l.get('rail')]
fl_lines = [n for pair in flights for n in (lines[pair[0]]['no'], lines[pair[1]]['no'])]
stringers = [l['no'] for l in lines if l['kind'] == 'stringer']
def hfrac(n): A, Bp, _ = S[n]; d = Bp - A; return math.hypot(d[0], d[1]) / np.linalg.norm(d)
# outward normal (plan) of each rail line: away from the centroid of its flight / landing
def part_centroid(l):
    same = [m for m in lines if m['title'].split(' ')[:3] == l['title'].split(' ')[:3] and m['kind'] in ('stringer', 'landing')]
    return np.mean([(m['a'] + m['b']) / 2 for m in same], axis=0)
def outward(l):
    d = (l['b'] - l['a'])[:2]; d /= np.linalg.norm(d); nb = np.array([-d[1], d[0]])
    mid = ((l['a'] + l['b']) / 2)[:2]; c = part_centroid(l)[:2]
    if l['kind'] == 'stringer':   # flight: the other stringer of the same flight
        other = [m for m in lines if m['kind'] == 'stringer' and m.get('flight') == l.get('flight') and m is not l][0]
        c = ((other['a'] + other['b']) / 2)[:2]
    return nb if np.dot(nb, mid - c) > 0 else -nb
def c4(x): return float('%.4g' % x)
def bexpr(base, c):
    c = c4(c)
    if abs(abs(c) - 1) < 1e-9: return ('-' if c < 0 else '') + base
    return ('-' if c < 0 else '') + base + '*' + ('%.4g' % abs(c))

# ---------------- 4. SOFILOAD ----------------
iLD = L.index('+PROG SOFILOAD urs:5'); iASE = L.index('+PROG ASE urs:6')
LD = L[iLD:iASE]
def find(lines_, head):
    i = lines_.index(head); j = i + 1
    while j < len(lines_) and lines_[j].strip(): j += 1
    return i, j
# 4a. LAR 603/604 rotated, new landing LARs 605-610
for k, l in enumerate(LD):
    m = re.match(r'LAR (603|604) T 0 (.*)', l)
    if m:
        pts = re.findall(r'(X\d)\s+(\S+)\s+(\S+)\s+(\S+)', m.group(2))
        LD[k] = 'LAR %s T 0 ' % m.group(1) + ' '.join('%s %.6f %.6f %.6f' % ((x,) + tuple(rot([float(a), float(b), float(c)]))) for x, a, b, c in pts)
        bump('LAR_rot')
i604 = next(k for k, l in enumerate(LD) if l.startswith('LAR 604 '))
newlar = []
for k, (t, pts) in enumerate(lars):
    newlar.append('LAR %d T 0 ' % (LAR0 + k) + ' '.join('X%d %.6f %.6f %.6f' % ((j + 1,) + tuple(p)) for j, p in enumerate(pts)) + '   $ v17 ' + t)
LD[i604 + 1:i604 + 1] = newlar
NEWLAR = list(range(LAR0, LAR0 + len(lars)))
# 4b. parameters
for k, l in enumerate(LD):
    if l.startswith('STO#STV '):
        LD[k] = l.replace('260-300 and 40-80 deg, Wing 2026-10-19', '260-300 and 20-60 deg (v17; was 40-80), Wing 2026-10-19')
    if l.startswith('STO#D6 '):
        LD.insert(k + 1, 'STO#D8     0.10       $ m SHS 100x100 depth facing the wind (v17 external stair legs + ring brackets, section 8)'); break
# 4c. L2 void: sector 34 (60-80) back to deck, sector 32 (20-40) becomes void (inner 814 + mid 834, outer 854 empty)
out = []; k = 0
while k < len(LD):
    l = LD[k]
    m = re.match(r"(\s*)IF #NSTV>0$", l)
    if m and k + 6 < len(LD) and re.match(r"\s*AREA LAR '34' ", LD[k + 1]) and "LAR '816'" in LD[k + 4]:
        ind = m.group(1); rest = LD[k + 1].split("AREA LAR '34' ", 1)[1]
        out.append(ind + "AREA LAR '34' " + rest); k += 7; bump('void34_off'); continue
    m = re.match(r"(\s*)AREA LAR '32' (.*)", l)
    if m:
        ind, rest = m.groups()
        out += [ind + 'IF #NSTV>0', ind + "  AREA LAR '32' " + rest, ind + 'ENDIF', ind + 'IF #STV>0',
                ind + "  AREA LAR '814' " + rest, ind + "  AREA LAR '834' " + rest, ind + 'ENDIF']
        k += 1; bump('void32_on'); continue
    out.append(l); k += 1
LD = out
txt = '\n'.join(LD)
n0 = txt.count("LC 456 TYPE")
txt = txt.replace("IF #NSTV>0\nLC 456 TYPE 'QB' TITL 'LL L2 sector 16 outer'\n  IF #NSTV>0\n    AREA LAR '856' WIDE 0 TYPE PG #LL\n  ENDIF\nENDIF",
                  "LC 456 TYPE 'QB' TITL 'LL L2 sector 16 outer'\n  AREA LAR '856' WIDE 0 TYPE PG #LL")
txt = txt.replace("LC 454 TYPE 'QB' TITL 'LL L2 sector 14 outer'\n  AREA LAR '854' WIDE 0 TYPE PG #LL",
                  "IF #NSTV>0\nLC 454 TYPE 'QB' TITL 'LL L2 sector 14 outer'\n  IF #NSTV>0\n    AREA LAR '854' WIDE 0 TYPE PG #LL\n  ENDIF\nENDIF")
assert "IF #NSTV>0\nLC 454" in txt and "IF #NSTV>0\nLC 456" not in txt
txt = txt.replace('LET#P2O 441,442,443,444,445,446,447,450,451,452,453,454,457,458', 'LET#P2O 441,442,443,444,445,446,447,450,451,452,453,456,457,458')
LD = txt.split('\n')
# 4d. stair load cases
def add_to(head, extra):
    i, j = find(LD, head); LD[j:j] = extra
EXT = '  $ v17 external stair'
add_to("LC 3 TYPE 'G' TITL 'SDL stairs handrail'", [EXT] + ["  LINE SLN '%d' WIDE 0 TYPE PG #HR" % n for n in rail] +
       ['  IF #SDLL>0'] + ["    AREA LAR '%d' WIDE 0 TYPE PG #SDLL" % n for n in NEWLAR] + ['  ENDIF'])
add_to("LC 4 TYPE 'G' TITL 'DL 0.2 kPa all floors'", [EXT] + ["  LINE SLN '%d' WIDE 0 TYPE PZP -#DLF*#BST/2" % n for n in fl_lines] +
       ["  AREA LAR '%d' WIDE 0 TYPE PG #DLF" % n for n in NEWLAR])
add_to("LC 14 TYPE 'QB' TITL 'LL stairs'", [EXT] + ["  LINE SLN '%d' WIDE 0 TYPE PZP -#LLS*#BST/2" % n for n in fl_lines] +
       ["  AREA LAR '%d' WIDE 0 TYPE PG #LLS" % n for n in NEWLAR])
Bset = set(B)
for lc, sg in ((15, 1), (16, -1)):
    head = [l for l in LD if l.startswith('LC %d TYPE' % lc)][0]
    i, j = find(LD, head); blk = LD[i:j]; new = [blk[0]]; q = 1
    while q < len(blk):
        m = re.match(r"  LINE SLN '(\d+)' WIDE 0 TYPE PXX (.*)", blk[q])
        if m and int(m.group(1)) in Bset:
            n = int(m.group(1))
            def val(e):
                s = -1 if e.startswith('-') else 1; e = e.lstrip('-'); mm = re.search(r'\*([\d.]+)$', e)
                return s * (float(mm.group(1)) if mm and not e.endswith('#HBR') else 1.0)
            nx = val(m.group(2)); ny = val(blk[q + 1].split('TYPE PYY ')[1])
            r = rot([nx, ny]); nx2, ny2 = r[0], r[1]
            new += ["  LINE SLN '%d' WIDE 0 TYPE PXX %s" % (n, bexpr('#BAR', nx2)), "  LINE SLN '%d' WIDE 0 TYPE PYY %s" % (n, bexpr('#BAR', ny2)),
                    "  LINE SLN '%d' WIDE 0 TYPE MXX %s" % (n, bexpr('#BAR*#HBR', -ny2)), "  LINE SLN '%d' WIDE 0 TYPE MYY %s" % (n, bexpr('#BAR*#HBR', nx2))]
            q += 4; bump('barrier_rot'); continue
        new.append(blk[q]); q += 1
    new.append(EXT)
    for n in rail:
        o = outward(ext[n]) * sg
        new += ["  LINE SLN '%d' WIDE 0 TYPE PXX %s" % (n, bexpr('#BAR', o[0])), "  LINE SLN '%d' WIDE 0 TYPE PYY %s" % (n, bexpr('#BAR', o[1])),
                "  LINE SLN '%d' WIDE 0 TYPE MXX %s" % (n, bexpr('#BAR*#HBR', -o[1])), "  LINE SLN '%d' WIDE 0 TYPE MYY %s" % (n, bexpr('#BAR*#HBR', o[0]))]
    LD[i:j] = new
# wind 25-28: regenerated for all stairs (generator logic, checked to reproduce v16 exactly on v16 geometry)
i3, j3 = find(LD, "LC 3 TYPE 'G' TITL 'SDL stairs handrail'")
bal = [int(m.group(1)) for l in LD[i3:j3] for m in [re.match(r"\s+LINE SLN '(\d+)'", l)] if m]
drag = [n for n, (a, b, s) in S.items() if (sln2[n]['grp'] == 60 and s in (5, 6)) or (sln2[n]['grp'] == 62 and s in (5, 8))]
W = stair_wind(S, drag, bal, [136, 137, 79, 90, 489, 490, 461, 472] + fl_lines, [601, 602, 603, 604] + NEWLAR,
               {5: ('#CF5', '#D5'), 6: ('#CF6', '#D6'), 8: ('#CF5', '#D8')})
for lc, blk in W.items():
    i, j = find(LD, blk[0]); LD[i:j] = blk; bump('wind_regen')
# EHF 501-508
SW = {5: '0.0115', 7: '0.002', 8: '0.00187'}
for lc, comp, sg in ((501, 'PXX', ''), (502, 'PXX', '-'), (503, 'PYY', '-'), (504, 'PYY', '')):
    head = [l for l in LD if l.startswith('LC %d TYPE' % lc)][0]
    add_to(head, ['  $ v17 external stair: member self-weight, handrail, DL, landing SDL x phi'] +
           ["  LINE SLN '%d' WIDE 0 TYPE %s %s#PHI*#RHOS*%s" % (l['no'], comp, sg, SW[l['sno']]) for l in lines] +
           ["  LINE SLN '%d' WIDE 0 TYPE %s %s#PHI*#HR" % (n, comp, sg) for n in rail] +
           ["  LINE SLN '%d' WIDE 0 TYPE %s %s#PHI*#DLF*#BST/2*%.5g" % (n, comp, sg, hfrac(n)) for n in fl_lines] +
           ["  AREA LAR '%d' WIDE 0 TYPE %s %s#PHI*#DLF" % (n, comp, sg) for n in NEWLAR] +
           ["  AREA LAR '%d' WIDE 0 TYPE %s %s#PHI*#SDLL" % (n, comp, sg) for n in NEWLAR])
for lc, comp, sg in ((505, 'PXX', ''), (506, 'PXX', '-'), (507, 'PYY', '-'), (508, 'PYY', '')):
    head = [l for l in LD if l.startswith('LC %d TYPE' % lc)][0]
    add_to(head, ['  $ v17 external stair LL x phi'] +
           ["  LINE SLN '%d' WIDE 0 TYPE %s %s#PHI*#LLS*#BST/2*%.5g" % (n, comp, sg, hfrac(n)) for n in fl_lines] +
           ["  AREA LAR '%d' WIDE 0 TYPE %s %s#PHI*#LLS" % (n, comp, sg) for n in NEWLAR])
# temperature
LD2 = []
for l in LD:
    LD2.append(l)
    m = re.match(r'(\s*BEAM FROM GRP TO )61( TYPE DT .*)', l)
    if m: LD2.append(m.group(1) + '62' + m.group(2)); bump('DT')
LD = LD2
L = L[:iLD] + LD + L[iASE:]

# ---------------- 5. LC lists (ASE / MAXIMA): 454 conditional, 456 always ----------------
txt = '\n'.join(L)
a = txt.count('IF #NSTV>0\n    LC 456\n  ENDIF') + txt.count('IF #NSTV>0\n    LC NO 456\n  ENDIF')
txt = re.sub(r'IF #NSTV>0\n(\s*)(LC (?:NO )?)456\n\s*ENDIF', lambda m: m.group(2) + '456', txt)
txt = re.sub(r'\n(\s*)(LC (?:NO )?)454\n', lambda m: '\n%sIF #NSTV>0\n%s  %s454\n%sENDIF\n' % (m.group(1), m.group(1), m.group(2), m.group(1)), txt)
cnt['LClist_456'] = a
L = txt.split('\n')

# ---------------- 6. BDK ----------------
txt = '\n'.join(L)
blk81 = re.search(r'\$ L2 radial 40 deg: SLN 81,.*?MEMB SLN 81 TYPE LTB ID 81\n', txt, re.S)
blk87 = re.search(r'\$ L2 radial 60 deg: SLN 87,.*?MEMB SLN 87 TYPE LTB ID 87\n', txt, re.S)
assert blk81 and blk87
def radial_block(no, deg, r0, L_, ends, stations, spans):
    s = ['$ L2 radial %d deg: SLN %d, r %.2f -> 0.66, L %.2f m, ends: %s (v17: stair B opening moved to 20-60 deg)' % (deg, no, r0, L_, ends),
         '$   spans between the ring crossings: %s' % spans,
         'IF #AUTO>0', '  CVA CB 0 CY AUTO CZ AUTO DX AUTO DY AUTO DZ AUTO', '  CVE CB 0 CY AUTO CZ AUTO DX AUTO DY AUTO DZ AUTO', 'ELSE',
         '  CVA CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0            $ fork support', '  CVE CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0', 'ENDIF']
    s += stations
    s += ['IF #DECK>0', '  CVL HDIV #NPART CY FIX EZ TOP                       $ top-flange lateral restraint by the deck', 'ENDIF',
          'MEMB SLN %d TYPE LTB ID %d' % (no, no)]
    return '\n'.join(s) + '\n'
new81 = radial_block(81, 40, 8.5, 7.84, 'column 121 (moved to 40 deg in v17) / kingpost plates',
                     ['CVL REF STRT S 5.500 CY FIX DX #DXR EZ #EZR          $ r 3.0: ring beams only'], '5.50 / 2.34 m')
new87 = radial_block(87, 60, 12.0, 11.34, 'ring r12 + perimeter diagonals / kingpost plates',
                     ['CVL REF STRT S 9.000 CY FIX DX #DXR EZ #EZR          $ r 3.0: ring beams only',
                      'CVL REF STRT S 3.500 CY FIX DX FIX  EZ #EZR          $ r 8.5: column 131 (moved 80 -> 60 deg in v17a)'], '3.50 / 5.50 / 2.34 m')
txt = txt.replace(blk81.group(0), new81).replace(blk87.group(0), new87)
# v17a: L2 radial 80 deg (SLN 89) loses column 131 at r 8.5 -> ring beams only, as the other radials without a column
o89 = 'CVL REF STRT S 3.500 CY FIX DX FIX  EZ #EZR          $ r 8.5: column 131\n'
assert txt.count(o89) == 1
txt = txt.replace(o89, 'CVL REF STRT S 3.500 CY FIX DX #DXR EZ #EZR          $ r 8.5: ring beams only (column 131 moved to 60 deg in v17a)\n')
txt = txt.replace('restraint stations: r 3.0 at 9.00 m (column 423), r 8.5 at 3.50 m (column 131)', 'restraint stations: r 3.0 at 9.00 m (column 423), r 8.5 at 3.50 m (ring beams only, v17a)')
txt = txt.replace('r 8.5 at 3.50 m (column 41/121/452)', 'r 8.5 at 3.50 m (column 41/131/452, v17a)')
txt = txt.replace('r 8.5 at 3.50 m (column 42/131)', 'r 8.5 at 3.50 m (column 42)')
txt = txt.replace('r 8.5 at 3.50 m (column 40)\n', 'r 8.5 at 3.50 m (column 40/121, v17a)\n')
memb = []
for l in lines:
    if l['kind'] == 'tread': continue
    Lm = float(np.linalg.norm(l['b'] - l['a'])); d = l['b'] - l['a']; inc = math.degrees(math.atan2(abs(d[2]), math.hypot(d[0], d[1])))
    sec = {5: 'RHS 200x100x6', 8: 'SHS 100x100x5'}[l['sno']]
    memb += ['$ group 62 SLN %d: %s, %s, L %.2f m, %.0f deg to the horizontal, fork ends, Lcr = L (v17)' % (l['no'], l['title'], sec, Lm, inc),
             '  CVA CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0            $ fork support', '  CVE CB 0 CY FIX CZ FIX DX FIX DY 0 DZ 0',
             'MEMB SLN %d TYPE LTB ID %d' % (l['no'], l['no'])]
anchor = 'MEMB SLN 604 TYPE LTB ID 604\n'
assert txt.count(anchor) == 1
txt = txt.replace(anchor, anchor + '\n'.join(memb) + '\n')
txt = txt.replace("STO#STR   1          $ 1 = check the RHS 200x100x6 stair stringers, posts and landing beams (group 60) and the SHS 100x100x5 landing posts (group 61)",
                  "STO#STR   1          $ 1 = check the RHS 200x100x6 stair stringers, posts and landing beams (group 60), the SHS 100x100x5 landing posts (group 61) and the external stair (group 62, v17)")
L = txt.split('\n')
hdr = ['$ 26016 member check v17 (6 Nov 2026) = v16 + (a) stair B moved one bay: foot on the L1 radial at 20 deg, landing ~42 deg, top on',
       '$   the L2 radial at 60 deg, landing posts SLN 603/604 on the L1 radial at 40 deg (SLN 263); L2 opening 40-80 -> 20-60 deg: L2 radial',
       '$   SLN 81 (40 deg) now r 8.5 -> 0.66, SLN 87 (60 deg) now r 12 -> 0.66; deck-load void (#STV) on sector 20-40 instead of 60-80;',
       '$   (b) external stair ground -> L1 (group 62, SLN 701-%d, SPT 901-%d, LAR 605-%d) from Wing DXF ALS-FAB-0140-REV00 (edited):' % (SLN0 + len(lines) - 1, SPT0 + len(supports) - 1, LAR0 + len(lars) - 1),
       '$   start platform at 332-348 deg (taken as ground), two arms with landings at +2.43 and +4.43 m (L1 at 15-25 and 295-305 deg),',
       '$   RHS 200x100x6 stringers + landing beams, 300x5 treads, SHS 100x100x5 legs (pinned bases) and 4 SHS ring brackets pinned on the',
       '$   L1 r12 ring at 15, 25, 295, 305 deg (S1-S4). Loads: handrail, DL, LL, barrier, wind (stair generator, all stairs regenerated),',
       '$   EHF, temperature as group 60. Built by make_v17.py.',
       '$ v17a (Wing 6 Nov 2026): both L1-L2 columns at r 8.5 follow stair B: SLN 121 60 -> 40 deg, SLN 131 80 -> 60 deg (v17 moved 121 only).']
L = hdr + [l.replace('radial SLN 266 at 60 deg', 'radial SLN 263 at 40 deg') for l in L]
open(dst, 'w', newline='').write('\n'.join(L))
print(cnt, 'B lines', len(B), 'ext lines', len(lines), 'supports', len(supports))
