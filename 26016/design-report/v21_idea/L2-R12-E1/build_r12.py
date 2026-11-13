"""L2-R12-E1 (v21) to drawing 970027-S01-ST-1103 rev 04 sections D1 / E (reading: L2-R12-E1_reading_v21.png, option (a)).
Base: v14 L2-R12-E1_000.xml (points, elements, load cases, result layout). Changes:
 - radial UB 457x191x98, stub to the ring outer flange tip; ring = ONE continuous member (SLN55 + SLN56), bearing member;
   ring eccentricity for flush bottoms; SLN55 segment reversed so the ring is a chain P4 -> node -> P5.
 - ConnectionData rebuilt: 395x145x20 plates (upper piece + 2 lower halves each side), 6 x M24 10.9 (3 grids),
   bracket (10 web, 20 inclined stiffener, 20 top plate), 20 ring stiffeners at 315, 20 bottom plates, radial bottom
   flange cut over the ring footprint, welds a 7.0 (10 leg) to flanges / a 4.2 (6 leg) to webs.
 - forces: v21 cdb end forces, mapping fitted on the v14 template (calib_e1.json), Vz/Mz flipped where the element
   orientation differs from the calibration.
py -3.11 build_r12.py <v21 cdb> <out.xml> [rotation_deg]"""
import sys, os, re, json, math
sys.path.insert(0, r"C:\Sofistik workflow\idea-statica\v21\builder")
from cdbend import Model
from sofistik_mcp import results as R
CDB, OUT = sys.argv[1], sys.argv[2]
ROT = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
HERE = os.path.dirname(os.path.abspath(__file__))
CAL = json.load(open(os.path.join(HERE, "calib_e1.json")))
t = open(r"C:\Sofistik workflow\idea-statica\v14\xml_E1\L2-R12-E1_000.xml", "rb").read().decode("utf-16")
src = open(r"C:\Sofistik workflow\idea-statica\v21\builder\build_v19m_xml.py", encoding="utf-8").read()
exec(src[src.index("def rotate_text"):src.index("def blk")])
# ---------------- sections / geometry constants (m)
RH, RB, Rtw, Rtf = 0.2596, 0.1473, 0.0072, 0.0127
BH, BB, Btw, Btf, Br = 0.4672, 0.1928, 0.0114, 0.0196, 0.0102
PT = 0.020; ZP_TOP = 0.4276; ZP_BOT = 0.0127 if os.environ.get('R12_FIN_TO_BF') else 0.0327; ROWS = [ZP_TOP - 0.105, ZP_TOP - 0.230, ZP_TOP - 0.330]; GAUGE = 0.039
A_FL, A_WB = 0.0070, float(os.environ.get("R12_A_WB", "0.0042"))   # weld throats: 10 mm leg to flanges, 6 mm leg to webs


def setp(txt, name, val):
    return re.sub(rf"(<Name>{name}</Name><Value>)[^<]*(</Value>)", rf"\g<1>{val}\g<2>", txt, count=1)


a = t.index("<Name>UB457x191x89</Name>"); b = t.index("</CrossSection>", a)
cs = t[a:b].replace("UB457x191x89", "UB457x191x98")
for k, v in (("B", BB), ("H", BH), ("s", Btw), ("t", Btf), ("r2", Br)):
    cs = setp(cs, k, v)
t = t[:a] + cs + t[b:]
pts = {int(m[1]): [float(m[3]), float(m[4]), float(m[5])] for m in re.finditer(r"<Point3D><Id>(\d+)</Id><Name>([^<]*)</Name><X>([^<]*)</X><Y>([^<]*)</Y><Z>([^<]*)</Z>", t)}
pts0 = {k: list(v) for k, v in pts.items()}   # original geometry (for matching the cdb beams)
N0 = pts[1]; zb = N0[2] - BH / 2                        # bottom of steel (radial centroid on the node, ring flush)
er = [pts[1][i] - pts[2][i] for i in range(3)]; l = math.hypot(*er); er = [x / l for x in er]
et = [-er[1], er[0], 0.0]                                # tangent (towards P4 / SLN55)


def P(s, tt, h):
    return [N0[i] + s * er[i] + tt * et[i] for i in range(2)] + [zb + h]


tip = P(RB / 2 / math.cos(math.radians(10)) + 0.001, 0, BH / 2)
t = re.sub(r"(<Point3D><Id>3</Id><Name>P3</Name><X>)[^<]*(</X><Y>)[^<]*(</Y><Z>)[^<]*(</Z>)",
           lambda m: f"{m[1]}{tip[0]!r}{m[2]}{tip[1]!r}{m[3]}{tip[2]!r}{m[4]}", t, count=1)
t = t.replace("radial stub (plain cut 85 past the node)", "radial stub to the ring outer flange tip")


def rev(m):
    s = m.group(0)
    s = s.replace("<StartPoint><TypeName>Point3D</TypeName><Id>1</Id></StartPoint><EndPoint><TypeName>Point3D</TypeName><Id>4</Id></EndPoint>",
                  "<StartPoint><TypeName>Point3D</TypeName><Id>4</Id></StartPoint><EndPoint><TypeName>Point3D</TypeName><Id>1</Id></EndPoint>")
    for tg in ("VecX", "VecY"):
        s = re.sub(rf"<{tg}><X>([^<]*)</X><Y>([^<]*)</Y><Z>([^<]*)</Z></{tg}>",
                   lambda q: f"<{tg}><X>{-float(q[1])!r}</X><Y>{-float(q[2])!r}</Y><Z>{-float(q[3]) + 0.0!r}</Z></{tg}>", s)
    return s


t = re.sub(r"<LineSegment3D><Id>3</Id>.*?</LineSegment3D>", rev, t, count=1)
if not os.environ.get("R12_CHORDS"):
    # IDEA 26.0 draws a continuous member as ONE straight line (it took the SLN 55 chord direction and ran it on through the
    # node, 20 deg off the SLN 56 chord). So the ring is modelled straight along the tangent at the node (the bisector of the
    # two chords, each 10 deg off), and every bracket / stiffener part is placed on that straight ring.
    for pid_, sg in ((4, +1), (5, -1)):
        Lr = math.dist(pts[pid_][:2], N0[:2]); newp = [N0[0] + sg * Lr * et[0], N0[1] + sg * Lr * et[1], pts[pid_][2]]
        t = re.sub(rf"(<Point3D><Id>{pid_}</Id><Name>P{pid_}</Name><X>)[^<]*(</X><Y>)[^<]*(</Y><Z>)[^<]*(</Z>)",
                   lambda m: f"{m[1]}{newp[0]!r}{m[2]}{newp[1]!r}{m[3]}{newp[2]!r}{m[4]}", t, count=1)
        pts[pid_] = newp
    vx, vy = [-et[0], -et[1], 0.0], [er[0], er[1], 0.0]          # both ring elements run P4 -> P1 -> P5 (along -et)
    for sid in (3, 4):
        def fixv(m, vx=vx, vy=vy):
            s = m.group(0)
            s = re.sub(r"<VecX><X>[^<]*</X><Y>[^<]*</Y><Z>[^<]*</Z></VecX>", f"<VecX><X>{vx[0]!r}</X><Y>{vx[1]!r}</Y><Z>0.0</Z></VecX>", s)
            s = re.sub(r"<VecY><X>[^<]*</X><Y>[^<]*</Y><Z>[^<]*</Z></VecY>", f"<VecY><X>{vy[0]!r}</X><Y>{vy[1]!r}</Y><Z>0.0</Z></VecY>", s)
            return s
        t = re.sub(rf"<LineSegment3D><Id>{sid}</Id>.*?</LineSegment3D>", fixv, t, count=1)
ecc = -(BH - RH) / 2
m2 = re.search(r"<Member1D><Id>2</Id>.*?</Member1D>", t).group(0)
m2n = m2.replace("<Name>SLN55 ring</Name>", "<Name>ring SLN55 + SLN56 (continuous)</Name>").replace(
    "<ReferenceElement><TypeName>Element1D</TypeName><Id>3</Id></ReferenceElement>",
    "<ReferenceElement><TypeName>Element1D</TypeName><Id>3</Id></ReferenceElement><ReferenceElement><TypeName>Element1D</TypeName><Id>4</Id></ReferenceElement>")
m2n = re.sub(r"<Z>-0\.1018[0-9]*</Z>", f"<Z>{ecc!r}</Z>", m2n)
assert m2n.count(f"<Z>{ecc!r}</Z>") == 2
t = t.replace(m2, m2n); t = re.sub(r"<Member1D><Id>3</Id>.*?</Member1D>", "", t, count=1)
t = t.replace("<Name>SLN73 radial (ends, plain cut)</Name>", "<Name>SLN73 radial (ends at the ring)</Name>")
cpb = ("<ConnectedMembers><ConnectedMember><Id>1</Id><MemberId><TypeName>Member1D</TypeName><Id>1</Id></MemberId><IsContinuous>false</IsContinuous><Length>0</Length></ConnectedMember>"
       "<ConnectedMember><Id>2</Id><MemberId><TypeName>Member1D</TypeName><Id>2</Id></MemberId><IsContinuous>true</IsContinuous><Length>0</Length></ConnectedMember></ConnectedMembers>"
       "<BearingMember><TypeName>Member1D</TypeName><Id>2</Id></BearingMember>")
t = re.sub(r"<ConnectedMembers>.*?</BearingMember>", cpb, t, count=1, flags=re.S)
ba = ("<BoltAssembly><BoltAssembly><Id>1</Id><Name>M24 10.9</Name><BoltGrade><TypeName>Material</TypeName><Id>1</Id></BoltGrade><Diameter>0.024</Diameter><Borehole>0.026</Borehole>"
      "<HeadDiameter>0.036</HeadDiameter><DiagonalHeadDiameter>0.0416</DiagonalHeadDiameter><HeadHeight>0.015</HeadHeight><GrossArea>0.000452389</GrossArea><TensileStressArea>0.000353</TensileStressArea>"
      "<NutThickness>0.0194</NutThickness><WasherThickness>0.004</WasherThickness><WasherAtHead>true</WasherAtHead><WasherAtNut>true</WasherAtNut><LoadFromLibrary>true</LoadFromLibrary></BoltAssembly></BoltAssembly>")
t = re.sub(r"<BoltAssembly><BoltAssembly>.*?</BoltAssembly></BoltAssembly>", ba, t, count=1, flags=re.S)
t = re.sub(r"<ProjectName>[^<]*</ProjectName>", "<ProjectName>26016 Concourse Viewing Platform</ProjectName>", t, count=1)
t = re.sub(r"<Author>[^<]*</Author>", "<Author>CaSE</Author>", t)

# ---------------- connection data
def F(v): return f"{v!r}"
def xyz(tag, p): return f"<{tag}><Id>0</Id><X>{F(p[0])}</X><Y>{F(p[1])}</Y><Z>{F(p[2])}</Z></{tag}>"
def vec(tag, v): return f"<{tag}><X>{F(v[0])}</X><Y>{F(v[1])}</Y><Z>{F(v[2])}</Z></{tag}>"
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def unit(v):
    l = math.sqrt(sum(x * x for x in v)); return [x / l for x in v]


plates, welds, grids, cuts, geo = [], [], [], [], []
pid = [200]; WID = [600]


def plate(name, origin, ax, ay, poly, th, neg=False):
    pid[0] += 1; i = pid[0]; az = cross(ax, ay)
    pp = poly + [poly[0]]
    op = "".join(f"<Point2D><X>{F(x)}</X><Y>{F(y)}</Y></Point2D>" for x, y in pp)
    reg = "M " + " L ".join(f"{x:.6f} {y:.6f}" for x, y in pp)
    seg = "".join(f'<Segment2D xsi:type="LineSegment2D"><EndPoint><X>{F(x)}</X><Y>{F(y)}</Y></EndPoint></Segment2D>' for x, y in pp[1:])
    plates.append(f"<PlateData><Id>{i}</Id><Name>{name}</Name><Thickness>{F(th)}</Thickness><Material>S 275</Material><OutlinePoints>{op}</OutlinePoints>"
                  + xyz("Origin", origin) + vec("AxisX", ax) + vec("AxisY", ay) + vec("AxisZ", az)
                  + f"<Region>{reg}</Region><Geometry><Outline><StartPoint><X>{F(pp[0][0])}</X><Y>{F(pp[0][1])}</Y></StartPoint><Segments>{seg}</Segments></Outline></Geometry>"
                  + f"<OriginalModelId>P{i}</OriginalModelId><IsNegativeObject>{'true' if neg else 'false'}</IsNegativeObject></PlateData>")
    g3 = [[origin[k] + x * ax[k] + y * ay[k] for k in range(3)] for x, y in poly]
    geo.append(dict(name=name, id=i, poly=g3, th=th, normal=az, neg=neg))
    return i


def weld(name, a_, b_, p1, p2, th, wt="DoubleFillet"):
    WID[0] += 1
    welds.append(f"<WeldData><Id>{WID[0]}</Id><Name>{name}</Name><Thickness>{F(th)}</Thickness><Material>S 275</Material><WeldType>{wt}</WeldType><IsIntermittent>false</IsIntermittent>"
                 f"<ConnectedPartIds><string>{a_}</string><string>{b_}</string></ConnectedPartIds>" + xyz("Start", p1) + xyz("End", p2) + "</WeldData>")
    geo.append(dict(name=name, weld=[p1, p2], th=th))


def bolts(name, origin, ax, ay, az, pos, parts, length):
    WID[0] += 1
    ps = "".join(xyz("Point3D", p) for p in pos)
    cp = "".join(f"<ReferenceElement><TypeName>{k}</TypeName><Id>{v}</Id></ReferenceElement>" for k, v in parts)
    grids.append(f"<BoltGrid><Id>{WID[0]}</Id>" + xyz("Origin", origin) + vec("AxisX", ax) + vec("AxisY", ay) + vec("AxisZ", az)
                 + f"<Positions>{ps}</Positions><ConnectedParts>{cp}</ConnectedParts>"
                 f"<Name>{name}</Name><Length>{F(length)}</Length><ShearInThread>true</ShearInThread><BoltInteraction>Bearing</BoltInteraction><BoltAssembly><TypeName>BoltAssembly</TypeName><Id>1</Id></BoltAssembly></BoltGrid>")
    geo.append(dict(name=name, bolts=pos, axis=az, length=length))


up = [0.0, 0.0, 1.0]
dring = {+1: unit([pts[4][i] - N0[i] for i in range(2)] + [0.0]), -1: unit([pts[5][i] - N0[i] for i in range(2)] + [0.0])}


def ring_s_at(sig, tt):
    d = dring[sig]; lam = tt / (d[0] * et[0] + d[1] * et[1]); return lam * (d[0] * er[0] + d[1] * er[1])



def fin_pt(sig, w, d, n):
    """(lam, w) of the point on the fin outer face plane at ring-web offset w (so that edges on the fin face run along er)."""
    tt = sig * (Btw / 2 + PT)
    # point X = N0 + lam d + w n with X.et = tt  ->  lam = (tt - w n.et) / d.et
    det = d[0] * et[0] + d[1] * et[1]; lam = (tt - w * (n[0] * et[0] + n[1] * et[1])) / det
    return (lam, w)

fin = {}
for sig in (+1, -1):
    tm = sig * (Btw / 2 + PT / 2); sw = ring_s_at(sig, tm)
    side = "SLN55 side" if sig > 0 else "SLN56 side"
    o = P(0, tm, 0)
    U = plate(f"395x145x20 fin plate upper ({side})", o, er, up, [(sw - 0.0725, RH), (sw + 0.0725, RH), (sw + 0.0725, ZP_TOP), (sw - 0.0725, ZP_TOP)], PT)
    L1 = plate(f"395x145x20 fin plate lower outer ({side})", o, er, up, [(sw - 0.0725, ZP_BOT), (sw - Rtw / 2, ZP_BOT), (sw - Rtw / 2, RH - Rtf), (sw - 0.0725, RH - Rtf)], PT)
    L2 = plate(f"395x145x20 fin plate lower inner ({side})", o, er, up, [(sw + Rtw / 2, ZP_BOT), (sw + 0.0725, ZP_BOT), (sw + 0.0725, RH - Rtf), (sw + Rtw / 2, RH - Rtf)], PT)
    fin[sig] = dict(U=U, L1=L1, L2=L2, s0=sw, tm=tm)
    weld(f"fin upper to ring top flange ({side})", f"P{U}", "2", P(sw - 0.0725, tm, RH), P(sw + 0.0725, tm, RH), A_FL)
    for Lp, s1, s2 in ((L1, sw - 0.0725, sw - Rtw / 2), (L2, sw + Rtw / 2, sw + 0.0725)):
        weld(f"fin lower to ring top flange ({side})", f"P{Lp}", "2", P(s1, tm, RH - Rtf), P(s2, tm, RH - Rtf), A_FL)
        sx = sw - Rtw / 2 if Lp == L1 else sw + Rtw / 2
        weld(f"fin lower to ring web ({side})", f"P{Lp}", "2", P(sx, tm, ZP_BOT), P(sx, tm, RH - Rtf), A_WB)
        if os.environ.get("R12_FIN_TO_BF"):
            weld(f"fin lower to ring bottom flange ({side})", f"P{Lp}", "2", P(s1, tm, ZP_BOT), P(s2, tm, ZP_BOT), A_FL)
L_grip = 2 * PT + Btw


def o_face(s, h): return P(s, Btw / 2 + PT, h)


for tag, rows_, key in (("top row", [ROWS[0]], "U"), ("lower rows outer column", ROWS[1:], "L1"), ("lower rows inner column", ROWS[1:], "L2")):
    pos = []
    for h in rows_:
        s0 = fin[+1]["s0"]
        cols = [s0 - GAUGE, s0 + GAUGE] if key == "U" else [s0 + (-GAUGE if key == "L1" else GAUGE)]
        pos += [o_face(c, h) for c in cols]
    bolts(f"M24 10.9 {tag}", pos[0], er, up, [-x for x in et], pos,
          [("PlateData", fin[+1][key]), ("BeamData", 1), ("PlateData", fin[-1][key])], L_grip)
for sig in ((+1, -1) if not os.environ.get("R12_ONLY_FINS") else ()):
    side = "SLN55 side" if sig > 0 else "SLN56 side"; d = dring[sig]; n = cross(up, d)
    lam0 = (Btw / 2 + PT) / abs(d[0] * et[0] + d[1] * et[1])

    def Q(lam, w, h, d=d, n=n): return [N0[0] + lam * d[0] + w * n[0], N0[1] + lam * d[1] + w * n[1], zb + h]
    lamS = 0.315
    # ring stiffener at 315: one full-width plate (overlaps the ring web), welded to both flanges; a half-plate on the
    # inner side of the reversed element never connected in IDEA 26.0 (mechanism), the full plate is held from both sides
    stf = None
    if not os.environ.get("R12_NO_BOTTOM"):
        stf = plate(f"20 ring stiffener at 315 ({side})", Q(lamS, 0, 0), n, up, [(-RB / 2, Rtf), (RB / 2, Rtf), (RB / 2, RH - Rtf), (-RB / 2, RH - Rtf)], PT)
        weld(f"ring stiffener to top flange ({side})", f"P{stf}", "2", Q(lamS, -RB / 2, RH - Rtf), Q(lamS, RB / 2, RH - Rtf), A_FL)
        weld(f"ring stiffener to bottom flange ({side})", f"P{stf}", "2", Q(lamS, -RB / 2, Rtf), Q(lamS, RB / 2, Rtf), A_FL)
    if os.environ.get("R12_V1") and stf:
        # variant 1: the drawing's 20 x 295 plates on the ring bottom flange, one plate 140 wide per side (overlaps the ring
        # web), from the radial web face to the 315 stiffener; long edges welded to the bottom flange face, end edge to the
        # stiffener, the lower fin plates stand on it (their bottom edges welded to it)
        def ept(tt, w, d=d, n=n):
            det = d[0] * et[0] + d[1] * et[1]; return ((tt - w * (n[0] * et[0] + n[1] * et[1])) / det, w)
        WB = 0.070; t_in = sig * Btw / 2
        v1 = plate(f"20 x 295 plate on ring bottom flange ({side})", Q(0, 0, Rtf + PT / 2), d, n,
                   [ept(t_in, -WB), (lamS - PT / 2, -WB), (lamS - PT / 2, WB), ept(t_in, WB)], PT)
        for wv in (-WB, WB):
            a_ = ept(t_in, wv)
            weld(f"295 plate to ring bottom flange ({side})", f"P{v1}", "2", Q(a_[0], wv, Rtf), Q(lamS - PT / 2, wv, Rtf), A_FL, "Fillet")
        weld(f"295 plate to ring stiffener ({side})", f"P{v1}", f"P{stf}", Q(lamS - PT / 2, -WB, Rtf + PT / 2), Q(lamS - PT / 2, WB, Rtf + PT / 2), A_WB)
        for key, s1, s2 in (("L1", -0.0725, -Rtw / 2), ("L2", Rtw / 2, 0.0725)):
            sw, tm = fin[sig]["s0"], fin[sig]["tm"]
            weld(f"fin lower {key} to 295 plate ({side})", f"P{fin[sig][key]}", f"P{v1}", P(sw + s1, tm, ZP_BOT), P(sw + s2, tm, ZP_BOT), A_WB)
        if os.environ.get("R12_V3"):
            # variant 3: cover plate under the ring bottom flange, 140 x 15, 400 per side from the node (800 overall, in two
            # pieces because the ring chords kink 20 deg at the node), welded all round to the flange underside, 8 mm leg (a 5.6)
            TC, LC, A8 = 0.015, float(os.environ.get("R12_V3_L", "0.400")), 0.0056
            L0 = 0.12; cv = plate(f"cover plate 140x15 under ring bottom flange ({side})", Q(0, 0, -TC / 2), d, n, [(L0, -WB), (LC, -WB), (LC, WB), (L0, WB)], TC)
            for (l1, w1_), (l2, w2_) in (((L0, -WB), (LC, -WB)), ((L0, WB), (LC, WB)), ((LC, -WB), (LC, WB)), ((L0, -WB), (L0, WB))):
                weld(f"cover plate to ring bottom flange ({side})", f"P{cv}", "2", Q(l1, w1_, -TC / 2), Q(l2, w2_, -TC / 2), A8)
    for half, ws in ((("a", +1), ("b", -1)) if not os.environ.get("R12_NO_BOTTOM") else ()):
        w1, w2 = ws * Rtw / 2, ws * RB / 2
        bp = None if not os.environ.get("R12_WITH_BOTPL") else plate(f"20 bottom plate {half} ({side})", Q(0, 0, Rtf + PT / 2), d, n, [fin_pt(sig, w1, d, n), (lamS - PT / 2, w1), (lamS - PT / 2, w2), fin_pt(sig, w2, d, n)], PT)
        if bp: weld(f"bottom plate to ring web ({side} {half})", f"P{bp}", "2", Q(lam0, w1, Rtf + PT / 2), Q(lamS - PT / 2, w1, Rtf + PT / 2), A_WB)
        if bp: weld(f"bottom plate to ring bottom flange ({side} {half})", f"P{bp}", "2", Q(lam0, w2, Rtf), Q(lamS - PT / 2, w2, Rtf), A_FL, "Fillet")
        st = stf
        if bp: weld(f"bottom plate to ring stiffener ({side} {half})", f"P{bp}", f"P{st}", Q(lamS - PT / 2, w1, Rtf + PT / 2), Q(lamS - PT / 2, w2, Rtf + PT / 2), A_WB)
    lt = 0.155; hT = ZP_TOP; hR = RH
    if os.environ.get("R12_NO_BRACKET"): continue
    bw = plate(f"10 bracket web plate ({side})", Q(0, 0, 0), d, up, [(lam0, hR), (lamS, hR), (lt, hT), (lam0, hT)], 0.010)
    weld(f"bracket web to ring top flange ({side})", f"P{bw}", "2", Q(lam0, 0, hR), Q(lamS, 0, hR), A_WB)
    weld(f"bracket web to fin upper ({side})", f"P{bw}", f"P{fin[sig]['U']}", Q(lam0, 0, hR), Q(lam0, 0, hT), A_WB)
    L_inc = math.hypot(lamS - lt, hT - hR); c_, s_ = (lamS - lt) / L_inc, (hR - hT) / L_inc
    ai = unit([c_ * d[0], c_ * d[1], s_]); nz = cross(ai, n)
    if nz[2] < 0: nz = [-x for x in nz]
    for half, ws in (("a", +1), ("b", -1)):
        w1, w2 = ws * 0.005, ws * 0.0725
        tp = plate(f"20 bracket top plate {half} ({side})", Q(0, 0, hT + PT / 2), d, n, [fin_pt(sig, w1, d, n), (lt, w1), (lt, w2), fin_pt(sig, w2, d, n)], PT)
        weld(f"top plate to bracket web ({side} {half})", f"P{tp}", f"P{bw}", Q(lam0, w1, hT), Q(lt, w1, hT), A_WB)
        e1, e2 = fin_pt(sig, w1, d, n), fin_pt(sig, w2, d, n)
        weld(f"top plate to fin upper ({side} {half})", f"P{tp}", f"P{fin[sig]['U']}", Q(e1[0], e1[1], hT + PT / 2), Q(e2[0], e2[1], hT + PT / 2), A_WB)
        o_i = Q(lt, 0, hT); o_i = [o_i[k] - PT / 2 * nz[k] for k in range(3)]
        ip = plate(f"20 inclined stiffener {half} ({side})", o_i, ai, n, [(0, w1), (L_inc, w1), (L_inc, w2), (0, w2)], PT)
        weld(f"inclined stiffener to bracket web ({side} {half})", f"P{ip}", f"P{bw}", Q(lt, w1, hT), Q(lamS, w1, hR), A_WB)
        weld(f"inclined stiffener to ring top flange ({side} {half})", f"P{ip}", "2", Q(lamS, w1, hR), Q(lamS, w2, hR), A_FL)
        weld(f"inclined stiffener to top plate ({side} {half})", f"P{ip}", f"P{tp}", Q(lt, w1, hT), Q(lt, w2, hT), A_FL)
smin = -0.105   # ring inner flange tip under the radial flange width (+-96) incl. the 10 deg chord, + 5 mm
if os.environ.get("R12_V2"):
    # variant 2: section E 185x70x20 plate under the fins: one plate 140 wide (2 x 70 + ring web, overlaps the web) x 185
    # along the ring, on the ring bottom flange; radial web cut to sit on it; edges along the ring welded to the flange face
    s0m = 0.5 * (fin[+1]["s0"] + fin[-1]["s0"])
    v2 = plate("185x70x20 plates under the fins (section E, 2 x 70 + web)", P(s0m, 0, Rtf + PT / 2), er, et,
               [(-0.070, -0.0925), (0.070, -0.0925), (0.070, 0.0925), (-0.070, 0.0925)], PT)
    for sv in (-0.070, 0.070):
        weld("185 plate to ring bottom flange", f"P{v2}", "2", P(s0m + sv, -0.0925, Rtf), P(s0m + sv, 0.0925, Rtf), A_FL, "Fillet")
    for sig in (+1, -1):
        for key, s1, s2 in (("L1", -0.0725, -Rtw / 2), ("L2", Rtw / 2, 0.0725)):
            sw, tm = fin[sig]["s0"], fin[sig]["tm"]
            weld(f"fin lower {key} to 185 plate", f"P{fin[sig][key]}", f"P{v2}", P(sw + s1, tm, ZP_BOT), P(sw + s2, tm, ZP_BOT), A_WB)
H_CUT = (Rtf + PT + 0.001) if os.environ.get("R12_V2") else Btf + 0.004
neg = plate("cut radial bottom flange over the ring", P(0, 0, H_CUT / 2 - 0.002), er, et, [(smin, -0.12), (0.09, -0.12), (0.09, 0.12), (smin, 0.12)], H_CUT, neg=True)
cuts.append(f"<CutBeamByBeamData><Name>Radial bottom flange cut over the ring</Name><ModifiedObject><TypeName>BeamData</TypeName><Id>1</Id></ModifiedObject><CuttingObject><TypeName>PlateData</TypeName><Id>{neg}</Id></CuttingObject>"
            "<IsWeld>false</IsWeld><Offset>0</Offset><Method>Surface</Method><Orientation>Default</Orientation><PlaneOnCuttingObject>Closer</PlaneOnCuttingObject><CutPart>Begin</CutPart><ExtendBeforeCut>false</ExtendBeforeCut></CutBeamByBeamData>")
BD = ("<Plates /><OriginalModelId>{o}</OriginalModelId><Cuts /><IsAdded>false</IsAdded><AddedMemberLength>0</AddedMemberLength><IsNegativeObject>false</IsNegativeObject><MirrorY>false</MirrorY>"
      "<RefLineInCenterOfGravity>false</RefLineInCenterOfGravity><IsBearingMember>{b}</IsBearingMember><AutoAddCutByWorkplane>false</AutoAddCutByWorkplane>")
beams = ("<Beams><BeamData><Id>1</Id><Name>SLN73 radial (ends at the ring)</Name>" + BD.format(o=1, b="false") + "</BeamData>"
         "<BeamData><Id>2</Id><Name>ring SLN55 + SLN56 (continuous)</Name>" + BD.format(o=2, b="true") + "</BeamData></Beams>")
if os.environ.get("R12_NOCUT"): cuts.clear(); plates[:] = [p for p in plates if "<IsNegativeObject>true" not in p]
cd = f"<ConnectionData>{beams}<Plates>{''.join(plates)}</Plates><BoltGrids>{''.join(grids)}</BoltGrids><Welds>{''.join(welds)}</Welds><CutBeamByBeams>{''.join(cuts)}</CutBeamByBeams></ConnectionData>"
t = re.sub(r"<ConnectionData>.*?</ConnectionData>", lambda m: cd, t, count=1, flags=re.S)

# ---------------- forces from the v21 cdb
m = Model(CDB)
lcs_xml = {int(q[1]): int(q[2]) for q in re.finditer(r"<LoadCase><Id>(\d+)</Id><Name>LC_(\d+)</Name>", t)}
node = m.node_at(N0, 0.05); assert node, "node not found"
bl = m.beams_at(node)


def far_dir(b):
    a_, c_ = m.idx[b]["nodes"]; o = c_ if a_ == node else a_
    return unit([m.xyz[o][i] - m.xyz[node][i] for i in range(3)])


want = {1: [pts0[2][i] - N0[i] for i in range(3)], 3: [pts0[4][i] - N0[i] for i in range(3)], 4: [pts0[5][i] - N0[i] for i in range(3)]}
pick = {}
for e, w in want.items():
    w = unit(w); bb = max(bl, key=lambda b: sum(far_dir(b)[i] * w[i] for i in range(3)))
    assert sum(far_dir(bb)[i] * w[i] for i in range(3)) > 0.999, (e, bb); pick[e] = bb
assert len(set(pick.values())) == len(bl) == 3, (pick, bl)
Fend = m.end_forces(node, sorted(set(lcs_xml.values())))
SC = ("N", "Qy", "Qz", "Mx", "My", "Mz")
rec = {}


def fill(mo):
    rom = mo.group(0); eid = int(re.search(r"<Member><MemberType>Element1D</MemberType><Id>(\d+)</Id>", rom).group(1))

    def secr(q):
        s = q.group(0); k = int(re.search(r"<Loading><LoadingType>LoadCase</LoadingType><Id>(\d+)</Id>", s).group(1)); lc = lcs_xml[k]
        if eid == 2:
            vals = {c: 0.0 for c in SC}
        else:
            cal = CAL["els"][str(eid)]; b = pick[eid]; fr = Fend[(b, lc)]
            at_start = m.idx[b]["nodes"][0] == node
            flip = (at_start != cal["start_at_node"]) ^ (eid == 3)
            vals = {}
            for c in SC:
                sc_, sg = cal["map"][c]
                if flip and sc_ in ("Vz", "Mz"): sg = -sg
                vals[c] = sg * fr[sc_] * 1000.0
            rec.setdefault(str(eid), {})[lc] = {c: round(v / 1000, 3) for c, v in vals.items()}
        for c, v in vals.items():
            s = re.sub(rf"<{c}>[^<]*</{c}>", f"<{c}>{v!r}</{c}>", s, count=1)
        return s
    return re.sub(r'<SectionResultBase xsi:type="ResultOfInternalForces">.*?</SectionResultBase>', secr, rom, flags=re.S)


t = re.sub(r"<ResultOnMember>.*?</ResultOnMember>", fill, t, flags=re.S)
binfo = {k: dict(beam=v, sln=m.idx[v]["sln"]) for k, v in pick.items()}
m.cdb.close()
if ROT: t = rotate_text(t, ROT)
name = os.path.splitext(os.path.basename(OUT))[0]
t = t.replace("<Name>L2-R12-E1_000</Name>", f"<Name>{name}</Name>")
open(OUT, "wb").write(t.encode("utf-16"))
json.dump(dict(node=node, beams=binfo, forces_kN_kNm_IDEA_axes=rec), open(os.path.splitext(OUT)[0] + "_build.json", "w"), indent=1, default=str)
json.dump(geo, open(os.path.splitext(OUT)[0] + "_geo.json", "w"))
print("wrote", OUT, "node", node, "plates", len(plates), "welds", len(welds), "bolt grids", len(grids))
