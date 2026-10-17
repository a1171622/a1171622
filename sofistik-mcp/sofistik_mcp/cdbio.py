"""Low-level read-only access to a SOFiSTiK .cdb through SOFiSTiK's own DLL (Windows only).

Taken from the report tool (reports/sofistik_report/sofrep/readers/cdb_reader.py, Cdb and
decode_text), which follows SOFiSTiK's shipped Python examples (interfaces/examples/python/python_3.x):
  sof_cdb_init(path_utf8, 99)            open an existing database, returns an index (< 0 = failed)
  sof_cdb_kexist(kwh, kwl)               0 missing, 1 key without data, 2 key with data
  sof_cdb_get(index, kwh, kwl, buf, len, 1)   0 ok, 1 record longer than buffer, 2 end of key, 3 no key
  sof_cdb_close(0)                       close all
  sof_lib_ps2cs(ints, buf, size)         SOFiSTiK text (4 chars per int) -> C string
Record layouts come from SOFiSTiK's sofistik_daten.py of the installed version.
"""
from __future__ import annotations

import ctypes
import importlib.util
import os
import struct


class CdbError(RuntimeError):
    """Problem with the SOFiSTiK installation or the .cdb (message is meant for the engineer)."""


def load_daten(path):
    """Import sofistik_daten.py from an explicit path."""
    if not path or not os.path.isfile(path):
        raise CdbError(f"sofistik_daten.py not found ({path}). It is normally in "
                       r"<SOFiSTiK>\interfaces\examples\python.")
    spec = importlib.util.spec_from_file_location("sofistik_daten_runtime", path)
    assert spec is not None and spec.loader is not None  # always set for an existing .py file
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise CdbError(f"Could not import {path}: {e}") from e
    return mod


def decode_text(ints, dll=None) -> str:
    """SOFiSTiK text field (array of c_int, 4 characters per int) -> str."""
    if dll is not None:
        try:
            n = len(ints)
            arr = (ctypes.c_int * n)(*list(ints))
            buf = ctypes.create_string_buffer(n * 4 + 1)
            dll.sof_lib_ps2cs(ctypes.byref(arr), ctypes.byref(buf), ctypes.sizeof(buf))
            raw = buf.value
            try:
                return raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                return raw.decode("latin-1").strip()
        except Exception:
            pass
    raw = b"".join(struct.pack("<i", int(i)) for i in ints)
    raw = raw.split(b"\0", 1)[0]
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        s = raw.decode("latin-1")
    return "".join(ch for ch in s if ch.isprintable()).strip()


class Cdb:
    """Read-only .cdb.  Interface (a test double implements the same): kexist, records, text, close."""

    BUF = 262144

    def __init__(self, path, info):
        if os.name != "nt":
            raise CdbError("Reading a .cdb needs Windows with SOFiSTiK installed.")
        if not os.path.isfile(path):
            raise CdbError(f".cdb file not found: {path}")
        if not info.get("dll"):
            raise CdbError("The SOFiSTiK CDB DLL (sof_cdb_w-20xx.dll) was not found under "
                           f"{info.get('root')}\\interfaces\\64bit.")
        self.path = os.path.abspath(path)
        for d in info["dll_dirs"]:
            try:
                os.add_dll_directory(d)
            except (AttributeError, OSError):
                pass
        try:
            self.dll = ctypes.cdll.LoadLibrary(info["dll"])
        except OSError as e:
            raise CdbError(f"Could not load {info['dll']}: {e}. Use 64-bit Python and check that "
                           f"SOFiSTiK {info.get('version', '')} is installed and licensed.") from e
        self.dll.sof_cdb_get.restype = ctypes.c_int
        self.dll.sof_cdb_kexist.restype = ctypes.c_int
        self.index = self.dll.sof_cdb_init(self.path.encode("utf-8"), 99)
        if self.index < 0:
            raise CdbError(f"SOFiSTiK could not open {self.path} (sof_cdb_init returned {self.index}). "
                           "If the project is open in SSD, Teddy or WinGRAF, close it (the .cdb may be locked) "
                           "or use 'Clean Locks', then try again.")
        self.status = self.dll.sof_cdb_status(self.index)
        self._buf = ctypes.create_string_buffer(self.BUF)
        self._cache = {}
        self.truncated = 0

    def kexist(self, kwh, kwl):
        return int(self.dll.sof_cdb_kexist(int(kwh), int(kwl)))

    def records(self, kwh, kwl, limit=50_000_000):
        """All records of key kwh/kwl as bytes.  Each key is read from the DLL once per open database
        and cached, because sof_cdb_get reads sequentially and a second pass is not documented."""
        key = (int(kwh), int(kwl))
        if key in self._cache:
            return self._cache[key]
        out = []
        idx = ctypes.c_int(self.index)
        k1, k2 = ctypes.c_int(int(kwh)), ctypes.c_int(int(kwl))
        for _ in range(limit):
            reclen = ctypes.c_int(self.BUF)          # reset the length before every sof_cdb_get
            ie = self.dll.sof_cdb_get(idx, k1, k2, ctypes.byref(self._buf), ctypes.byref(reclen), 1)
            if ie >= 2:
                break
            if ie == 1:
                self.truncated += 1
            n = max(0, min(reclen.value, self.BUF))
            out.append(self._buf.raw[:n])
        self._cache[key] = out
        return out

    def forget(self, kwh, kwl):
        self._cache.pop((int(kwh), int(kwl)), None)

    def text(self, ints):
        return decode_text(ints, self.dll)

    def close(self):
        try:
            self.dll.sof_cdb_close(0)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
