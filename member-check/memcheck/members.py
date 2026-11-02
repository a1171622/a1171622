"""Design members (code independent): structural lines chained into members, positions along the member,
restraint stations and the force diagrams per load case.

A Member is a chain of SOFiSTiK structural lines (one line, or MEMB SLN a + CONT b + CONT c in BDK).  Positions s are
measured in metres from the member start (the start of its first line, as BDK's REF STRT S).  Lines that run against
the chain direction are reversed: their stations are mirrored and Vz, Mz change sign (a 180 degree turn about the
local z axis keeps N, Vy, Mt, My and flips Vz, Mz).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .sofistik import BdkMember, Sln


@dataclass
class DesignInput:
    """What the engineer decides per member.  Defaults reproduce the 26016 BDK file."""
    Ly_mode: str = "member"       # 'member' = Lcr,y over the whole member (as BDK); 'segment' = between restraints
    k_y: float = 1.0
    k_z: float = 1.0              # applied to each segment between lateral restraints
    k_LT: float = 1.0
    zg_mm: float = 0.0            # load height above the shear centre (+ = destabilising); BDK has no load height
    c1_method: str = "diagram"    # 'diagram' (Kirby-Nethercot from the real diagram) or 'one' (C1 = 1, conservative)
    mcr_method: str = "eigen"     # 'eigen' = Mcr from the real diagram and the lateral-only restraints (ltb.py, as
                                  # BDK / LTBeam; I-sections with zg = 0); 'formula' = SN003b with C1 (spreadsheet)
    torsion_restrained: bool = False   # True = continuous torsional restraint (no LTB, as spreadsheet 'No')
    sway: bool = False            # True = sway buckling mode: Cmy = Cmz = 0.9 (Table B.3), as BDK SWY/SWZ
    lt_at_lateral: bool = False   # True = a lateral-only restraint (ring beam at the shear centre, no twist hold)
                                  # also ends the LTB length; False (default) = only twist-holding restraints do


@dataclass
class Member:
    id: int
    slns: list
    section_no: int
    group: int
    length: float
    restraints: list               # [(s, kind, note)] sorted, inside (0, L)
    comment: str = ""
    path: list = field(default_factory=list)       # [(sln, reversed, s0, s1)]
    pts: list = field(default_factory=list)        # polyline of the member axis (x, y, z) start -> end
    design: DesignInput = field(default_factory=DesignInput)

    def segments(self, kind="LT"):
        """Buckling segments.  kind 'z' = between all lateral restraints (flexural buckling about z);
        'LT' = between restraints that also hold the twist (CY+DX, e.g. a column), unless the member's
        DesignInput.lt_at_lateral says lateral-only restraints count for LTB too."""
        use_all = kind == "z" or self.design.lt_at_lateral
        b = [0.0] + [s for s, k, _ in self.restraints if use_all or "DX" in k] + [self.length]
        return [(b[i], b[i + 1]) for i in range(len(b) - 1) if b[i + 1] - b[i] > 1e-6]

    def point_at(self, s):
        """(x, y, z) at position s along the member axis."""
        acc = 0.0
        for i in range(len(self.pts) - 1):
            seg = math.dist(self.pts[i], self.pts[i + 1])
            if acc + seg >= s - 1e-9 or i == len(self.pts) - 2:
                t = 0.0 if seg == 0 else max(0.0, min(1.0, (s - acc) / seg))
                return tuple(self.pts[i][k] + t * (self.pts[i + 1][k] - self.pts[i][k]) for k in range(3))
            acc += seg
        return self.pts[-1]


def _orient(chain, slns):
    """Order and orientation of the lines in a chain: [(sln, reversed)], following the first line's direction."""
    out = []
    first = slns[chain[0]]
    if len(chain) > 1:
        nxt = slns[chain[1]]
        ends = (nxt.pts[0], nxt.pts[-1])
        d_end = min(math.dist(first.pts[-1], e) for e in ends)
        d_start = min(math.dist(first.pts[0], e) for e in ends)
        rev0 = d_start < d_end - 1e-6          # chain continues from the first line's start: run it backwards
    else:
        rev0 = False
    out.append((chain[0], rev0))
    tail = first.pts[0] if rev0 else first.pts[-1]
    for no in chain[1:]:
        ln = slns[no]
        rev = math.dist(ln.pts[-1], tail) < math.dist(ln.pts[0], tail)
        out.append((no, rev))
        tail = ln.pts[0] if rev else ln.pts[-1]
    return out


def build_members(bdk: list, slns: dict, sections: dict, extra_slns=(), skip_sections=(7,)) -> list:
    """Members from the BDK definitions, plus every other beam line in extra_slns as its own fork-ended member."""
    used = {n for m in bdk for n in m.slns}
    defs = [(m.id, m.slns, m.stations, m.comment) for m in bdk]
    for no in extra_slns:
        if no not in used and no in slns and slns[no].sno not in skip_sections:
            defs.append((no, [no], [], f"SLN {no} (not in the BDK file): own member, fork ends"))
    out = []
    for mid, chain, stations, comment in defs:
        if any(n not in slns for n in chain):
            continue
        sec = slns[chain[0]].sno
        if sec in skip_sections:
            continue
        orient = _orient(chain, slns)
        s0, path, pts = 0.0, [], []
        for no, rev in orient:
            ln = slns[no]
            L = ln.length
            path.append((no, rev, s0, s0 + L))
            p = list(reversed(ln.pts)) if rev else list(ln.pts)
            pts += p if not pts else p[1:]
            s0 += L
        rs = sorted((s, k, n) for s, k, n in stations if 1e-6 < s < s0 - 1e-6)
        out.append(Member(mid, list(chain), sec, slns[chain[0]].grp, s0, rs, comment, path, pts))
    return out


def diagrams(member: Member, forces_lc: dict):
    """Stations of the member for one load case: list of (s, N, Vy, Vz, Mt, My, Mz, beam), sorted by s.
    forces_lc = {sln: [(beam, x, N, Vy, Vz, Mt, My, Mz[, u])]}.  u = position on the line from the beam's node
    coordinates (sofistik.remap_forces); without it the beams are placed in increasing beam number."""
    rows = []
    for no, rev, s0, s1 in member.path:
        recs = forces_lc.get(no, [])
        if not recs:
            continue
        L = s1 - s0
        if all(len(r) > 8 and r[8] is not None for r in recs):
            pos = [r[8] for r in recs]
        else:
            acc, beam_len, start = 0.0, {}, {}
            for r in recs:
                beam_len[r[0]] = max(beam_len.get(r[0], 0.0), r[1])
            for b in sorted(beam_len):
                start[b] = acc
                acc += beam_len[b]
            scale = L / acc if acc > 0 else 1.0
            pos = [(start[r[0]] + r[1]) * scale for r in recs]
        for u, r in zip(pos, recs):
            b, x, N, Vy, Vz, Mt, My, Mz = r[:8]
            u = max(0.0, min(L, u))
            if rev:
                rows.append((s1 - u, N, Vy, -Vz, Mt, My, -Mz, b))
            else:
                rows.append((s0 + u, N, Vy, Vz, Mt, My, Mz, b))
    rows.sort(key=lambda r: r[0])
    return rows


def length_check(member: Member, forces_lc: dict):
    """Sum of beam lengths per line vs the line length from the .dat (should agree within a few mm)."""
    out = []
    for no, rev, s0, s1 in member.path:
        lens = {}
        for r in forces_lc.get(no, []):
            lens[r[0]] = max(lens.get(r[0], 0.0), r[1])
        out.append((no, s1 - s0, sum(lens.values())))
    return out
