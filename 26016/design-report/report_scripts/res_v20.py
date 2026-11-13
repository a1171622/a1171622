"""v19 derived numbers for the report: sliding, overturning, leg direct check. Output res_v19.json"""
import sys, json, re, math
sys.path.insert(0, '.')
from memcheck.codes.en1993_1_1 import *
A = '/mnt/project-files/26016/design-report/rev_2026-11-12/v20_export/A_followup/'
a3 = json.load(open(A + 'partA3.json')); a1 = json.load(open(A + 'partA1.json')); a2 = json.load(open(A + 'partA2.json'))
xy = {r['node']: (r['x'], r['y']) for r in a3['rows']}
zst = {n: 0.64 for n in (901, 902, 909, 910)}
L = open('../v20/txt/26016_check_v20.erg', encoding='latin-1').read().splitlines()
react = {}
cur = None
for l in L:
    m = re.match(r'\s+Nodal Reactions\s+Loadcase\s+(\d+)\s', l)
    if m: cur = int(m[1]); continue
    if cur is None: continue
    m = re.match(r'^\s{8,}(\d+)\s+(-?\d+\.\d)\s+(-?\d+\.\d)\s+(-?\d+\.\d)', l)
    if m: react.setdefault(cur, {})[int(m[1])] = tuple(float(m[k]) for k in (2, 3, 4))
    elif l.strip() and not re.search(r'Node|No  |\[kN\]|CaSE|ASE|Viewing|26016|Nodal', l): cur = None
out = {}
bs = {c['lc']: c for c in json.load(open('/mnt/project-files/26016/design-report/rev_2026-11-12/v20_export/reactions_basic_sums.json'))['load_cases']}
for lc in (1, 2, 3, 4, 71, 72, 73, 74):
    s = [sum(v[k] for v in react[lc].values()) for k in range(3)]
    print(lc, len(react[lc]), [round(x, 1) for x in s], bs[lc]['sum_Fz'])
DL = sum(bs[k]['sum_Fz'] for k in (1, 2, 3, 4)); LL = sum(bs[k]['sum_Fz'] for k in (11, 12, 13, 14))
out['DL'] = DL; out['LL'] = LL
rows = []
for name, fd, fl, fw in (('DL + 0.7 LL + 0.5 WL', 1, .7, .5), ('DL + WL', 1, 0, 1), ('DL + LL + 0.5 WL', 1, 1, .5)):
    for lc, wd in ((71, '+X'), (72, '-X'), (73, '-Y'), (74, '+Y')):
        fx = fw * bs[lc]['sum_Fx']; fy = fw * bs[lc]['sum_Fy']; fz = fd * DL + fl * LL + fw * bs[lc]['sum_Fz']
        H = math.hypot(fx, fy); rows.append([name, wd, fx, fy, fz, H, 0.4 * fz / H])
out['sliding'] = rows
# overturning about the edge of the base polygon (distance a = 12 cos 20 from the centre), unfactored DL + WL
a = 12.0 * math.cos(math.radians(20)); ov = []
def mom(lcs, ux, uy):   # moment of the reactions about the horizontal axis through the centre: sum pz * s - sum ph * z
    M = 0; Fz = 0
    for lc in lcs:
        for n, (px, py, pz) in react[lc].items():
            x, y = xy[n]; s = x * ux + y * uy
            M += pz * s - (px * ux + py * uy) * zst.get(n, 0.0); Fz += pz
    return M, Fz
for lc, wd in ((71, '+X'), (72, '-X'), (73, '-Y'), (74, '+Y')):
    fx, fy = bs[lc]['sum_Fx'], bs[lc]['sum_Fy']; H = math.hypot(fx, fy); ux, uy = -fx / H, -fy / H   # wind direction (reaction opposite)
    MG, G = mom((1, 2, 3, 4), ux, uy); MW, FW = mom((lc,), ux, uy)
    # about the leeward edge at s = a: restoring = G a - MG ; overturning = MW - FW a  (FW < 0 uplift)
    Mst = G * a - MG; Mov = MW - FW * a
    ov.append(dict(lc=lc, wind=wd, G=G, xG=MG / G, M_wind_centre=MW, uplift=-FW, M_stab=Mst, M_ov=Mov, factor=Mst / Mov, a=a))
    print(ov[-1])
out['overturning'] = ov
sec = SectionData.from_name('SHS 80x80x6.3')
S = json.load(open('/mnt/project-files/26016/design-report/rev_2026-11-12/v20_export/stair_ext.json'))
legs = []
for m in S['members']:
    if m['kind'] != 'leg': continue
    Lm = m['length_m']
    for key, gf in m.get('governing_forces', {}).items():
        if not key.startswith(('bdk_lc', 'aqb_lc')): continue
        N = gf['N']['min']['value']; My = max(abs(gf['My']['max']['value']), abs(gf['My']['min']['value'])); Mz = max(abs(gf['Mz']['max']['value']), abs(gf['Mz']['min']['value']))
        for f in (1.0, 2.0):
            bk = Buckling(L=Lm, Lcr_y=f * Lm, Lcr_z=f * Lm, L_LT=Lm, fy_y=shape_factors('Linear', 0.0), fz=shape_factors('Linear', 0.0), fLT=shape_factors('Linear', 0.0))
            r = check(sec, 'S275', Demand(N=N, My=My, Mz=Mz), bk)
            u = max(c[1] if isinstance(c, (list, tuple)) and len(c) > 1 and isinstance(c[1], float) else 0 for c in r['checks'])
            legs.append(dict(sln=m['sln'], title=m['title'], L=Lm, key=key, f=f, N=N, My=My, Mz=Mz, util=u, checks=[list(c) for c in r['checks']]))
            print(m['sln'], Lm, key, f, round(N, 1), round(My, 2), round(Mz, 2), r['checks'])
out['legs'] = legs
# stair supports: envelope over the ULS combinations
feet = (901, 902, 909, 910); bases = tuple(n for n in range(903, 917) if n not in feet)
uls = [lc for lc in react if 101 <= lc <= 154]
print('ULS lcs', len(uls))
def env(nodes, lcs):
    mx = max((react[lc][n][2], n, lc) for lc in lcs for n in nodes); mn = min((react[lc][n][2], n, lc) for lc in lcs for n in nodes)
    hh = max((math.hypot(react[lc][n][0], react[lc][n][1]), n, lc) for lc in lcs for n in nodes)
    return dict(pz_max=mx, pz_min=mn, H_max=hh)
strl = [lc for lc in uls if not 131 <= lc <= 134]
out['feet_env'] = env(feet, uls); out['bases_env'] = env(bases, uls); out['feet_env_STR'] = env(feet, strl); out['bases_env_STR'] = env(bases, strl)
for k in ('feet_env', 'bases_env', 'feet_env_STR', 'bases_env_STR'): print(k, out[k])
allcol = [n for n in react[102] if n < 900 or n > 1000]
print('all', env(list(react[102].keys()), uls), env(list(react[102].keys()), strl))
br = S['ring_brackets']['ULS_envelope']; out['bracket_N'] = [max(v['N_max'] for v in br.values()), min(v['N_min'] for v in br.values())]; print(out['bracket_N'])
json.dump(out, open('/mnt/project-files/26016/design-report/rev_2026-11-12/v20_export/res_v19.json', 'w'), indent=1, default=str)
