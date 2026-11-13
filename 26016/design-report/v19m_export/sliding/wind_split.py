import re, json, math
DAT = r"C:\Sofistik workflow\26016-member-check\v19m\26016_check_v19m.dat"
L = open(DAT, encoding="latin-1").read().splitlines()
P = {}
for l in L:
    m = re.match(r"STO#(\w+)\s+(\S+)", l)
    if m and m[1] not in P:
        try: P[m[1]] = eval(m[2].replace('#', 'P_').replace('**', '**'), {}, {f'P_{k}': v for k, v in P.items()})
        except Exception: pass
P['Q'] = P['CE'] * 0.613 * P['VB'] ** 2 / 1000
S = {s['sln']: s for s in json.load(open(r"C:\Sofistik workflow\26016-member-check\v19m\builder\slns_v19.json"))['slns']}
def ln(n): s = S[n]; return math.dist(s['x1'], s['x2'])
def block(lc):
    i = next(k for k, l in enumerate(L) if re.match(rf"LC {lc} TYPE", l)); out = []
    for l in L[i + 1:]:
        if re.match(r"LC \d+ TYPE", l) or l.startswith('$ ===='): break
        m = re.match(r"\s*LINE SLN '(\d+)' WIDE 0 TYPE P(XX|YY|ZZ) (.+)$", l)
        if m: out.append((int(m[1]), m[2], m[3].strip()))
    return out
cat = lambda e: 'cladding (qp x 3 m, cf 1.0)' if '#BCL' in e else 'rakers/struts (cf 1.45 x 0.15 m)' if '#CFR' in e else 'deck edge + balustrade' if '#CFE' in e else 'other'
for lc in (83, 81):
    tot = {}; n = {}
    for sln, d, e in block(lc):
        v = eval(e.replace('#', 'P_'), {}, {f'P_{k}': x for k, x in P.items()})
        tot[cat(e)] = tot.get(cat(e), 0) + v * ln(sln); n[cat(e)] = n.get(cat(e), 0) + 1
    print('LC', lc, {k: (round(v, 1), n[k]) for k, v in tot.items()}, 'sum', round(sum(tot.values()), 1))
print('qp', round(P['Q'], 4), {k: P[k] for k in ('CE','VB','BCL','DR','CFR','CFE','DE1','DE2','DE3','CFL','PHIB','HBAL','LEE','LEEB','CPU','CPUD','CPD')})
# cladding lines detail
for sln, d, e in block(83):
    if '#BCL' in e: s = S[sln]; print('clad', sln, s['grp'], [round(x, 2) for x in s['x1']], [round(x, 2) for x in s['x2']], round(ln(sln), 2))

import numpy as np
for lc, w in ((83, np.array([0, -1.0, 0])), (81, np.array([1.0, 0, 0]))):
    full = np.zeros(3); cf = np.zeros(3)
    for sln, d, e in block(lc):
        if '#CFR' not in e: continue
        s = S[sln]; a = np.array(s['x2']) - np.array(s['x1']); Ln = np.linalg.norm(a); a = a / Ln
        q = P['Q'] * P['CFR'] * P['DR']
        full += q * Ln * w
        vn = w - (w @ a) * a; sn = np.linalg.norm(vn)
        if sn > 1e-9: cf += q * Ln * sn * vn          # q sin^2 theta along the normal direction (vn has length sin theta)
    print('rakers LC', lc, 'model', np.round(full, 1), 'cross-flow', np.round(cf, 1))
