"""The plug-in interface every design code module follows.

The workflow (memcheck.run) knows nothing about any code.  It hands a code module:
  - the section (SectionData), the steel grade, the member (memcheck.members.Member) with its DesignInput,
  - for the section checks: the concurrent forces at one station,
  - for the member checks: the force diagram over one buckling segment and over the whole member,
and gets back a list of Check results.  To add a code (e.g. AS 4100), write a module with the same two functions
and register it in CODES at the bottom of this file.  Nothing else changes: extraction, members, restraints,
load cases, tables and pictures are shared.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Check:
    label: str          # e.g. "Bending + compression, eq. 6.62"
    clause: str         # e.g. "6.3.3"
    util: float         # utilisation (demand / resistance)
    details: dict = field(default_factory=dict)


class DesignCode:
    """Interface.  Units: kN, kNm, m; N compression negative (SOFiSTiK convention)."""
    name = "abstract"

    def section(self, sec_name: str):
        """Return the code's section object for a catalogue name such as 'UB 254x146x43'."""
        raise NotImplementedError

    def station_checks(self, sec, grade: str, N, Vy, Vz, Mt, My, Mz) -> list:
        """Cross-section checks with concurrent forces at one station -> [Check]."""
        raise NotImplementedError

    def segment_checks(self, sec, grade: str, member, seg: tuple, seg_rows: list, member_rows: list) -> list:
        """Member (buckling) checks for one segment between lateral restraints -> [Check].
        seg = (s_start, s_end) in m; *_rows = [(s, N, Vy, Vz, Mt, My, Mz, beam)] sorted by s."""
        raise NotImplementedError


def get_code(name: str) -> DesignCode:
    from . import as4100, en1993
    codes = {"EN1993": en1993.EN1993, "AS4100": as4100.AS4100}
    try:
        return codes[name.upper().replace(" ", "").replace("-", "")]()
    except KeyError:
        raise ValueError(f"unknown code {name!r}; available: {', '.join(codes)}") from None
