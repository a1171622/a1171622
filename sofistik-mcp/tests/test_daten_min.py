"""tests/daten_min.py (committed) must be an exact copy of the classes in SOFiSTiK's sofistik_daten.py."""
from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys

import fake_cdb
import pytest

from sofistik_mcp import cdbio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REAL = fake_cdb.find_real_daten(allow_force_min=False)
need_real = pytest.mark.skipif(REAL is None, reason="SOFiSTiK's sofistik_daten.py is not on this machine")

MIN = cdbio.load_daten(fake_cdb.DATEN_MIN_PATH)


def _used_class_names():
    """Class names quoted in the server source and in the fake .cdb builder."""
    src = os.path.join(ROOT, "sofistik_mcp")
    files = [os.path.join(src, n) for n in os.listdir(src) if n.endswith(".py")] + [os.path.join(HERE, "fake_cdb.py")]
    names = set()
    for path in files:
        with open(path, encoding="utf-8") as f:
            names |= set(re.findall(r'"(C[A-Z][A-Z0-9_]+)"', f.read()))
    # strings in the source that are not sofistik_daten classes
    return {n for n in names if not n.startswith(("CDB", "CREATE"))}


def _type_sig(t):
    """Comparable description of a ctypes type (array types are new objects in each module)."""
    if issubclass(t, ctypes.Array):
        return ("array", t._length_, _type_sig(t._type_))
    if issubclass(t, (ctypes.Structure, ctypes.Union)):
        return ("struct", t.__name__, tuple((f[0], _type_sig(f[1])) for f in t._fields_))
    return ("simple", t._type_, ctypes.sizeof(t))


def test_min_has_every_class_the_code_uses():
    used = _used_class_names()
    assert {"CSYST", "CN_DISP", "CBEAM_FOR", "CLC_EIGE", "CTRUS_RES", "CCABL_RES"} <= used
    missing = sorted(n for n in used if not hasattr(MIN, n))
    assert missing == [], f"add these to CLASSES in tests/make_daten_min.py and regenerate: {missing}"
    assert set(MIN.CLASSES) == {n for n in vars(MIN) if n.startswith("C") and isinstance(getattr(MIN, n), type)
                                and issubclass(getattr(MIN, n), ctypes.Structure)}


def test_min_known_layouts():
    """Sizes and offsets that the result readers rely on (independent of the real file)."""
    assert ctypes.sizeof(MIN.CN_DISP) == 60 and MIN.CN_DISP.m_uz.offset == 12 and MIN.CN_DISP.m_pz.offset == 40
    assert ctypes.sizeof(MIN.CBEAM_FOR) == 128 and MIN.CBEAM_FOR.m_my.offset == 24
    assert ctypes.sizeof(MIN.CSYST) == 352 and MIN.CSYST.m_txt.offset == 96
    assert ctypes.sizeof(MIN.CNODE) == 28 and MIN.CNODE.m_xyz.offset == 16
    assert ctypes.sizeof(MIN.CBEAM) == 108 and MIN.CBEAM.m_nref.offset == 80
    assert ctypes.sizeof(MIN.CLC_CTRL) == ctypes.sizeof(MIN.CLC_EIGE) == 188
    assert MIN.CLC_CTRL.m_rz.offset == 64 and MIN.CLC_EIGE.m_omega.offset == 24


@need_real
def test_min_matches_real_sofistik_daten_exactly():
    real = cdbio.load_daten(REAL)
    for name in MIN.CLASSES:
        a, b = getattr(MIN, name), getattr(real, name)
        assert [f[0] for f in a._fields_] == [f[0] for f in b._fields_], name
        assert [_type_sig(f[1]) for f in a._fields_] == [_type_sig(f[1]) for f in b._fields_], name
        assert ctypes.sizeof(a) == ctypes.sizeof(b), name
        assert ctypes.alignment(a) == ctypes.alignment(b), name
        assert getattr(a, "_pack_", None) == getattr(b, "_pack_", None), name
        for fname, _t in a._fields_:
            fa, fb = getattr(a, fname), getattr(b, fname)
            assert (fa.offset, fa.size) == (fb.offset, fb.size), f"{name}.{fname}"


@need_real
def test_generator_reproduces_committed_file(tmp_path):
    import make_daten_min
    with open(REAL, encoding="utf-8", errors="replace") as f:
        code = make_daten_min.render(make_daten_min.extract(f.read()), "SOFiSTiK 2027 sofistik_daten.py", "")
    with open(fake_cdb.DATEN_MIN_PATH, encoding="utf-8") as f:
        assert f.read() == code, "tests/daten_min.py is stale: run python tests/make_daten_min.py"


def test_generator_cli_without_source(tmp_path):
    env = dict(os.environ, SOFISTIK_DATEN=str(tmp_path / "missing.py"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "make_daten_min.py"), str(tmp_path / "missing.py")],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 1 and "not found" in r.stderr


def test_generator_on_a_tiny_source(tmp_path, monkeypatch):
    import make_daten_min
    src = ("from ctypes import *\n\nclass CA(Structure):   # 1/2  A\n   _pack_ = 4\n   _fields_ = [\n"
           "      ('m_a', c_int),\n      ('m_b', c_float * 3 * 2)   # c\n   ]\n\nclass CB(Structure):\n"
           "   _fields_ = [('m_d', c_double)]\n")
    classes = make_daten_min.extract(src, names=("CB", "CA"))
    code = make_daten_min.render(classes, "x", "")
    ns = {}
    exec(compile(code, "gen", "exec"), ns)
    assert ns["CLASSES"] == ("CB", "CA")
    assert ns["CA"]._pack_ == 4 and ctypes.sizeof(ns["CA"]) == 28 and ns["CA"].m_b.offset == 4
    assert ctypes.sizeof(ns["CB"]) == 8
    with pytest.raises(SystemExit, match="Not in the source"):
        make_daten_min.extract(src, names=("CZ",))
