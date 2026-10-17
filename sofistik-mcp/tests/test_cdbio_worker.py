"""cdbio.py (DLL wrapper, with a fake DLL) and cdb_worker.py (every OPS entry, the JSON hand-over)."""
from __future__ import annotations

import ctypes
import json
import os
import struct
import subprocess
import sys
import types

import fake_cdb
import pytest

from sofistik_mcp import cdb_worker, cdbio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------- load_daten / decode_text

def test_load_daten_errors(tmp_path):
    with pytest.raises(cdbio.CdbError, match="sofistik_daten.py not found"):
        cdbio.load_daten(str(tmp_path / "none.py"))
    with pytest.raises(cdbio.CdbError, match="not found"):
        cdbio.load_daten(None)
    bad = tmp_path / "bad.py"
    bad.write_text("raise ImportError('broken')\n")
    with pytest.raises(cdbio.CdbError, match="Could not import .*broken"):
        cdbio.load_daten(str(bad))


def test_load_daten_min_and_real_path():
    d = cdbio.load_daten(fake_cdb.DATEN_MIN_PATH)
    assert ctypes.sizeof(d.CN_DISP) == 60


def ints(s, n):
    return list(struct.unpack(f"<{n}i", s.ljust(n * 4, b"\0")))


def test_decode_text_without_dll():
    assert cdbio.decode_text(ints(b"HEA 200", 4)) == "HEA 200"
    assert cdbio.decode_text(ints(b"  padded  ", 4)) == "padded"
    assert cdbio.decode_text(ints(b"Tr\xc3\xa4ger", 4)) == "Träger"          # UTF-8
    assert cdbio.decode_text(ints(b"Tr\xe4ger", 4)) == "Träger"              # latin-1 fallback
    assert cdbio.decode_text(ints(b"ab\0junk", 4)) == "ab"                        # stops at NUL
    assert cdbio.decode_text(ints(b"a\tb\x01c", 4)) == "abc"                      # unprintable removed
    assert cdbio.decode_text([]) == ""


class Ps2csDll:
    """sof_lib_ps2cs as SOFiSTiK's DLL does it: copy the text into the C buffer."""

    def __init__(self, out=None, fail=False):
        self.out, self.fail = out, fail

    def sof_lib_ps2cs(self, arr_ref, buf_ref, size):
        if self.fail:
            raise OSError("access violation")
        arr = arr_ref._obj
        raw = self.out if self.out is not None else bytes(arr)
        buf_ref._obj.value = raw[: size - 1]


def test_decode_text_with_dll():
    assert cdbio.decode_text(ints(b"S 355", 2), Ps2csDll()) == "S 355"
    assert cdbio.decode_text(ints(b"x", 2), Ps2csDll(out=b" Stahl \xe4 ")) == "Stahl ä"
    assert cdbio.decode_text(ints(b"x", 2), Ps2csDll(out=" Träger ".encode())) == "Träger"
    assert cdbio.decode_text(ints(b"from ints", 3), Ps2csDll(fail=True)) == "from ints"   # DLL fails: Python


# ---------------------------------------------------------------- Cdb with a fake DLL

class FakeDll:
    """sof_cdb_* functions over {(kwh, kwl): [bytes]} with SOFiSTiK's return codes."""

    def __init__(self, keys, index=0):
        self.keys, self.index, self.pos, self.closed = keys, index, {}, 0
        self.calls = []

        def get(idx, k1, k2, buf_ref, len_ref, pos):
            key = (k1.value, k2.value)
            self.calls.append(("get", key, len_ref._obj.value))
            if key not in self.keys:
                return 3
            i = self.pos.get(key, 0)
            if i >= len(self.keys[key]):
                return 2
            self.pos[key] = i + 1
            data = self.keys[key][i]
            cap = len_ref._obj.value
            ctypes.memmove(buf_ref._obj, data, min(len(data), cap))
            len_ref._obj.value = min(len(data), cap)
            return 1 if len(data) > cap else 0

        def kexist(kwh, kwl):
            r = self.keys.get((kwh, kwl))
            return 0 if r is None else (2 if r else 1)

        # cdbio sets .restype on these, as on ctypes function objects
        self.sof_cdb_get = CallableAttr(get)
        self.sof_cdb_kexist = CallableAttr(kexist)

    def sof_cdb_init(self, path, mode):
        self.calls.append(("init", path, mode))
        return self.index

    def sof_cdb_status(self, index):
        return 3

    def sof_cdb_close(self, n):
        self.closed += 1

    def sof_lib_ps2cs(self, arr_ref, buf_ref, size):
        buf_ref._obj.value = bytes(arr_ref._obj).split(b"\0")[0]


class CallableAttr:
    def __init__(self, fn):
        self.fn = fn
        self.restype = None

    def __call__(self, *a):
        return self.fn(*a)


def make_dll(keys, **kw):
    return FakeDll(keys, **kw)


@pytest.fixture
def windows_cdb(monkeypatch, tmp_path):
    """cdbio as if on Windows, with ctypes.cdll.LoadLibrary returning a fake DLL."""
    state = {}

    class Loader:
        def LoadLibrary(self, path):
            if state.get("load_error"):
                raise OSError("bad image")
            state["loaded"] = path
            return state["dll"]

    real_ctypes = ctypes
    fake_ctypes = types.SimpleNamespace(**{n: getattr(real_ctypes, n) for n in dir(real_ctypes)
                                           if not n.startswith("__")})
    fake_ctypes.cdll = Loader()
    added = []
    fake_os = types.SimpleNamespace(name="nt", path=os.path, add_dll_directory=added.append)
    monkeypatch.setattr(cdbio, "ctypes", fake_ctypes)
    monkeypatch.setattr(cdbio, "os", fake_os)
    cdb = tmp_path / "m.cdb"
    cdb.write_bytes(b"x")
    info = {"root": str(tmp_path), "dll": str(tmp_path / "sof_cdb_w-2027.dll"), "dll_dirs": ["A", "B"],
            "version": "2027"}
    state.update(cdb=str(cdb), info=info, added=added)
    return state


def test_cdb_reads_records_once_and_caches(windows_cdb):
    recs = [b"\x01\x00\x00\x00" + b"a" * 8, b"\x02\x00\x00\x00" + b"b" * 4]
    dll = windows_cdb["dll"] = make_dll({(24, 1): recs, (5, 5): []})
    c = cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    assert windows_cdb["added"] == ["A", "B"] and windows_cdb["loaded"] == windows_cdb["info"]["dll"]
    assert dll.calls[0] == ("init", os.path.abspath(windows_cdb["cdb"]).encode("utf-8"), 99)
    assert c.status == 3 and c.kexist(24, 1) == 2 and c.kexist(5, 5) == 1 and c.kexist(1, 1) == 0
    assert c.records(24, 1) == recs
    gets = [x for x in dll.calls if x[0] == "get"]
    assert all(x[2] == cdbio.Cdb.BUF for x in gets)                # length reset before every get
    assert c.records(24, 1) == recs and len([x for x in dll.calls if x[0] == "get"]) == len(gets)  # cached
    c.forget(24, 1)
    dll.pos.clear()
    assert c.records(24, 1) == recs                                   # read again after forget
    assert c.records(9, 9) == [] and c.truncated == 0
    assert c.text(ints(b"HEA", 1)) == "HEA"
    with c as same:
        assert same is c
    assert dll.closed == 1


def test_cdb_truncated_records_counted(windows_cdb, monkeypatch):
    monkeypatch.setattr(cdbio.Cdb, "BUF", 8)
    windows_cdb["dll"] = make_dll({(1, 1): [b"12345678", b"1234567890ab"]})
    c = cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    assert c.records(1, 1) == [b"12345678", b"12345678"] and c.truncated == 1


def test_cdb_open_errors(windows_cdb, tmp_path):
    windows_cdb["dll"] = make_dll({}, index=-3)
    with pytest.raises(cdbio.CdbError, match=r"sof_cdb_init returned -3.*Clean Locks"):
        cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    windows_cdb["load_error"] = True
    with pytest.raises(cdbio.CdbError, match="Could not load .*64-bit Python"):
        cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    with pytest.raises(cdbio.CdbError, match="DLL"):
        cdbio.Cdb(windows_cdb["cdb"], {"root": "R"})
    with pytest.raises(cdbio.CdbError, match=".cdb file not found"):
        cdbio.Cdb(str(tmp_path / "none.cdb"), windows_cdb["info"])


def test_cdb_close_swallows_errors(windows_cdb):
    dll = windows_cdb["dll"] = make_dll({})
    c = cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    dll.sof_cdb_close = None
    c.close()                                                          # must not raise


def test_cdb_on_this_machine_without_sofistik(tmp_path):
    cdb = tmp_path / "m.cdb"
    cdb.write_bytes(b"x")
    with pytest.raises(cdbio.CdbError) as e:
        cdbio.Cdb(str(cdb), {"dll": None, "root": "R"})
    assert ("needs Windows" in str(e.value)) if os.name != "nt" else ("DLL" in str(e.value))


# ---------------------------------------------------------------- worker

@pytest.fixture
def fake_cdb_frame(monkeypatch):
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: fake_cdb.FakeCdb(fake_cdb.build_frame()))


def req(op, **args):
    return {"op": op, "cdb": "x.cdb", "info": {"daten": fake_cdb.DATEN_PATH}, "args": args}


def test_every_op(fake_cdb_frame):
    expect = {
        "overview": ({}, lambda r: r["system"]["project"] == "FRAME TEST"),
        "load_cases": ({"lcs": "1-2"}, lambda r: [x["lc"] for x in r] == [1, 2]),
        "nodes": ({"ids": "1-2", "max_rows": 1}, lambda r: r["count"] == 2 and len(r["rows"]) == 1),
        "node_results": ({"lc": 1, "ids": "3", "include_coords": True},
                         lambda r: r["rows"][0]["uz"] == -10.5 and r["rows"][0]["x"] == 5.0),
        "support_reactions": ({"lc": 1}, lambda r: r["sum_kN"]["pz"] == 80.0),
        "beam_forces": ({"lc": 2, "groups": "2", "ends_only": True},
                        lambda r: [(x["beam"], x["N"]) for x in r["rows"]] == [(2001, 40.0), (2001, 40.0)]),
        "axial_forces": ({"lc": 1, "element_type": "cable"}, lambda r: r["rows"][0]["N"] == 80.0),
        "envelope": ({"lcs": "1-2", "what": "beam", "slns": "7"},
                     lambda r: r["overall"]["My"]["max"]["value"] == 50.0),
        "read_key": ({"kwh": 152, "kwl": 1, "class_name": "CTRUS_RES", "max_records": 1, "skip": 1},
                     lambda r: r["records"][0]["m_nr"] == 5002),
    }
    assert set(expect) == set(cdb_worker.OPS)
    for op, (args, check) in expect.items():
        a = cdb_worker.handle(req(op, **args))
        assert a["ok"], (op, a)
        assert check(a["result"]), (op, a["result"])
        json.dumps(a)


def test_op_defaults(fake_cdb_frame):
    a = cdb_worker.handle(req("beam_forces", lc=1))
    assert a["result"]["stations"] == 8
    a = cdb_worker.handle(req("axial_forces", lc=1))
    assert a["result"]["type"] == "truss"
    a = cdb_worker.handle(req("envelope", lcs="1"))
    assert a["result"]["what"] == "beam"


def test_unknown_op_and_truncation_warning(monkeypatch):
    assert cdb_worker.handle(req("format_disk")) == {"ok": False, "error": "unknown operation format_disk"}
    c = fake_cdb.FakeCdb(fake_cdb.build_frame())
    c.truncated = 2
    closed = []
    c.close = lambda: closed.append(1)
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: c)
    a = cdb_worker.handle(req("nodes"))
    assert a["result"]["warning_truncated_records"] == 2 and closed == [1]


def test_cdb_closed_even_on_error(monkeypatch):
    c = fake_cdb.FakeCdb(fake_cdb.build_frame())
    closed = []
    c.close = lambda: closed.append(1)
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: c)
    with pytest.raises(ValueError):
        cdb_worker.handle(req("nodes", ids="abc"))
    assert closed == [1]


def test_main_writes_answers(tmp_path, fake_cdb_frame):
    def call(request):
        rq, an = tmp_path / "req.json", tmp_path / "ans.json"
        rq.write_text(json.dumps(request), encoding="utf-8")
        assert cdb_worker.main(["w", str(rq), str(an)]) == 0
        return json.loads(an.read_text(encoding="utf-8"))
    assert call(req("support_reactions", lc=1))["result"]["sum_kN"]["px"] == -2.5
    bad = call(req("nodes", ids="1-x"))
    assert bad["ok"] is False and "Cannot read number list" in bad["error"]
    assert call({"op": "nodes", "cdb": "x"})["ok"] is False                     # KeyError: no info
    nodaten = call({"op": "nodes", "cdb": "x", "info": {"daten": str(tmp_path / "no.py")}})
    assert nodaten["ok"] is False and "sofistik_daten.py not found" in nodaten["error"]
    (tmp_path / "req.json").write_text("{not json")
    assert cdb_worker.main(["w", str(tmp_path / "req.json"), str(tmp_path / "ans.json")]) == 0
    a = json.loads((tmp_path / "ans.json").read_text())
    assert a["ok"] is False


def test_worker_as_subprocess_on_this_machine(tmp_path):
    """The real worker process without SOFiSTiK: a clean error answer, never a crash or stdout noise."""
    (tmp_path / "m.cdb").write_bytes(b"x")
    rq, an = tmp_path / "req.json", tmp_path / "ans.json"
    rq.write_text(json.dumps({"op": "overview", "cdb": str(tmp_path / "m.cdb"),
                              "info": {"daten": fake_cdb.DATEN_MIN_PATH, "dll": None, "root": "R"}}))
    p = subprocess.run([sys.executable, "-m", "sofistik_mcp.cdb_worker", str(rq), str(an)], cwd=ROOT,
                       capture_output=True, timeout=120)
    assert p.returncode == 0 and p.stdout == b""
    a = json.loads(an.read_text())
    assert a["ok"] is False and ("needs Windows" in a["error"] or "DLL" in a["error"])


def test_worker_runs_as_plain_script(tmp_path):
    """python sofistik_mcp/cdb_worker.py ... (no -m) finds its package too."""
    rq, an = tmp_path / "req.json", tmp_path / "ans.json"
    rq.write_text(json.dumps({"op": "nope", "cdb": "x", "info": {}}))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "sofistik_mcp", "cdb_worker.py"), str(rq), str(an)],
                       cwd=str(tmp_path), capture_output=True, timeout=120)
    assert p.returncode == 0, p.stdout
    assert json.loads(an.read_text()) == {"ok": False, "error": "unknown operation nope"}


def test_truncation_warning_on_list_result(monkeypatch):
    # load_cases returns a list; the warning must not raise TypeError
    c = fake_cdb.FakeCdb(fake_cdb.build_frame())
    c.truncated = 1
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: c)
    a = cdb_worker.handle(req("load_cases"))
    assert a["ok"] and a["result"]["warning_truncated_records"] == 1
    assert isinstance(a["result"]["rows"], list) and a["result"]["rows"]


# ---------------------------------------------------------------- review: sof_cdb_get error codes

@pytest.mark.parametrize("code", [-1, -7, 4, 99])
def test_cdb_get_error_code_stops_the_key_and_is_recorded(windows_cdb, code):
    """A return value other than 0 / 1 (record) or 2 / 3 (end, no key) is an error, never a record."""
    good = b"\x01\x00\x00\x00" + b"a" * 8
    dll = windows_cdb["dll"] = make_dll({(24, 1): [good, good, good]})
    real_get = dll.sof_cdb_get.fn
    n = {"calls": 0}

    def get(*a):
        n["calls"] += 1
        return code if n["calls"] == 2 else real_get(*a)
    dll.sof_cdb_get = CallableAttr(get)
    c = cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    assert c.records(24, 1) == [good] and n["calls"] == 2          # stopped at the error, nothing appended
    assert c.read_errors == [(24, 1, code)]


def test_cdb_get_end_codes_are_not_errors(windows_cdb):
    windows_cdb["dll"] = make_dll({(24, 1): [b"\x01\x00\x00\x00"]})
    c = cdbio.Cdb(windows_cdb["cdb"], windows_cdb["info"])
    assert c.records(24, 1) == [b"\x01\x00\x00\x00"] and c.records(7, 7) == [] and c.read_errors == []


def test_worker_reports_read_errors(monkeypatch):
    c = fake_cdb.FakeCdb(fake_cdb.build_frame())
    c.read_errors = [(102, 1, -1)]
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: c)
    a = cdb_worker.handle(req("beam_forces", lc=1))
    assert a["ok"] and "102/1 (code -1)" in a["result"]["warning_read_errors"]
    assert "warning_truncated_records" not in a["result"]
    lst = cdb_worker.handle(req("load_cases"))                        # list result is wrapped, not crashed
    assert lst["result"]["rows"] and "warning_read_errors" in lst["result"]
