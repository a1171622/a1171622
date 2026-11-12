"""Build the v19m no-flange IOM XMLs from the v15 no-flange templates, with v19m forces (43 ULS cases), plates/bolts/welds untouched.

Topology in v19 (v17a, Wing 6 Nov 2026): the L1-L2 column at r 8.5 moved from 80 to 60 deg (SLN 131) and from 60 to 40 deg (SLN 121).
So at 40 deg the joint has a column above (= B layout) and at 80 deg it has none (= A layout). Those two joints use a template
rotated about the global Z axis through the platform centre: B_040 <- B_080 rotated -40 deg, A_080 <- A_120 rotated -40 deg.

Force mapping: per element, fitted on the v15 templates against the v15 cdb (calib_v15.json, round trip < 0.12 kN/kNm).
If the v19m beam at the joint runs the other way than the v15 beam the template was calibrated on (start vs end at the joint),
Vz and Mz change sign (local x reversed, local z kept by DRX); N, Vy, Mt, My keep their sign.

py -3.11 build_v19m_xml.py <v19m cdb> <out_root>"""
import sys, os, re, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iomx import load
from calib import geom, match, IC
from cdbend import Model
from sofistik_mcp import results as R

CDB, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
CAL = json.load(open(os.path.join(HERE, 'calib_v15.json')))
T15 = r"C:\Sofistik workflow\idea-statica\v15"
TARGETS = [  # new name, template folder, template file, rotation deg
    ('L1-R8-A_000', 'xml_A_noflange_asis', 'L1-R8-A_000.xml', 0),
    ('L1-R8-A_080', 'xml_A_noflange_asis', 'L1-R8-A_120.xml', -40),
    ('L1-R8-A_120', 'xml_A_noflange_asis', 'L1-R8-A_120.xml', 0),
    ('L1-R8-A_160', 'xml_A_noflange_asis', 'L1-R8-A_160.xml', 0),
    ('L1-R8-A_200', 'xml_A_noflange_asis', 'L1-R8-A_200.xml', 0),
    ('L1-R8-A_240', 'xml_A_noflange_asis', 'L1-R8-A_240.xml', 0),
    ('L1-R8-A_320', 'xml_A_noflange_asis', 'L1-R8-A_320.xml', 0),
    ('L1-R8-B_040', 'xml_B_noflange_asis', 'L1-R8-B_080.xml', -40),
    ('L1-R8-B_280', 'xml_B_noflange_asis', 'L1-R8-B_280.xml', 0),
]
LCS = list(range(101, 131)) + [135] + list(range(141, 149)) + list(range(151, 155))
VZMZ = ('Vz', 'Mz')


def rotate_text(t, deg):
    """Rotate every GLOBAL point / vector in the IOM text about Z: Point3D, bolt positions, plate / bolt-grid Origin and
    axes, segment LCS vectors, weld Start/End. Local items (eccentricities, 2D outlines) are left alone."""
    if not deg:
        return t
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    def rot_xy(block):
        mx = re.search(r'<X>([^<]*)</X>', block); my = re.search(r'<Y>([^<]*)</Y>', block)
        x, y = float(mx.group(1)), float(my.group(1))
        nx, ny = c * x - s * y, s * x + c * y
        block = block[:mx.start()] + f'<X>{nx!r}</X>' + block[mx.end():]
        my = re.search(r'<Y>([^<]*)</Y>', block)
        return block[:my.start()] + f'<Y>{ny!r}</Y>' + block[my.end():]
    tags = ['VecX', 'VecY', 'VecZ', 'Origin', 'AxisX', 'AxisY', 'AxisZ', 'Start', 'End']
    for tg in tags:
        t = re.sub(rf'<{tg}>(?:\s*<Id>[^<]*</Id>)?\s*<X>[^<]*</X>\s*<Y>[^<]*</Y>\s*<Z>[^<]*</Z>\s*</{tg}>', lambda m: rot_xy(m.group(0)), t)
    # Point3D: top-level points (with Id) and bolt Positions (no Id)
    t = re.sub(r'<Point3D>(\s*<Id>[^<]*</Id>)?(\s*<Name>[^<]*</Name>)?\s*<X>[^<]*</X>\s*<Y>[^<]*</Y>\s*<Z>[^<]*</Z>', lambda m: rot_xy(m.group(0)), t)
    return t


def blk(t, tag, ind):
    a = t.index('\n' + ind + '<' + tag + '>')
    b = t.index('\n' + ind + '</' + tag + '>', a) + len('\n' + ind + '</' + tag + '>')
    return a, b


def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


SLNS = json.load(open(os.path.join(r'C:\Sofistik workflow\26016-member-check\v19m\builder', 'slns_v19.json')))['slns']
def parent_sln(bnr):
    n1, n2 = m.idx[bnr]['nodes']; p1, p2 = m.xyz[n1], m.xyz[n2]
    def on(p, a, b):
        ab = [b[i] - a[i] for i in range(3)]; L2 = sum(v * v for v in ab); tt = sum((p[i] - a[i]) * ab[i] for i in range(3)) / L2
        return -1e-3 <= tt <= 1.001 and math.dist([a[i] + tt * ab[i] for i in range(3)], p) < 0.01
    hits = [x['sln'] for x in SLNS if on(p1, x['x1'], x['x2']) and on(p2, x['x1'], x['x2'])]
    assert len(hits) == 1, (bnr, hits)
    return hits[0]


m15 = Model(r"C:\Sofistik workflow\26016-member-check\v15\26016_check_v15.cdb")
m = Model(CDB)
TT = {l['lc']: l['title'] for l in R.load_cases(m.cdb, m.d)}
LCS = [lc for lc in LCS if lc in TT]
summary = {}
for new, sub_t, tname, deg in TARGETS:
    f = os.path.join(T15, sub_t, tname)
    cal = CAL[tname]
    t0 = open(f, 'rb').read().decode('utf-16')
    # v15 orientation of each template element's beam
    from iomx import ET
    els0, cp0, _, _ = geom(load(f)); n15 = m15.node_at(cp0, 0.1); mt15 = match(m15, n15, els0, cp0)
    at15 = {e: (m15.idx[mt15[e]['beam']]['nodes'][0] == n15) for e in els0}
    t = rotate_text(t0, deg)
    tmp = os.path.join(HERE, '_tmp.xml'); open(tmp, 'wb').write(t.encode('utf-16'))
    els, cp, _, _ = geom(load(tmp)); os.remove(tmp)
    node = m.node_at(cp, 0.1); mt = match(m, node, els, cp)
    F = m.end_forces(node, LCS)
    used = set()
    info = {}
    for eid in els:
        assert mt[eid]['dot'] > 0.999, (new, eid, mt[eid])
        b = mt[eid]['beam']; used.add(b)
        at = m.idx[b]['nodes'][0] == node
        info[eid] = dict(beam=b, sln=m.idx[b]['sln'], flip=(at != at15[eid]), tpl_name=els[eid]['name'])
    extra = [b for b in m.beams_at(node) if b not in used]
    assert not extra, (new, 'beams at the node not in the template', extra)
    # names: element / member / joint labels to v19m SLNs
    # parent SLN of split beams (SOFiMSHC 15xx/16xx) from the template name when the beam keeps that line
    for eid, inf in info.items():
        old = inf['tpl_name']
        if deg:
            newsln = parent_sln(inf['beam'])
            if newsln and old != f'SLN{newsln}':
                t = t.replace(f'<Name>{old}</Name>', f'<Name>SLN{newsln}</Name>')
                t = re.sub(rf'\b{old}\b', f'SLN{newsln}', t)
                inf['name'] = f'SLN{newsln}'
            else:
                inf['name'] = old
        else:
            inf['name'] = old
    if deg:
        a_old, a_new = tname[8:11], new[8:11]
        t = t.replace(f'L1-R8-{tname[6]}-{a_old}', f'L1-R8-{new[6]}-{a_new}')
    # LoadCase list
    a, b = blk(t, 'LoadCase', '    ')
    first = re.search(r'\n      <LoadCase>.*?\n      </LoadCase>', t[a:b], re.S).group(0)
    items = []
    for i, lc in enumerate(LCS, 1):
        s = re.sub(r'<Id>\d+</Id>', f'<Id>{i}</Id>', first, count=1)
        s = re.sub(r'<Name>[^<]*</Name>', f'<Name>LC_{lc}</Name>', s, count=1)
        s = re.sub(r'<Description>[^<]*</Description>', f'<Description>{esc(f"{lc}:{TT[lc]}")}</Description>', s, count=1)
        items.append(s)
    t = t[:a] + '\n    <LoadCase>' + ''.join(items) + '\n    </LoadCase>' + t[b:]
    # CombiInput list
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

    def repl_rom(mo):
        rom = mo.group(0)
        eid = int(re.search(r'<Member>\s*<MemberType>Element1D</MemberType>\s*<Id>(\d+)</Id>', rom).group(1))
        mp = cal['els'][str(eid)]['map']; inf = info[eid]; bnr = inf['beam']
        tmpl = re.search(r'\n( *)<SectionResultBase xsi:type="ResultOfInternalForces">.*?</SectionResultBase>', rom, re.S).group(0)
        out = []
        for i, lc in enumerate(LCS, 1):
            fr = F[(bnr, lc)]
            vals = {}
            for c in IC:
                src, sg = mp[c][0], mp[c][1]
                if inf['flip'] and src in VZMZ:
                    sg = -sg
                vals[c] = sg * fr[src] * 1000.0
            jrec.setdefault(inf['name'], {})[lc] = {c: round(v / 1000, 3) for c, v in vals.items()}
            s = re.sub(r'(<Loading>\s*<LoadingType>LoadCase</LoadingType>\s*<Id>)\d+(</Id>)', rf'\g<1>{i}\g<2>', tmpl, count=1)
            for c in IC:
                s = re.sub(rf'<{c}>[^<]*</{c}>', f'<{c}>{vals[c]!r}</{c}>', s, count=1)
            out.append(s)
        new_ = ''.join(out)
        return re.sub(r'(<Results>)(\s*<SectionResultBase.*?)(\n *</Results>)', lambda q: q.group(1) + new_ + q.group(3), rom, flags=re.S)

    t = re.sub(r'<ResultOnMember>.*?</ResultOnMember>', repl_rom, t, flags=re.S)
    t = re.sub(r'(<ProjectName>)([^<]*)(</ProjectName>)', lambda q: q.group(1) + f'26016 {new} no flange plates, v19m forces'
               + (f' (geometry = v15 {tname[:-4]} rotated {deg} deg)' if deg else '') + q.group(3), t, count=1)
    sub = 'xml_A_noflange' if '-A_' in new else 'xml_B_noflange'
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    open(os.path.join(OUT, sub, new + '.xml'), 'wb').write(t.encode('utf-16'))
    summary[new] = dict(template=f'v15/{sub_t}/{tname}', rotation_deg=deg, node=node, cp=cp, lcs=LCS,
                        elements={str(e): dict(name=v['name'], template_name=v['tpl_name'], beam=v['beam'], beam_sln=v['sln'], vz_mz_flipped=v['flip'])
                                  for e, v in info.items()},
                        forces_kN_kNm_IDEA_axes=jrec)
    print(new, 'node', node, 'from', tname, 'rot', deg, 'flips', [v['name'] for v in info.values() if v['flip']])
json.dump(summary, open(os.path.join(OUT, 'forces_v19m.json'), 'w'), indent=1)
m.cdb.close(); m15.cdb.close()
