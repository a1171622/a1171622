"""Run a SOFiSTiK .dat file in batch mode with sps.exe and report what happened.

sps.exe options used (SOFiSTiK 2027 manual, "Special Features for Start", batch-only parameters):
  -B0        show nothing of the calculation on screen
  -R         do not stop the calculation on error (only when continue_on_error=True)
  -urs:xx    run only the +PROG block with urs:xx, all others inactive
The calculation writes, next to the .dat:  name.cdb (database), name.prt (protocol: errors, warnings,
programs run), name.erg (output of the whole analysis), name.plb (report browser file).

Safety (CADINP manual cadinp_1.pdf, 1.9 "Starting an Analysis"):
  * "+SYS cmd" always and "*SYS cmd" (if the last PROG was active) make SOFiSTiK run any Windows
    command.  $(name) text substitution is active on every line, so a record whose first word holds
    $(...) ("$(X) calc", "+S$(Y) calc"), a #define value starting with SYS or containing ';', and SYS
    beyond the 255-character line limit can build such a command.  Unless settings.json says
    "allow_sys_commands": true, every such line (also in files pulled in by #INCLUDE or +APPLY, three
    levels deep) refuses the run before anything starts, and so does a file that cannot be decoded for
    certain (NUL bytes, an unknown byte order mark).  The rule is deliberately broad.
  * Every file SPS could open for an #INCLUDE / +APPLY is scanned (name and name.dat, next to the
    including file and next to the main .dat); one that cannot be found or checked refuses the run.
    One outside the folders this server may read is always refused: SOFiSTiK copies included text
    into the .erg, which Claude can read.
  * Each run's sps.exe runs in its own Windows job object (made before sps.exe starts): a stop or
    time-out ends the whole job (also programs whose parent has already ended), and Windows closes it,
    killing what is left, when the server process ends.  The run is also watched, and every program
    seen below sps.exe that is still alive after a stop is ended one by one.  A <name>.mcp-running
    lock file (PC name, process numbers and start times) next to the .dat stops a second server from
    starting a calculation of the same model (other models may run alongside).
"""
from __future__ import annotations

import atexit
import datetime
import glob
import hashlib
import json
import ntpath
import os
import re
import socket
import subprocess
import sys
import threading
import time
import unicodedata

try:
    import psutil
except ImportError:                                  # pragma: no cover - psutil is in requirements.txt
    psutil = None

from . import cdblock, config, messages

CREATE_NO_WINDOW = 0x08000000
RESULT_EXTS = (".cdb", ".prt", ".erg", ".plb", ".lst")
SCAN_MAX_BYTES = 50_000_000            # the most messages.read_text reads; bigger files are refused
INCLUDE_DEPTH = 3
CONSOLE_TAIL_BYTES = 64 * 1024         # sps.exe console output kept (the end of it)
LOCK_EXT = ".mcp-running"

# --- line rules (applied to a cleaned copy of each line, see _clean) ---------------------------------
# +SYS / *SYS (any spelling, also +SYSTEM: sps may only look at the first letters) and a bare SYS word
SYS_RE = re.compile(r"^\s*(?:[+*]\s*sys|sys(?![a-z0-9_]))", re.IGNORECASE)
# a record whose first word (after an optional + / * sign) is built, wholly or partly, by $(...)
# substitution: "$(X) calc", "+S$(Y) calc" with Y = YS, "+SY$(UNDEFINED)S", "*S$(NAME)" ...
DOLLAR_FIRST_RE = re.compile(r"^\s*[+*]?\s*[^\s;]*\$\(")
FIRST_WORD_RE = re.compile(r"^\s*[+*]?\s*([^\s;]*)")
DEFINE_RE = re.compile(r"^\s*#\s*define\s+([^\s=]+)\s*(?:=(.*))?$", re.IGNORECASE)
ENDDEF_RE = re.compile(r"^\s*#\s*enddef\b", re.IGNORECASE)
UNDEF_RE = re.compile(r"^\s*#\s*undef\s+(\S+)", re.IGNORECASE)
BLOCK_OLD_RE = re.compile(r"^\s*\$\s*block\b", re.IGNORECASE)          # old $BLOCK BEG/END/SET form
# #INCLUDE and APPLY, also abbreviated to their first four letters (#INCL, APPL: CADINP compares the first
# four characters of a name, cadinp_1.pdf 1.1.4; the manual gives no shorter form), with or without the
# + sign (and *, which is not documented for APPLY but costs nothing to follow).  -APPLY is skipped by SPS.
INCLUDE_RE = re.compile(r"^\s*(?:#\s*incl\w*|[+*]?\s*appl\w*)\s+(.+)$", re.IGNORECASE)
# +PROG name and, as in the manual's examples (cadinp_1 p. 1-2), PROG name without the sign
PROG_RE = re.compile(r"^\s*(?:\+\s*)?prog(?:\s+(\S+)(.*))?$", re.IGNORECASE)
REF_RE = re.compile(r"\$\(([^()$]*)\)")
COMMENT_LINE_RE = re.compile(r"^\s*(?:\$(?:\s|$)|!|//)")
SAFE_VALUE_RE = re.compile(r"^[0-9.\s+\-*/(),eE]*$")
# a #define value that puts SYS into the first word of a record: "+SYS", "*sys", "SYSTEM", "X+SYS"
VALUE_SYS_RE = re.compile(r"^\s*[+*]?\s*[^\s;]*sys", re.IGNORECASE)
# CADINP: "Each line contains up to 255 characters" (cadinp_1.pdf 1.1.1).  What SPS does with the rest of
# a longer line is not documented (cut off, or read as a new line?), so SYS after it refuses the run.
LINE_LIMIT = 255
_BLANK_CATEGORIES = {"Zs", "Zl", "Zp", "Cc", "Cf"}


def _clean(line: str) -> str:
    """The line as SPS might see it: compatibility forms folded (NFKC), every Unicode space, control
    or invisible format character (NBSP, \\v, \\f, BOM, zero-width space ...) turned into a blank."""
    line = unicodedata.normalize("NFKC", line)
    return "".join(" " if (ch.isspace() or unicodedata.category(ch) in _BLANK_CATEGORIES) else ch
                   for ch in line)


def _strip_value_comment(v: str) -> str:
    return re.split(r"\s(?:\$|!|//)(?:\s|$)", " " + v)[0].strip()


def _beyond_line_limit(line: str, enc: str = "utf-8") -> str:
    """The part of line after its first LINE_LIMIT bytes in enc (UTF-8 for UTF-8 and cp1252 files: never
    fewer bytes than characters, so both readings are covered), with two characters before it; '' for a
    line within the limit."""
    n = 0
    for i, ch in enumerate(line):
        n += len(ch.encode(enc, "surrogatepass"))
        if n > LINE_LIMIT:
            return line[max(0, i - 2):]
    return ""


def sys_lines_in_text(text: str, file: str, readable=None) -> list[dict]:
    """+SYS-like lines of a text about to be written as `file` (write_dat_file), with the same rules as
    scan_dat.  Include files that already exist are read too (their #define values count for the
    $(...) rule; their own +SYS lines are reported as well); missing ones do not matter here."""
    sc = _Scanner(main=file, readable=readable)
    sc.seen.add(os.path.normcase(os.path.realpath(os.path.abspath(file))))     # not the old version of itself
    sc.scan_text(text, file, depth=INCLUDE_DEPTH)
    return sc.out["sys_lines"]


class _Scanner:
    def __init__(self, main: str, readable, max_bytes: int | None = None):
        self.main = main
        self.main_dir = os.path.dirname(os.path.abspath(main))
        self.stem = os.path.splitext(os.path.basename(main))[0]
        self.readable = readable
        self.max_bytes = SCAN_MAX_BYTES if max_bytes is None else max_bytes
        self.seen: set = set()
        self.blocks: set = set()               # #define NAME ... #enddef blocks in memory
        self.defines: dict = {}                # name -> [values] of the definitions read so far (scan order)
        self.out: dict = {"sys_lines": [], "programs": [], "includes": [], "missing_includes": [],
                          "blocked_includes": [], "hashes": {}}

    # -- files ------------------------------------------------------------------------------------
    def _blocked(self, name, path, why, kind):
        self.out["blocked_includes"].append({"include": name, "file": path, "why": why, "kind": kind})

    def scan_file(self, path: str, depth: int, name: str | None = None) -> None:
        key = os.path.normcase(os.path.realpath(os.path.abspath(path)))
        if key in self.seen:
            return
        self.seen.add(key)
        label = name or path
        if os.path.isdir(path):
            self._blocked(label, path, "it is a folder, not a file", "unscannable")
            return
        if self.readable is not None and not config.is_inside(path, self.readable):
            self._blocked(label, path, "it is outside the folders this server may read (SOFiSTiK copies "
                                       "included text into the .erg)", "outside")
            return
        try:
            size = os.path.getsize(path)
            if size > self.max_bytes:
                self._blocked(label, path, f"it is too big to check ({size / 1e6:.0f} MB, the limit is "
                                           f"{self.max_bytes / 1e6:.0f} MB)", "unscannable")
                return
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            self._blocked(label, path, f"it cannot be read ({e.strerror or e})", "unscannable")
            return
        self.out["hashes"][path] = hashlib.sha256(raw).hexdigest()
        try:
            text, enc = messages.decode_input(raw)
        except ValueError as e:
            self._blocked(label, path, str(e), "unscannable")
            return
        self.scan_text(text, path, depth, enc=enc)

    # -- lines ------------------------------------------------------------------------------------
    def _flag(self, file, line_no, original, why):
        self.out["sys_lines"].append({"file": file, "line": line_no,
                                      "text": original.strip().lstrip("\ufeff").replace("\x00", "")[:300],
                                      "why": why})

    def _safe_ref(self, ref: str, stack=()) -> bool:
        """True if $(ref) can only expand to numbers: it is defined before this line (scan order) and
        every definition read so far is numeric."""
        key = ref.strip().casefold()
        if key in stack or key not in self.defines:
            return False
        for v in self.defines[key]:
            v = _strip_value_comment(v)
            for inner in REF_RE.findall(v):
                if not self._safe_ref(inner, stack + (key,)):
                    return False
            if not SAFE_VALUE_RE.match(REF_RE.sub("", v)):
                return False
        return True

    def _dollar_record_is_safe(self, seg: str) -> bool:
        """A record whose first word holds $(...): safe only when no letter is glued to the references in
        that first word (only digits and signs such as "#(" ",9.3)") and every reference in the record is
        numeric, defined before this line: "$(NRQ)  1  2" table rows and "#($(sig_x1),9.3)" report
        lines of the shipped examples.  Numbers and signs can never spell SYS or a command."""
        fw = FIRST_WORD_RE.match(seg)
        if not fw or re.search(r"[^\W\d_]", REF_RE.sub("", fw.group(1))):
            return False
        literal = REF_RE.sub("", seg)
        return ("$(" not in literal and "sys" not in literal.casefold()
                and all(self._safe_ref(r) for r in REF_RE.findall(seg)))

    def scan_text(self, text: str, file: str, depth: int, follow: bool = True, enc: str = "utf-8") -> None:
        for i, original in enumerate(text.split("\n")):
            n = i + 1
            if "\x00" in original:
                self._flag(file, n, original, "NUL character (SOFiSTiK may read this line differently)")
                continue
            if "sys" in _clean(_beyond_line_limit(original, enc)).casefold():
                self._flag(file, n, original, f"line longer than {LINE_LIMIT} characters with SYS after character "
                                              f"{LINE_LIMIT} (CADINP lines have at most {LINE_LIMIT} characters; "
                                              "what SOFiSTiK does with the rest is not known)")
                continue
            ln = _clean(original)
            if not ln.strip():
                continue
            m = DEFINE_RE.match(ln)
            if m:
                dname, value = m.group(1).casefold(), m.group(2)
                if value is None:                       # start of a block definition (lines are scanned too)
                    self.blocks.add(dname)
                else:
                    self.defines.setdefault(dname, []).append(value)
                    if ";" in value:
                        self._flag(file, n, original, "#define value containing ';' ($(...) substitution can start "
                                                      "a new record with it)")
                    elif VALUE_SYS_RE.match(_strip_value_comment(value)):
                        self._flag(file, n, original, "#define value starting with SYS ($(...) substitution can "
                                                      "turn it into a +SYS command)")
                continue
            if ENDDEF_RE.match(ln):
                continue
            m = UNDEF_RE.match(ln)
            if m:
                self.blocks.discard(m.group(1).casefold())
                continue
            if BLOCK_OLD_RE.match(ln):
                if "sys" in ln.casefold():
                    self._flag(file, n, original, "old $BLOCK line containing SYS")
                continue
            if COMMENT_LINE_RE.match(ln):
                continue
            segs = ln.split(";")
            for seg in segs:
                if SYS_RE.match(seg):
                    self._flag(file, n, original, "+SYS / *SYS operating system command")
                    break
                if DOLLAR_FIRST_RE.match(seg) and not self._dollar_record_is_safe(seg):
                    self._flag(file, n, original, "record whose first word is built by $(...) substitution, "
                                                  "which could make a +SYS command")
                    break
            m = PROG_RE.match(ln)
            if m and m.group(1):
                prog = m.group(1)
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", prog):
                    self._flag(file, n, original, "PROG with a program name that is not a plain name")
                else:
                    urs = re.search(r"urs\s*:\s*(\d+)", m.group(2) or "", re.IGNORECASE)
                    self.out["programs"].append({"program": prog.upper(), "urs": int(urs.group(1)) if urs else None,
                                                 "file": os.path.basename(file), "line": n})
                continue
            if not follow:
                continue
            for seg in segs:                          # "END;+APPLY x": every record of the line
                m = INCLUDE_RE.match(seg)
                if m:
                    self.include(m.group(1), file, depth)

    def include(self, arg: str, including: str, depth: int) -> None:
        name = re.split(r"\s\$(?:\s|$)|\s//|[;!]", arg)[0].strip().strip("\"'").strip()
        if not name:
            return
        is_block = name.casefold() in self.blocks
        if depth <= 0:
            if not is_block:
                # deeper includes are not scanned, so they are reported as missing and the run is refused
                self.out["missing_includes"].append(
                    f"{name} (nested more than {INCLUDE_DEPTH} levels deep in {os.path.basename(including)})")
            return
        resolved = name
        if re.search(r"\$\(\s*name\s*\)", resolved, re.IGNORECASE) and "name" not in self.defines:
            resolved = re.sub(r"\$\(\s*name\s*\)", lambda _m: self.stem, resolved, flags=re.IGNORECASE)
        shown = name if resolved == name else f"{name} (= {resolved})"
        if "$(" in resolved or re.match(r"^[A-Za-z]:(?![\\/])", resolved):
            if not is_block:
                self.out["missing_includes"].append(name)
            return
        names = [resolved] + ([resolved + ".dat"] if not resolved.lower().endswith(".dat") else [])
        if os.path.isabs(resolved) or ntpath.isabs(resolved):
            cands = names
        else:
            dirs: list[str] = []
            for d in (os.path.dirname(os.path.abspath(including)), self.main_dir):
                if os.path.normcase(d) not in (os.path.normcase(x) for x in dirs):
                    dirs.append(d)
            cands = [os.path.join(d, x) for d in dirs for x in names]
        found, keys = [], set()
        for c in cands:
            if os.path.exists(c):
                k = os.path.normcase(os.path.realpath(c))
                if k not in keys:
                    keys.add(k)
                    found.append(c)
        if not found:
            if not is_block:
                self.out["missing_includes"].append(shown)
            return
        for c in found:                      # SPS may open any of them: check every one
            self.out["includes"].append(c)
            self.scan_file(c, depth - 1, name)


def scan_dat(path: str, depth: int = INCLUDE_DEPTH, readable=None, max_bytes: int | None = None) -> dict:
    """+SYS-like lines, active PROG blocks and included files of a .dat (follows #INCLUDE / +APPLY).

    readable: folders includes must be inside (None: not checked).  Returns sys_lines, programs,
    includes, missing_includes, blocked_includes ({include, file, why, kind: outside|unscannable})
    and hashes ({path: sha256} of every file read, for the changed-during-run check)."""
    sc = _Scanner(path, readable, max_bytes)
    sc.scan_file(path, depth)
    return sc.out


def _sha(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------
# processes: Windows job object / POSIX process group, lock files
# ------------------------------------------------------------------------------------------------

_ACTIVE: set = set()          # running sps processes (killed when the server exits)
_ACTIVE_LOCK = threading.Lock()   # held from Popen until the process is in _ACTIVE (and at exit)
_LOCKS: set = set()           # lock files this server process wrote
_RUN_JOBS: list = []          # the job object of every run, kept open until the server process ends
HOST = socket.gethostname() or "?"


class _NoJob:
    """Stand-in where there is no Win32 job object (POSIX, or creating one failed): a stop falls back to
    killing the process group (POSIX) or taskkill /T (Windows)."""
    handle = None

    def __init__(self, error: str | None = None):
        self.error = error
        self.assigned = False

    def assign(self, proc) -> str | None:
        return self.error

    def terminate(self) -> bool:
        return False


# Each branch runs (and is tested) only on its own OS, so neither counts for coverage; the Windows
# branch is exercised by tests/test_review_safety.py on windows-latest in CI.
if sys.platform == "win32":  # pragma: no cover
    import ctypes
    from ctypes import wintypes

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _STILL_ACTIVE = 259

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                      "OtherOperationCount", "ReadTransferCount",
                                                      "WriteTransferCount", "OtherTransferCount")]

    class _BASIC_LIMIT(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BASIC_LIMIT), ("IoInfo", _IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                               wintypes.LPVOID]
    _k32.QueryInformationJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    _k32.IsProcessInJob.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _k32.GetExitCodeProcess.restype = wintypes.BOOL
    _k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    _k32.GetProcessTimes.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL

    class _Job(_NoJob):
        """A Win32 job object for one run, made before sps.exe starts.  Every process sps.exe starts is
        in it too (also when its own parent has ended), so TerminateJobObject stops them all.  The handle
        stays open until the server process ends: Windows then closes it, and KILL_ON_JOB_CLOSE ends every
        process still in the job (also when the server is killed outright)."""

        def __init__(self):
            super().__init__()
            h = _k32.CreateJobObjectW(None, None)
            if not h:
                self.error = f"CreateJobObject failed ({ctypes.get_last_error()})"
                return
            info = _EXTENDED_LIMIT()
            info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _k32.SetInformationJobObject(h, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                                ctypes.byref(info), ctypes.sizeof(info)):
                self.error = f"SetInformationJobObject failed ({ctypes.get_last_error()})"
                _k32.CloseHandle(h)
                return
            self.handle = h
            _RUN_JOBS.append(self)

        def assign(self, proc) -> str | None:
            if self.handle is None:
                return self.error
            h = _k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, proc.pid)
            if not h:
                return f"OpenProcess failed ({ctypes.get_last_error()})"
            try:
                if not _k32.AssignProcessToJobObject(self.handle, h):
                    return f"AssignProcessToJobObject failed ({ctypes.get_last_error()})"
            finally:
                _k32.CloseHandle(h)
            self.assigned = True
            return None

        def terminate(self) -> bool:
            """Kill every process in the job.  False if sps.exe is not in it (then taskkill is used)."""
            return bool(self.assigned and self.handle and _k32.TerminateJobObject(self.handle, 1))

    def _new_job() -> _NoJob:
        return _Job()

    def pid_alive(pid: int) -> bool:
        h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ctypes.get_last_error() == 5           # access denied: it exists
        try:
            code = wintypes.DWORD()
            return bool(_k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == _STILL_ACTIVE
        finally:
            _k32.CloseHandle(h)

    def proc_start_time(pid: int) -> int | None:
        """Creation time of process pid (100 ns since 1601), None if it cannot be read."""
        h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            t = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
                return None
            return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
        finally:
            _k32.CloseHandle(h)

    def _popen_kw() -> dict:
        return {"creationflags": CREATE_NO_WINDOW}

    def _kill_group(proc) -> None:
        job = getattr(proc, "_mcp_job", None)
        if job is not None and job.terminate():
            return
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
else:  # pragma: no cover
    import signal

    def _new_job() -> _NoJob:
        return _NoJob()                                      # start_new_session + atexit (below)

    def pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def proc_start_time(pid: int) -> int | None:
        """Start time of process pid in clock ticks after boot (Linux /proc), None if not known."""
        try:
            with open(f"/proc/{int(pid)}/stat", encoding="ascii", errors="replace") as f:
                return int(f.read().rsplit(")", 1)[1].split()[19])
        except (OSError, IndexError, ValueError):
            return None

    def _popen_kw() -> dict:
        return {"start_new_session": True}

    def _kill_group(proc) -> None:
        job = getattr(proc, "_mcp_job", None)
        if job is not None and job.terminate():
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)              # sps and everything it started
        except (ProcessLookupError, PermissionError):
            proc.kill()


def _kill_tree(proc):
    """Stop sps.exe and everything it started.  The job object (or taskkill) does most of it; every
    program the run's watcher saw is then ended too if it is still there, because a program that left
    the job (seen on SOFiSTiK 2027: BDK outlived a stopped run and kept the .cdb locked) would
    otherwise keep running.  What is still alive after that is kept in proc._mcp_survivors."""
    watch = getattr(proc, "_mcp_watch", None)
    if watch is not None:
        watch.snapshot()                                    # the tree while its parents still exist
    try:
        _kill_group(proc)
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
    if watch is not None:
        setattr(proc, "_mcp_survivors", watch.end_all())    # noqa: B010


POLL_S = 3.0
WRAPPERS = {"sps", "wpsjob", "conhost"}


class _Watch:
    """Follows one run while it goes: every program below sps.exe (for a complete stop), the RAM of the
    whole run (and its peak), the program running now, and the programs the .prt has started so far
    with the time each one took (for the dashboard's run-time estimate).  Never fails the run."""

    def __init__(self, proc, prt: str | None = None, prt_mtime_before: int | None = None, on_tick=None):
        self.proc, self.prt, self._prt_before, self.on_tick = proc, prt, prt_mtime_before, on_tick
        self.seen: dict = {}                     # pid -> (create_time, name)
        self.ram_mb = self.peak_ram_mb = 0
        self.module: str | None = None
        self.timeline: list[dict] = []           # [{"program", "t0", "t1"}] in the order the .prt shows them
        self._offset = 0
        self._partial = b""
        self._root = None
        self._stop = threading.Event()
        self._mutex = threading.Lock()
        if psutil is not None:
            try:
                self._root = psutil.Process(proc.pid)
            except Exception:
                self._root = None
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> _Watch:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(POLL_S + 2)
        self.tick()                              # last look at the .prt (the final Stop lines)

    def _loop(self) -> None:
        while not self._stop.wait(POLL_S):
            self.tick()

    def tick(self) -> None:
        try:
            self.snapshot()
            self._read_prt()
        except Exception:                        # pragma: no cover - never let the watcher fail a run
            pass
        if self.on_tick is not None:
            try:
                self.on_tick(self)
            except Exception:
                pass

    def snapshot(self) -> list:
        """Record the run's programs now; -> the live descendants (psutil.Process)."""
        if self._root is None:
            return []
        with self._mutex:
            try:
                kids = self._root.children(recursive=True)
            except Exception:
                kids = []
            ram = 0
            newest = None
            for k in [self._root] + kids:
                try:
                    ct = k.create_time()
                    name = k.name()
                    ram += k.memory_info().rss
                except Exception:
                    continue
                if k is not self._root:
                    self.seen[k.pid] = (ct, name)
                    base = os.path.splitext(name)[0].lower()
                    if base not in WRAPPERS and (newest is None or ct >= newest[0]):
                        newest = (ct, os.path.splitext(name)[0].upper())
            self.ram_mb = round(ram / 2**20)
            self.peak_ram_mb = max(self.peak_ram_mb, self.ram_mb)
            self.module = newest[1] if newest else None
            return kids

    def _read_prt(self) -> None:
        if not self.prt:
            return
        try:
            st = os.stat(self.prt)
        except OSError:
            return
        if self._prt_before is not None and st.st_mtime_ns <= self._prt_before:
            return                               # still the protocol of the previous run
        if st.st_size < self._offset:            # rewritten (sps.exe retried): start again
            self._offset, self._partial, self.timeline = 0, b"", []
        if st.st_size == self._offset:
            return
        with open(self.prt, "rb") as f:
            f.seek(self._offset)
            chunk = f.read(4_000_000)
        self._offset += len(chunk)
        data = self._partial + chunk
        cut = data.rfind(b"\n") + 1
        self._partial = data[cut:]
        now = time.time()
        for line in data[:cut].decode("latin-1").splitlines():
            m = messages.START_RE.match(line)
            if m and not m.group(1).lower().startswith("calculation"):
                if self.timeline and self.timeline[-1]["t1"] is None:
                    self.timeline[-1]["t1"] = now
                self.timeline.append({"program": m.group(1).split()[0].upper(), "t0": now, "t1": None})
            elif messages.STOP_RE.match(line) and self.timeline and self.timeline[-1]["t1"] is None:
                self.timeline[-1]["t1"] = now

    def modules(self) -> list[dict]:
        """[{"program", "seconds"}] of the programs that finished, in order."""
        return [{"program": t["program"], "seconds": round(t["t1"] - t["t0"], 1)}
                for t in self.timeline if t["t1"] is not None]

    def leftovers(self, names=None) -> list[dict]:
        """Programs of this run that are still alive (optionally only those with these base names)."""
        out = []
        for pid, (ct, name) in list(self.seen.items()):
            if names is not None and os.path.splitext(name)[0].lower() not in names:
                continue
            try:
                p = psutil.Process(pid)
                if abs(p.create_time() - ct) <= 1 and p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    out.append({"pid": pid, "name": name, "proc": p})
            except Exception:
                continue
        return out

    def end_all(self, names=None) -> list[dict]:
        """End every program of this run still alive; -> those that could not be ended."""
        if psutil is None:                       # pragma: no cover
            return []
        left = self.leftovers(names)
        for x in left:
            try:
                x["proc"].kill()
            except Exception:
                pass
        if not left:
            return []
        _, alive = psutil.wait_procs([x["proc"] for x in left], timeout=10)
        alive_pids = {p.pid for p in alive}
        return [{"pid": x["pid"], "name": x["name"]} for x in left if x["pid"] in alive_pids]


def kill_tree_async(proc) -> threading.Thread:
    """Start _kill_tree in the background (stop_calculation answers at once)."""
    t = threading.Thread(target=_kill_tree, args=(proc,), daemon=True)
    t.start()
    return t


@atexit.register
def _cleanup_at_exit():
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE)
    for proc in procs:
        if proc.poll() is None:
            _kill_tree(proc)
    for lock in list(_LOCKS):
        _remove(lock)


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
    _LOCKS.discard(path)


# --- lock files ----------------------------------------------------------------------------------
# <name>.mcp-running holds one JSON line: {"host": PC name, "procs": [[pid, start time], ...] (the server,
# then sps.exe), "started": local time}.  Older servers wrote only the process numbers.

def _lock_content(pids) -> str:
    return json.dumps({"host": HOST, "procs": [[p, proc_start_time(p)] for p in pids],
                       "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}) + "\n"


def _read_lock(path) -> dict | None:
    """{host (None in an old lock), procs [[pid, start or None]], started} or None if unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(4096)
    except OSError:
        return None
    try:
        d = json.loads(text)
        procs = [[int(p[0]), None if p[1] is None else int(p[1])] for p in d.get("procs", [])]
        return {"host": str(d["host"]) if d.get("host") else None, "procs": procs, "started": d.get("started")}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {"host": None, "procs": [[int(x), None] for x in re.findall(r"\d+", text)[:2]], "started": None}


def _lock_holder(path: str, info: dict | None) -> str | None:
    """Why the lock is live ('another PC' / 'running'), or None when it is stale."""
    if info is not None and info["host"] and info["host"].casefold() != HOST.casefold():
        return "another PC"                    # its processes cannot be checked from here: never stale
    procs = info["procs"] if info else []
    if not procs:                              # being written by another server right now, or garbage
        try:
            return "running" if time.time() - os.path.getmtime(path) < 10 else None
        except OSError:
            return None
    me = os.getpid()
    for pid, start in procs:
        now = proc_start_time(pid) if start is not None else None
        if pid == me and (start is None or now in (None, start)):
            if path in _LOCKS:
                return "running"               # this server's own run
            continue
        if pid_alive(pid) and (start is None or now is None or now == start):
            return "running"                   # alive, and not a later process that got the same number
    return None


def lock_message(path: str, info: dict | None, what: str = "Another calculation of this model is running") -> str:
    name = os.path.basename(path)
    if info is not None and info["host"] and info["host"].casefold() != HOST.casefold():
        return (f"{what}, started from the PC '{info['host']}'" + (f" at {info['started']}" if info["started"]
                                                                   else "") +
                f" (lock file {path}). This server cannot see that PC's programs, so it never removes this lock "
                f"by itself. If nothing is running on '{info['host']}' any more, delete {name} by hand.")
    return (f"{what} ({name}, started by another Claude window or server). Wait for it to finish, or delete "
            "the lock file if you are sure nothing is running.")


def live_lock(folder: str, skip: str | None = None, stem: str | None = None) -> tuple[str, dict | None] | None:
    """(path, contents) of a lock file in folder that is still live (stale ones are removed).
    stem: only the lock of that model (<stem>.mcp-running) counts, so different models in one folder
    can run at the same time; else any lock in the folder."""
    mine = os.path.normcase(stem + LOCK_EXT) if stem else None
    for p in sorted(glob.glob(os.path.join(glob.escape(folder), "*" + LOCK_EXT))):
        if skip is not None and os.path.normcase(p) == os.path.normcase(skip):
            continue
        info = _read_lock(p)
        if _lock_holder(p, info):
            if mine is None or os.path.normcase(os.path.basename(p)) == mine:
                return p, info
            continue                               # another model's calculation: may run alongside
        if skip is None:
            _remove(p)
    return None


def _write_lock(path: str, pids) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_lock_content(pids))


# ------------------------------------------------------------------------------------------------
# running sps.exe
# ------------------------------------------------------------------------------------------------

def _launch(cmd, folder, timeout_s, on_start, cap: int = CONSOLE_TAIL_BYTES, watch_kw: dict | None = None):
    """Start sps.exe in a new job object, wait for it (killing the whole process tree on timeout;
    timeout_s None: no time limit).  A _Watch follows the run (proc._mcp_watch).
    -> (proc, output tail, timed_out, containment problem or None)"""
    try:
        job = _new_job()                                    # before sps.exe exists
    except Exception as e:                                  # never fail the run over it
        job = _NoJob(f"{type(e).__name__}: {e}")
    with _ACTIVE_LOCK:
        proc = subprocess.Popen(cmd, cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, **_popen_kw())
        _ACTIVE.add(proc)
    setattr(proc, "_mcp_job", job)                          # noqa: B010 - Popen has no such attribute
    try:
        problem = job.assign(proc)
    except Exception as e:
        problem = f"{type(e).__name__}: {e}"
    buf = bytearray()
    stdout = proc.stdout
    assert stdout is not None

    def pump():
        fd = stdout.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > 2 * cap:
                del buf[:-cap]
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    watch = _Watch(proc, **(watch_kw or {}))
    setattr(proc, "_mcp_watch", watch)                      # noqa: B010
    watch.start()
    if on_start:
        on_start(proc)
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        timed_out = True
    finally:
        _ACTIVE.discard(proc)
        watch.stop()
    if not timed_out and not hasattr(proc, "_mcp_survivors"):
        # sps.exe ended by itself: a calculation program still running now has left the run (it would
        # keep the .cdb locked), so it is given a moment and then ended.
        if watch.leftovers(cdblock.CALC_NAMES):
            time.sleep(3)
            left = [{"pid": x["pid"], "name": x["name"]} for x in watch.leftovers(cdblock.CALC_NAMES)]
            if left:
                setattr(proc, "_mcp_leftovers", left)           # noqa: B010
                setattr(proc, "_mcp_survivors", watch.end_all(cdblock.CALC_NAMES))  # noqa: B010
    reader.join(10)
    if not reader.is_alive():
        try:
            stdout.close()
        except Exception:
            pass
    return proc, bytes(buf[-cap:]), timed_out, problem


def _stat_ns(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


OK_STATUSES = ("ok", "ok with warnings")


def _left(timeout_s: float | None, t0: float) -> float | None:
    """What is left of the time limit (None: no limit)."""
    return None if timeout_s is None else max(1.0, timeout_s - (time.time() - t0))


def _pre_run_lock(cdb: str, root: str | None, auto_clear: bool) -> dict:
    """Look at who holds the model's .cdb before SOFiSTiK opens it.
    -> {} when nothing holds it, else a report with "ended" (orphans ended), "refuse" (a live
    calculation holds it: do not start) or "warning"."""
    if psutil is None or not os.path.isfile(cdb):
        return {}
    try:
        info = cdblock.check(cdb, root)
    except Exception as e:                       # never fail a run over the check itself
        return {"warning": f"Could not check whether the .cdb is locked ({type(e).__name__}: {e})."}
    if not info["locked"]:
        return {}
    kinds = {h["kind"] for h in info["holders"]}
    rep: dict = {"holders": info["holders"]}
    if "run" in kinds:
        rep["refuse"] = ("The database " + os.path.basename(cdb) + " is in use by a calculation that is still "
                         "running: " + " ".join(info["advice"]))
        return rep
    if "orphan" in kinds and auto_clear:
        c = cdblock.clear(cdb, root)
        rep.update(ended=c["ended"], failed=c["failed"], locked_now=c["locked_now"])
        info = {"advice": c["advice"], "locked": c["locked_now"]}
    if info["locked"]:
        rep["warning"] = ("The database " + os.path.basename(cdb) + " is open in another program, so SOFiSTiK may "
                          "not be able to write it: " + " ".join(info["advice"]))
    return rep


LOCK_WAIT_RE = re.compile(r"WAIT\s+FOR\s+LOCK\s+ABORTED", re.IGNORECASE)


def _lock_abort(out: bytes, prt: str, fresh) -> bool:
    """Did SOFiSTiK give up because the .cdb was locked ("CDBASE: WAIT FOR LOCK ABORTED BY USER") and
    the run did not finish cleanly?  A run that waited for a lock and then went on is not one."""
    hit = bool(LOCK_WAIT_RE.search((out or b"").decode("latin-1")) or
               (fresh(prt) and LOCK_WAIT_RE.search(messages.read_text(prt))))
    if not hit:
        return False
    return messages.summarize_run(prt if fresh(prt) else None).get("status") not in OK_STATUSES


def run(dat_path: str, sps: str, timeout_s: float | None, allow_sys: bool = False,
        continue_on_error: bool = False, only_urs: int | None = None, on_start=None,
        stopped=lambda: False, readable=None, on_tick=None, sofistik_root: str | None = None,
        auto_clear_locks: bool = True, on_scan=None, clean_cmd: str = "") -> dict:
    """Run sps.exe on dat_path (already access-checked) and return a summary dict.
    on_start(proc) is called with the running process; stopped() tells whether the caller killed it.
    readable: folders an #INCLUDE / +APPLY file must be in (None: not checked).
    timeout_s None: no time limit.  on_tick(watch) is called every few seconds while it runs.
    auto_clear_locks: end SOFiSTiK programs left behind by a stopped run that still hold this model's
    .cdb (before the run); if SOFiSTiK still reports "WAIT FOR LOCK", also reset the locks stored in the
    .cdb with SOFiSTiK's Clean Locks (clean_cmd: its command, "" = found in the registry) and run once more.
    on_scan(scan) gets the input check (its files) before the run starts."""
    if not os.path.isfile(dat_path):
        return {"status": "not run", "reason": f".dat file not found: {dat_path}"}
    if not dat_path.lower().endswith(".dat"):
        return {"status": "not run", "reason": "Only .dat files can be run."}
    bad = config.bad_file_name(dat_path)
    if bad:
        return {"status": "not run", "reason": bad}
    if not sps or not os.path.isfile(sps):
        return {"status": "not run", "reason": f"sps.exe not found ({sps}). Set \"sofistik_dir\" in settings.json."}
    folder, name = os.path.split(dat_path)
    stem = os.path.splitext(name)[0]
    held = live_lock(folder, stem=stem)
    if held:
        return {"status": "not run", "lock_file": held[0], "lock_host": (held[1] or {}).get("host"),
                "reason": lock_message(*held)}
    scan = scan_dat(dat_path, readable=readable)
    outside = [b for b in scan["blocked_includes"] if b["kind"] == "outside"]
    if outside:
        return {"status": "not run",
                "reason": "These #INCLUDE / +APPLY files are outside the folders this server may read, and SOFiSTiK "
                          "copies included text into the .erg: " + ", ".join(b["file"] for b in outside) +
                          ". Copy them into the work folder, or add their folder to \"read_folders\".",
                "blocked_includes": scan["blocked_includes"]}
    if scan["sys_lines"] and not allow_sys:
        return {"status": "not run",
                "reason": "The input contains lines that can make SOFiSTiK run Windows commands (+SYS / *SYS, or "
                          "$(...) substitution that could build one). They are blocked by settings.json "
                          "(\"allow_sys_commands\": false). Remove them; if the engineer really means to run "
                          "them, they can set \"allow_sys_commands\": true in settings.json and restart Claude.",
                "sys_lines": scan["sys_lines"]}
    unscannable = [b for b in scan["blocked_includes"] if b["kind"] != "outside"]
    if unscannable and not allow_sys:
        return {"status": "not run",
                "reason": "These #INCLUDE / +APPLY files could not be checked for +SYS commands: " +
                          "; ".join(f"{b['file']} ({b['why']})" for b in unscannable) + ".",
                "blocked_includes": scan["blocked_includes"]}
    if scan["missing_includes"] and not allow_sys:
        return {"status": "not run",
                "reason": "These #INCLUDE / +APPLY files could not be found next to the .dat, so they could not "
                          "be checked for +SYS commands: " + ", ".join(scan["missing_includes"]) +
                          ". Give their full path or copy them next to the .dat.",
                "missing_includes": scan["missing_includes"]}
    if not scan["programs"]:
        return {"status": "not run", "reason": "No active PROG / +PROG block found in the file (or its includes)."}
    if on_scan is not None:
        on_scan(scan)

    prt = os.path.join(folder, stem + ".prt")
    erg = os.path.join(folder, stem + ".erg")
    before = {ext: _stat_ns(os.path.join(folder, stem + ext)) for ext in RESULT_EXTS}
    cdb_before = before[".cdb"] is not None
    opts = ["-B0"]
    if continue_on_error:
        opts.append("-R")
    if only_urs is not None:
        opts.append(f"-urs:{int(only_urs)}")

    def fresh(p):
        """Written by this run: exists and newer than before the start."""
        now, old = _stat_ns(p), before.get(os.path.splitext(p)[1].lower())
        return now is not None and (old is None or now > old)

    lock_path = os.path.join(folder, stem + LOCK_EXT)
    server_warnings: list[str] = []
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, _lock_content([os.getpid()]).encode("utf-8"))
        finally:
            os.close(fd)
    except FileExistsError:
        return {"status": "not run", "lock_file": lock_path,
                "reason": f"{os.path.basename(lock_path)} appeared just now: another calculation is starting here."}
    _LOCKS.add(lock_path)
    try:
        other = live_lock(folder, skip=lock_path, stem=stem)
        if other:
            return {"status": "not run", "lock_file": other[0], "lock_host": (other[1] or {}).get("host"),
                    "reason": lock_message(*other, what="Another calculation of this model started at the same "
                                                        "moment")}
        cdb = os.path.join(folder, stem + ".cdb")
        lock_report = _pre_run_lock(cdb, sofistik_root, auto_clear_locks)
        if lock_report.get("refuse"):
            return {"status": "not run", "reason": lock_report["refuse"], "cdb_lock": lock_report}
        if lock_report.get("warning"):
            server_warnings.append(lock_report["warning"])
        watch_kw = {"prt": prt, "prt_mtime_before": before[".prt"], "on_tick": on_tick}

        def started(proc):
            try:
                _write_lock(lock_path, [os.getpid(), proc.pid])
            except OSError:
                pass
            if on_start:
                on_start(proc)
            if stopped():                  # stop asked for before sps.exe existed
                kill_tree_async(proc)

        t0 = time.time()
        cmd = [sps] + opts + [name]
        proc, out, timed_out, problem = _launch(cmd, folder, timeout_s, started, watch_kw=watch_kw)
        if problem:
            server_warnings.append("sps.exe could not be tied to the server (" + problem + "): if the server is "
                                   "closed during the run, the calculation may keep running.")
        retried = None
        if not timed_out and not stopped() and not fresh(prt) and time.time() - t0 < 120:
            # The order of options and file name for sps.exe is not documented: try file name first once.
            first = cmd
            cmd = [sps, name] + opts
            proc, out2, timed_out, _ = _launch(cmd, folder, _left(timeout_s, t0), started, watch_kw=watch_kw)
            out = (out or b"") + (out2 or b"")
            retried = (f"sps.exe wrote no protocol with {' '.join(first[1:])}, so it was retried with the file "
                       f"name first: {' '.join(cmd[1:])}")
        # sps.exe writes the protocol as it goes; give the file system a moment to show the last lines
        deadline = time.time() + 15
        while not timed_out and not stopped() and time.time() < deadline:
            if fresh(prt) and messages.END_RE.search(messages.read_text(prt)):
                break
            time.sleep(0.5)
        if (not timed_out and not stopped() and auto_clear_locks and _lock_abort(out, prt, fresh)):
            # SOFiSTiK gave up waiting for the .cdb: end what a stopped run left holding it, then once more
            again = _pre_run_lock(cdb, sofistik_root, True)
            if not again.get("refuse") and not again.get("warning") and os.path.isfile(cdb):
                settled = cdblock.quiet(cdb, sofistik_root)          # not just a gap between two programs
                if settled["locked"]:
                    again["refuse"] = "Another program uses the database: " + " ".join(settled["advice"])
                    again["holders"] = settled["holders"]
                elif not stopped():
                    # no program uses it: the lock is the one written inside the .cdb
                    again["clean_locks"] = cdblock.clean_locks(cdb, sofistik_root, clean_cmd)
            lock_report.setdefault("after_lock_error", again)
            if not stopped() and (again.get("ended") or (again.get("clean_locks") or {}).get("cleaned")):
                proc, out3, timed_out, _ = _launch(cmd, folder, _left(timeout_s, t0), started, watch_kw=watch_kw)
                out = (out or b"") + (out3 or b"")
                server_warnings.append("SOFiSTiK reported the .cdb as locked (WAIT FOR LOCK); " +
                                       ("the programs left behind by an earlier run were ended" if again.get("ended")
                                        else "its stale locks were cleared with SOFiSTiK's Clean Locks") +
                                       " and the calculation was run again.")
                deadline = time.time() + 15
                while not timed_out and not stopped() and time.time() < deadline:
                    if fresh(prt) and messages.END_RE.search(messages.read_text(prt)):
                        break
                    time.sleep(0.5)
        elapsed = time.time() - t0
    finally:
        _remove(lock_path)

    summary = messages.summarize_run(prt if fresh(prt) else None, erg if fresh(erg) else None)
    exit_code = None if timed_out else proc.returncode
    watch = getattr(proc, "_mcp_watch", None)
    if watch is not None:
        summary["peak_ram_mb"] = watch.peak_ram_mb
        summary["module_times"] = watch.modules()
    survivors = getattr(proc, "_mcp_survivors", None) or []
    leftovers = getattr(proc, "_mcp_leftovers", None) or []
    if leftovers:
        server_warnings.append("These SOFiSTiK programs were still running after sps.exe ended and were ended: " +
                               ", ".join(f"{x['name']} ({x['pid']})" for x in leftovers))
    if survivors:
        server_warnings.append("These SOFiSTiK programs of the run could not be ended and may keep the .cdb "
                               "locked: " + ", ".join(f"{x['name']} ({x['pid']})" for x in survivors) +
                               ". check_cdb_lock shows what holds it.")
        summary["left_running"] = survivors
    if lock_report.get("ended") or lock_report.get("after_lock_error"):
        summary["cdb_lock"] = {k: v for k, v in lock_report.items() if k != "warning"}
    if _lock_abort(out, prt, fresh) and summary.get("status") not in OK_STATUSES:
        info = cdblock.check(cdb, sofistik_root)
        cl = ((lock_report.get("after_lock_error") or {}).get("clean_locks") or {})
        summary["reason"] = ("SOFiSTiK could not open the database because it is locked (WAIT FOR LOCK). " +
                             (" ".join(info["advice"]) or cl.get("error") or
                              "No program holds it any more and Clean Locks ran: run it again, or call "
                              "clear_cdb_lock.") +
                             ("" if auto_clear_locks else
                              " (settings.json \"auto_clear_cdb_locks\" is false, so nothing was ended.)"))
    if stopped():
        summary["status"] = "stopped"
        summary["reason"] = "The calculation was stopped on request; results are incomplete."
    elif timed_out:
        summary["status"] = "timed out"
        summary["reason"] = (f"Stopped after {(timeout_s or 0) / 60:.0f} minutes (the time limit asked for this run, "
                             "or settings.json \"run_timeout_minutes\"). The calculation was killed; results are "
                             "incomplete.")
    elif not fresh(prt):
        summary["reason"] = "sps.exe wrote no new .prt protocol, so the calculation did not run."
    elif summary["status"] in OK_STATUSES and exit_code not in (0, None):
        # SOFiSTiK does not document sps.exe's exit codes, so a clean protocol decides the status
        server_warnings.append(f"sps.exe exit code {exit_code}, meaning not verified (SOFiSTiK does not document "
                               "sps.exe's exit codes; the protocol shows no errors).")
    changed = [p for p, h in scan["hashes"].items() if _sha(p) != h]
    if changed:
        server_warnings.append("These input files changed while the calculation ran, so SOFiSTiK may have read "
                               "something else than what was checked: " + ", ".join(changed))
        if summary["status"] in OK_STATUSES:
            summary["status"] = "check: input changed during run"
    files = {}
    for ext in RESULT_EXTS:
        p = os.path.join(folder, stem + ext)
        if os.path.isfile(p):
            files[ext[1:]] = {"path": p, "updated_by_this_run": fresh(p),
                              "size_kb": round(os.path.getsize(p) / 1024, 1)}
    tail = (out or b"").decode("utf-8", errors="replace").strip()[-1500:]
    summary.update({
        "dat": dat_path, "command": " ".join(f'"{c}"' if " " in c else c for c in cmd),
        "exit_code": exit_code, "seconds": round(elapsed, 1),
        "cdb_existed_before_run": cdb_before,
        "programs_in_input": scan["programs"], "missing_includes": scan["missing_includes"],
        "files": files, "sps_console_tail": tail,
    })
    if retried:
        summary["retried"] = retried
    if changed:
        summary["changed_during_run"] = changed
    if server_warnings:
        summary["server_warnings"] = server_warnings
    return summary
