"""Clean up Wing's report docx (26016-RPT-001-A, 02.11.2026 edit). Usage: edit_report.py in.docx out.docx [pagemap.json]
Pass 1 without pagemap writes '0' page numbers; render to PDF, build the pagemap, run again."""
import sys, re, json, copy
import docx
from docx.oxml.ns import qn
from docx.oxml import parse_xml, OxmlElement
from docx.text.paragraph import Paragraph
from docx.table import Table

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = 'xmlns:w="%s"' % W
src, dst = sys.argv[1], sys.argv[2]
pagemap = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
d = docx.Document(src)
body = d.element.body
ch = list(body.iterchildren())          # indexes as in dump.txt (taken before any edit)
log = []

def P(i): return Paragraph(ch[i], d)
def T(i): return Table(ch[i], d)

def wts(el):
    """w:t elements of the direct runs of a paragraph (not inside math)."""
    return [t for t in el.iter(qn('w:t'))]

def sub(el, old, new, count=1):
    """Replace old by new in the text of a paragraph or cell element, also across runs."""
    ts = wts(el)
    full = ''.join(t.text or '' for t in ts)
    k = full.find(old)
    if k < 0:
        raise SystemExit('NOT FOUND: %r in %r' % (old, full[:120]))
    pos = 0; first = True
    for t in ts:
        s = t.text or ''
        a, b = pos, pos + len(s)
        lo, hi = max(a, k), min(b, k + len(old))
        if lo < hi or (first and a <= k <= b and len(old) == 0):
            piece = new if first else ''
            t.text = s[:lo - a] + piece + s[hi - a:]
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            first = False
        pos = b
    log.append((old[:50], new[:50]))

def settext(i, new):
    """Whole new text for a paragraph without math: keep the first run's format."""
    el = ch[i]
    assert not el.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'), i
    ts = wts(el)
    if not ts: Paragraph(el, d).add_run(new); log.append((i, new[:60])); return
    ts[0].text = new
    ts[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    for t in ts[1:]:
        t.text = ''
    log.append((i, new[:60]))

def cellsub(tbl_i, old, new):
    n = 0
    for tc in ch[tbl_i].iter(qn('w:tc')):
        for p in tc.findall(qn('w:p')):
            if old in ''.join(t.text or '' for t in wts(p)):
                sub(p, old, new); n += 1
    if not n: raise SystemExit('cell NOT FOUND: %r' % old)

def remove(i):
    ch[i].getparent().remove(ch[i])

# ------------------------------------------------------------------ text corrections
sub(ch[98], 'Appendix B', 'Appendix C')                                   # drawings are in Appendix C
cellsub(94, 'EN 10025 to 2', 'EN 10025-2')
cellsub(94, 'EN ISO 898 to 1', 'EN ISO 898-1')
cellsub(121, 'Current design (model v15)', 'Current design')
cellsub(121, 'BS EN 12811 to 1 with TG20:13, BS 5950 to 1', 'BS EN 12811-1 with TG20:13, BS 5950-1')
cellsub(121, 'BS EN 12811 to 1', 'BS EN 12811-1')
cellsub(121, 'Removed in v15 at', 'Removed at')
sub(ch[154], 'LC 501 to 512', 'LC 501 to 508')
settext(156, 'A uniform temperature change of +15 °C and -15 °C has been considered. The structure is an open steel frame and '
             'the thermal movement of about 3 mm at the raking strut ends is accommodated by the bolt hole clearance of the '
             'strut connections, which are detailed with snug tight bolts. Hence the temperature load is not combined with '
             'the other actions for the member and connection checks.')
sub(ch[181], 'The temperature combinations 136 to 139 are not used.', 'The temperature load is not combined, as stated in section 4.5.')
sub(ch[198], 'The critical members are verified in addition with a direct hand check to EN 1993-1-1 (section 7.2.2).',
            'The critical member is verified in addition with a direct check to EN 1993-1-1 (Appendix B).')
sub(ch[215], ' The analysis model is version 15 of 27.10.2026. The six inner columns between Level 2 and the roof of the earlier models have been removed',
            ' The six inner columns between Level 2 and the roof have been removed')
sub(ch[216], 'Members and stability: the global', 'The global')
sub(ch[217], 'Connections: all existing', 'All existing')
sub(ch[218], 'Stability: the stability', 'The stability')
for i in (216, 217, 218):                                              # the former bold labels
    for b in list(ch[i].iter(qn('w:b'))) + list(ch[i].iter(qn('w:bCs'))): b.getparent().remove(b)
settext(220, 'Figure 8: SOFiSTiK model with the member groups. The six inner columns removed between Level 2 and the roof are shown red dashed.')
settext(223, 'The radials, the outer rings at 12 m radius, the Level 1 ring at 3.0 m radius, the columns and the facade diagonals are continuous.')
settext(224, 'The rings at 8.5 m radius, the rings at 3.0 m radius at Level 2 and the roof, the ring at 1.9 m radius, the raking struts and the stair stringers are released for bending about the major axis at both ends.')
settext(225, 'The Level 2 and roof radials are coupled rigidly to the kingpost collar, and the kingpost is modelled with 20 mm shell elements.')
# move the three end condition sentences under the heading 6.2 Member End Conditions
for i in (225, 224, 223):
    ch[226].addnext(ch[i])
sub(ch[237], ', WinGRAF', '')
sub(ch[239], ', WinGRAF', '')
sub(ch[241], ', WinGRAF', '')
sub(ch[244], 'verified independently with a hand check to EN 1993-1-1.', 'verified independently with a direct check to EN 1993-1-1 (Appendix B).')
sub(ch[245], '(section 7.2.2)', '(Appendix B)')
settext(248, 'Table 13. Deflection results (SLS)')
sub(ch[254], ' is given below, followed by the extract of the BDK and AQB output for the highest members.', ' is given below.')
sub(ch[289], 'taken from the v15 model', 'taken from the model')
sub(ch[300], 'with the welds governing at 90% utilisation. The existing ring to radial connection at 12 m radius is satisfactory at the limit of its welds.',
            'with a maximum weld utilisation of 87%. The existing ring to radial connection at 12 m radius satisfies EN 1993-1-8 with a maximum weld utilisation of 80% (Appendix A).')
settext(303, 'The IDEA StatiCa results of the new connections at 8.5 m radius are summarised below, followed by the IDEA StatiCa report of the existing Level 2 ring to radial connection at 12 m radius.')
settext(309, 'IDEA StatiCa report of the Level 2 ring to radial connection at 12 m radius (L2-R12-E1)')
settext(385, 'Appendix B: Level 2 Outer Ring Member Check')
remove(307); remove(306)                                                   # caption of a figure that is not in the document


# ================================================================== external stairs and model update (v19)
import os
from docx.shared import Emu
FIG = os.environ.get('FIGDIR', '/mnt/project-files/26016/design-report/rev_2026-11-12/figures/')
V = json.load(open(os.environ['V19JSON'])) if os.environ.get('V19JSON') else None
MAXW = 5900000                                      # text width in EMU (about 16.4 cm)

def new_picture(el, png, width=None):
    """Replace the picture of paragraph el by png (same paragraph, same alignment)."""
    from PIL import Image
    for r in list(el.findall(qn('w:r'))):
        if r.findall('.//' + qn('w:drawing')): el.remove(r)
    w, h = Image.open(png).size
    width = width or MAXW
    if h / w * width > 7600000: width = int(7600000 * w / h)      # not taller than about 21 cm
    Paragraph(el, d).add_run().add_picture(png, width=Emu(width))

def clone_after(ref, proto, text=None):
    """Insert a copy of paragraph proto after ref; optional new text."""
    new = copy.deepcopy(proto)
    for b in new.findall(qn('w:bookmarkStart')) + new.findall(qn('w:bookmarkEnd')): new.remove(b)
    ref.addnext(new)
    if text is not None:
        ts = wts(new)
        if not ts: Paragraph(new, d).add_run(text); return new
        ts[0].text = text
        for t in ts[1:]: t.text = ''
    return new

def fig_after(ref, png, caption, proto_img, proto_cap, width=None):
    pi = clone_after(ref, proto_img); new_picture(pi, png, width)
    return clone_after(pi, proto_cap, caption)

def row_texts(tr): return [''.join(t.text or '' for t in tc.iter(qn('w:t'))) for tc in tr.findall(qn('w:tc'))]
def set_row(tr, texts):
    for tc, tx in zip(tr.findall(qn('w:tc')), texts):
        ts = list(tc.iter(qn('w:t')))
        if not ts:
            p = tc.find(qn('w:p')); Paragraph(p, d).add_run(tx); continue
        ts[0].text = tx
        for t in ts[1:]: t.text = ''
def add_row(tbl_el, after_tr, texts):
    new = copy.deepcopy(after_tr); after_tr.addnext(new); set_row(new, texts); return new
def find_row(tbl_i, key):
    for tr in ch[tbl_i].findall(qn('w:tr')):
        if row_texts(tr)[0].strip() == key: return tr
    raise SystemExit('row not found ' + key)

# --- scope and description
sub(ch[83], 'the new internal staircase from Level 2 to Level 1 in accordance', 'the new internal staircases from Level 1 to Level 2 and the new external staircase from the ground to Level 1 in accordance')
sub(ch[83], 'balustrades, the exterior staircase and the vibration checks', 'balustrades and the vibration checks')
sub(ch[109], 'Two staircases connect Level 1 and Level 2. All 33 column bases and the kingpost base are considered pinned.',
    'Two internal staircases connect Level 1 and Level 2, and an external staircase with two arms connects the ground to Level 1. All 33 column bases, the kingpost base and the supports of the external staircase are considered pinned.')
new_picture(ch[80], FIG + 'F14_one_deck_two_decks.png', 5300000)
new_picture(ch[114], FIG + 'F06_stairs_internal.png')
settext(115, 'Figure 4: Internal stairs between Level 1 and Level 2')
p1 = clone_after(ch[115], ch[109], 'The internal stairs are located between 8.5 m and 12 m radius, at 260 to 300 degrees (Stair A) and at 20 to 60 degrees (Stair B). Each stair has two flights with a middle landing at +6.04 m. The stringers are RHS 160x80x5 and the landing frames are RHS 200x100x6, and each middle landing is supported by two SHS 100x100x5 posts on the Level 1 radial beam below.')
p2 = clone_after(p1, ch[109], 'The external staircase has two arms. Each arm rises from the start platform at +0.64 m to a first landing at +2.43 m and to a landing at Level 1, which meets the deck at 15 to 25 degrees and at 295 to 305 degrees. The stringers and the landing beams are RHS 160x80x5. The landings stand on SHS 80x80x6.3 legs with pinned bases, connected by SHS 80x80x6.3 transverse beams which are pinned at both ends. At Level 1 each landing bears on the outer ring beam through two brackets which transfer vertical load only.')
fig_after(p2, FIG + 'F15_stairs_external.png', 'Figure 0: External staircase from the ground to Level 1', ch[114], ch[115])
new_picture(ch[116], FIG + 'F04_supports.png', 4300000)
# --- loads
sub(ch[137], 'at 260 to 300 degrees and at 40 to 80 degrees', 'at 260 to 300 degrees and at 20 to 60 degrees')
cellsub(144, 'cf 1.5 RHS 250, 1.2 RHS 50', 'cf 1.5 RHS 200, 1.2 RHS 50')
# --- analysis
sub(ch[215], 'and the kingpost is modelled with shell elements.', 'and the kingpost is modelled with shell elements. The internal and the external staircases are included in the model.')
new_picture(ch[219], FIG + 'F01_model_3d.png')
new_picture(ch[221], FIG + 'F02_section_20_200.png')
new_picture(ch[227], FIG + 'F03_level_plans.png')
clone_after(ch[225], ch[225], 'The stringers of the internal stairs are pinned at the foot and at the top. The stringers of the external staircase are released for bending about the major axis at both ends of each flight, and their feet stand on pinned supports. The brackets of the external staircase on the Level 1 outer ring transfer vertical force only, and the transverse beams between the legs are pinned at both ends.')
tr = find_row(232, '5 / 6 / 7')
set_row(tr, ['5 / 6 / 7', 'RHS 200x100x6 / RHS 50x50x5 / tray 300x5', 'Landing frames of the internal stairs (60) / landing joists / treads (60, 62)'])
tr8 = add_row(ch[232], tr, ['8', 'SHS 100x100x5', 'Landing posts of the internal stairs (61)'])
tr9 = add_row(ch[232], tr8, ['9', 'SHS 80x80x6.3', 'Legs, transverse beams and ring brackets of the external staircase (62)'])
add_row(ch[232], tr9, ['10', 'RHS 160x80x5', 'Stair stringers (60, 62), landing beams of the external staircase (62)'])

# ================================================================== v19 results (tables, checks, conclusion)
import math
M_T = '{http://schemas.openxmlformats.org/officeDocument/2006/math}t'
VX = os.environ.get('V19DIR', '/mnt/project-files/26016/design-report/rev_2026-11-12/v21_export/')
A3 = json.load(open(VX + 'A_followup/partA3.json')); RES = json.load(open(VX + 'res_v19.json'))

def msub(el, old, new):
    """Replace inside one math text token."""
    for t in el.iter(M_T):
        if old in (t.text or ''):
            t.text = t.text.replace(old, new, 1); log.append((old, new)); return
    raise SystemExit('MATH NOT FOUND: %r' % old)

def setcell(tc, text, bold=None):
    ts = list(tc.iter(qn('w:t')))
    if not ts:
        Paragraph(tc.find(qn('w:p')), d).add_run(text); ts = list(tc.iter(qn('w:t')))
    else:
        ts[0].text = text; ts[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        for t in ts[1:]: t.text = ''
    if bold is not None:
        for r in tc.iter(qn('w:r')):
            rPr = r.find(qn('w:rPr'))
            if rPr is None: rPr = OxmlElement('w:rPr'); r.insert(0, rPr)
            for b in rPr.findall(qn('w:b')) + rPr.findall(qn('w:bCs')): rPr.remove(b)
            if bold: rPr.insert(0, OxmlElement('w:b'))

def fill(tbl_i, rows, proto=1, bold=None, keep_math_col0=False):
    """Replace all data rows of a table by rows (list of text lists); the row format is copied from row proto."""
    trs = ch[tbl_i].findall(qn('w:tr')); p = trs[proto]; last = trs[0]
    new = []
    for k, tx in enumerate(rows):
        r = copy.deepcopy(p); last.addnext(r); last = r; new.append(r)
        for j, (tc, t) in enumerate(zip(r.findall(qn('w:tc')), tx)):
            setcell(tc, t, bold(k, j, t) if bold else None)
    for r in trs[1:]: ch[tbl_i].remove(r)
    return new

# --- analysis output pictures (WinGRAF, v19)
new_picture(ch[236], VX + 'W3_L2_My_LC119.png')
new_picture(ch[238], VX + 'W2_deformed_LC201_x100.png')
new_picture(ch[240], VX + 'W4_buckling_mode1_PLC102.png')
sub(ch[241], '7.09', '6.95')

# --- section 7 introduction
sub(ch[245], 'at the two nodes where the facade diagonals meet it the elastic program check exceeds 1.0 at the node centreline, and the direct check at the face of the stiffened connection (Appendix B) gives 0.88.',
    'at the nodes at 340 and 220 degrees the elastic program check exceeds 1.0 at the node centreline, and the direct check at the face of the stiffened connection (Appendix B) gives 0.89.')
sub(ch[245], 'All the members of the two deck structure were found', 'All the members of the two deck structure and of the staircases were found')

# --- Table 13 deflections
fill(249, [
 ['Level 1 deck, outer ring between diagonal nodes (L = 8.2 m)', 'G + Q + 0.5W', '15.8', '221', '32.8 (L/250)', 'OK'],
 ['Level 1 deck, same, imposed load only', 'Q', '7.9', '11', '22.8 (L/360)', 'OK'],
 ['Level 2 deck, radial kingpost to r 12 (L = 11.3 m)', 'G + Q', '32.2', '201', '45.4 (L/250)', 'OK'],
 ['Level 2 deck, same, imposed load only', 'Q', '24.1', '11 + 12 + 13', '31.5 (L/360)', 'OK'],
 ['Roof, radial kingpost to r 12, downward (L = 11.3 m)', 'G + Q', '15.9', '201', '45.4 (L/250)', 'OK'],
 ['Roof, same, imposed load only', 'Q roof', '9.5', '12', '31.5 (L/360)', 'OK'],
 ['Roof, upward under wind uplift', 'G + W', '18.8 (up)', '206', '45.4 (L/250)', 'OK'],
 ['Horizontal, Level 2 (h = 8.1 m) / roof (h = 12.1 m)', 'G + W (+ Q)', '1.3 / 1.3', '202 / 204', '27 / 40 (h/300)', 'OK'],
 ['Internal stairs, stringer Level 1 to middle landing (L = 4.0 m)', 'G + Q', '7.1', '201', '15.9 (L/250)', 'OK'],
 ['External staircase, flight between its ends (L = 3.1 m)', 'G + Q', '2.9', '201', '12.3 (L/250)', 'OK'],
 ['External staircase, landing at Level 1, horizontal (h = 4.43 m)', 'G + Q / G + Q + 0.5W', '23.4 / 26.7', '201 / 218', '14.8 (h/300)', 'See 7.2.3'],
])
sub(ch[247], 'of the decks and the roof.', 'of the decks, the roof and the staircases. The deck and roof values are absolute displacements of the model.')

# --- Table 14 member buckling check
fill(256, [
 ['11', 'Facade diagonals, ground to Level 1', 'SHS 150x150x10', '0.38', 'SLN 25 / LC 147', 'OK'],
 ['21', 'Facade diagonals, Level 1 to Level 2', 'SHS 150x150x10', '0.39', 'SLN 17 / LC 145', 'OK'],
 ['31', 'Facade diagonals, Level 2 to roof', 'SHS 150x150x10', '0.24', 'SLN 380 / LC 147', 'OK'],
 ['12', 'Raking struts', 'SHS 150x150x10', '0.09', 'SLN 448 / LC 121', 'OK'],
 ['13', 'Columns r 8.5 m, ground to Level 1', 'SHS 150x150x10', '0.25', 'SLN 41 / LC 121', 'OK'],
 ['23', 'Columns r 8.5 m, Level 1 to Level 2', 'SHS 150x150x10', '0.14', 'SLN 96 / LC 119', 'OK'],
 ['14', 'Inner columns, ground to Level 1', 'SHS 150x150x10', '0.37', 'SLN 399 / LC 145', 'OK'],
 ['24', 'Inner columns, Level 1 to Level 2', 'SHS 150x150x10', '0.29', 'SLN 417 / LC 122', 'OK'],
 ['15', 'Level 1 beams', 'UB 254x146x43', '0.66', 'SLN 223 / LC 153', 'OK'],
 ['25', 'Level 2 beams', 'UB 457 / UB 254', '0.89', 'SLN 56 / LC 120', 'OK'],
 ['35', 'Roof beams', 'UB 254x146x43', '0.38', 'SLN 318 / LC 107', 'OK'],
 ['60', 'Internal stairs', 'RHS 160x80x5 / RHS 200x100x6', '0.43', 'SLN 490 / LC 122', 'OK'],
 ['61', 'Landing posts of the internal stairs', 'SHS 100x100x5', '0.11', 'SLN 602 / LC 120', 'OK'],
 ['62', 'External staircase, stringers and landing beams', 'RHS 160x80x5', '0.38', 'SLN 746 / LC 135', 'OK'],
 ['62', 'External staircase, legs', 'SHS 80x80x6.3', '0.90', 'SLN 767 / LC 121', 'OK'],
])
settext(257, 'For the Level 2 outer ring the result of the direct check at 300 mm from the node is given (Appendix B); the program check at the node centreline gives 1.07 for this member and 1.01 for the adjacent members SLN 57 and SLN 62, which are covered by the same direct check. The UB 457x191x98 radials of Level 2 reach 0.65 (SLN 73, combination 147). The legs of the external staircase are verified in section 7.2.3.')

# --- Table 15 cross section check
fill(259, [
 ['1', 'SHS 150x150x10', '0.39', 'beam 110113 (GRP 21) / LC 146', 'OK'],
 ['2', 'UB 254x146x43', '0.79', 'beam 140020 (GRP 25) / LC 120', 'OK'],
 ['4', 'UB 457x191x98', '0.61', 'beam 140389 (GRP 25) / LC 145', 'OK'],
 ['5', 'RHS 200x100x6', '0.47', 'beam 170305 (GRP 60) / LC 120', 'OK'],
 ['6', 'RHS 50x50x5', '0.22', 'beam 170128 (GRP 60) / LC 120', 'OK'],
 ['7', 'Tread tray 300x5 (elastic)', '0.72', 'beam 170105 (GRP 60) / LC envelope, elastic', 'OK'],
 ['8', 'SHS 100x100x5', '0.10', 'beam 180010 (GRP 61) / LC 120', 'OK'],
 ['9', 'SHS 80x80x6.3', '0.29', 'beam 190493 (GRP 62) / LC 152', 'OK'],
 ['10', 'RHS 160x80x5', '0.48', 'beam 170403 (GRP 60) / LC 122', 'OK'],
])
settext(260, 'For the UB 254x146x43 the governing section is the Level 2 outer ring at 300 mm from the 340 degree node (Appendix B); the program check at the node centreline gives 1.07.')

# --- Table 16 global stability
cellsub(265, '7.09', '6.95'); cellsub(265, '7.46', '7.15')
setcell(ch[265].findall(qn('w:tr'))[2].findall(qn('w:tc'))[2], 'Level 1 radials between 3.0 m and 8.5 m radius, lateral (group 15)')
settext(267, 'The first 20 modes lie between 6.95 and 9.50 (combination 102) and between 7.15 and 10.07 (combination 119). Mode 1 of combination 102 is the buckling of a ground floor diagonal between its end nodes, with all the other member groups moving less than a quarter of it. It is a member mode, which BDK checks directly. Mode 1 of combination 119 is a lateral mode of the Level 1 radials between 3.0 m and 8.5 m radius, in which the inner rings turn about the vertical axis; these radials are verified for lateral buckling by BDK with a maximum utilisation of 0.66. The external staircase does not govern any of the first 20 modes of either combination: its largest displacement in these modes is 12% of the displacement of the governing member.')
msub(ch[269], '1 - 1/7.09', '1 - 1/6.95'); msub(ch[269], ' = 1.164', ' = 1.168')
settext(270, 'For the columns, struts and diagonals the amplified utilisation is 0.39 x 1.168 = 0.46.')

# --- 7.2.4 external staircase (new, before Connection Design)
h = clone_after(ch[270], ch[263], 'External Staircase')
p = clone_after(h, ch[270], 'The external staircase is part of the analysis model and is verified for the same combinations. The maximum utilisation of each member type is given below.')
cap = clone_after(p, ch[258], 'Table 0. External staircase: maximum utilisation per member type')
tb = copy.deepcopy(ch[259]); cap.addnext(tb)
trs = tb.findall(qn('w:tr'))
for tc, t in zip(trs[0].findall(qn('w:tc')), ['Member', 'Profile', 'Clause 6.3 / 6.2', 'Member / LC', 'Status']): setcell(tc, t)
rows = [
 ['Stringers', 'RHS 160x80x5', '0.38 / 0.34', 'SLN 746 / LC 135, SLN 758 / LC 121', 'OK'],
 ['Stringer seats of the upper flights on the first landing', 'RHS 160x80x5', '0.32 / 0.42', 'SLN 711 / LC 135, SLN 756 / LC 135', 'OK'],
 ['Landing beams', 'RHS 160x80x5', '0.29 / 0.40', 'SLN 764 / LC 135, SLN 763 / LC 121', 'OK'],
 ['Legs', 'SHS 80x80x6.3', '0.90 / 0.29', 'SLN 767 / LC 121, SLN 768 / LC 152', 'OK'],
 ['Transverse beams between the legs', 'SHS 80x80x6.3', '0.01 / 0.05', 'SLN 793 / LC 119', 'OK'],
 ['Brackets on the Level 1 ring', 'SHS 80x80x6.3', '0.04 / 0.04', 'SLN 724 / LC 122', 'OK'],
 ['Treads', '5 mm plate (elastic)', '0.57', 'SLN 728 / LC envelope', 'OK'],
]
for k, tx in enumerate(rows):
    if k + 1 < len(trs): r = trs[k + 1]
    else: r = copy.deepcopy(trs[1]); trs[-1].addnext(r); trs.append(r)
    for tc, t in zip(r.findall(qn('w:tc')), tx): setcell(tc, t)
for r in trs[len(rows) + 1:]: tb.remove(r)
grid = tb.find(qn('w:tblGrid')).findall(qn('w:gridCol')); tot = sum(int(g.get(qn('w:w'))) for g in grid)
wd = [int(tot * f) for f in (0.34, 0.19, 0.13, 0.24, 0.10)]
for g, w_ in zip(grid, wd): g.set(qn('w:w'), str(w_))
for r in tb.findall(qn('w:tr')):
    for tc, w_ in zip(r.findall(qn('w:tc')), wd):
        tcw = tc.find(qn('w:tcPr')).find(qn('w:tcW')) if tc.find(qn('w:tcPr')) is not None else None
        if tcw is not None: tcw.set(qn('w:w'), str(w_)); tcw.set(qn('w:type'), 'dxa')
sp = clone_after(tb, ch[257], '')
for t in wts(sp): t.text = ''
p1 = clone_after(sp, ch[270], 'The stringers are pinned at both ends of each flight and carry the stair load as simply supported beams. The legs are SHS 80x80x6.3 with a height of 4.43 m at the Level 1 landing and a design compression of 28 kN (combination 121). They are verified conservatively with a buckling length of twice their height, which gives 0.90. The landings are held in position by the flights, which act as raking struts to their pinned feet, and with a buckling length equal to the height the EN 1993-1-1 interaction check gives 0.32.')
p2 = clone_after(p1, ch[270], 'The feet of the lower flights are pinned and provide the lateral support of the staircase. Under the ULS combinations each foot carries up to 40 kN downward and up to 22 kN uplift, with a horizontal force of up to 47 kN (combination 111), and is anchored to the foundation for these forces. The leg bases carry up to 32 kN downward, up to 6 kN uplift and about 1 kN horizontally. The brackets on the Level 1 outer ring carry an axial force between 2 kN tension and 21 kN compression.')
p3 = clone_after(p2, ch[270], 'Under the characteristic combination G + Q the landing at Level 1 moves horizontally by 23.4 mm, and by 26.7 mm with wind (combination 218), while the Level 1 deck moves less than 2 mm. The first landing moves by 4.0 mm and 7.8 mm. The vertical deflection of the flights between their ends is 2.9 mm.')

# --- reactions
new_picture(ch[283], FIG + 'F20_reactions.png')
rw = A3['rows']; col = [r for r in rw if 2 <= r['node'] <= 34]; st = [r for r in rw if 901 <= r['node'] <= 916]; kp = [r for r in rw if r['r'] < 1]
f1 = lambda v: ('%.1f' % v).replace('-0.0', '0.0') if abs(v) < 0.05 else '%.1f' % v
def rrow(r): return [str(r['node']), '%.1f' % r['r'], '%d' % (round(r['th'] / 5.0) * 5 % 360 if r['node'] < 900 else round(r['th']) % 360), f1(r['px']), f1(r['py']), f1(r['pz']), f1(r['pz201']), f1(r['eq'][0]), str(r['eq'][1])]
rows = [rrow(r) for r in col] + [rrow(r) for r in st]
kp102 = sum(r['pz'] for r in kp); kp201 = sum(r['pz201'] for r in kp)
rows.append(['Kingpost base', '0.3', 'all', '', '', '%.1f (sum)' % kp102, '%.1f (sum)' % kp201, '', ''])
rows.append(['Total', '', '', '', '', '%.1f' % A3['tot102'][2], '%.1f' % A3['tot201'], '', ''])
assert abs(sum(r['pz'] for r in rw) - A3['tot102'][2]) < 0.2
fill(286, rows, bold=lambda k, j, t: (j in (5, 6, 7) and t.startswith('-')))
sub(ch[282], 'its total is given (102: 995.8 kN, 201: 690.2 kN).', 'its total is given (102: %.1f kN, 201: %.1f kN). Nodes 901 to 916 are the supports of the external staircase: nodes 901, 902, 909 and 910 are the feet of the lower flights at +0.64 m, and the other nodes are the leg bases.' % (kp102, kp201))
sub(ch[282], 'EQU = 0.9G + 1.5W + 0.9EHF (131 to 134, the lowest of the four is given).', 'EQU = 0.9G + 1.5W + 0.9EHF (131 to 134, the lowest of the four is given). The largest reactions over all ULS combinations are 428.3 kN compression (node 2, combination 146), 53.2 kN uplift (node 12, combination 133) and 112.7 kN horizontal (node 27, combination 105).')

# --- sliding and overturning
sl = RES['sliding']
fill(292, [[r[0], r[1], '%.1f' % r[2], '%.1f' % r[3], '%.1f' % r[4], '%.1f' % r[5], '%.2f' % r[6]] for r in sl])
dw = [r[6] for r in sl if r[0] == 'DL + WL']; other = min(r[6] for r in sl if r[0] != 'DL + WL')
Hs = [abs(RES_b) for RES_b in (308.0, 300.4, 317.9, 315.0)]
sub(ch[289], 'the friction at the 34 bases', 'the friction at the bases')
sub(ch[289], 'taken from the model for the basic load cases (dead load 1881 kN, imposed load 4489 kN, wind with uplift on the decks and the roof 271 to 288 kN horizontal and 936 to 986 kN uplift per direction):',
    'taken from the model for the basic load cases (dead load %.0f kN, imposed load %.0f kN, wind with uplift on the decks and the roof 196 to 208 kN horizontal and 608 to 651 kN uplift per direction):' % (RES['DL'], RES['LL']))
ov = RES['overturning']
def ovf(o): return ((o['G'] - o['uplift']) * o['a'] - o['G'] * o['xG']) / o['M_wind_centre']
ofs = [ovf(o) for o in ov]; k = ofs.index(min(ofs)); o = ov[k]
ovtxt = ('Overturning is assessed for DL + WL about the edge of the base polygon, which is 11.3 m from the centre of the structure. For the governing wind direction (%s) the stabilising moment of the dead load reduced by the wind uplift is %.0f kNm and the overturning moment of the wind at base level is %.0f kNm, which gives a factor of %.1f. The factors of the other directions lie between %.1f and %.1f.'
         % (o['wind'], (o['G'] - o['uplift']) * o['a'] - o['G'] * o['xG'], o['M_wind_centre'], ofs[k], sorted(ofs)[1], max(ofs)))
clone_after(ch[293], ch[270], ovtxt)
print('sliding DL+WL', min(dw), max(dw), 'other min', other, 'overturning', ofs)


# --- Level 1 ring to radial joints without flange plates (ring ends pinned about both axes)
clone_after(ch[224], ch[224], 'The Level 1 rings at 8.5 m radius are also released for bending about the minor axis where they frame into the web of the radial, at 0, 40, 80, 120, 160, 200, 240, 280 and 320 degrees.')
sub(ch[272], 'At Level 1 the ring end plates are strengthened with 12 mm flange plates, and the raking struts', 'At Level 1 the ring is connected through its web only and is pinned about both axes, and the raking struts')
cellsub(274, 'Radial continuous; ring end plate 125x150x12, 4 M20, with 12 mm flange plates 125x200 (half plates either side of the ring web)', 'Radial continuous; ring web end plate 125x150x12, 4 M20, ring pinned about both axes')
cellsub(274, 'Level 1, r 8.5 at 80 / 280 deg', 'Level 1, r 8.5 at 40 / 280 deg')
trsA = ch[305].findall(qn('w:tr'))
for tr_, tx in ((trsA[1], ['L1-R8-A (7), worst at 160 deg', '0.0', '13.7', '76.5', 'Pass']), (trsA[2], ['L1-R8-B_040', '0.2', '18.1', '73.9', 'Pass']), (trsA[3], ['L1-R8-B_280', '0.6', '17.8', '93.8', 'Pass'])):
    assert row_texts(tr_)[0].startswith('L1-R8-'), row_texts(tr_)
    for tc, t in zip(tr_.findall(qn('w:tc')), tx): setcell(tc, t)
sub(ch[300], 'with a maximum weld utilisation of 87%.', 'with a maximum weld utilisation of 99%.')
# --- conclusion
sub(ch[297], 'at the two nodes at 140 and 220 degrees where the facade diagonals meet it: the direct check at the face of the stiffened ring to radial connection, 300 mm from the node, gives 0.88.',
    'at the nodes at 340 and 220 degrees: the direct check at the face of the stiffened ring to radial connection, 300 mm from the node, gives 0.89. The members of the internal stairs reach 0.72 and the members of the external staircase reach 0.90.')
sub(ch[298], '7.09', '6.95'); sub(ch[298], 'is 0.48.', 'is 0.46.')
sub(ch[298], 'friction factor of safety 1.27 to 1.39 under DL + WL with mu = 0.40, 13 and more with the imposed load) and overturning (factor 3.9).',
    'friction factor of safety %.2f to %.2f under DL + WL with mu = 0.40, above the minimum of 1.4 adopted in the original design, %d and more with the imposed load) and overturning (factor %.1f).' % (min(dw), max(dw), int(other), min(ofs)))
sub(ch[299], 'the deflections of the decks and the roof are within', 'the deflections of the decks, the roof and the stair flights are within')

# --- Appendix B: Level 2 outer ring, SLN 56 at the 340 degree node, combination 120
settext(386, 'The Level 2 outer ring UB 254x146x43 at 12 m radius is continuous and hogs at the nodes at 340 and 220 degrees. The hogging moment at the 340 degree node centreline is 163.8 kNm under combination 120. The ring to radial connection at these nodes is a stiffened detail with 20 mm plates, 10 mm web plates and stiffeners over about 300 mm either side of the radial (figure below), so the bare section is verified at 300 mm from the node, at the end of the connection plates. The moment there follows from the node moment and the shear at the node:')
msub(ch[389], ' = 157.0 - 89 × 0.3 + 0.7 = 131 ', ' = 163.8 - 91 × 0.3 + 0.1 = 137 ')
sub(ch[390], 'for the segment between the radial nodes either side of the 140 degree node:', 'for the segment between the 340 degree node and the radial node at 0 degrees:')
trs = ch[392].findall(qn('w:tr'))
def c(r, j): return trs[r].findall(qn('w:tc'))[j]
sub(c(0, 0), 'from the 140 degree node (combination 121)', 'from the 340 degree node (combination 120)')
sub(c(1, 0), '(compression)', '(tension, neglected)'); setcell(c(1, 1), '16.5 kN')
setcell(c(2, 1), '91 kN (at the node)')
setcell(c(3, 1), '137 kNm (163.8 kNm at the node centreline)')
setcell(c(4, 1), '1.0 kNm'); setcell(c(5, 1), '4.17 m')
msub(ch[403], '89', '91')
sub(ch[404], ' = 0.014 below 0.25', ' = 0.011 below 0.25')
msub(ch[405], '131', '137'); msub(ch[405], '1.2', '1.0'); msub(ch[405], ' = 0.708 + 0.031 = 0.74 ≤ 0.90', ' = 0.766 + 0.026 = 0.79 ≤ 0.90')
settext(406, 'The axial force is a tension of 16.5 kN. It is neglected, so that the member is verified for bending only and flexural buckling does not apply.')
for i in (407, 408, 409, 410): remove(i)
for b_ in list(ch[406].iter(qn('w:b'))) + list(ch[406].iter(qn('w:bCs'))): b_.getparent().remove(b_)
sub(ch[412], 'L = 4.1 m', 'L = 4.17 m')
msub(ch[413], ' = 415 ', ' = 406 ')
msub(ch[414], '415', '406'); msub(ch[414], ' = 0.61', ' = 0.62')
msub(ch[415], ' = 0.677 ', ' = 0.681 ')
msub(ch[416], ' = 0.83 ', ' = 0.82 ')
msub(ch[417], '0.83', '0.82')
sub(ch[420], ' = 0.38, ', ' = 0.36, '); sub(ch[420], ' = 0.98, ', ' = 1.00, '); sub(ch[420], ' = 0.63 (Table B.1):', ' = 0.60 (Table B.1, with the axial force neglected):')
MF = '{http://schemas.openxmlformats.org/officeDocument/2006/math}f'
for i in (421, 422):                                   # remove the axial term N / Nb,Rd
    f = next(ch[i].iter(MF)); assert ''.join(t.text for t in f.iter(M_T)).startswith('21'); f.getparent().remove(f)
msub(ch[421], ' + 0.40 ', '0.40 '); msub(ch[421], '131', '137'); msub(ch[421], ' + 0.38 ', ' + 0.36 '); msub(ch[421], '1.2', '1.0'); msub(ch[421], ' = 0.015 + 0.337 + 0.012 = 0.36 ≤ 0.90', ' = 0.350 + 0.009 = 0.36 ≤ 0.90')
msub(ch[422], ' + 0.98 ', '1.00 '); msub(ch[422], '131', '137'); msub(ch[422], ' + 0.63 ', ' + 0.60 '); msub(ch[422], '1.2', '1.0'); msub(ch[422], ' = 0.034 + 0.822 + 0.019 = 0.88 ≤ 0.90', ' = 0.877 + 0.016 = 0.89 ≤ 0.90')


# --- wind pressure 0.50 kPa
sub(ch[125], 'The wind pressure is 0.766 kPa,', 'The wind pressure is 0.50 kPa,')
settext(139, 'The basic velocity pressure is calculated in accordance with EN 1991-1-4 clause 4.5 with a basic wind velocity of 25 m/s:')
_w = clone_after(ch[141], ch[139], 'The design wind pressure is taken as 0.50 kPa, which is the pressure adopted on the cladded area in the original design (1.3 x 0.383 kPa).')
remove(141)
for old, new in (('2.30 kN/m', '1.50 kN/m'), ('0.167 kN/m', '0.109 kN/m'), ('0.84 kN/m', '0.55 kN/m'), ('1.16 kN/m', '0.75 kN/m'), ('0.46 / 0.39 kN/m', '0.30 / 0.25 kN/m'), ('0.766 kPa average', '0.50 kPa average'), ('0.766 kPa', '0.50 kPa'), ('0.153 kPa', '0.10 kPa')):
    cellsub(144, old, new)
nw = 0
for i_, el_ in enumerate(ch):
    if el_.tag != qn('w:tbl') or i_ == 144: continue
    for p_ in el_.iter(qn('w:p')):
        tx_ = ''.join(t.text or '' for t in wts(p_))
        if 'qp = 0.766 kPa (EN 1991-1-4)' in tx_: sub(p_, 'qp = 0.766 kPa (EN 1991-1-4)', 'qp = 0.50 kPa'); nw += 1
        elif '0.766 kPa' in tx_: sub(p_, '0.766 kPa', '0.50 kPa'); nw += 1
assert nw == 4, nw
new_picture(ch[146], FIG + 'F08_wind_directions.png', 4680000)

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

# --- sections to the drawings of 13.11.2026
_n = 0
for _t in body.iter(qn('w:t')):
    if _t.text and '457x191x89' in _t.text: _t.text = _t.text.replace('457x191x89', '457x191x98'); _n += 1
print('UB 457x191x98 replacements', _n)

# ------------------------------------------------------------------ figure and table numbers in document order
fig = tab = 0
for el in body.iter(qn('w:p')):
    txt = ''.join(t.text or '' for t in wts(el))
    m = re.match(r'Figure (\d+):', txt)
    if m:
        fig += 1
        if int(m.group(1)) != fig: sub(el, 'Figure %s:' % m.group(1), 'Figure %d:' % fig)
    m = re.match(r'Table (\d+)\.', txt)
    if m and el.getparent() is body:
        tab += 1
        if int(m.group(1)) != tab: sub(el, 'Table %s.' % m.group(1), 'Table %d.' % tab)
print('figures', fig, 'tables', tab)

# ------------------------------------------------------------------ neutral picture names
n = 0
for el in body.iter('{http://schemas.openxmlformats.org/drawingml/2006/picture}cNvPr'):
    n += 1; el.set('name', 'Picture %d' % n)

# ------------------------------------------------------------------ contents: a real TOC field with links
def fld(kind):
    return '<w:r %s><w:fldChar w:fldCharType="%s"/></w:r>' % (NS, kind)

heads = []                                # (level, number, text, bookmark)
c1 = c2 = 0; bid = 9000
for el in body.iterchildren(qn('w:p')):
    pPr = el.find(qn('w:pPr'))
    st = pPr.find(qn('w:pStyle')) if pPr is not None else None
    sid = st.get(qn('w:val')) if st is not None else ''
    if sid not in ('Heading1', 'Heading2'): continue
    txt = ''.join(t.text or '' for t in wts(el)).strip()
    numbered = True
    numPr = pPr.find(qn('w:numPr'))
    if numPr is not None and numPr.find(qn('w:numId')).get(qn('w:val')) == '0': numbered = False
    if sid == 'Heading1':
        if numbered: c1 += 1; c2 = 0; num = str(c1)
        else: num = ''
        lvl = 1
    else:
        c2 += 1; num = '%d.%d' % (c1, c2); lvl = 2
    bid += 1; name = '_Toc26016%03d' % (bid - 9000)
    bs = parse_xml('<w:bookmarkStart %s w:id="%d" w:name="%s"/>' % (NS, bid, name))
    be = parse_xml('<w:bookmarkEnd %s w:id="%d"/>' % (NS, bid))
    first_r = el.find(qn('w:r'))
    first_r.addprevious(bs); el.append(be)
    heads.append((lvl, num, txt, name))

toc_first, toc_last = ch[44], ch[75]
anchor = ch[43]
for i in range(44, 76): remove(i)
prev = anchor
from xml.sax.saxutils import escape
for k, (lvl, num, txt, name) in enumerate(heads):
    page = str(pagemap.get(name, 0))
    runs = ''
    if k == 0:
        runs += fld('begin') + '<w:r %s><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>' % NS + fld('separate')
    link = ''
    if num: link += '<w:r><w:t>%s</w:t></w:r><w:r><w:tab/></w:r>' % num
    link += '<w:r><w:t xml:space="preserve">%s</w:t></w:r><w:r><w:tab/></w:r>' % escape(txt)
    link += ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGEREF %s \\h </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>%s</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>') % (name, page)
    runs += '<w:hyperlink %s w:anchor="%s" w:history="1">%s</w:hyperlink>' % (NS, name, link)
    if k == len(heads) - 1:
        runs += fld('end') + '<w:r %s><w:br w:type="page"/></w:r>' % NS
    p = parse_xml('<w:p %s><w:pPr><w:pStyle w:val="TOC%d"/></w:pPr>%s</w:p>' % (NS, lvl, runs))
    prev.addnext(p); prev = p
json.dump([list(h) for h in heads], open(dst + '.heads.json', 'w'), indent=1)

d.core_properties.last_modified_by = 'CaSE Engineering Services'
d.save(dst)
print(len(log), 'edits;', len(heads), 'contents entries')
