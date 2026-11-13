"""Build v19m IOM XMLs for the L1 strut joints (S x7, T x2) and the L2 r 8.5 haunch-flush M20 joints (18) from the
current v15 templates, plates / bolts / welds untouched, forces from the v19m cdb, all 43 ULS STR cases.
Same route as build_v19m_xml.py (L1 A/B no flange): per element the cdb -> IOM mapping is fitted on the v15
templates against the v15 cdb (calib_v15_strut_L2.json + a least-squares fit done here).

MODE direct : each IOM component = sign x one cdb component (the dominant term of the fit), as for L1 A/B.
MODE v15tr  : strut ring ends only: IOM N / Qy = the linear combination of N, Vy found in the v15 templates
              (they carry the forces rotated by about 10 deg: Qy = 0.985 Vy +/- 0.174 N). Reproduces the v15 route.
v19 topology (columns L1-L2 at r 8.5 moved to 40 / 60 deg): L2 joints at 40, 60, 80 deg use the v15 template of the
same layout rotated -20 deg; every v19m beam at the node must match a template member (dot > 0.999) and no beam may
be left over, else the joint is not built.
py -3.11 build_more.py <v19m cdb> <out_root> <direct|v15tr> [struts|L2|all]"""
import sys, os, re, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iomx import load
from calib import geom, match, IC
from cdbend import Model
from sofistik_mcp import results as R

CDB, OUT, MODE = sys.argv[1], sys.argv[2], sys.argv[3]
WHICH = sys.argv[4] if len(sys.argv) > 4 else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
CAL = json.load(open(os.path.join(HERE, 'calib_v15_strut_L2.json')))
T15 = r"C:\Sofistik workflow\idea-statica\v15"
SC = ('N', 'Vy', 'Vz', 'Mt', 'My', 'Mz')
TARGETS = []
if WHICH in ("struts", "all"):
    for j in ('S_020', 'S_100', 'S_140', 'S_180', 'S_220', 'S_300', 'S_340', 'T_060', 'T_260'):
        TARGETS.append((f'L1-R8-{j}', 'xml_strut_10deg_asis', f'L1-R8-{j}.xml', 0, 'xml_strut_10deg' + ('' if MODE == 'direct' else '_v15tr')))
if WHICH in ("L2", "all"):
    pa = {a: 'partA' if a in (0, 20, 40, 100, 120, 140, 160, 180, 200) else 'partB' for a in range(0, 360, 20)}
    for a in (0, 20, 100, 120, 140, 160, 180, 200, 220, 240, 300, 320, 340):
        TARGETS.append((f'L2-R8-A_{a:03d}', f'xml_L2haunch_flush_asis\\{pa[a]}', f'L2-R8-A_{a:03d}.xml', 0, 'xml_L2haunch_flush_M20'))
    TARGETS += [('L2-R8-A_080', 'xml_L2haunch_flush_asis\\partA', 'L2-R8-A_100.xml', -20, 'xml_L2haunch_flush_M20'),
                ('L2-R8-B_040', 'xml_L2haunch_flush_asis\\partB', 'L2-R8-B_060.xml', -20, 'xml_L2haunch_flush_M20'),
                ('L2-R8-B_060', 'xml_L2haunch_flush_asis\\partB', 'L2-R8-B_080.xml', -20, 'xml_L2haunch_flush_M20'),
                ('L2-R8-B_260', 'xml_L2haunch_flush_asis\\partB', 'L2-R8-B_260.xml', 0, 'xml_L2haunch_flush_M20'),
                ('L2-R8-B_280', 'xml_L2haunch_flush_asis\\partB', 'L2-R8-B_280.xml', 0, 'xml_L2haunch_flush_M20')]
LCS = list(range(101, 131)) + [135] + list(range(141, 149)) + list(range(151, 155))
VZMZ = ('Vz', 'Mz')

# reuse the text helpers of the L1 builder
src = open(os.path.join(HERE, 'build_v19m_xml.py'), encoding='utf-8').read()
exec(src[src.index('def rotate_text'):src.index('SLNS = json.load')])          # rotate_text, blk, esc
SLNS = json.load(open(r'C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json'))['slns']


def parent_sln(bnr):
    n1, n2 = m.idx[bnr]['nodes']; p1, p2 = m.xyz[n1], m.xyz[n2]
    def on(p, a, b):
        ab = [b[i] - a[i] for i in range(3)]; L2 = sum(v * v for v in ab); tt = sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2
        return -1e-3 <= tt <= 1.001 and math.dist([a[i] + tt * ab[i] for i in range(3)], p) < 0.01
    hits = [x['sln'] for x in SLNS if on(p1, x['x1'], x['x2']) and on(p2, x['x1'], x['x2'])]
    return hits[0] if len(hits) == 1 else None


m15 = Model(r"C:\Sofistik workflow\26016-member-check\v15\26016_check_v15.cdb")
m = m15 if os.path.normcase(os.path.abspath(CDB)) == os.path.normcase(r"C:\Sofistik workflow\26016-member-check\v15\26016_check_v15.cdb") else Model(CDB)
TT = {l['lc']: l['title'] for l in R.load_cases(m.cdb, m.d)}
LCS = [lc for lc in LCS if lc in TT]
summary, maps = {}, {}
for new, sub_t, tname, deg, sub_out in TARGETS:
    f = os.path.join(T15, sub_t, tname)
    t0 = open(f, 'rb').read().decode('utf-16')
    # --- fit the mapping on the v15 template (all its load cases) ---
    els0, cp0, lcs0, res0 = geom(load(f)); n15 = m15.node_at(cp0, 0.1); mt15 = match(m15, n15, els0, cp0)
    lcn0 = {k: int(v.split('_')[1]) for k, v in lcs0.items()}
    F15 = m15.end_forces(n15, sorted(set(lcn0.values())))
    at15 = {e: (m15.idx[mt15[e]['beam']]['nodes'][0] == n15) for e in els0}
    fit = {}
    cal = CAL[tname]['els']
    for eid in els0:
        ks = sorted(lcn0); b = mt15[eid]['beam']; cm = cal[str(eid)]['map']
        zero = all(abs(res0[(eid, k)][c]) < 1e-6 for k in ks for c in IC)
        X = np.array([[F15[(b, lcn0[k])][c] for c in SC] for k in ks])
        fit[eid] = {}
        for c in IC:
            if zero or mt15[eid]['dot'] < 0.999:
                fit[eid][c] = ('zero', None); continue
            srcc, sg = cm[c][0], float(cm[c][1])
            if cm[c + '_max'] > 1000 and cm[c + '_relerr'] > 0.01:      # strut ring N / Qy: rotated in the v15 templates
                y = np.array([res0[(eid, k)][c] for k in ks]) / 1000.0
                c3 = np.zeros(6); sub = [0, 1, 2]
                c3[sub] = np.linalg.lstsq(X[:, sub], y, rcond=None)[0]
                if MODE == 'v15tr':
                    fit[eid][c] = ('lin', [round(float(v), 5) for v in c3], round(float(np.abs(X @ c3 - y).max()), 4)); continue
                sg = 1.0 if c3[SC.index(srcc)] > 0 else -1.0             # direct: sign of the dominant term
                fit[eid][c] = ('one', (srcc, sg), round(float(np.abs(sg * X[:, SC.index(srcc)] - y).max()), 4)); continue
            fit[eid][c] = ('one', (srcc, sg), cm[c + '_relerr'])    # --- geometry of the target (rotated template) at the v19m node ---
    t = rotate_text(t0, deg)
    tmp = os.path.join(HERE, '_tmp.xml'); open(tmp, 'wb').write(t.encode('utf-16'))
    els, cp, _, _ = geom(load(tmp)); os.remove(tmp)
    node = m.node_at(cp, 0.1); assert node, (new, 'no v19m node at', cp)
    mt = match(m, node, els, cp)
    F = m.end_forces(node, LCS)
    used, info = set(), {}
    for eid in els:
        if fit[eid]['N'][0] == 'zero':
            info[eid] = dict(beam=None, sln=None, flip=False, tpl_name=els[eid]['name'], name=els[eid]['name']); continue
        assert mt[eid]['dot'] > 0.999, (new, eid, els[eid]['name'], mt[eid])
        b = mt[eid]['beam']; used.add(b)
        at = m.idx[b]['nodes'][0] == node
        info[eid] = dict(beam=b, sln=m.idx[b]['sln'], flip=(at != at15[eid]), tpl_name=els[eid]['name'])
    extra = [b for b in m.beams_at(node) if b not in used]
    assert not extra, (new, 'beams at the node not in the template', extra)
    for eid, inf in info.items():
        old = inf['tpl_name']; inf.setdefault('name', old)
        if deg and inf['beam'] and re.fullmatch(r'SLN\d+', old):
            ns = parent_sln(inf['beam'])
            if ns and old != f'SLN{ns}':
                t = re.sub(rf'\b{old}\b', f'SLN{ns}', t); inf['name'] = f'SLN{ns}'
    if deg:
        t = t.replace(f'{tname[:5]}-{tname[6]}-{tname[8:11]}', f'{new[:5]}-{new[6]}-{new[8:11]}')
    # LoadCase / CombiInput lists: all 43 ULS STR cases
    a, b = blk(t, 'LoadCase', '    ')
    first = re.search(r'\n      <LoadCase>.*?\n      </LoadCase>', t[a:b], re.S).group(0)
    items = []
    for i, lc in enumerate(LCS, 1):
        s = re.sub(r'<Id>\d+</Id>', f'<Id>{i}</Id>', first, count=1)
        s = re.sub(r'<Name>[^<]*</Name>', f'<Name>LC_{lc}</Name>', s, count=1)
        s = re.sub(r'<Description>[^<]*</Description>', f'<Description>{esc(f"{lc}:{TT[lc]}")}</Description>', s, count=1)
        items.append(s)
    t = t[:a] + '\n    <LoadCase>' + ''.join(items) + '\n    </LoadCase>' + t[b:]
    a, b = blk(t, 'CombiInput', '    ')
    first = re.search(r'\n      <CombiInput xsi:type="CombiInputEC">.*?\n      </CombiInput>', t[a:b], re.S).group(0)
    items = []
    for i, lc in enumerate(LCS, 1):
        s = re.sub(r'(\n        <Id>)\d+(</Id>)', rf'\g<1>{i}\g<2>', first, count=1)
        s = re.sub(r'<Name>[^<]*</Name>', f'<Name>C LC_{lc}</Name>', s, count=1)
        s = re.sub(r'(<TypeName>LoadCase</TypeName>\s*<Id>)\d+(</Id>)', rf'\g<1>{i}\g<2>', s, count=1)
        s = re.sub(r'<Description>[^<]*</Description>', f'<Description>{esc(f"{lc}:{TT[lc]}")}</Description>', s, count=1)
        items.append(s)
    t = t[:a] + '\n    <CombiInput>' + ''.join(items) + '\n    </CombiInput>' + t[b:]
    jrec = {}

    def val(eid, c, fr, flip):
        kind = fit[eid][c]
        if kind[0] == 'zero': return 0.0
        if kind[0] == 'one':
            src, sg = kind[1]
            if flip and src in VZMZ: sg = -sg
            return sg * fr[src] * 1000.0
        coef = list(kind[1])
        if flip:
            for k, s_ in enumerate(SC):
                if s_ in VZMZ: coef[k] = -coef[k]
        return sum(coef[k] * fr[SC[k]] for k in range(6)) * 1000.0

    def repl_rom(mo):
        rom = mo.group(0)
        eid = int(re.search(r'<Member>\s*<MemberType>Element1D</MemberType>\s*<Id>(\d+)</Id>', rom).group(1))
        inf = info[eid]
        tmpl = re.search(r'\n( *)<SectionResultBase xsi:type="ResultOfInternalForces">.*?</SectionResultBase>', rom, re.S).group(0)
        out = []
        for i, lc in enumerate(LCS, 1):
            fr = F[(inf['beam'], lc)] if inf['beam'] else None
            vals = {c: (val(eid, c, fr, inf['flip']) if fr else 0.0) for c in IC}
            jrec.setdefault(inf['name'], {})[lc] = {c: round(v / 1000, 3) for c, v in vals.items()}
            s = re.sub(r'(<Loading>\s*<LoadingType>LoadCase</LoadingType>\s*<Id>)\d+(</Id>)', rf'\g<1>{i}\g<2>', tmpl, count=1)
            for c in IC:
                s = re.sub(rf'<{c}>[^<]*</{c}>', f'<{c}>{vals[c]!r}</{c}>', s, count=1)
            out.append(s)
        return re.sub(r'(<Results>)(\s*<SectionResultBase.*?)(\n *</Results>)', lambda q: q.group(1) + ''.join(out) + q.group(3), rom, flags=re.S)

    t = re.sub(r'<ResultOnMember>.*?</ResultOnMember>', repl_rom, t, flags=re.S)
    t = re.sub(r'<ProjectName>[^<]*</ProjectName>', '<ProjectName>26016 Concourse Viewing Platform</ProjectName>', t, count=1)
    t = re.sub(r'<Author>[^<]*</Author>', '<Author>CaSE</Author>', t)
    assert 'Claude' not in t, new
    os.makedirs(os.path.join(OUT, sub_out), exist_ok=True)
    open(os.path.join(OUT, sub_out, new + '.xml'), 'wb').write(t.encode('utf-16'))
    summary[new] = dict(template=f'v15/{sub_t}/{tname}', rotation_deg=deg, node=node, mode=MODE, lcs=LCS,
                        elements={str(e): dict(name=v['name'], template_name=v['tpl_name'], beam=v['beam'], beam_sln=v['sln'], vz_mz_flipped=v['flip'],
                                               mapping={c: fit[e][c] for c in IC}) for e, v in info.items()},
                        forces_kN_kNm_IDEA_axes=jrec)
    print(new, 'node', node, 'from', tname, 'rot', deg, 'flips', [v['name'] for v in info.values() if v['flip']],
          'lin', [(info[e]['name'], c) for e in fit for c in IC if fit[e][c][0] == 'lin'],
          'worst one-to-one resid', max([fit[e][c][2] for e in fit for c in IC if fit[e][c][0] == 'one'] or [0]), flush=True)
json.dump(summary, open(os.path.join(OUT, f'forces_v19m_{MODE}_{WHICH}.json'), 'w'), indent=1)
