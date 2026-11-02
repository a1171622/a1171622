"""AS 4100-2020 plug-in: NOT WRITTEN YET.  This file shows where Australian checks go.

To add it, fill the three methods with the same inputs/outputs as en1993.py:
  section()         section properties incl. Ze (effective section modulus, 5.2), kf (6.2.2), form factor
  station_checks()  section capacity: N* <= phi Ns (6.2), M* <= phi Ms (5.1/5.2), V* <= phi Vv (5.11),
                    combined 8.3 (reduced Mr for N + M, biaxial 8.3.4)
  segment_checks()  member capacity: phi Nc with alpha_c (6.3, member constant alpha_b, Le = ke L),
                    phi Mb = alpha_m alpha_s phi Ms (5.6.1, alpha_m from the real moment diagram 5.6.1.1(a)(iii)
                    = 1.7 M*m / sqrt(M2*^2 + M3*^2 + M4*^2) <= 2.5, le = kt kl kr l, 5.6.3),
                    in-plane 8.4.2 and out-of-plane 8.4.4 interaction (8.4.5 biaxial)
phi = 0.9.  The member, segment and load-case loops, the SOFiSTiK reading and the outputs are shared, so nothing else
needs to change.  Validate it against a worked example set (e.g. the AISC/ASI design capacity tables) before use.
"""
from __future__ import annotations

from .base import DesignCode


class AS4100(DesignCode):
    name = "AS 4100-2020 (not implemented)"

    def section(self, sec_name):
        raise NotImplementedError("AS 4100 module not written yet: see memcheck/codes/as4100.py")

    def station_checks(self, *a, **k):
        raise NotImplementedError

    def segment_checks(self, *a, **k):
        raise NotImplementedError
