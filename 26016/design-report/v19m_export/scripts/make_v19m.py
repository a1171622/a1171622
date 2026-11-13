import re, json, math, sys, shutil
SRC = r"C:\Sofistik workflow\26016-member-check\v19\26016_check_v19.dat"
DST = r"C:\Sofistik workflow\26016-member-check\v19m\26016_check_v19m.dat"
L = open(SRC, encoding='latin-1').read().split('\n')
d = json.load(open('slns_v19.json'))
def r(p): return math.hypot(p[0], p[1])
def ang(p): return round(math.degrees(math.atan2(p[1], p[0])) % 360) % 360
AB = set(range(0, 360, 40))
changes = []
for s in d['slns']:
    if s['grp'] != 15: continue
    for end, p, q in (('A', s['x1'], s['x2']), ('E', s['x2'], s['x1'])):
        if abs(r(p)-8.5) > 0.05 or abs(p[2]-4.054) > 0.01: continue
        if abs(r(q)-8.5) > 0.05: continue          # ring only (other end also r 8.5)
        a = ang(p)
        if a not in AB: continue
        key = 'FIXA' if end == 'A' else 'FIXE'
        i = s['line'] - 1
        old = re.search(key + r"\s+'([^']*)'", L[i])
        oldlit = old.group(1) if old else ''
        assert oldlit == 'MY', (s['sln'], end, oldlit)
        L[i] = L[i].replace(f"{key} 'MY'", f"{key} 'MYMZ'", 1)
        changes.append(dict(sln=s['sln'], end=end, angle=a, joint='L1-R8-B' if a in (40, 280) else 'L1-R8-A',
                            old=oldlit, new='MYMZ', x=p[0], y=p[1], z=p[2], other=s['x1'] if end=='E' else s['x2']))
hdr = ["$ v19m (13 Nov 2026): copy of v19 with MZ released (FIXA/FIXE 'MY' -> 'MYMZ') at the 18 Level 1 r 8.5 m ring ends",
       "$ that frame into the radial web at the A/B joints 0,40,...,320 deg (flange plates removed, Wing 13 Nov). Nothing else changed."]
L = hdr + L
open(DST, 'w', encoding='latin-1', newline='').write('\n'.join(L))
changes.sort(key=lambda c: (c['angle'], c['sln']))
json.dump(changes, open('released_ends.json', 'w'), indent=1)
for c in changes: print(c['angle'], c['joint'], 'SLN', c['sln'], c['end'], c['old'], '->', c['new'])
print(len(changes))
