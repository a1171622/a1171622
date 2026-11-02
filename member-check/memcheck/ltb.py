"""Elastic critical moment Mcr by a small finite-element eigenvalue analysis (code independent: EN 1993 uses it as
Mcr, AS 4100 as Mo).  Same idea as LTBeam / SOFiSTiK BDK: the real moment diagram, intermediate restraints.

Thin-walled beam, doubly symmetric section, loads through the shear centre (zg = 0).
Unknowns per node: v (lateral displacement of the shear centre), v', phi (twist), phi' (warping).
Strain energy   U  = 1/2 int( E Iz v''^2 + E Iw phi''^2 + G It phi'^2 ) dx
Second order    V2 = int( M(x) v'' phi ) dx          (M = major-axis moment, linear inside each element)
Mcr = lambda_cr * max|M| where lambda_cr is the smallest positive root of det(K - lambda Kg) = 0.
Supports: fork at both ends (v = phi = 0, free to rotate and warp); 'CY' restraint (v = 0 at the shear centre,
twist free) and 'CY+DX' (v = 0 and phi = 0) at given positions.
Checked against the closed-form uniform-moment solution and SN003b C1 values in tests/test_ltb.py.
"""
from __future__ import annotations

import math

import numpy as np

E = 210000.0
G = 80770.0
_GP = np.polynomial.legendre.leggauss(6)


def _herm(xi, l):
    """Hermite shape functions and their 2nd derivatives (w.r.t. x) at xi in [0, 1]."""
    N = np.array([1 - 3 * xi ** 2 + 2 * xi ** 3, l * (xi - 2 * xi ** 2 + xi ** 3), 3 * xi ** 2 - 2 * xi ** 3,
                  l * (-xi ** 2 + xi ** 3)])
    d1 = np.array([-6 * xi + 6 * xi ** 2, l * (1 - 4 * xi + 3 * xi ** 2), 6 * xi - 6 * xi ** 2,
                   l * (-2 * xi + 3 * xi ** 2)]) / l
    d2 = np.array([-6 + 12 * xi, l * (-4 + 6 * xi), 6 - 12 * xi, l * (-2 + 6 * xi)]) / l ** 2
    return N, d1, d2


def mcr_eigen(s, m, Iz, It, Iw, restraints=(), n_min=24, E_=E, G_=G):
    """s = positions (m) from the segment start (first = 0), m = My (kNm) at those positions;
    Iz, It (mm4), Iw (mm6); restraints = [(position m, 'CY' or 'CY+DX')].
    Returns (Mcr in kNm referred to max|M|, lambda_cr)."""
    L = (s[-1] - s[0]) * 1000.0
    mmax = max(abs(v) for v in m)
    if L <= 0 or mmax < 1e-9:
        return math.inf, math.inf
    # mesh: at least n_min elements, nodes at every restraint
    xs = set(np.linspace(0.0, L, n_min + 1).round(6).tolist())
    for p, _ in restraints:
        xs.add(round((p - s[0]) * 1000.0, 6))
    xs = sorted(x for x in xs if -1e-6 <= x <= L + 1e-6)
    nn = len(xs)
    nd = 4 * nn                       # per node: v, v', phi, phi'
    K = np.zeros((nd, nd))
    Kg = np.zeros((nd, nd))
    sx = [(v - s[0]) * 1000.0 for v in s]

    def M_at(x):
        return float(np.interp(x, sx, m)) * 1e6 / mmax        # N mm, scaled to max|M| = 1 kNm -> lambda in kNm

    for e in range(nn - 1):
        x0, x1 = xs[e], xs[e + 1]
        l = x1 - x0
        if l <= 1e-9:
            continue
        iv = [4 * e, 4 * e + 1, 4 * (e + 1), 4 * (e + 1) + 1]
        ip = [4 * e + 2, 4 * e + 3, 4 * (e + 1) + 2, 4 * (e + 1) + 3]
        kb = np.zeros((4, 4))
        ks = np.zeros((4, 4))
        kc = np.zeros((4, 4))
        for g, w in zip(*_GP):
            xi = 0.5 * (g + 1)
            N, d1, d2 = _herm(xi, l)
            wl = 0.5 * w * l
            kb += np.outer(d2, d2) * wl
            ks += np.outer(d1, d1) * wl
            kc += M_at(x0 + xi * l) * np.outer(d2, N) * wl      # rows v'', columns phi
        K[np.ix_(iv, iv)] += E_ * Iz * kb
        K[np.ix_(ip, ip)] += E_ * Iw * kb + G_ * It * ks
        Kg[np.ix_(iv, ip)] += kc
        Kg[np.ix_(ip, iv)] += kc.T
    fixed = {0, 2, 4 * (nn - 1), 4 * (nn - 1) + 2}          # fork ends: v = phi = 0
    for p, kind in restraints:
        x = (p - s[0]) * 1000.0
        i = min(range(nn), key=lambda k: abs(xs[k] - x))
        fixed.add(4 * i)
        if "DX" in kind:
            fixed.add(4 * i + 2)
    if Iw <= 0:                                                # closed sections: warping stiffness 0, keep K regular
        K[np.ix_(range(3, nd, 4), range(3, nd, 4))] += np.eye(nn) * G_ * It * 1e-6
    free = [i for i in range(nd) if i not in fixed]
    Kf = K[np.ix_(free, free)]
    Gf = Kg[np.ix_(free, free)]
    mu = np.linalg.eigvals(np.linalg.solve(Kf, Gf))
    mu = mu[np.isfinite(mu)]
    mpos = max(abs(mu.real)) if len(mu) else 0.0
    if mpos <= 0:
        return math.inf, math.inf
    lam = 1.0 / mpos                                          # kNm per unit diagram (max|M| = 1 kNm)
    return lam, lam / mmax
