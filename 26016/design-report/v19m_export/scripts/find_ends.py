import re, math, json, sys
src = sys.argv[1]
L = open(src, encoding='latin-1').read().splitlines()
slns = []
i = 0
while i < len(L):
    m = re.match(r"^SLN\s+(\d+)\s+GRP\s+(\d+)(.*)$", L[i])
    if m:
        no, grp, rest = int(m.group(1)), int(m.group(2)), m.group(3)
        fa = re.search(r"FIXA\s+'([^']*)'", rest); fe = re.search(r"FIXE\s+'([^']*)'", rest)
        j = i + 1
        while not L[j].startswith('SLNB'): j += 1
        t = L[j].split(); v = [float(t[t.index('X1')+k]) for k in (1,2,3)] + [float(t[t.index('X2')+k]) for k in (1,2,3)]
        slns.append(dict(line=i+1, sln=no, grp=grp, fixa=fa.group(1) if fa else '', fixe=fe.group(1) if fe else '',
                         x1=v[:3], x2=v[3:], text=L[i]))
    i += 1
def r(p): return math.hypot(p[0], p[1])
def ang(p): return math.degrees(math.atan2(p[1], p[0])) % 360
out = []
for s in slns:
    if s['grp'] != 15: continue
    for end, p, q in (('A', s['x1'], s['x2']), ('E', s['x2'], s['x1'])):
        if abs(r(p) - 8.5) < 0.05:
            # direction: radial if other end differs mainly in r
            dr = abs(r(q) - r(p)); dt = math.dist(p[:2], q[:2])
            kind = 'radial' if dr > 0.7 * dt else 'ring'
            a = ang(p)
            out.append(dict(sln=s['sln'], line=s['line'], end=end, z=p[2], angle=round(a, 2), kind=kind,
                            lit=s['fixa'] if end == 'A' else s['fixe'], other_r=round(r(q), 3)))
json.dump(dict(slns=slns), open(sys.argv[2], 'w'))
for o in sorted(out, key=lambda o: (o['angle'], o['kind'])):
    print(o)
