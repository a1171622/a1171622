"""26016 v21 combined PDF of the 13 Nov 2026 work (author CaSE):
A results summary (RESULTS_v21.md) + WinGRAF W pictures; B ULS envelopes PDF; C kingpost von Mises (KINGPOST.md + pictures);
D L2-R12-E1 ring to radial joint (summary, pictures, IDEA reports V6 and V4); E IDEA appendix, 36 r 8.5 joints.
py -3.11 make_combined.py"""
import os, re, json, datetime
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter
from PIL import Image
E = r"C:\Sofistik workflow\26016-design-report\v21_export"; K = E + r"\kingpost"; ENV = r"C:\Sofistik workflow\26016-member-check\v21\envelopes"
R12 = r"C:\Sofistik workflow\idea-statica\v21\R12"; APP = r"C:\Sofistik workflow\idea-statica\26016_IDEA_appendix\26016_IDEA_StatiCa_all_joints_v21.pdf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "26016_v21_combined_13Nov2026.pdf")
TMP = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\arial.ttf"; FONTB = r"C:\Windows\Fonts\arialbd.ttf"


class Doc(FPDF):
    title_txt = ""
    def header(self):
        self.set_font("A", "", 7); self.set_text_color(110)
        self.cell(0, 4, f"26016 Concourse Viewing Platform - model v21 - {self.title_txt}", align="L")
        self.ln(5); self.set_text_color(0)
    def footer(self):
        self.set_y(-10); self.set_font("A", "", 7); self.set_text_color(110); self.cell(0, 4, "CaSE  |  13.11.2026", align="C"); self.set_text_color(0)


def new(title):
    p = Doc("P", "mm", "A4"); p.add_font("A", "", FONT); p.add_font("A", "B", FONTB); p.set_auto_page_break(True, 14); p.title_txt = title
    p.set_author("CaSE"); p.set_creator("CaSE"); p.set_title("26016 v21 combined results")
    return p


def md_pages(p, path, max_lines=None):
    txt = open(path, encoding="utf-8").read().replace("\t", "  ")
    for a, b in (("(Wing, 13 Nov 2026)", "(13 Nov 2026)"), ("(Wing to decide)", "(for decision)"), ("(for Wing)", ""), ("Wing's three comments", "Review comments"),
                 ("Wing to decide", "for decision"), ("Wing wants", "a more conservative check is wanted"), ("Wing", "the reviewer")):
        txt = txt.replace(a, b)
    lines = txt.splitlines()[:max_lines] if max_lines else txt.splitlines()
    table = []
    def flush():
        if not table: return
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table if not re.match(r"^\s*\|?\s*-{3}", r)]
        n = max(len(r) for r in rows); w = (p.w - 20) / n
        fs = 6.5 if n <= 6 else 5.5
        p.set_font("A", "", fs)
        for i, r in enumerate(rows):
            r = r + [""] * (n - len(r))
            h = max(p.multi_cell(w, 3.2, c.replace("**", ""), dry_run=True, output="LINES").__len__() for c in r) * 3.2
            if p.get_y() + h > p.h - 15: p.add_page()
            y0 = p.get_y(); x0 = p.l_margin
            for j, c in enumerate(r):
                p.set_xy(x0 + j * w, y0); p.set_font("A", "B" if i == 0 else "", fs)
                p.multi_cell(w, 3.2, c.replace("**", ""), border=1)
            p.set_y(y0 + h)
        p.ln(1.5); table.clear()
    for l in lines:
        if l.strip().startswith("|"): table.append(l); continue
        flush(); p.set_x(p.l_margin)
        if l.startswith("# "): p.set_font("A", "B", 13); p.multi_cell(0, 6, l[2:]); p.ln(1)
        elif l.startswith("## "): p.ln(1.5); p.set_font("A", "B", 10); p.multi_cell(0, 5, l[3:]); p.ln(0.5)
        elif l.strip() == "": p.ln(1.5)
        else:
            p.set_font("A", "", 8); p.multi_cell(0, 3.8, re.sub(r"(\S{90})", r" ", l.replace("**", "").replace("`", "")))
    flush()


def img_page(p, path, caption):
    p.add_page(); im = Image.open(path); w_mm = p.w - 20; h_mm = w_mm * im.height / im.width
    maxh = p.h - 40
    if h_mm > maxh: h_mm = maxh; w_mm = h_mm * im.width / im.height
    p.set_font("A", "B", 9); p.multi_cell(0, 4.5, caption); p.ln(1)
    jp = os.path.join(TMP, "_img_" + os.path.basename(path) + ".jpg")
    im.convert("RGB").save(jp, quality=88)
    p.image(jp, x=(p.w - w_mm) / 2, w=w_mm, h=h_mm)


parts = []   # (title, pdf path)
# ---------------- cover + contents (written last, needs page numbers) -> placeholder
# ---------------- A results summary
p = new("A  Results summary (SOFiSTiK v21)"); p.add_page(); md_pages(p, os.path.join(E, "RESULTS_v21.md"))
for f, c in (("v21_changed_members_reading.png", "v21: members changed to drawings 970027-S01-ST (stair RHS 160x80x5, L2 radials UB 457x191x98, landing supports SHS 80x80x6.3)"),
             ("W1_model_3D_sections.png", "W1 model v21, 3D with rendered cross sections"), ("W2_deformed_LC201_x100.png", "W2 deformed shape, SLS LC 201 (G + Q), x100"),
             ("W3_L2_My_LC119.png", "W3 Level 2 framing, My, ULS LC 119"), ("W4_buckling_mode1_PLC102.png", "W4 buckling mode 1 of PLC 102 (alpha_cr 6.95)"),
             ("W5_buckling_PLC119_mode1_L1.png", "W5 buckling mode 1 of PLC 119, Level 1 plan (alpha_cr 7.15)"), ("W8_external_stair_sections.png", "W8 external stair, sections to scale")):
    img_page(p, os.path.join(E, f), c)
a = os.path.join(TMP, "_A.pdf"); p.output(a); parts.append(("A  Results summary, model v21 (run, global results, member checks, stair, buckling, deflections, sliding)", a))
# ---------------- B envelopes
parts.append(("B  ULS member force envelopes (WinGRAF)", os.path.join(ENV, "26016_v21_ULS_envelopes.pdf")))
# ---------------- C kingpost
p = new("C  Kingpost von Mises"); p.add_page(); md_pages(p, os.path.join(K, "KINGPOST.md"))
img_page(p, os.path.join(K, "kingpost_reading_v21.png"), "Kingpost shell model as read from the cdb")
for d in json.load(open(os.path.join(K, "pictures.json"))):
    img_page(p, os.path.join(K, d["file"]), f"{d['title']} - LC {d['lc']}, legend max {d['legend_max_MPa']} MPa (node-averaged). {d['shows']}")
c = os.path.join(TMP, "_C.pdf"); p.output(c); parts.append(("C  Kingpost: von Mises check of the shell model", c))
# ---------------- D L2-R12-E1
p = new("D  L2-R12-E1 ring to radial joint at r 12"); p.add_page(); md_pages(p, os.path.join(R12, "final", "L2-R12-E1_results_v21.md"))
for f, cap in ((os.path.join(R12, "L2-R12-E1_reading_v21.png"), "Reading of drawing 970027-S01-ST-1103 rev 04, sections D1 / E"),
               (os.path.join(R12, "final", "L2-R12-E1_as_built_v21.png"), "Corrected model (variant 4) after the review comments: views, plan, strain"),
               (os.path.join(R12, "final", "L2-R12-E1_variants_v21.png"), "Earlier variants (before the straight-ring correction): strain with the drawing's extra plates")):
    img_page(p, f, cap)
d = os.path.join(TMP, "_D.pdf"); p.output(d); parts.append(("D  L2-R12-E1: summary and pictures", d))
parts.append(("D1 L2-R12-E1 IDEA StatiCa report, variant 6 (15 mm... 12 mm leg stiffener welds) - PASS", os.path.join(R12, "var_V6", "report", "L2-R12-E1_000.pdf")))
parts.append(("D2 L2-R12-E1 IDEA StatiCa report, variant 4 (corrected model)", os.path.join(R12, "var_V4s", "report", "L2-R12-E1_000.pdf")))
# ---------------- E appendix
parts.append(("E  IDEA StatiCa appendix: 36 ring to radial joints at r 8.5 on v21 forces", APP))
parts[4] = ("D1 L2-R12-E1 IDEA StatiCa report, variant 6 (315 stiffener flange welds 12 mm leg) - PASS", parts[4][1])
# ---------------- cover with contents
counts = [len(PdfReader(f).pages) for _, f in parts]
start = 2; toc = []
for (t, f), n in zip(parts, counts):
    toc.append((t, start, n)); start += n
cv = new("Contents"); cv.add_page(); cv.set_font("A", "B", 16); cv.ln(20)
cv.multi_cell(0, 8, "26016 Concourse Viewing Platform\nModel v21 - combined results"); cv.ln(4)
cv.set_font("A", "", 10)
cv.multi_cell(0, 5, "Model 26016_check_v21: v20 updated to drawings 970027-S01-ST (issue 13.11.2026): stair stringers RHS 160x80x5, Level 2 radials "
                    "UB 457x191x98, external stair landing supports SHS 80x80x6.3. SOFiSTiK 2027 run 13.11.2026 (exit 0, 0 errors, 212 warnings). "
                    "IDEA StatiCa Connection 26.0.\nPrepared by CaSE, 13.11.2026.")
cv.ln(6); cv.set_font("A", "B", 11); cv.cell(0, 6, "Contents", new_x="LMARGIN", new_y="NEXT"); cv.ln(2)
cv.set_font("A", "", 9)
for t, s, n in toc:
    cv.cell(165, 6, t[:110]); cv.cell(0, 6, f"p. {s}", align="R", new_x="LMARGIN", new_y="NEXT")
cvf = os.path.join(TMP, "_cover.pdf"); cv.output(cvf)
w = PdfWriter(); w.append(cvf)
for (t, f), (tt, s, n) in zip(parts, toc):
    w.append(f, outline_item=t)
w.add_metadata({"/Author": "CaSE", "/Title": "26016 Concourse Viewing Platform - model v21 - combined results", "/CreationDate": "D:20261113000000"})
w.write(OUT); w.close()
tot = len(PdfReader(OUT).pages)
print(OUT, tot, "pages", round(os.path.getsize(OUT) / 1e6, 1), "MB"); print(json.dumps(toc, indent=0))
for f in os.listdir(TMP):
    if f.startswith("_"): os.remove(os.path.join(TMP, f))
