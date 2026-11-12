import sys, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0,'.'); import ext_geom
lines, supports, lars, flights = ext_geom.build()
fig = plt.figure(figsize=(16, 8.5), dpi=110)
for k, (arm, side, rot) in enumerate((('R', 'right', (18, -150)), ('L', 'left', (18, -40)))):
    ax = fig.add_subplot(1, 2, k + 1, projection='3d'); ax.view_init(*rot)
    L = [l for l in lines if l['title'].startswith(side)]
    for l in L:
        a, b = l['a'], l['b']
        st = dict(tread=('#bbb', 0.6), stringer=('#e08a00', 2), landing=('#e08a00', 2), stub=('#e08a00', 2), leg=('#1565c0', 2.5), bracket=('#c62828', 3))[l['kind']]
        ax.plot(*zip(a, b), c=st[0], lw=st[1])
    legs = {l['title'].replace(side + ' ', ''): l['a'] for l in L if l['kind'] == 'leg'}
    for l in L:
        if l['kind'] == 'leg':
            p = l['b']; ax.scatter(*p, marker='^', s=60, c='k')
        if l['kind'] == 'bracket':
            p = l['b']; ax.scatter(*p, marker='o', s=70, c='#c62828')
            ax.text(p[0], p[1], p[2] - 0.5, 'Z only\n(was pinned)', color='#c62828', fontsize=8)
    for l in L:
        if l['kind'] == 'stringer' and '1' in l.get('flight', ''):
            ax.scatter(*l['a'], marker='^', s=60, c='k')
    g = lambda nm: legs[nm]
    B = [('landing 1 leg inner-low', 'landing 1 leg inner-high', 1.235), ('landing 1 leg outer-low', 'landing 1 leg outer-high', 1.235),
         ('landing 2 leg outer-low', 'landing 2 leg outer-high', 1.45), ('landing 2 leg outer-low', 'landing 2 leg outer-high', 2.90)]
    for a, b, z in B:
        pa, pb = np.r_[g(a)[:2], z], np.r_[g(b)[:2], z]
        ax.plot(*zip(pa, pb), c='#2e7d32', lw=3)
        for p in (pa, pb): ax.scatter(*p, s=25, facecolors='white', edgecolors='#2e7d32', zorder=5)
        m = (pa + pb) / 2; ax.text(m[0], m[1], m[2] + 0.12, '+%.3g' % z, color='#2e7d32', fontsize=8)
    ax.text(*(g('landing 2 leg outer-low') + [0, 0, 0.3]), 'landing 2 (L1)', fontsize=8)
    ax.text(*(g('landing 1 leg outer-low') + [0, 0, 0.3]), 'landing 1', fontsize=8)
    ax.set_title('%s arm (to L1 at %s)' % (side, '15-25 deg' if arm == 'R' else '295-305 deg'), fontsize=11)
    ax.set_box_aspect((1, 1, 0.55)); ax.set_zlim(0, 4.6); ax.set_xlabel('x'); ax.set_ylabel('y'); ax.set_zlabel('z (m)')
fig.suptitle('26016 v19 reading: external stair stability set-up\n'
             'blue = legs SHS 80x80x6.3 (was 100x100x5), pinned bases (black triangles);  green = new transverse SHS 80x80x6.3, pinned both ends (open circles);\n'
             'red = 4 ring brackets, vertical force only at the L1 ring (no horizontal, no moment);  orange = stringers / landings RHS 200x100x6 (unchanged), flight 1 feet pinned',
             fontsize=10)
plt.tight_layout(); fig.subplots_adjust(top=0.86); plt.savefig('/mnt/project-files/26016/member-check/run/v19/v19_reading.png', bbox_inches='tight')
