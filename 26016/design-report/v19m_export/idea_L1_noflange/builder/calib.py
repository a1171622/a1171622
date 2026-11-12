"""Fit the SOFiSTiK-cdb -> IOM-XML force mapping per element on the v15 templates (v15 cdb made those XMLs)."""
import sys, json, math, glob, os, re
sys.path.insert(0, '.')
from iomx import *
from cdbend import Model
IC = ('N', 'Qy', 'Qz', 'Mx', 'My', 'Mz'); SC = ('N', 'Vy', 'Vz', 'Mt', 'My', 'Mz')
CAND = {'N': ['N'], 'Qy': ['Vy', 'Vz'], 'Qz': ['Vy', 'Vz'], 'Mx': ['Mt'], 'My': ['My', 'Mz'], 'Mz': ['My', 'Mz']}
def geom(tree):
    r = tree.getroot(); pts = {}
    for p in find(r, 'Point3D'):
        if p.find('Id') is not None and p.find('X') is not None: pts[int(p.findtext('Id'))] = tuple(float(p.findtext(k)) for k in 'XYZ')
    seg = {}
    for s in find(r, 'LineSegment3D'):
        if s.find('Id') is not None and s.find('StartPoint') is not None:
            seg[int(s.findtext('Id'))] = (pts[int(s.findtext('StartPoint/Id'))], pts[int(s.findtext('EndPoint/Id'))])
    els = {}
    for e in find(r, 'Element1D'):
        if e.find('Id') is not None and e.find('Segment') is not None: els[int(e.findtext('Id'))] = dict(name=e.findtext('Name'), seg=seg[int(e.findtext('Segment/Id'))])
    from collections import Counter
    cnt = Counter(p for a in seg.values() for p in a); cp = cnt.most_common(1)[0][0]
    lcs = {int(lc.findtext('Id')): lc.findtext('Name') for lc in find(r, 'LoadCase') if lc.find('Name') is not None}
    res = {}
    for rom in find(r, 'ResultOnMember'):
        eid = int(rom.findtext('Member/Id'))
        for rb in rom.find('Results'):
            if rb.findtext('Position') != '0': continue
            for s in rb.find('Results'):
                res[(eid, int(s.findtext('Loading/Id')))] = {k: float(s.findtext(k)) for k in IC}
    return els, cp, lcs, res
def match(model, node, els, cp):
    bl = model.beams_at(node); out = {}
    for eid, e in els.items():
        a, b = e['seg']; far = b if math.dist(a, cp) < math.dist(b, cp) else a
        u = [far[i] - cp[i] for i in range(3)]; nu = math.hypot(*u); u = [x / nu for x in u]
        best = None
        for bb in bl:
            n1, n2 = model.idx[bb]['nodes']; o = n2 if n1 == node else n1
            v = [model.xyz[o][i] - model.xyz[node][i] for i in range(3)]; nv = math.hypot(*v)
            dot = sum(u[i] * v[i] / nv for i in range(3))
            if best is None or dot > best[0]: best = (dot, bb)
        out[eid] = dict(beam=best[1], dot=round(best[0], 4), toward_far=(a == cp or math.dist(a, cp) < math.dist(b, cp)))
    return out
if __name__ == '__main__':
    m = Model(r"C:\Sofistik workflow\26016-member-check\v15\26016_check_v15.cdb")
    allmap = {}
    for f in sorted(glob.glob(r"C:\Sofistik workflow\idea-statica\v15\xml_[AB]_noflange_asis\*.xml")):
        t = load(f); els, cp, lcs, res = geom(t)
        node = m.node_at(cp, tol=0.1); mt = match(m, node, els, cp)
        lcn = {k: int(v.split('_')[1]) for k, v in lcs.items()}
        F = m.end_forces(node, sorted(set(lcn.values())))
        jm = {}
        for eid in els:
            b = mt[eid]['beam']; mp = {}; worst = 0
            for c in IC:
                xs = [res[(eid, k)][c] for k in lcn]; best = None
                for sc in CAND[c]:
                    for sg in (1, -1):
                        ys = [sg * F[(b, lcn[k])][sc] * 1000 for k in lcn]
                        err = math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys)) / len(xs)); mag = max(abs(x) for x in xs) + 1e-9
                        if best is None or err < best[0]: best = (err, sc, sg, mag)
                mp[c] = (best[1], best[2]); worst = max(worst, best[0] / max(best[3], 1000))
                mp[c + '_relerr'] = round(best[0] / best[3], 4); mp[c + '_rms'] = round(best[0], 1); mp[c + '_max'] = round(best[3], 1)
            jm[eid] = dict(els[eid], beam=b, dot=mt[eid]['dot'], map=mp, start_at_joint=mt[eid]['toward_far'])
            print(os.path.basename(f), eid, els[eid]['name'], 'beam', b, 'dot', mt[eid]['dot'], 'start@joint', mt[eid]['toward_far'],
                  ' '.join(f"{c}={'+' if mp[c][1] > 0 else '-'}{mp[c][0]}({mp[c+'_rms']:.0f}/{mp[c+'_max']:.0f})" for c in IC))
        allmap[os.path.basename(f)] = dict(node=node, cp=cp, els={str(k): dict(v, seg=None) for k, v in jm.items()})
    json.dump(allmap, open('calib_v15.json', 'w'), indent=1)
