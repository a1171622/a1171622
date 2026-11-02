"""EN 1993-1-1 plug-in: connects the workflow to the calculation in en1993_1_1.py."""
from __future__ import annotations

from . import en1993_1_1 as EC
from ..ltb import mcr_eigen
from .base import Check, DesignCode


class EN1993(DesignCode):
    name = "EN 1993-1-1 (UK NA)"

    def __init__(self, settings: EC.Settings | None = None):
        self.st = settings or EC.Settings()
        self._sec = {}

    def section(self, sec_name):
        if sec_name not in self._sec:
            self._sec[sec_name] = EC.SectionData.from_name(sec_name)
        return self._sec[sec_name]

    def station_checks(self, sec, grade, N, Vy, Vz, Mt, My, Mz):
        v = EC.check(sec, grade, EC.Demand(N, Vy, Vz, My, Mz, Mt), EC.Buckling(), self.st, section_only=True)
        return [Check(lab, cl, u) for lab, cl, u in v["checks"]]

    def segment_checks(self, sec, grade, member, seg, seg_rows, member_rows):
        d = member.design
        a, b = seg
        seg_rows = _pad(seg_rows, a, b)           # diagram must span the whole length (Mcr, C1, Cm are length based)
        s = [r[0] for r in seg_rows]
        N = min(r[1] for r in seg_rows)                     # most compressive (negative) in the segment
        if N > 0:
            N = 0.0                                         # all tension: no buckling demand from N
        My = max(abs(r[5]) for r in seg_rows)
        Mz = max(abs(r[6]) for r in seg_rows)
        Mt = max(abs(r[4]) for r in seg_rows)
        fLT = EC.diagram_factors(s, [r[5] for r in seg_rows])
        if d.c1_method == "one":
            fLT = dict(fLT, C1=1.0, kc=1.0)
        # Table B.3: Cmz and CmLT between points braced in y-y (the lateral restraints), Cmy between z-z bracing
        # (the member ends here).  Each lateral sub-length is evaluated and the largest factor kept.
        zsubs = [(max(a, z0), min(b, z1)) for z0, z1 in member.segments("z") if min(b, z1) - max(a, z0) > 1e-6] \
            or [(a, b)]
        Lz = max(z1 - z0 for z0, z1 in zsubs)
        fz, cmlt = None, 0.0
        for z0, z1 in zsubs:
            sub = _pad([r for r in seg_rows if z0 - 1e-4 <= r[0] <= z1 + 1e-4], z0, z1)
            ss = [r[0] for r in sub]
            f1 = EC.diagram_factors(ss, [r[6] for r in sub])
            if fz is None or f1["CmB"] > fz["CmB"]:
                fz = f1
            cmlt = max(cmlt, EC.diagram_factors(ss, [r[5] for r in sub])["CmB"])
        fLT = dict(fLT, CmB=cmlt)
        if d.Ly_mode == "member":
            Ly = member.length
            mr = _pad(member_rows, 0.0, member.length)
            fy_d = EC.diagram_factors([r[0] for r in mr], [r[5] for r in mr])
        else:
            Ly = b - a
            fy_d = EC.diagram_factors(s, [r[5] for r in seg_rows])
        if d.sway:
            fy_d = dict(fy_d, CmB=0.9)
            fz = dict(fz, CmB=0.9)
        bk = EC.Buckling(L=b - a, Lcr_y=d.k_y * Ly, Lcr_z=d.k_z * Lz, L_LT=d.k_LT * (b - a), kT=1.0,
                         fy_y=fy_d, fz=fz, fLT=fLT, zg=d.zg_mm,
                         torsion_susceptible=False if d.torsion_restrained else None)
        if d.mcr_method == "eigen" and sec.kind == "I" and abs(d.zg_mm) < 1e-9 and d.c1_method != "one" \
                and d.k_LT == 1.0 and My > 1e-6:
            # lateral-only stations inside this LTB length hold v = 0 at the shear centre (twist free)
            cy = [(p - a, "CY") for p, k, _ in member.restraints if a + 1e-6 < p < b - 1e-6 and "DX" not in k]
            p = sec.props
            bk.Mcr = mcr_eigen([x - a for x in s], [r[5] for r in seg_rows], p["Iz"], p["It"], p["Iw"], cy)[0]
        v = EC.check(sec, grade, EC.Demand(N=N, Vy=0, Vz=0, My=My, Mz=Mz, Mt=0), bk, self.st)
        keep = ("Lcry_", "Lcrz_", "LLT_", "chiy_", "chiz_", "Cfac1_", "Mcr_", "lamLT_", "chiLT_", "Mb_", "CmyB_",
                "CmzB_", "CmLTB_", "kc_", "kyyB_", "kzyB_", "kzzB_", "kyzB_", "Nby_", "Nbz_", "cls_", "Nc_", "My_",
                "Mz_")
        det = {k: v[k] for k in keep if k in v}
        det.update(segment=(round(a, 3), round(b, 3)), Mt_max=Mt, Mcr_method="eigen" if bk.Mcr is not None else "C1")
        return [Check(lab, cl, u, det) for lab, cl, u in v["checks"][6:]]


def _pad(rows, a, b):
    """Rows (s, ...) extended to s = a and s = b with the nearest end values when the first / last station falls
    inside the length (keeps the length right for Mcr, C1 and Cm)."""
    rows = sorted(rows, key=lambda r: r[0])
    if not rows:
        return rows
    if rows[0][0] > a + 1e-3:
        rows = [(a,) + tuple(rows[0][1:])] + rows
    if rows[-1][0] < b - 1e-3:
        rows = rows + [(b,) + tuple(rows[-1][1:])]
    return rows
