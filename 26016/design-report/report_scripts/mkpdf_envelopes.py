import csv, json, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
SRC = '../repo/26016/design-report/v21_export/envelopes/'
OUT = sys.argv[1]
pics = json.load(open(SRC + 'pictures_final.json'))[1:]
rows = list(csv.DictReader(open(SRC + 'env_table_ULS.csv')))
D = {11:('Raking V columns, ground to Level 1','SHS 150x150x10'),12:('Raking struts, ground to Level 1','SHS 150x150x10'),13:('Vertical columns, ground to Level 2','SHS 150x150x10'),
14:('Vertical columns, ground to Level 1','SHS 150x150x10'),15:('Level 1 radial and ring beams','UB 254x146x43'),21:('Raking V columns, Level 1 to Level 2','SHS 150x150x10'),
23:('Vertical columns, Level 1 to Level 2','SHS 150x150x10'),24:('Vertical columns, Level 1 to Level 2','SHS 150x150x10'),25:('Level 2 radial and ring beams','UB 254x146x43, UB 457x191x98'),
31:('Raking V columns, Level 2 to roof','SHS 150x150x10'),35:('Roof radial and ring beams','UB 254x146x43'),60:('Internal stairs','RHS 160x80x5, RHS 200x100x6, SHS 50x50x5, 5 mm plate'),
61:('Internal stair landing posts','SHS 100x100x5'),62:('External stair','RHS 160x80x5, SHS 80x80x6.3, 5 mm plate')}
H1 = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=14, leading=18, spaceAfter=6)
H2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=8, spaceAfter=4)
B = ParagraphStyle('b', fontName='Helvetica', fontSize=10, leading=13.5, spaceAfter=5, alignment=4)
CAP = ParagraphStyle('cap', fontName='Helvetica', fontSize=9.5, leading=12.5, spaceBefore=5, alignment=4)
CL = ParagraphStyle('cl', fontName='Helvetica', fontSize=7.6, leading=9.2)
CC = ParagraphStyle('cc', fontName='Helvetica', fontSize=7.6, leading=9.2, alignment=1)
CH = ParagraphStyle('ch', fontName='Helvetica-Bold', fontSize=8, leading=9.6, alignment=1)
def foot(c, d):
    c.setFont('Helvetica', 8); c.setFillColor(colors.grey)
    c.drawString(20*mm, 10*mm, '26016 Concourse Viewing Platform, Member Force Envelopes'); c.drawRightString(190*mm, 10*mm, 'Page %d' % d.page)
doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=16*mm, bottomMargin=16*mm, title='26016 Member Force Envelopes', author='CaSE')
doc.addPageTemplates(PageTemplate(frames=[Frame(20*mm, 16*mm, 170*mm, 265*mm, 0, 0, 0, 0)], onPage=foot))
S = []
S += [Paragraph('Member Force Envelopes', H1),
 Paragraph('The member forces of the SOFiSTiK analysis model are presented in this Appendix as envelope diagrams, which were generated with the SOFiSTiK graphics module WinGRAF from the current analysis model which includes the external staircase and the release of the weak axis moment at the ends of the Level 1 ring beams at radius 8.5 m.', B),
 Paragraph('The envelope was formed with the SOFiSTiK superposition module MAXIMA over the 43 ULS (STR) load combinations 101 to 130, 135, 141 to 148 and 151 to 154 as listed in the load combination table of the report. Each combination is taken as one complete alternative, hence every envelope value is the value of one single combination and no forces of different combinations are added together. The 4 EQU combinations 131 to 134 are used for the base stability only and are not included.', B),
 Paragraph('The envelope was verified by comparing the MAXIMA result at every result station of all 4759 beam elements against the largest and smallest value read directly from the 43 combinations, and the values were found to be identical.', B),
 Paragraph('Presentation', H2),
 Paragraph('One internal force is shown per figure. The maximum envelope is drawn in red and the minimum envelope in blue. Values are printed at the governing locations only, so that the figures remain readable, and the complete maximum and minimum values of every member group are tabulated in Table 1 and Table 2 together with the governing combination and structural line. The diagram scale and the envelope extremes are noted in the legend at the bottom of each figure.', B),
 Paragraph('The forces are in kN and the moments in kNm. The sign convention is that of the SOFiSTiK local beam axes. Where, N is the axial force (tension positive), Vz and My are the shear force and bending moment about the strong axis, and Vy and Mz are the shear force and bending moment about the weak axis.', B),
 Paragraph('The floor framing is shown in an isometric view from above, since My and Vz act in the vertical plane and can not be read in a true plan view. The weak axis moment Mz of Level 1 is shown in plan. The columns and raking columns are shown storey by storey. The central kingpost is modelled with shell elements and therefore has no beam force diagram.', B),
 Paragraph('Contents', H2)]
names = {'L1':'Level 1 framing','L2':'Level 2 framing','RF':'Roof framing','V_G-L1':'Columns and raking columns, ground to Level 1','V_L1-L2':'Columns and raking columns, Level 1 to Level 2',
 'V_L2-RF':'Raking columns, Level 2 to roof','S_int':'Internal stairs','S_ext':'External stair'}
qn = {'MY':('bending moment My','kNm'),'MZ':('bending moment Mz','kNm'),'VZ':('shear force Vz','kN'),'N':('axial force N','kN')}
grp = {'L1':'group 15','L2':'group 25','RF':'group 35','V_G-L1':'groups 11 to 14','V_L1-L2':'groups 13, 21, 23 and 24','V_L2-RF':'group 31','S_int':'groups 60 and 61','S_ext':'group 62'}
figs = []
for p in pics:
    q = p['picture']; nm = q['name']
    if nm == 'L1_Mz_plan': part, extra = 'L1', ', plan view'
    elif nm == 'L1_ring85_Mz_plan': part, extra = 'L1', ', ring beams at radius 8.5 m only, plan view'
    else: part, extra = nm.rsplit('_', 1)[0], ''
    qq, u = qn[q['q']]
    figs.append((p['file'], '%s, %s%s' % (names[part], qq, extra), grp[part], q, u))
toc = [['Table 1', 'Envelope of the forces N, Vy and Vz per member group'], ['Table 2', 'Envelope of the moments Mt, My and Mz per member group'], ['Figure 1', 'Member groups of the analysis model']]
toc += [['Figure %d' % (i + 2), f[1]] for i, f in enumerate(figs)]
t = Table([[Paragraph(a, CL), Paragraph(b, CL)] for a, b in toc], colWidths=[22*mm, 148*mm]); t.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,-1), 1), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
S += [t, PageBreak()]
def tab(title, qs):
    hd = [Paragraph('Group', CH), Paragraph('Members', CH)] + [Paragraph('%s %s' % (q, m), CH) for q in qs for m in ('max', 'min')]
    data = [hd]
    for r in rows:
        g = int(r['group']); line = [Paragraph(str(g), CC), Paragraph('%s<br/><font color="#555555">%s</font>' % D[g], CL)]
        for q in qs:
            for m in ('max', 'min'):
                k = '%s_%s' % (q, m); v = float(r[k]); v = 0.0 if abs(v) < 0.05 else v
                line.append(Paragraph('<b>%.1f</b><br/><font color="#555555">LC %s<br/>SLN %s</font>' % (v, r[k + '_lc'], r[k + '_sln']), CC))
        data.append(line)
    t = Table(data, colWidths=[11*mm, 51*mm] + [18*mm] * 6, repeatRows=1)
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.4, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e6e6e6')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2.5), ('LEFTPADDING', (0,0), (-1,-1), 2), ('RIGHTPADDING', (0,0), (-1,-1), 2)]))
    return [Paragraph(title, H2), t, Paragraph('Each cell gives the envelope value, the governing ULS combination (LC) and the structural line (SLN) on which it occurs.', CAP), PageBreak()]
S += tab('Table 1. Envelope of the forces N, Vy and Vz per member group (kN)', ['N', 'Vy', 'Vz'])
S += tab('Table 2. Envelope of the moments Mt, My and Mz per member group (kNm)', ['Mt', 'My', 'Mz'])
S += [Image('key_groups.png', width=170*mm, height=170*mm*10.2/8.0), Paragraph('<b>Figure 1.</b> Member groups of the analysis model. The group numbers are those referred to in Table 1, Table 2 and in the member verification tables of the report.', CAP), PageBreak()]
for i, (f, title, gtxt, q, u) in enumerate(figs):
    w = 170*mm; h = w * 3024 / 2658
    if h > 222*mm: h = 222*mm; w = h * 2658 / 3024
    cap = '<b>Figure %d.</b> %s (%s), %s. ULS envelope, maximum in red (load case %d) and minimum in blue (load case %d). Values are printed where the magnitude exceeds %g %s. Envelope maximum %.1f %s and minimum %.1f %s.' % (
        i + 2, title, u, gtxt, q['lcs'][0], q['lcs'][1], q['thr'], u, q['max'], u, q['min'], u)
    S += [Image(SRC + 'png/' + f, width=w, height=h), Paragraph(cap, CAP), PageBreak()]
S.pop()
doc.build(S)
