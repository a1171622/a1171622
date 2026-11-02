"""Mcr eigen-solver against closed-form / SN003b values.  Run: python3 tests/test_ltb.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memcheck.ltb import mcr_eigen, E, G  # noqa: E402
from memcheck.codes import en1993_1_1 as EC  # noqa: E402

sec = EC.SectionData.from_name("UB 254x146x43")
p = sec.props
Iz, It, Iw = p["Iz"], p["It"], p["Iw"]


def mcr0w(L, Iw_):
    Lm = L * 1000
    Ncr = math.pi ** 2 * E * Iz / Lm ** 2
    return Ncr * math.sqrt(Iw_ / Iz + G * It / Ncr) / 1e6


def mcr0(L):
    Lm = L * 1000
    Ncr = math.pi ** 2 * E * Iz / Lm ** 2
    return Ncr * math.sqrt(Iw / Iz + G * It / Ncr) / 1e6


fails = 0


def chk(name, got, want, tol):
    global fails
    ok = abs(got - want) / want <= tol
    fails += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {name}: {got:.3f} vs {want:.3f} ({(got / want - 1) * 100:+.2f} %)")


L = 4.0
n = 41
xs = [L * i / (n - 1) for i in range(n)]
# uniform moment: exact
chk("uniform, C1", mcr_eigen(xs, [100.0] * n, Iz, It, Iw)[0] / mcr0(L), 1.0, 0.002)
# linear moment: SN003b / ECCS tabulated C1 are the kappa_wt = 0 values (no warping stiffness): 1.31, 1.77, 2.33, 2.55
for psi, want in ((0.5, 1.31), (0.0, 1.77), (-0.5, 2.33), (-1.0, 2.55)):
    chk(f"psi = {psi:+.1f}, C1 at kappa = 0", mcr_eigen(xs, [100 * (1 - (1 - psi) * x / L) for x in xs], Iz, It, 1.0)[0]
        / mcr0w(L, 1.0), want, 0.01)
# with warping stiffness C1 rises (known kappa effect): UB 254 at 4 m gives psi = -1 about 2.72
# UDL, simply supported (SN003b 1.127 at zg = 0)
chk("UDL, C1", mcr_eigen(xs, [400 * x / L * (1 - x / L) for x in xs], Iz, It, Iw)[0] / mcr0(L), 1.127, 0.015)
# central lateral + twist restraint under uniform moment = two spans of L/2
chk("uniform, restraint CY+DX at mid", mcr_eigen(xs, [100.0] * n, Iz, It, Iw, [(L / 2, "CY+DX")])[0], mcr0(L / 2), 0.002)
# lateral-only restraint at the shear centre at mid: between the free case and the full restraint
a = mcr_eigen(xs, [100.0] * n, Iz, It, Iw, [(L / 2, "CY")])[0]
print(f"     uniform, CY only at mid: {a:.1f} kNm (free {mcr0(L):.1f}, CY+DX {mcr0(L / 2):.1f})")
fails += not (mcr0(L) < a <= mcr0(L / 2) * 1.001)
# lateral-only restraint under psi = 0: between free and fully restrained
psi0 = [100 * (1 - x / L) for x in xs]
f0 = mcr_eigen(xs, psi0, Iz, It, Iw)[0]
f1 = mcr_eigen(xs, psi0, Iz, It, Iw, [(L / 2, "CY")])[0]
f2 = mcr_eigen(xs, psi0, Iz, It, Iw, [(L / 2, "CY+DX")])[0]
print(f"     psi = 0, mid restraint: free {f0:.1f}, CY {f1:.1f}, CY+DX {f2:.1f} kNm")
fails += not (f0 < f1 <= f2 * 1.001)
print("ALL OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
