import sys, math, json
sys.path.insert(0, '.')
from cdbend import Model
m = Model(r"C:\Sofistik workflow\26016-member-check\v19m\envelopes\26016_env_v19m.cdb")
m15 = Model(r"C:\Sofistik workflow\26016-member-check\v15\26016_check_v15.cdb")
def desc(mm, z):
    out = {}
    for a in range(0, 360, 20):
        p = (8.5 * math.cos(math.radians(a)), 8.5 * math.sin(math.radians(a)), z)
        n = mm.node_at(p, 0.15)
        if n is None: out[a] = 'no node'; continue
        bl = mm.beams_at(n); s = []
        for b in bl:
            n1, n2 = mm.idx[b]['nodes']; o = n2 if n1 == n else n1
            v = [mm.xyz[o][i] - mm.xyz[n][i] for i in range(3)]
            g = b // 10000 if False else None
            r0 = math.hypot(*mm.xyz[n][:2]); r1 = math.hypot(*mm.xyz[o][:2])
            kind = 'up' if v[2] > 0.1 else 'down' if v[2] < -0.1 else ('out' if r1 > r0 + 0.05 else 'in' if r1 < r0 - 0.05 else 'ring')
            s.append(kind)
        out[a] = ' '.join(sorted(s))
    return out
for lab, z in (('L1', 4.054), ('L2', 8.05)):
    d15, d19 = desc(m15, z), desc(m, z)
    for a in range(0, 360, 20):
        print(lab, a, '| v15:', d15[a], '| v19m:', d19[a], '' if d15[a] == d19[a] else '  <-- CHANGED')
