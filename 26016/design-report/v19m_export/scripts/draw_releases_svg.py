import json, math, sys
d = json.load(open('slns_v19.json')); ch = json.load(open('released_ends.json'))
W = 1400; S = 40.0; C = W/2
def P(x, y): return C + x*S, C - y*S
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W+120}" font-family="Arial">',
     f'<rect width="100%" height="100%" fill="white"/>',
     '<text x="700" y="30" font-size="20" text-anchor="middle" font-weight="bold">26016 v19m - Level 1 (z +4.054) plan: MZ added at ring ends of the 9 A/B joints, r 8.5 m</text>',
     '<text x="700" y="54" font-size="14" text-anchor="middle">geometry read from 26016_check_v19m.dat (SOFiMSHC SLNB), X right, Y up, angle from +X anticlockwise</text>']
def ln(p, q, col, w): a = P(*p[:2]); b = P(*q[:2]); return f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="{w}"/>'
for s in d['slns']:
    p, q = s['x1'], s['x2']
    if abs(p[2]-4.054) < 0.02 and abs(q[2]-4.054) < 0.02 and s['grp'] != 15: o.append(ln(p, q, '#c8c8c8', 1))
for s in d['slns']:
    p, q = s['x1'], s['x2']
    if abs(p[2]-4.054) < 0.02 and abs(q[2]-4.054) < 0.02 and s['grp'] == 15: o.append(ln(p, q, '#1f4e9c', 2.5))
# strut grp 60 ends at L1 r 8.5
for s in d['slns']:
    if s['grp'] != 60: continue
    for p, q in ((s['x1'], s['x2']), (s['x2'], s['x1'])):
        if abs(p[2]-4.054) < 0.05 and abs(math.hypot(p[0], p[1])-8.5) < 0.1:
            o.append(ln(p, q, '#2e8b57', 2)); x, y = P(*p[:2])
            o.append(f'<rect x="{x-8}" y="{y-8}" width="16" height="16" fill="none" stroke="#2e8b57" stroke-width="2.5"/>')
for a in range(0, 360, 40):
    t = 'B' if a in (40, 280) else 'A'; col = '#b00000' if t == 'A' else '#7a00a8'
    x, y = P(8.5*1.33*math.cos(math.radians(a)), 8.5*1.33*math.sin(math.radians(a)))
    o.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="16" font-weight="bold" fill="{col}" text-anchor="middle">L1-R8-{t}</text>')
    o.append(f'<text x="{x:.0f}" y="{y+18:.0f}" font-size="15" fill="{col}" text-anchor="middle">{a:03d}°</text>')
for a in range(20, 360, 40):
    x, y = P(8.5*0.80*math.cos(math.radians(a)), 8.5*0.80*math.sin(math.radians(a)))
    o.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="12" fill="#2e8b57" text-anchor="middle">S/T {a:03d}°</text>')
    o.append(f'<text x="{x:.0f}" y="{y+14:.0f}" font-size="11" fill="#2e8b57" text-anchor="middle">unchanged</text>')
for c in ch:
    p = (c['x'], c['y']); q = c['other']; L = math.dist(p, q[:2]); f = 0.5/L
    hx, hy = P(p[0]+(q[0]-p[0])*f, p[1]+(q[1]-p[1])*f)
    o.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="8" fill="white" stroke="red" stroke-width="3"/>')
    tx, ty = P(p[0]+(q[0]-p[0])*f*3.0, p[1]+(q[1]-p[1])*f*3.0)
    # offset label outward radially
    rr = math.hypot(*p); ux, uy = p[0]/rr, p[1]/rr
    tx += -ux*22; ty += uy*22
    o.append(f'<text x="{tx:.0f}" y="{ty+4:.0f}" font-size="12" fill="red" text-anchor="middle" font-weight="bold">{c["sln"]}{c["end"]}</text>')
o.append(f'<circle cx="{C}" cy="{C}" r="4" fill="black"/>')
box = ["Reading used:", "- radial UB (group 15) continuous through r 8.5: no release", "- ring UB end: web-only end plate, 4 M20",
       "  -> pinned about both axes: 'MY' -> 'MYMZ'", "- torsion MT, shear VY/VZ, axial N still carried", "- strut joints S/T (20, 60 ... 340 deg),",
       "  L2 rings, everything else: unchanged"]
for k, t in enumerate(box): o.append(f'<text x="905" y="{1278+k*19}" font-size="14" fill="#5a4600">{t}</text>')
o.insert(4 + 0, '<rect x="890" y="1256" width="470" height="148" fill="#fff8e0" stroke="#c9a000"/>')
ly = W + 20
leg = [('#1f4e9c', 'line', 'Group 15: L1 rings r 3 / 8.5 / 12 m and radials'), ('#c8c8c8', 'line', 'Other Level 1 lines (z +4.054)'),
       ('red', 'circle', "Ring end released, FIXA/FIXE 'MY' -> 'MYMZ' (18 ends, label = SLN + end A/E)"), ('#2e8b57', 'text', "S/T label (green) = raking strut joint: ring ends stay 'MY' only")]
for k, (col, kind, t) in enumerate(leg):
    y = ly + k*24
    if kind == 'line': o.append(f'<line x1="60" y1="{y}" x2="100" y2="{y}" stroke="{col}" stroke-width="3"/>')
    if kind == 'circle': o.append(f'<circle cx="80" cy="{y}" r="8" fill="white" stroke="red" stroke-width="3"/>')
    if kind == 'rect': o.append(f'<rect x="72" y="{y-8}" width="16" height="16" fill="none" stroke="{col}" stroke-width="2.5"/>')
    if kind == 'text': o.append(f'<text x="62" y="{y+5}" font-size="13" fill="{col}">S/T</text>')
    o.append(f'<text x="115" y="{y+5}" font-size="15">{t}</text>')
o.append('</svg>')
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(o))
