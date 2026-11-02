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
        fz = EC.diagram_factors(s, [r[6] for r in seg_rows])
        if d.Ly_mode == "member":
            Ly = member.length
            fy_d = EC.diagram_factors([r[0] for r in member_rows], [r[5] for r in member_rows])
        else:
            Ly = b - a
            fy_d = EC.diagram_factors(s, [r[5] for r in seg_rows])
        # flexural buckling about z: the longest stretch between lateral restraints inside this LTB segment
        Lz = max((min(b, z1) - max(a, z0) for z0, z1 in member.segments("z") if min(b, z1) - max(a, z0) > 1e-6),
                 default=b - a)
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
                "CmzB_", "CmLTB_", "kc_", "kyyB_", "kzyB_", "kzzB_", "kyzB_", "Nby_", "Nbz_", "cls_", "Nc_", "My_", "Mz_")
        det = {k: v[k] for k in keep if k in v}
        det.update(segment=(round(a, 3), round(b, 3)), Mt_max=Mt, Mcr_method="eigen" if bk.Mcr is not None else "C1")
        return [Check(lab, cl, u, det) for lab, cl, u in v["checks"][6:]]
