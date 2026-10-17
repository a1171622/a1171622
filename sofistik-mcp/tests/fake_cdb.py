"""A fake .cdb for tests on Linux: the selftest cantilever (HEA 200, L 6 m, P 1 kN at node 7) built
from SOFiSTiK's real record layouts (vendor copy of sofistik_daten.py, 2027)."""
from __future__ import annotations

import ctypes
import os
import struct

from sofistik_mcp import cdbio

def _find_daten():
    """SOFiSTiK's sofistik_daten.py (not shipped here): $SOFISTIK_DATEN, the installed copy, or the
    report tool's vendor copy next to this project."""
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.environ.get("SOFISTIK_DATEN"),
              r"C:\Program Files\SOFiSTiK\2027\SOFiSTiK 2027\interfaces\examples\python\sofistik_daten.py",
              os.path.join(here, "..", "..", "reports", "sofistik_report", "vendor", "sofistik_daten.py"),
              "/mnt/project-files/reports/sofistik_report/vendor/sofistik_daten.py"):
        if p and os.path.isfile(p):
            return p
    raise RuntimeError("Set SOFISTIK_DATEN to SOFiSTiK's sofistik_daten.py to run the tests.")


DATEN_PATH = _find_daten()
daten = cdbio.load_daten(DATEN_PATH)

E, G = 2.1e8, 8.1e7            # kN/m2
A, IY, IZ, AZ = 53.8e-4, 3692e-8, 1336e-8, 18.0e-4
P, L = 1.0, 6.0


def text_ints(s, n):
    b = s.encode("utf-8")[: n * 4].ljust(n * 4, b"\0")
    return list(struct.unpack(f"<{n}i", b))


def rec(clsname, **fields):
    cls = getattr(daten, clsname)
    o = cls()
    for k, v in fields.items():
        attr = getattr(o, k)
        if isinstance(attr, ctypes.Array):
            flat = v
            if isinstance(attr[0], ctypes.Array):          # 2-D
                for i, row in enumerate(v):
                    for j, x in enumerate(row):
                        attr[i][j] = x
                continue
            for i, x in enumerate(flat):
                attr[i] = x
        else:
            setattr(o, k, v)
    return bytes(o)


def build():
    keys = {}
    keys[(10, 0)] = [rec("CSYST", m_iprob=30, m_igdiv=1000, m_nknot=7, m_mknot=7, m_txt=text_ints("SELFTEST", 64))]
    keys[(1, 1)] = [rec("CMAT", m_id=0, m_title=text_ints("S 355", 17)),
                    rec("CMAT_STEE", m_id=1, m_emod=E, m_gmod=G)]
    keys[(9, 1)] = [rec("CSECT", m_id=0, m_mno=1, m_a=A, m_iy=IY, m_iz=IZ, m_az=AZ, m_em=E, m_gm=G),
                    rec("CSECT_TXT", m_id=19, m_txt=text_ints("HEA 200", 128))]
    keys[(11, 0)] = [rec("CGRP", m_ng=0, m_typ=100, m_num=6, m_min=1, m_max=6, m_text=text_ints("grp0", 17))]
    keys[(12, 1)] = [rec("CLC_CTRL", m_kind=0, m_fact=1.0, m_rz=P, m_rtex=text_ints("self-test tip load 1 kN", 17))]
    keys[(12, 2001)] = [rec("CLC_EIGE", m_kind=4, m_nr_mode=1, m_omega=2 * 3.141592653589793 * 2.5,
                            m_rtex=text_ints("mode 1", 17))]
    keys[(20, 0)] = [rec("CNODE", m_nr=i, m_xyz=[float(i - 1), 0.0, 0.0], m_kfix=(63 if i == 1 else 0))
                     for i in range(1, 8)]
    beams = []
    for i in range(1, 7):
        beams.append(rec("CBEAM", m_nr=i, m_node=[i, i + 1], m_np=1, m_dl=1.0, m_nref=0))
        beams.append(rec("CBEAM_SCT", m_id=0, m_nq=1))
    keys[(100, 0)] = beams
    d = []
    d.append(rec("CN_DISPC", m_id=0))
    for i in range(1, 8):
        x = i - 1.0
        uz = P * x * x * (3 * L - x) / (6 * E * IY)          # bending only, m
        kw = dict(m_nr=i, m_uz=uz)
        if i == 1:
            kw.update(m_pz=P, m_my=P * L)
        d.append(rec("CN_DISP", **kw))
    keys[(24, 1)] = d
    f = [rec("CBEAM_FOC", m_id=0, m_my=P * L)]
    for i in range(1, 7):
        for x in (0.0, 0.5, 1.0):
            xg = i - 1 + x
            f.append(rec("CBEAM_FOR", m_nr=i, m_x=x, m_vz=P, m_my=-(P * (L - xg)), m_n=0.0, m_mz=1e35))
    keys[(102, 1)] = f
    keys[(152, 1)] = [rec("CTRUS_RES", m_nr=5001, m_n=12.5, m_v=0.001)]
    return keys


class FakeCdb:
    def __init__(self, keys=None):
        self.keys = keys if keys is not None else build()
        self.truncated = 0
        self.reads = {}

    def kexist(self, kwh, kwl):
        r = self.keys.get((int(kwh), int(kwl)))
        if r is None:
            return 0
        return 2 if r else 1

    def records(self, kwh, kwl):
        k = (int(kwh), int(kwl))
        self.reads[k] = self.reads.get(k, 0) + 1
        return list(self.keys.get(k, []))

    def text(self, ints):
        return cdbio.decode_text(ints)

    def close(self):
        pass
