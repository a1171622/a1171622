"""A fake .cdb for tests without SOFiSTiK: the selftest cantilever (HEA 200, L 6 m, P 1 kN at node 7)
built from SOFiSTiK's real record layouts (sofistik_daten.py 2027 when it is on this machine, otherwise
the field-for-field copy tests/daten_min.py, checked against the real file by tests/test_daten_min.py)."""
from __future__ import annotations

import ctypes
import os
import struct

from sofistik_mcp import cdbio

HERE = os.path.dirname(os.path.abspath(__file__))
DATEN_MIN_PATH = os.path.join(HERE, "daten_min.py")


def find_real_daten(allow_force_min=True):
    """SOFiSTiK's own sofistik_daten.py (never committed here): $SOFISTIK_DATEN, the installed copy,
    or the report tool's vendor copy next to this project.  None if none is there (e.g. on CI).
    SOFISTIK_DATEN=min forces the minimal copy tests/daten_min.py."""
    env = os.environ.get("SOFISTIK_DATEN")
    if env == "min":
        if allow_force_min:
            return None
        env = None
    for p in (env,
              r"C:\Program Files\SOFiSTiK\2027\SOFiSTiK 2027\interfaces\examples\python\sofistik_daten.py",
              os.path.join(HERE, "..", "..", "reports", "sofistik_report", "vendor", "sofistik_daten.py"),
              "/mnt/project-files/reports/sofistik_report/vendor/sofistik_daten.py"):
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return None


REAL_DATEN_PATH = find_real_daten()
USING_REAL_DATEN = REAL_DATEN_PATH is not None
# the path the server's worker gets as info["daten"]: loaded the same way (cdbio.load_daten) as on a PC
DATEN_PATH = REAL_DATEN_PATH or DATEN_MIN_PATH
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
    """Same interface as cdbio.Cdb (kexist, records, text, close); keys = {(kwh, kwl): [bytes, ...]}."""

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


# ------------------------------------------------------------------------------------------------
# a richer model with hand-chosen numbers for every result type (tests/test_results.py)
# ------------------------------------------------------------------------------------------------

UNDEF = 1e35        # how SOFiSTiK marks a value that does not exist

# (beam, x [m], N, Vy, Vz [kN], Mt, My, Mz [kNm]) as stored in 102/1 (SI: kN, kNm, m)
FRAME_BEAM_LC1 = [
    (1001, 0.0, -10.0, 1.0, 2.0, 0.1, -20.0, 3.0),
    (1001, 2.5, -10.0, 1.0, 2.0, 0.1, 5.0, 3.0),
    (1001, 5.0, -10.0, 1.0, -2.0, 0.1, -15.0, UNDEF),
    (1002, 0.0, 25.0, 0.0, 4.0, 0.0, -30.0, 0.0),
    (1002, 4.0, 25.0, 0.0, -4.0, 0.0, 12.0, 0.0),
    (2001, 0.0, -100.0, 0.5, 0.0, 0.0, 2.0, 0.0),
    (2001, 1.5, -100.0, 0.5, 0.0, 0.0, 0.5, 0.0),
    (2001, 3.0, -100.0, 0.5, 0.0, 0.0, -1.0, 0.0),
]
# LC 2: everything x 1.5, except column 2001 in tension (N = +40) and 1002 My = 50 at x = 4
FRAME_BEAM_LC2 = [(b, x, (40.0 if b == 2001 else n * 1.5), vy * 1.5, vz * 1.5, mt * 1.5,
                   (50.0 if (b, x) == (1002, 4.0) else my * 1.5), (mz if mz >= 1e30 else mz * 1.5))
                  for b, x, n, vy, vz, mt, my, mz in FRAME_BEAM_LC1]

# node results LC 1 (SI: m, rad, kN, kNm)
FRAME_NODE_LC1 = {
    1: dict(m_pz=50.0, m_my=-12.0),
    2: dict(m_ux=0.001, m_uz=-0.0042, m_ury=0.0013),
    3: dict(m_uz=-0.0105, m_urx=-0.0005),
    4: dict(m_px=-2.5, m_pz=30.0),
    5: dict(m_uy=0.0021, m_urz=UNDEF),
}
ACTION_G = text_ints("G", 1)[0]
ACTION_Q = text_ints("Q", 1)[0]


def build_frame():
    """Frame: girder beams 1001-1002 on structural line 7 (group 1), column 2001-2002 (group 2),
    trusses 5001/5002, cable 6001.  LC 1 (G), LC 2 (Q), LC 3 superposition, LC 2001/2002 eigenmodes."""
    keys = {}
    keys[(10, 0)] = [rec("CSYST", m_iprob=30, m_igdiv=1000, m_nknot=5, m_mknot=5,
                         m_box=[[0.0, 0.0, 0.0], [9.0, 0.0, 3.0]], m_txt=text_ints("FRAME TEST", 64))]
    keys[(1, 1)] = [rec("CMAT", m_id=0, m_title=text_ints("S 355", 17)),
                    rec("CMAT_STEE", m_id=1, m_emod=E, m_gmod=G)]
    keys[(1, 2)] = [rec("CMAT", m_id=0, m_title=text_ints("C 30/37", 17))]
    keys[(9, 1)] = [rec("CSECT", m_id=0, m_mno=1, m_a=A, m_iy=IY, m_iz=IZ, m_it=20.98e-8),
                    rec("CSECT_TXT", m_id=19, m_txt=text_ints("HEA 200", 128))]
    keys[(9, 2)] = [rec("CSECT", m_id=0, m_mno=1, m_a=53.81e-4, m_iy=8356e-8, m_iz=604e-8),
                    rec("CSECT_PRO", m_id=12, m_bez=text_ints("IPE 300", 8))]
    keys[(11, 0)] = [rec("CGRP", m_ng=1, m_typ=100, m_num=2, m_min=1001, m_max=1002, m_text=text_ints("girder", 17)),
                     rec("CGRP", m_ng=2, m_typ=100, m_num=2, m_min=2001, m_max=2002, m_text=text_ints("columns", 17)),
                     # a truss group whose number range overlaps the girder: beams must stay in group 1
                     rec("CGRP", m_ng=5, m_typ=150, m_num=2, m_min=1001, m_max=5002, m_text=text_ints("bracing", 17))]
    keys[(12, 1)] = [rec("CLC_CTRL", m_kind=0, m_ityp=ACTION_G, m_fact=1.0, m_facz=1.0, m_rx=-2.5, m_rz=80.0,
                         m_rtex=text_ints("dead load", 17))]
    keys[(12, 2)] = [rec("CLC_CTRL", m_kind=0, m_ityp=ACTION_Q, m_fact=1.5, m_rz=160.0,
                         m_rtex=text_ints("imposed", 17))]
    keys[(12, 3)] = [rec("CLC_CTRL", m_kind=2, m_ityp=0, m_fact=1.0, m_rz=999.0, m_rtex=text_ints("MAX MY", 17))]
    keys[(12, 2001)] = [rec("CLC_EIGE", m_kind=4, m_nr_mode=1, m_omega=2 * 3.141592653589793 * 4.0,
                            m_rtex=text_ints("eigenmode 1", 17))]
    keys[(12, 2002)] = [rec("CLC_EIGE", m_kind=4, m_nr_mode=2, m_omega=0.0, m_rtex=text_ints("eigenmode 2", 17))]
    keys[(14, ACTION_G)] = [rec("CLC_ACT", m_id=1, m_action=ACTION_G, m_txt=text_ints("Permanent loads", 17))]
    keys[(20, 0)] = [rec("CNODE", m_nr=i, m_xyz=[float(x), 0.0, float(z)], m_kfix=(63 if i in (1, 4) else 0))
                     for i, x, z in ((1, 0, 0), (2, 2.5, 3), (3, 5, 3), (4, 9, 0), (5, 9, 3))]
    beams = []
    for nr, nodes, sec, length, sln in ((1001, [2, 3], 1, 5.0, 7), (1002, [3, 5], 1, 4.0, 7),
                                        (2001, [1, 2], 2, 3.0, 0), (2002, [4, 5], 2, 3.0, 0)):
        beams += [rec("CBEAM", m_nr=nr, m_node=nodes, m_np=sec, m_dl=length, m_nref=sln),
                  rec("CBEAM_SCT", m_id=0, m_nq=sec)]
    keys[(100, 0)] = beams

    def node_key(rows, scale=1.0):
        out = [rec("CN_DISPC", m_id=0, m_uz=9.9)]               # id-0 record: maxima, never a node
        for nr, kw in rows.items():
            out.append(rec("CN_DISP", m_nr=nr, **{k: (v if abs(v) >= 1e30 else v * scale) for k, v in kw.items()}))
        return out
    keys[(24, 1)] = node_key(FRAME_NODE_LC1)
    keys[(24, 2)] = node_key(FRAME_NODE_LC1, 2.0)
    keys[(24, 2001)] = [rec("CN_DISPC", m_id=0), rec("CN_DISP", m_nr=3, m_uz=1.0)]   # mode shape, normalised

    def beam_key(rows):
        out = [rec("CBEAM_FOC", m_id=0, m_my=999.0)]
        for b, x, n, vy, vz, mt, my, mz in rows:
            out.append(rec("CBEAM_FOR", m_nr=b, m_x=x, m_n=n, m_vy=vy, m_vz=vz, m_mt=mt, m_my=my, m_mz=mz))
        return out
    keys[(102, 1)] = beam_key(FRAME_BEAM_LC1)
    keys[(102, 2)] = beam_key(FRAME_BEAM_LC2)
    keys[(152, 1)] = [rec("CTRUS_RES", m_nr=5001, m_n=12.5, m_v=0.001),
                      rec("CTRUS_RES", m_nr=5002, m_n=-7.25, m_v=-0.0004)]
    keys[(162, 1)] = [rec("CCABL_RES", m_nr=6001, m_n=80.0, m_v=0.0123)]
    keys[(162, 2)] = [rec("CCABL_RES", m_nr=6001, m_n=95.0, m_v=0.0150)]
    return keys


def build_crash():
    """Stands in for SOFiSTiK's DLL crashing the worker process (prints, then dies without an answer)."""
    print("forrtl: severe (157): Program Exception - access violation", flush=True)
    os._exit(3)
