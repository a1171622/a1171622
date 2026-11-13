"""Reviewer comments of 13.11.2026 (KK) on top of edit_v20.py -> edit_v21.py"""
s = open('edit_v20.py').read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:70])
    s = s.replace(a, b)
rep("'A uniform temperature change of +15 K and -15 K has been considered.", "'A uniform temperature change of +15 °C and -15 °C has been considered.")
rep("'friction factor of safety %.2f to %.2f under DL + WL with mu = 0.40, %d and more with the imposed load) and overturning (factor %.1f).'",
    "'friction factor of safety %.2f to %.2f under DL + WL with mu = 0.40, above the minimum of 1.4 adopted in the original design, %d and more with the imposed load) and overturning (factor %.1f).'")
rev = r"""
# --- reviewer comments 13.11.2026
cellsub(16, '02-11-2026', '13-11-2026')
cellsub(94, 'M20 grade 8.8 (M30 grade 8.8 at the 12 m radius ring joints)', 'Ring beam connections: M20 grade 8.8 (M30 grade 8.8 at the 12 m radius ring joints)')
WDW = int(next(ch[426].iter('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent')).get('cx'))
cellsub(160, 'Uniform temperature +15 / -15 K', 'Uniform temperature +15 / -15 °C'); cellsub(160, '+/-15 K', '+/-15 °C')
clone_after(ch[293], ch[270], 'The original design adopted a minimum factor of safety of 1.4 against sliding (DCR R1). The lowest factor of %.2f under DL + WL satisfies this requirement.' % min(dw))
settext(303, 'The IDEA StatiCa report of the existing Level 2 ring to radial connection at 12 m radius (L2-R12-E1) is given below. The IDEA StatiCa reports of the new connections at 8.5 m radius, with the summary of the results, are given in Appendix D.')
for i in (304, 305, 308): remove(i)
remove(309)
DW = [('1000', 'General note', '02', '30.10.2026'), ('1101', 'Level 2 general arrangement plan and elevation view', '04', '13.11.2026'),
      ('1102', 'Typical framing arrangement plan and details sheet 1', '03', '04.11.2026'), ('1103', 'Typical framing arrangement plan and details sheet 2', '04', '13.11.2026'),
      ('1201', 'Typical staircase plan, elevation view and details sheet 1', '02', '04.11.2026'), ('1202', 'Typical staircase plan, elevation view and details sheet 2', '02', '04.11.2026'),
      ('1301', 'External staircase general arrangement', '01', '13.11.2026')] + [('130%d' % (k + 1), 'External staircase plan details sheet %d' % k, '01', '13.11.2026') for k in range(1, 6)]
fill(100, [['970027-S01-ST-' + n, t, '%s, %s' % (i, dt)] for n, t, i, dt in DW])
settext(425, 'The drawings 970027-S01-ST-1000 to 1306 are reproduced below at their current issue, reduced from A3.')
cellsub(94, 'Ring beam connections: M20 grade 8.8 (M30 grade 8.8 at the 12 m radius ring joints)', 'Grade 8.8 (M20, and M16 at the external staircase). Grade 10.9 (M24) at the ring to radial connections of the existing ring beams only')
last = None
for k, (n, t, i, dt) in enumerate(DW):
    jpg = FIG + 'dwg/d-%02d.jpg' % (k + 1); cap = 'Figure 0: 970027-S01-ST-%s: %s (%s)' % (n, t, i)
    if k < 6:
        ip, cp = ch[426 + 3 * k], ch[427 + 3 * k]; new_picture(ip, jpg, WDW); settext(427 + 3 * k, cap); last = cp
    else:
        pb = clone_after(last, ch[428]); ip = clone_after(pb, ch[426]); new_picture(ip, jpg, WDW); last = clone_after(ip, ch[427], cap)
for title, text in (('Appendix D: Connection Design Reports', 'The IDEA StatiCa reports of the 36 new connections at 8.5 m radius are given on the following pages. The first page summarises the results of all the connections.'),
                    ('Appendix E: Member Force Envelopes', 'The envelopes of the member forces over the ULS combinations are given on the following pages for each member group.')):
    pb = clone_after(last, ch[423]); h = clone_after(pb, ch[424], title); last = clone_after(h, ch[425], text)
"""
rep("\n# ------------------------------------------------------------------ figure and table numbers in document order", rev + "\n# ------------------------------------------------------------------ figure and table numbers in document order")
open('edit_v21.py', 'w').write(s)
