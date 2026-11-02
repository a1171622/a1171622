"""EN 1993-1-1 ULS member check: cross-section (6.2) and member buckling (6.3.1-6.3.3).

For rolled I/H sections every equation is the same as Wing's spreadsheet
/mnt/project-files/beam-column-calc/EC3_beam_column_ULS.xlsx (sheet 'Calc'); the dictionary keys below carry the
spreadsheet's cell names (Npl_, Mcr_, chiLT_, u61B_ ...) so tests/test_vs_workbook.py can compare them one by one.

Added beyond the spreadsheet (marked HOLLOW): RHS / SHS / CHS hot-finished sections
  - properties from memcheck.sections_lib (EN 10210-2 corner radii)
  - class: Table 5.2 internal parts c = h - 3t / b - 3t; CHS d/t limits 50/70/90 eps^2
  - shear area 6.2.6(3) f/g; reduced moments 6.2.9.1 (6.39)/(6.40), CHS Mpl (1 - n^1.7)
  - biaxial exponent 6.2.9.1(6): RHS alpha = beta = 1.66/(1 - 1.13 n^2) <= 6, CHS 2
  - closed sections are not susceptible to torsional deformation: no torsional buckling, Annex B kzy = 0.6 kyy
  - SHS/CHS: chi,LT = 1; RHS: Mcr with Iw = 0 (practically chi,LT = 1)
Also added: torsion with shear 6.2.7(9) (6.26)/(6.28) using the St Venant shear stress (warping ignored).

Units in: forces kN, moments kNm, lengths m (member) / mm (section). Compression is NEGATIVE in N (as SOFiSTiK
and the spreadsheet).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import sections_lib as SL

CODE_NAME = "EN 1993-1-1:2005+AC:2009"

E = 210000.0
G = 80770.0          # as the spreadsheet / SN003b (EN gives 81000: 0.1 % on Mcr)

# EN 1993-1-1 Table 3.1 (t <= 40 / 40 < t <= 80)
FY_TABLE31 = {"S235": (235, 215), "S275": (275, 255), "S355": (355, 335), "S460": (460, 430)}
# EN 10025-2 Table 7 steps t<=16, <=40, <=63, <=80, <=100 (S460: EN 10025-4)
FY_PRODUCT = {"S235": (235, 225, 215, 215, 215), "S275": (275, 265, 255, 245, 235),
              "S355": (355, 345, 335, 325, 315), "S460": (460, 440, 430, 410, 400)}

ALPHA = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}

# SN003b Table 3.1 (end moments, k = 1)
C1_TABLE = ((1, 1.00), (0.75, 1.14), (0.5, 1.31), (0.25, 1.52), (0, 1.77), (-0.25, 2.05),
            (-0.5, 2.33), (-0.75, 2.57), (-1, 2.55))
# (shape, support) -> C1, C2, Cm (Table B.3), pi2EId/(L2M) (Table A.2), kc (Table 6.6)   -- spreadsheet sheet C1C2
SHAPE_TABLE = {
    ("Parabolic", "Pinned/Pinned"): (1.127, 0.454, 0.95, 1.0281, 0.94),
    ("Parabolic", "Fixed/Fixed"): (2.578, 1.554, 0.50, 0.3084, 0.90),
    ("Parabolic", "Fixed/Pinned"): (2.23, 0.89, 0.55, 0.4268, 0.91),
    ("Triangular", "Pinned/Pinned"): (1.348, 0.630, 0.90, 0.8225, 0.86),
    ("Triangular", "Fixed/Fixed"): (1.683, 1.645, 0.80, 0.4112, 0.77),
    ("Triangular", "Fixed/Pinned"): (1.78, 1.02, 0.6667, 0.4904, 0.82),
}


@dataclass
class Settings:
    """National Annex and method choices.  Defaults = UK NA, as the spreadsheet's 'UK' preset and the 26016 BDK run."""
    na: str = "UK"                       # "UK" or "CEN"
    gM0: float = 1.0
    gM1: float = 1.0
    eta: float | None = None             # None = preset (UK 1.0, CEN 1.2 up to S460)
    ltb_method: str = "Rolled/welded 6.3.2.3"   # or "General 6.3.2.2"
    lam0: float | None = None            # None = preset (0.4 rolled; UK welded 0.2)
    beta: float | None = None            # None = preset (0.75 rolled; UK welded 1.0)
    f_method: str | None = None          # None = preset (UK 1/sqrt(C1), CEN Table 6.6); or "f = 1"
    interaction: str = "Annex B"         # "Annex A", "Annex B", "Both (worst)", "Any (best)"
    fy_rule: str = "Table 3.1"           # or "Product standard"


@dataclass
class SectionData:
    """A cross-section.  kind = 'I', 'RHS' or 'CHS'.  dims in mm."""
    name: str
    kind: str
    dims: dict
    fabrication: str = "rolled"          # 'rolled' / 'welded' for I, 'hot_finished' / 'cold_formed' for hollow
    props: dict = field(default_factory=dict)

    @classmethod
    def from_name(cls, name: str, fabrication: str | None = None) -> "SectionData":
        d = SL.from_name(name, fabrication)
        if d is None:
            raise ValueError(f"unknown section {name!r}")
        dims = d["dims"]
        if "tw" in dims:
            kind = "I"
        elif "d" in dims:
            kind = "CHS"
        else:
            kind = "RHS"
        s = cls(d["name"], kind, dims, d.get("fabrication") or ("rolled" if kind == "I" else "hot_finished"))
        s.props = section_props(s)
        return s


def section_props(s: SectionData) -> dict:
    d = s.dims
    if s.kind == "I":
        # spreadsheet sheet 'Calc' section 2 (thin-walled It and Iw as eurocodeapplied.com)
        h, b, tw, tf, r = d["h"], d["b"], d["tw"], d["tf"], d.get("r", 0.0)
        hw = h - 2 * tf
        A = 2 * b * tf + hw * tw + (4 - math.pi) * r ** 2
        Iy = (b * h ** 3 - (b - tw) * hw ** 3) / 12 + 0.03 * r ** 4 + 0.2146 * r ** 2 * (hw - 0.4468 * r) ** 2
        Iz = (2 * tf * b ** 3 + hw * tw ** 3) / 12 + 0.03 * r ** 4 + 0.2146 * r ** 2 * (tw + 0.4468 * r) ** 2
        Wply = b * tf * (h - tf) + tw * hw ** 2 / 4 + 0.4292 * r ** 2 * (hw - 0.4468 * r)
        Wplz = b ** 2 * tf / 2 + hw * tw ** 2 / 4 + 0.4292 * r ** 2 * (tw + 0.4468 * r)
        It = (2 * b * tf ** 3 + (h - tf) * tw ** 3) / 3
        Iw = tf * b ** 3 * (h - tf) ** 2 / 24
        return dict(h=h, b=b, tw=tw, tf=tf, r=r, hw=hw, A=A, Iy=Iy, Iz=Iz, Wely=2 * Iy / h, Welz=2 * Iz / b,
                    Wply=Wply, Wplz=Wplz, It=It, Iw=Iw, Wt=It / max(tw, tf), tmax=max(tf, tw))
    if s.kind == "RHS":
        p = SL.props_RHS(d["h"], d["b"], d["t"], fabrication=s.fabrication)
        return dict(h=d["h"], b=d["b"], t=d["t"], A=p["A"], Iy=p["Iy"], Iz=p["Iz"], Wely=p["Wel_y"], Welz=p["Wel_z"],
                    Wply=p["Wpl_y"], Wplz=p["Wpl_z"], It=p["It"], Iw=0.0, Wt=p["Wt"], tmax=d["t"],
                    Avz=p["Avz"], Avy=p["Avy"])
    p = SL.props_CHS(d["d"], d["t"])
    return dict(d=d["d"], t=d["t"], h=d["d"], b=d["d"], A=p["A"], Iy=p["Iy"], Iz=p["Iz"], Wely=p["Wel_y"],
                Welz=p["Wel_z"], Wply=p["Wpl_y"], Wplz=p["Wpl_z"], It=p["It"], Iw=0.0, Wt=p["Wt"], tmax=d["t"],
                Avz=p["Avz"], Avy=p["Avy"])


def fy_of(grade: str, t: float, rule: str = "Table 3.1", fy_custom: float | None = None) -> float:
    if grade == "Custom":
        return float(fy_custom)
    if rule == "Table 3.1":
        a, b = FY_TABLE31[grade]
        return a if t <= 40 else b
    steps = FY_PRODUCT[grade]
    for lim, v in zip((16, 40, 63, 80, 100), steps):
        if t <= lim:
            return v
    return steps[-1]


def chi_curve(lam: float, alpha: float) -> float:
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam ** 2)
    return min(1.0, 1 / (phi + math.sqrt(max(phi ** 2 - lam ** 2, 0.0))))


def c1_linear(psi: float) -> float:
    """SN003b Table 3.1 by linear interpolation (spreadsheet C1lin_)."""
    p = max(-1.0, min(1.0, psi))
    i = min(7, int((1 - p) / 0.25))
    c_a, c_b = C1_TABLE[i][1], C1_TABLE[i + 1][1]
    return c_a + ((1 - p) / 0.25 - i) * (c_b - c_a)


def shape_factors(shape: str, psi: float, support: str = "Pinned/Pinned") -> dict:
    """Spreadsheet input route: a named moment diagram -> C1, C2, Cm (B.3), Cm0 data (A.2), kc (Table 6.6)."""
    p = max(-1.0, min(1.0, psi))
    if shape == "Uniform":
        return dict(C1=1.0, C2=0.0, CmB=1.0, kc=1.0, A2=None, shape=shape, psi=1.0)
    if shape == "Linear":
        return dict(C1=c1_linear(p), C2=0.0, CmB=max(0.4, 0.6 + 0.4 * p), kc=1 / (1.33 - 0.33 * p), A2=None,
                    shape=shape, psi=p)
    C1, C2, Cm, a2, kc = SHAPE_TABLE[(shape, support)]
    return dict(C1=C1, C2=C2, CmB=Cm, kc=kc, A2=a2, shape=shape, psi=p)


# ---------------------------------------------------------------------------------------------------------------
# Moment diagram -> factors (automatic route used for SOFiSTiK members)
# ---------------------------------------------------------------------------------------------------------------

def _interp(s, m, x):
    for i in range(len(s) - 1):
        if s[i] <= x <= s[i + 1]:
            if s[i + 1] == s[i]:
                return m[i + 1]
            return m[i] + (m[i + 1] - m[i]) * (x - s[i]) / (s[i + 1] - s[i])
    return m[-1] if x >= s[-1] else m[0]


def diagram_factors(s: list, m: list) -> dict:
    """Factors from a real moment diagram (positions s in m, moments m in kNm) over one buckling length.

    C1   Kirby & Nethercot (1979) / AISC Cb = 12.5 Mmax / (2.5 Mmax + 3 MA + 4 MB + 3 MC), quarter points, <= 2.5
         (within about 1 % of SN003b for uniform, linear psi = 0 and UDL; conservative for psi = -1 and point loads)
    Cm   EN 1993-1-1 Table B.3, UDL column (the larger of the two columns in every row).  Ms = the largest interior
         turning point of the diagram (where the shear changes sign); a diagram without one (monotonic between the
         ends) uses row 1 with psi = ratio of the end moments (0.6 + 0.4 psi >= 0.4)
    kc   Table 6.6 is not used for real diagrams: the f-factor takes kc = 1/sqrt(C1) (UK NA), or Table 6.6 'linear'
         kc = 1/(1.33 - 0.33 psi) when the diagram is a straight line (CEN).
    """
    L0, L1 = s[0], s[-1]
    L = L1 - L0
    mabs = max(abs(v) for v in m) if m else 0.0
    if L <= 0 or mabs < 1e-9:
        return dict(C1=1.0, C2=0.0, CmB=1.0, kc=1.0, psi=1.0, linear=True, Ms=0.0, Mh=0.0)
    MA, MB, MC = (abs(_interp(s, m, L0 + f * L)) for f in (0.25, 0.5, 0.75))
    C1 = min(2.5, 12.5 * mabs / (2.5 * mabs + 3 * MA + 4 * MB + 3 * MC))
    ma, mb = m[0], m[-1]
    if abs(ma) >= abs(mb):
        Mh, Mo = ma, mb
    else:
        Mh, Mo = mb, ma
    psi = Mo / Mh if abs(Mh) > 1e-9 else 1.0
    psi = max(-1.0, min(1.0, psi))
    # span moment Ms = the largest interior local extremum (a point where the diagram turns, i.e. V changes sign);
    # none = the diagram is monotonic between the ends and Table B.3 row 1 (end moments only) applies
    pts = []
    for x, v in zip(s, m):
        if pts and abs(x - pts[-1][0]) < 1e-6:
            continue
        pts.append((x, v))
    ext = [pts[i][1] for i in range(1, len(pts) - 1)
           if (pts[i][1] - pts[i - 1][1]) * (pts[i + 1][1] - pts[i][1]) < 0
           and abs(pts[i][1] - (ma + (mb - ma) * (pts[i][0] - L0) / L)) > 0.02 * mabs]
    linear = not ext
    if linear:
        Cm = max(0.4, 0.6 + 0.4 * psi)
        Ms = 0.5 * (ma + mb)
        kc = 1 / (1.33 - 0.33 * psi)
    else:
        Ms = max(ext, key=abs)
        if abs(Mh) >= abs(Ms) and abs(Mh) > 1e-9:
            a_s = Ms / Mh
            if a_s >= 0:
                Cm = max(0.4, 0.2 + 0.8 * a_s)
            elif psi >= 0:
                Cm = max(0.4, 0.1 - 0.8 * a_s)
            else:
                Cm = max(0.4, 0.1 * (1 - psi) - 0.8 * a_s)
        else:
            a_h = Mh / Ms if abs(Ms) > 1e-9 else 0.0
            if a_h >= 0 or psi >= 0:
                Cm = 0.95 + 0.05 * a_h
            else:
                Cm = 0.95 + 0.05 * a_h * (1 + 2 * psi)
        kc = None
    return dict(C1=C1, C2=0.0, CmB=min(1.0, Cm), kc=kc, psi=psi, linear=linear, Ms=Ms, Mh=Mh)


# ---------------------------------------------------------------------------------------------------------------
# The check itself
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Demand:
    """Design forces for one check.  N compression negative.  Moments are the governing |values| over the
    buckling length for the member checks, or the concurrent values at one station for the section checks."""
    N: float = 0.0
    Vy: float = 0.0
    Vz: float = 0.0
    My: float = 0.0
    Mz: float = 0.0
    Mt: float = 0.0


@dataclass
class Buckling:
    """Buckling lengths in m and the moment-diagram factors (from shape_factors or diagram_factors)."""
    L: float = 1.0               # member length (m), used for torsional buckling L_T = kT L
    Lcr_y: float = 1.0
    Lcr_z: float = 1.0
    L_LT: float = 1.0
    kT: float = 1.0
    fy_y: dict | None = None     # factors for the My diagram over Lcr_y (Cmy)
    fz: dict | None = None       # factors for the Mz diagram over Lcr_z (Cmz)
    fLT: dict | None = None      # factors for the My diagram over L_LT (C1, C2, CmLT, kc)
    zg: float = 0.0              # load height above the shear centre (mm), + = destabilising
    torsion_susceptible: bool | None = None   # None = by section type (I: yes, closed: no)
    Mcr: float | None = None     # kNm: elastic critical moment from elsewhere (ltb.mcr_eigen); None = SN003b with C1


def check(sec: SectionData, grade: str, dem: Demand, bk: Buckling, st: Settings | None = None,
          fy_custom: float | None = None, section_only: bool = False) -> dict:
    """Run every EN 1993-1-1 check.  Returns a dict of named intermediate values (spreadsheet names) and
    'checks': list of (label, clause, utilisation)."""
    st = st or Settings()
    p = sec.props
    v: dict = {}
    hollow = sec.kind != "I"
    tors = bk.torsion_susceptible if bk.torsion_susceptible is not None else (sec.kind == "I")
    rolled = sec.fabrication in ("rolled", "hot_finished")
    A, Iy, Iz, It, Iw = p["A"], p["Iy"], p["Iz"], p["It"], p["Iw"]
    h, b = p["h"], p["b"]
    # --- 1 NDPs
    fy = fy_of(grade, p["tmax"], st.fy_rule, fy_custom)
    eps = math.sqrt(235 / fy)
    eta = st.eta if st.eta is not None else (1.0 if st.na == "UK" else (1.2 if fy <= 460 else 1.0))
    gM0, gM1 = st.gM0, st.gM1
    v.update(fy_=fy, eps_=eps, eta_=eta, gM0_=gM0, gM1_=gM1)
    # --- 4 forces
    NEd = dem.N
    Nc, Nt = max(-NEd, 0.0), max(NEd, 0.0)
    My, Mz = abs(dem.My), abs(dem.Mz)
    v.update(Nc_=Nc, Nt_=Nt, My_=My, Mz_=Mz)
    # --- 2 shear areas
    if sec.kind == "I":
        tw, tf, r, hw = p["tw"], p["tf"], p["r"], p["hw"]
        Avz = max(A - 2 * b * tf + (tw + 2 * r) * tf if rolled else eta * hw * tw, eta * hw * tw)
        Avy = 2 * b * tf if rolled else A - hw * tw
    else:
        Avz, Avy = p["Avz"], p["Avy"]
    v.update(A_=A, Iy_=Iy, Iz_=Iz, Wely_=p["Wely"], Welz_=p["Welz"], Wply_=p["Wply"], Wplz_=p["Wplz"], It_=It,
             Iw_=Iw, Avz_=Avz, Avy_=Avy)
    # --- 5 classification under N + My
    if sec.kind == "I":
        cf = (b - tw - 2 * r) / 2
        clf = 1 if cf / tf <= 9 * eps else 2 if cf / tf <= 10 * eps else 3 if cf / tf <= 14 * eps else 4
        cw, tweb = hw - 2 * r, tw
        Ny_part = A
    elif sec.kind == "RHS":
        t = p["t"]
        cf = b - 3 * t                     # HOLLOW: internal compression part (flange), uniform compression
        clf = 1 if cf / t <= 33 * eps else 2 if cf / t <= 38 * eps else 3 if cf / t <= 42 * eps else 4
        cw, tweb = h - 3 * t, 2 * t        # HOLLOW: two webs carry the axial force for alpha
    else:
        clf = None
    if sec.kind == "CHS":
        dt = p["d"] / p["t"]
        cls_c = 1 if dt <= 50 * eps ** 2 else 2 if dt <= 70 * eps ** 2 else 3 if dt <= 90 * eps ** 2 else 4
        v.update(clf_=cls_c, clw_=cls_c)
    else:
        t1 = tweb if sec.kind == "I" else p["t"]
        if My == 0:
            alw = 1 if Nc - Nt > 0 else 0.5
        else:
            alw = min(1.0, max(0.0, (cw / 2 + (Nc - Nt) * 1000 / (2 * tweb * fy)) / cw))
        s1 = (Nc - Nt) * 1000 / A + My * 1e6 * cw / (2 * Iy)
        s2 = (Nc - Nt) * 1000 / A - My * 1e6 * cw / (2 * Iy)
        psw = 1 if s1 <= 0 else s2 / s1
        if sec.kind == "I":
            lw1 = 396 * eps / (13 * alw - 1) if alw > 0.5 else 36 * eps / max(alw, 1e-6)
            lw2 = 456 * eps / (13 * alw - 1) if alw > 0.5 else 41.5 * eps / max(alw, 1e-6)
            lw3 = 42 * eps / (0.67 + 0.33 * psw) if psw > -1 else 62 * eps * (1 - psw) * math.sqrt(-psw)
        else:   # same Table 5.2 sheet 1 limits for internal parts
            lw1 = 396 * eps / (13 * alw - 1) if alw > 0.5 else 36 * eps / max(alw, 1e-6)
            lw2 = 456 * eps / (13 * alw - 1) if alw > 0.5 else 41.5 * eps / max(alw, 1e-6)
            lw3 = 42 * eps / (0.67 + 0.33 * psw) if psw > -1 else 62 * eps * (1 - psw) * math.sqrt(-psw)
        cwt = cw / t1
        clw = 1 if (s1 <= 0 or alw <= 0) else 1 if cwt <= lw1 else 2 if cwt <= lw2 else 3 if cwt <= lw3 else 4
        cls_c = max(clf, clw)
        v.update(alw_=alw, psw_=psw, clf_=clf, clw_=clw)
    cls = cls_c
    v["cls_"] = cls
    Wy = p["Wply"] if cls <= 2 else p["Wely"]
    Wz = p["Wplz"] if cls <= 2 else p["Welz"]
    v.update(Wy_=Wy, Wz_=Wz)
    # --- 6 cross-section resistance
    Npl = A * fy / gM0 / 1000
    Vplz = Avz * fy / math.sqrt(3) / gM0 / 1000
    Vply = Avy * fy / math.sqrt(3) / gM0 / 1000
    # torsion with shear 6.2.7(9): St Venant shear stress (warping not included)
    tau_t = abs(dem.Mt) * 1e6 / p["Wt"] if p.get("Wt") else 0.0
    tau_rd = fy / math.sqrt(3) / gM0
    if sec.kind == "I":
        red = math.sqrt(max(0.0, 1 - tau_t / (1.25 * tau_rd)))          # (6.26)
    else:
        red = max(0.0, 1 - tau_t / tau_rd)                                # (6.28)
    VplzT, VplyT = Vplz * red, Vply * red
    uVz = abs(dem.Vz) / VplzT if VplzT > 0 else 9.99
    uVy = abs(dem.Vy) / VplyT if VplyT > 0 else 9.99
    rhoz = 0 if uVz <= 0.5 else (2 * uVz - 1) ** 2
    rhoy = 0 if uVy <= 0.5 else (2 * uVy - 1) ** 2
    Mcy = Wy * fy / gM0 / 1e6
    Mcz = Wz * fy / gM0 / 1e6
    if sec.kind == "I":
        MyV = min(Mcy, (p["Wply"] - rhoz * hw ** 2 * tw / 4 if cls <= 2 else p["Wely"] - rhoz * tw * hw ** 2 / 6)
                  * fy / gM0 / 1e6)
        MzV = min(Mcz, (p["Wplz"] - rhoy * tf * b ** 2 / 2 if cls <= 2 else p["Welz"] - rhoy * tf * b ** 2 / 3)
                  * fy / gM0 / 1e6)
    else:   # HOLLOW: conservative (1 - rho) on the whole modulus
        MyV, MzV = Mcy * (1 - rhoz), Mcz * (1 - rhoy)
    uMy = My / MyV if MyV > 0 else 9.99
    uMz = Mz / MzV if MzV > 0 else 9.99
    n = abs(NEd) / Npl
    if sec.kind == "I":
        aw = min((A - 2 * b * tf) / A, 0.5)
        if cls <= 2:
            if abs(NEd) <= 0.25 * Npl and abs(NEd) <= 0.5 * hw * tw * fy / gM0 / 1000:
                MNy = MyV
            else:
                MNy = min(MyV, MyV * (1 - n) / (1 - 0.5 * aw))
            if abs(NEd) <= hw * tw * fy / gM0 / 1000 or n <= aw:
                MNz = MzV
            else:
                MNz = MzV * (1 - ((n - aw) / (1 - aw)) ** 2)
        else:
            MNy, MNz = MyV, MzV
        bet = max(5 * n, 1)
        alp = 2.0
    elif sec.kind == "RHS":
        t = p["t"]
        aw = min((A - 2 * b * t) / A, 0.5)
        af = min((A - 2 * h * t) / A, 0.5)
        MNy = min(MyV, MyV * (1 - n) / (1 - 0.5 * aw)) if cls <= 2 else MyV
        MNz = min(MzV, MzV * (1 - n) / (1 - 0.5 * af)) if cls <= 2 else MzV
        alp = bet = min(6.0, 1.66 / (1 - 1.13 * n ** 2)) if n < 0.94 else 6.0
    else:
        aw = 0.0
        MNy = MyV * (1 - min(n, 1) ** 1.7) if cls <= 2 else MyV
        MNz = MzV * (1 - min(n, 1) ** 1.7) if cls <= 2 else MzV
        alp = bet = 2.0
    if cls <= 2:
        if sec.kind == "CHS":       # resultant moment for a circular section
            uNM = math.hypot(My, Mz) / MNy if MNy > 0 else 9.99
        else:
            uNM = ((My / MNy) ** alp if MNy > 0 else 9.99) + ((Mz / MNz) ** bet if MNz > 0 else 9.99)
    else:
        uNM = n + My / MyV + Mz / MzV
    v.update(Npl_=Npl, uN_=abs(NEd) / Npl, Vplz_=Vplz, Vply_=Vply, uVz_=uVz, uVy_=uVy, rhoz_=rhoz, rhoy_=rhoy,
             Mcy_=Mcy, Mcz_=Mcz, MyV_=MyV, MzV_=MzV, uMy_=uMy, uMz_=uMz, nN_=n, aw_=aw, MNy_=MNy, MNz_=MNz,
             bet_=bet, uNM_=uNM, tau_t=tau_t, uT_=tau_t / tau_rd)
    checks = [("Axial force", "6.2.3/6.2.4", abs(NEd) / Npl),
              ("Shear Vz" + (" + torsion" if dem.Mt else ""), "6.2.6/6.2.7", uVz),
              ("Shear Vy" + (" + torsion" if dem.Mt else ""), "6.2.6/6.2.7", uVy),
              ("Bending My (with shear)", "6.2.5/6.2.8", uMy),
              ("Bending Mz (with shear)", "6.2.5/6.2.8", uMz),
              ("Bending + axial (biaxial)", "6.2.9", uNM)]
    if section_only:
        if cls == 4:   # effective section (6.2.2.5, EN 1993-1-5) not implemented: flag, never pass silently
            checks.append(("Class 4 section: effective properties not implemented, check by hand", "6.2.2.5", 9.99))
        v["checks"] = checks
        return v
    # --- 7 flexural buckling 6.3.1
    if sec.kind == "I":
        hb = h / b
        s460 = grade == "S460"
        if not rolled:
            cvy, cvz = ("b", "c") if tf <= 40 else ("c", "d")
        elif hb > 1.2:
            cvy = ("a0" if s460 else "a") if tf <= 40 else ("a" if s460 else "b")
            cvz = ("a0" if s460 else "b") if tf <= 40 else ("a" if s460 else "c")
        else:
            cvy = ("a" if s460 else "b") if tf <= 100 else ("c" if s460 else "d")
            cvz = ("a" if s460 else "c") if tf <= 100 else ("c" if s460 else "d")
    else:   # HOLLOW Table 6.2: hot finished a (S460 a0), cold formed c
        cvy = cvz = ("a0" if grade == "S460" else "a") if sec.fabrication == "hot_finished" else "c"
    out = {}
    for ax, I, Lcr in (("y", Iy, bk.Lcr_y), ("z", Iz, bk.Lcr_z)):
        Lmm = Lcr * 1000
        Ncr = math.pi ** 2 * E * I / Lmm ** 2 / 1000
        lam = math.sqrt(A * fy / (Ncr * 1000))
        chi = chi_curve(lam, ALPHA[cvy if ax == "y" else cvz])
        Nb = chi * A * fy / gM1 / 1000
        out[ax] = (Ncr, lam, chi, Nb)
        v.update({f"Lcr{ax}_": Lmm, f"Ncr{ax}_": Ncr, f"lam{ax}_": lam, f"chi{ax}_": chi, f"Nb{ax}_": Nb,
                  f"uNb{ax}_": Nc / Nb, f"cv{ax}_": cvy if ax == "y" else cvz})
    Ncry, lamy, chiy, Nby = out["y"]
    Ncrz, lamz, chiz, Nbz = out["z"]
    # torsional buckling (doubly symmetric; closed sections are not susceptible)
    LT = bk.kT * bk.L * 1000
    i0s = (Iy + Iz) / A
    NcrT = (G * It + math.pi ** 2 * E * Iw / LT ** 2) / i0s / 1000
    lamT = math.sqrt(A * fy / (NcrT * 1000))
    chiT = chi_curve(lamT, ALPHA[cvz])
    NbT = chiT * A * fy / gM1 / 1000
    v.update(NcrT_=NcrT, lamT_=lamT, chiT_=chiT, NbT_=NbT, uNbT_=Nc / NbT if tors else 0.0)
    # --- 8 LTB with Mcr from SN003b
    fLT = bk.fLT or dict(C1=1.0, C2=0.0, CmB=1.0, kc=1.0, psi=1.0, shape="Uniform")
    C1, C2 = fLT["C1"], fLT.get("C2", 0.0)
    LLT = bk.L_LT * 1000
    zg = bk.zg
    NcrzLT = math.pi ** 2 * E * Iz / LLT ** 2
    Mcr = C1 * NcrzLT * (math.sqrt(Iw / Iz + G * It / NcrzLT + (C2 * zg) ** 2) - C2 * zg) / 1e6
    if bk.Mcr is not None:
        Mcr = bk.Mcr
    lamLT = math.sqrt(Wy * fy / (Mcr * 1e6))
    gen = st.ltb_method.startswith("General")
    hb = h / b
    if gen:
        cvLT = ("a" if hb <= 2 else "b") if rolled else ("c" if hb <= 2 else "d")
        lam0, bLT = 0.2, 1.0
    else:
        if rolled:
            cvLT = "b" if hb <= 2 else ("d" if (st.na == "UK" and hb > 3.1) else "c")
        else:
            cvLT = "c" if hb <= 2 else "d"
        lam0 = st.lam0 if st.lam0 is not None else (0.2 if (st.na == "UK" and not rolled) else 0.4)
        bLT = st.beta if st.beta is not None else (1.0 if (st.na == "UK" and not rolled) else 0.75)
    aLT = ALPHA[cvLT]
    PhiLT = 0.5 * (1 + aLT * (lamLT - lam0) + bLT * lamLT ** 2)
    chiLT0 = min(1.0, 1.0 if gen else 1 / lamLT ** 2, 1 / (PhiLT + math.sqrt(max(PhiLT ** 2 - bLT * lamLT ** 2, 0))))
    fm = st.f_method or ("1/sqrt(C1)" if st.na == "UK" else "Table 6.6")
    if fm == "1/sqrt(C1)" or fLT.get("kc") is None:
        kc = 1 / math.sqrt(C1)
    else:
        kc = fLT["kc"]
    ff = 1.0 if (gen or fm == "f = 1") else min(1.0, 1 - 0.5 * (1 - kc) * (1 - 2 * (lamLT - 0.8) ** 2))
    no_ltb = (not tors) and sec.kind != "RHS"        # SHS / CHS and continuously restrained members
    if sec.kind == "RHS" and abs(h - b) < 1e-6:
        no_ltb = True
    chiLT = 1.0 if (no_ltb or (bk.torsion_susceptible is False and sec.kind == "I")) else \
        min(1.0, 1.0 if gen else 1 / lamLT ** 2, chiLT0 / ff)
    Mb = chiLT * Wy * fy / gM1 / 1e6
    v.update(LLT_=LLT, zg_=zg, Cfac1_=C1, Cfac2_=C2, Mcr_=Mcr, lamLT_=lamLT, cvLT_=cvLT, aLTi_=aLT, lam0_=lam0,
             bLTi_=bLT, PhiLT_=PhiLT, chiLT0_=chiLT0, kc_=kc, ff_=ff, chiLT_=chiLT, Mb_=Mb, uLT_=My / Mb)
    # --- 9 Annex B
    fy_d = bk.fy_y or dict(CmB=1.0)
    fz_d = bk.fz or dict(CmB=1.0)
    CmyB, CmzB, CmLTB = fy_d["CmB"], fz_d["CmB"], fLT["CmB"]
    ny, nz = Nc / Nby, Nc / Nbz
    if cls <= 2:
        kyyB = min(CmyB * (1 + (lamy - 0.2) * ny), CmyB * (1 + 0.8 * ny))
        kzzB = min(CmzB * (1 + (2 * lamz - 0.6) * nz), CmzB * (1 + 1.4 * nz)) if not hollow else \
            min(CmzB * (1 + (lamz - 0.2) * nz), CmzB * (1 + 0.8 * nz))      # HOLLOW: Table B.1 RHS row
        kyzB = 0.6 * kzzB
    else:
        kyyB = min(CmyB * (1 + 0.6 * lamy * ny), CmyB * (1 + 0.6 * ny))
        kzzB = min(CmzB * (1 + 0.6 * lamz * nz), CmzB * (1 + 0.6 * nz))
        kyzB = kzzB
    if not tors:
        kzyB = (0.6 if cls <= 2 else 0.8) * kyyB
    elif cls <= 2:
        if lamz < 0.4:
            kzyB = min(0.6 + lamz, 1 - 0.1 * lamz * nz / (CmLTB - 0.25))
        else:
            kzyB = max(1 - 0.1 * lamz * nz / (CmLTB - 0.25), 1 - 0.1 * nz / (CmLTB - 0.25))
    else:
        kzyB = max(1 - 0.05 * lamz * nz / (CmLTB - 0.25), 1 - 0.05 * nz / (CmLTB - 0.25))
    v.update(CmyB_=CmyB, CmzB_=CmzB, CmLTB_=CmLTB, ny_=ny, nz_=nz, kyyB_=kyyB, kzzB_=kzzB, kyzB_=kyzB, kzyB_=kzyB)
    MzR1 = Wz * fy / gM1 / 1e6
    u61B = Nc / Nby + kyyB * My / Mb + kyzB * Mz / MzR1
    u62B = Nc / Nbz + kzyB * My / Mb + kzzB * Mz / MzR1
    v.update(MzR1_=MzR1, u61B_=u61B, u62B_=u62B, uB_=max(u61B, u62B))
    # --- 10 Annex A (needs Cm,0 data: available for the spreadsheet shapes; for real diagrams see annex_a_cm0)
    if st.interaction != "Annex B":
        _annex_a(v, sec, p, bk, fLT, fy_d, fz_d, tors, cls, Nc, My, Mz, Ncry, Ncrz, NcrT, chiy, chiz, chiLT, lamz,
                 lamy, Wy, fy, gM0, gM1, C1, Iz, Iw, It)
        u61A, u62A = v["u61A_"], v["u62A_"]
        uA, uB = max(u61A, u62A), max(u61B, u62B)
        if st.interaction == "Annex A":
            u61, u62 = u61A, u62A
        elif st.interaction.startswith("Any"):
            u61, u62 = (u61A, u62A) if uA <= uB else (u61B, u62B)
        else:
            u61, u62 = max(u61A, u61B), max(u62A, u62B)
    else:
        u61, u62 = u61B, u62B
    v.update(u61_=u61, u62_=u62)
    checks += [("Flexural buckling y-y", "6.3.1", Nc / Nby),
               ("Flexural buckling z-z", "6.3.1", Nc / Nbz),
               ("Torsional buckling", "6.3.1.4", Nc / NbT if tors else 0.0),
               ("Lateral-torsional buckling", "6.3.2", My / Mb),
               ("Bending + compression, eq. 6.61", "6.3.3", u61),
               ("Bending + compression, eq. 6.62", "6.3.3", u62)]
    v["checks"] = checks
    return v


def _annex_a(v, sec, p, bk, fLT, fy_d, fz_d, tors, cls, Nc, My, Mz, Ncry, Ncrz, NcrT, chiy, chiz, chiLT, lamz,
             lamy, Wy, fy, gM0, gM1, C1, Iz, Iw, It):
    A, Iy = p["A"], p["Iy"]
    if Nc >= 0.999 * min(Ncry, Ncrz, NcrT):      # spreadsheet gives #NUM here: report as a failure
        v.update(u61A_=99.0, u62A_=99.0)
        return
    npl = Nc / (A * fy / gM1 / 1000)
    wy = min(1.5, p["Wply"] / p["Wely"])
    wz = min(1.5, p["Wplz"] / p["Welz"])
    aLT = max(0.0, 1 - It / Iy)
    LLT = bk.L_LT * 1000
    NcrzLT = math.pi ** 2 * E * Iz / LLT ** 2
    Mcr0 = NcrzLT * math.sqrt(Iw / Iz + G * It / NcrzLT) / 1e6
    lam0A = math.sqrt(Wy * fy / (Mcr0 * 1e6)) if tors else 0.0
    lim0 = 0.2 * math.sqrt(C1) * ((1 - Nc / Ncrz) * (1 - Nc / NcrT)) ** 0.25

    def cm0(fd, Ncr):
        shape = fd.get("shape")
        if shape == "Uniform":
            return 1 + 0.36 * 0.67 * Nc / Ncr
        if shape == "Linear" or fd.get("linear"):
            ps = max(-1.0, min(1.0, fd.get("psi", 1.0)))
            return 0.79 + 0.21 * ps + 0.36 * (ps - 0.33) * Nc / Ncr
        a2 = fd.get("A2")
        if a2 is None:          # real non-linear diagram: pinned-UDL value (Table A.2), noted in the docs
            a2 = 1.0281
        return 1 + (a2 - 1) * Nc / Ncr

    Cmy0, Cmz0 = cm0(fy_d, Ncry), cm0(fz_d, Ncrz)
    epy = My * 1e6 / (Nc * 1000) * A / p["Wely"] if Nc > 0 else 1e9
    CmyA = Cmy0 if lam0A <= lim0 else Cmy0 + (1 - Cmy0) * math.sqrt(epy) * aLT / (1 + math.sqrt(epy) * aLT)
    CmzA = Cmz0
    CmLTA = 1.0 if lam0A <= lim0 else max(1.0, CmyA ** 2 * aLT / math.sqrt((1 - Nc / Ncrz) * (1 - Nc / NcrT)))
    muy = (1 - Nc / Ncry) / (1 - chiy * Nc / Ncry)
    muz = (1 - Nc / Ncrz) / (1 - chiz * Nc / Ncrz)
    lmax = max(lamy, lamz)
    Mply = p["Wply"] * fy / gM0 / 1e6
    Mplz = p["Wplz"] * fy / gM0 / 1e6
    bLT = 0.5 * aLT * lam0A ** 2 * My / (chiLT * Mply) * Mz / Mplz
    cLT = 10 * aLT * lam0A ** 2 / (5 + lamz ** 4) * My / (CmyA * chiLT * Mply)
    dLT = 2 * aLT * lam0A / (0.1 + lamz ** 4) * My / (CmyA * chiLT * Mply) * Mz / (CmzA * Mplz)
    eLT = 1.7 * aLT * lam0A / (0.1 + lamz ** 4) * My / (CmyA * chiLT * Mply)
    Cyy = max(p["Wely"] / p["Wply"], 1 + (wy - 1) * ((2 - 1.6 / wy * CmyA ** 2 * lmax - 1.6 / wy * CmyA ** 2 * lmax ** 2) * npl - bLT))
    Cyz = max(0.6 * math.sqrt(wz / wy) * p["Welz"] / p["Wplz"], 1 + (wz - 1) * ((2 - 14 * CmzA ** 2 * lmax ** 2 / wz ** 5) * npl - cLT))
    Czy = max(0.6 * math.sqrt(wy / wz) * p["Wely"] / p["Wply"], 1 + (wy - 1) * ((2 - 14 * CmyA ** 2 * lmax ** 2 / wy ** 5) * npl - dLT))
    Czz = max(p["Welz"] / p["Wplz"], 1 + (wz - 1) * ((2 - 1.6 / wz * CmzA ** 2 * lmax - 1.6 / wz * CmzA ** 2 * lmax ** 2) * npl - eLT))
    c12 = cls <= 2
    kyyA = CmyA * CmLTA * muy / (1 - Nc / Ncry) * (1 / Cyy if c12 else 1)
    kyzA = CmzA * muy / (1 - Nc / Ncrz) * (0.6 * math.sqrt(wz / wy) / Cyz if c12 else 1)
    kzyA = CmyA * CmLTA * muz / (1 - Nc / Ncry) * (0.6 * math.sqrt(wy / wz) / Czy if c12 else 1)
    kzzA = CmzA * muz / (1 - Nc / Ncrz) * (1 / Czz if c12 else 1)
    Mb = v["Mb_"]
    MzR1 = v["MzR1_"]
    Nby, Nbz = v["Nby_"], v["Nbz_"]
    v.update(nplA_=npl, wfy_=wy, wfz_=wz, aLTA_=aLT, Mcr0_=Mcr0, lam0A_=lam0A, lim0_=lim0, Cmy0_=Cmy0, Cmz0_=Cmz0,
             epy_=epy, CmyA_=CmyA, CmzA_=CmzA, CmLTA_=CmLTA, muy_=muy, muz_=muz, Cyy_=Cyy, Cyz_=Cyz, Czy_=Czy,
             Czz_=Czz, kyyA_=kyyA, kyzA_=kyzA, kzyA_=kzyA, kzzA_=kzzA,
             u61A_=Nc / Nby + kyyA * My / Mb + kyzA * Mz / MzR1, u62A_=Nc / Nbz + kzyA * My / Mb + kzzA * Mz / MzR1)
