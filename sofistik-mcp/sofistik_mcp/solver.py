"""Run a SOFiSTiK .dat file in batch mode with sps.exe and report what happened.

sps.exe options used (SOFiSTiK 2027 manual, "Special Features for Start", batch-only parameters):
  -B0        show nothing of the calculation on screen
  -R         do not stop the calculation on error (only when continue_on_error=True)
  -urs:xx    run only the +PROG block with urs:xx, all others inactive
The calculation writes, next to the .dat:  name.cdb (database), name.prt (protocol: errors, warnings,
programs run), name.erg (output of the whole analysis), name.plb (report browser file).

Safety (CADINP manual cadinp_1.pdf, 1.9 "Starting an Analysis"):
  * "+SYS cmd" always and "*SYS cmd" (if the last PROG was active) make SOFiSTiK run any Windows
    command.  $(name) text substitution is active on every line, so a line that starts with $(...)
    or a #define value containing SYS can build such a command.  Unless settings.json says
    "allow_sys_commands": true, every such line (also in files pulled in by #INCLUDE or +APPLY, three
    levels deep) refuses the run before anything starts.  The rule is deliberately broad.
  * Every file SPS could open for an #INCLUDE / +APPLY is scanned (name and name.dat, next to the
    including file and next to the main .dat); one that cannot be found or checked refuses the run.
    One outside the folders this server may read is always refused: SOFiSTiK copies included text
    into the .erg, which Claude can read.
  * sps.exe runs in a Windows job object that is closed (killing sps.exe and the programs it
    started) when the server process ends, and a <name>.mcp-running lock file next to the .dat stops
    a second server from starting a calculation in the same folder.
"""
from __future__ import annotations

import atexit
import glob
import hashlib
import ntpath
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata

from . import config, messages

CREATE_NO_WINDOW = 0x08000000
RESULT_EXTS = (".cdb", ".prt", ".erg", ".plb", ".lst")
SCAN_MAX_BYTES = 50_000_000            # the most messages.read_text reads; bigger files are refused
INCLUDE_DEPTH = 3
CONSOLE_TAIL_BYTES = 64 * 1024         # sps.exe console output kept (the end of it)
LOCK_EXT = ".mcp-running"

# --- line rules (applied to a cleaned copy of each line, see _clean) ---------------------------------
# +SYS / *SYS (any spelling, also +SYSTEM: sps may only look at the first letters) and a bare SYS word
SYS_RE = re.compile(r"^\s*(?:[+*]\s*sys|sys(?![a-z0-9_]))", re.IGNORECASE)
# a line whose first word is built by $(...) substitution
DOLLAR_FIRST_RE = re.compile(r"^\s*[+*]?\s*\$\(", re.IGNORECASE)
DEFINE_RE = re.compile(r"^\s*#\s*define\s+([^\s=]+)\s*(?:=(.*))?$", re.IGNORECASE)
ENDDEF_RE = re.compile(r"^\s*#\s*enddef\b", re.IGNORECASE)
UNDEF_RE = re.compile(r"^\s*#\s*undef\s+(\S+)", re.IGNORECASE)
BLOCK_OLD_RE = re.compile(r"^\s*\$\s*block\b", re.IGNORECASE)          # old $BLOCK BEG/END/SET form
INCLUDE_RE = re.compile(r"^\s*(?:#\s*incl\w*|\+?\s*apply)\s+(.+)$", re.IGNORECASE)
# +PROG name and, as in the manual's examples (cadinp_1 p. 1-2), PROG name without the sign
PROG_RE = re.compile(r"^\s*(?:\+\s*)?prog(?:\s+(\S+)(.*))?$", re.IGNORECASE)
REF_RE = re.compile(r"\$\(([^()$]*)\)")
COMMENT_LINE_RE = re.compile(r"^\s*(?:\$(?:\s|$)|!|//)")
SAFE_VALUE_RE = re.compile(r"^[0-9.\s+\-*/(),eE]*$")
_BLANK_CATEGORIES = {"Zs", "Zl", "Zp", "Cc", "Cf"}


def _clean(line: str) -> str:
    """The line as SPS might see it: compatibility forms folded (NFKC), every Unicode space, control
    or invisible format character (NBSP, \\v, \\f, BOM, zero-width space ...) turned into a blank."""
    line = unicodedata.normalize("NFKC", line)
    return "".join(" " if (ch.isspace() or unicodedata.category(ch) in _BLANK_CATEGORIES) else ch
                   for ch in line)


def _strip_value_comment(v: str) -> str:
    return re.split(r"\s(?:\$|!|//)(?:\s|$)", " " + v)[0].strip()


def sys_lines_in_text(text: str, file: str, readable=None) -> list[dict]:
    """+SYS-like lines of a text about to be written as `file` (write_dat_file), with the same rules as
    scan_dat.  Include files that already exist are read too (their #define values count for the
    $(...) rule; their own +SYS lines are reported as well); missing ones do not matter here."""
    sc = _Scanner(main=file, readable=readable)
    sc.seen.add(os.path.normcase(os.path.realpath(os.path.abspath(file))))     # not the old version of itself
    sc.scan_text(text, file, depth=INCLUDE_DEPTH)
    sc.finish()
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
        self.defines: dict = {}                # name -> [values] (every definition seen anywhere)
        self.dollar_lines: list = []           # lines whose first word is $(...), judged in finish()
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
        self.scan_text(messages.decode_text(raw), path, depth)

    # -- lines ------------------------------------------------------------------------------------
    def _flag(self, file, line_no, original, why):
        self.out["sys_lines"].append({"file": file, "line": line_no, "text": original.strip().lstrip("﻿"),
                                      "why": why})

    def scan_text(self, text: str, file: str, depth: int, follow: bool = True) -> None:
        for i, original in enumerate(text.split("\n")):
            n = i + 1
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
                    if "sys" in value.casefold():
                        self._flag(file, n, original, "#define value containing SYS ($(...) substitution "
                                                      "can turn it into a +SYS command)")
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
            for seg in ln.split(";"):
                if SYS_RE.match(seg):
                    self._flag(file, n, original, "+SYS / *SYS operating system command")
                    break
                if DOLLAR_FIRST_RE.match(seg):
                    self.dollar_lines.append((file, n, original, seg))
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
            m = INCLUDE_RE.match(ln)
            if m and follow:
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

    # -- after all files ---------------------------------------------------------------------------
    def _safe_ref(self, ref: str, stack=()) -> bool:
        """True if $(ref) can only expand to numbers (every definition in the files is numeric)."""
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

    def finish(self) -> None:
        for file, n, original, seg in self.dollar_lines:
            refs = REF_RE.findall(seg)
            literal = REF_RE.sub("", seg)
            if (refs and "$(" not in literal and all(self._safe_ref(r) for r in refs)
                    and "sys" not in literal.casefold()):
                continue
            self._flag(file, n, original, "line starting with $(...) substitution, which could build a +SYS "
                                          "command")
        self.dollar_lines = []


def scan_dat(path: str, depth: int = INCLUDE_DEPTH, readable=None, max_bytes: int | None = None) -> dict:
    """+SYS-like lines, active PROG blocks and included files of a .dat (follows #INCLUDE / +APPLY).

    readable: folders includes must be inside (None: not checked).  Returns sys_lines, programs,
    includes, missing_includes, blocked_includes ({include, file, why, kind: outside|unscannable})
    and hashes ({path: sha256} of every file read, for the changed-during-run check)."""
    sc = _Scanner(path, readable, max_bytes)
    sc.scan_file(path, depth)
    sc.finish()
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
_JOB: dict = {"handle": None, "error": None}

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
    _k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    _k32.IsProcessInJob.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _k32.GetExitCodeProcess.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL

    def _job_handle():
        """The server's job object (created once, never closed: Windows closes it when the server
        process ends, and KILL_ON_JOB_CLOSE then ends every process in it)."""
        if _JOB["handle"] is None and _JOB["error"] is None:
            h = _k32.CreateJobObjectW(None, None)
            if not h:
                _JOB["error"] = f"CreateJobObject failed ({ctypes.get_last_error()})"
                return None
            info = _EXTENDED_LIMIT()
            info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _k32.SetInformationJobObject(h, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                                ctypes.byref(info), ctypes.sizeof(info)):
                _JOB["error"] = f"SetInformationJobObject failed ({ctypes.get_last_error()})"
                _k32.CloseHandle(h)
                return None
            _JOB["handle"] = h
        return _JOB["handle"]

    def _contain(proc) -> str | None:
        """Put proc in the job object.  None if done, else why not."""
        job = _job_handle()
        if job is None:
            return _JOB["error"]
        h = _k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, proc.pid)
        if not h:
            return f"OpenProcess failed ({ctypes.get_last_error()})"
        try:
            if not _k32.AssignProcessToJobObject(job, h):
                return f"AssignProcessToJobObject failed ({ctypes.get_last_error()})"
        finally:
            _k32.CloseHandle(h)
        return None

    def pid_alive(pid: int) -> bool:
        h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ctypes.get_last_error() == 5           # access denied: it exists
        try:
            code = wintypes.DWORD()
            return bool(_k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == _STILL_ACTIVE
        finally:
            _k32.CloseHandle(h)

    def _popen_kw() -> dict:
        return {"creationflags": CREATE_NO_WINDOW}

    def _kill_group(proc) -> None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
else:  # pragma: no cover
    import signal

    def _contain(proc) -> str | None:
        return None                                          # start_new_session + atexit (below)

    def pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _popen_kw() -> dict:
        return {"start_new_session": True}

    def _kill_group(proc) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)              # sps and everything it started
        except (ProcessLookupError, PermissionError):
            proc.kill()


def _kill_tree(proc):
    try:
        _kill_group(proc)
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


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


def _lock_pids(path) -> list[int]:
    try:
        with open(path, encoding="ascii", errors="replace") as f:
            return [int(x) for x in re.findall(r"\d+", f.read())[:2]]
    except OSError:
        return []


def live_lock(folder: str) -> str | None:
    """A lock file in folder whose process is still running (stale ones are removed)."""
    for p in sorted(glob.glob(os.path.join(glob.escape(folder), "*" + LOCK_EXT))):
        pids = _lock_pids(p)
        alive = any(pid_alive(pid) for pid in pids if pid != os.getpid())
        if os.getpid() in pids and p in _LOCKS:
            alive = True
        if not pids:                     # being written by another server right now, or garbage
            try:
                alive = time.time() - os.path.getmtime(p) < 10
            except OSError:
                continue
        if alive:
            return p
        _remove(p)
    return None


def _write_lock(path: str, pids) -> None:
    with open(path, "w", encoding="ascii") as f:
        f.write(" ".join(str(p) for p in pids) + "\n")


# ------------------------------------------------------------------------------------------------
# running sps.exe
# ------------------------------------------------------------------------------------------------

def _launch(cmd, folder, timeout_s, on_start, cap: int = CONSOLE_TAIL_BYTES):
    """Start sps.exe, wait for it (killing the whole process tree on timeout).
    -> (proc, output tail, timed_out, containment problem or None)"""
    with _ACTIVE_LOCK:
        proc = subprocess.Popen(cmd, cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, **_popen_kw())
        _ACTIVE.add(proc)
    problem = None
    try:
        problem = _contain(proc)
    except Exception as e:                                  # never fail the run over it
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


def run(dat_path: str, sps: str, timeout_s: float, allow_sys: bool = False,
        continue_on_error: bool = False, only_urs: int | None = None, on_start=None,
        stopped=lambda: False, readable=None) -> dict:
    """Run sps.exe on dat_path (already access-checked) and return a summary dict.
    on_start(proc) is called with the running process; stopped() tells whether the caller killed it.
    readable: folders an #INCLUDE / +APPLY file must be in (None: not checked)."""
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
    lock = live_lock(folder)
    if lock:
        return {"status": "not run", "lock_file": lock,
                "reason": f"Another calculation is running in this folder ({os.path.basename(lock)}, started by "
                          "another Claude window or server). Wait for it to finish, or delete the lock file if "
                          "you are sure nothing is running."}
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

    stem = os.path.splitext(name)[0]
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
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        finally:
            os.close(fd)
    except FileExistsError:
        return {"status": "not run", "lock_file": lock_path,
                "reason": f"{os.path.basename(lock_path)} appeared just now: another calculation is starting here."}
    _LOCKS.add(lock_path)
    try:
        other = None
        for p in glob.glob(os.path.join(glob.escape(folder), "*" + LOCK_EXT)):
            if os.path.normcase(p) != os.path.normcase(lock_path) and any(
                    pid_alive(x) for x in _lock_pids(p) if x != os.getpid()):
                other = p
        if other:
            return {"status": "not run", "lock_file": other,
                    "reason": "Another calculation started in this folder at the same moment "
                              f"({os.path.basename(other)})."}

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
        proc, out, timed_out, problem = _launch(cmd, folder, timeout_s, started)
        if problem:
            server_warnings.append("sps.exe could not be tied to the server (" + problem + "): if the server is "
                                   "closed during the run, the calculation may keep running.")
        retried = None
        if not timed_out and not stopped() and not fresh(prt) and time.time() - t0 < 120:
            # The order of options and file name for sps.exe is not documented: try file name first once.
            first = cmd
            cmd = [sps, name] + opts
            proc, out2, timed_out, _ = _launch(cmd, folder, max(1.0, timeout_s - (time.time() - t0)), started)
            out = (out or b"") + (out2 or b"")
            retried = (f"sps.exe wrote no protocol with {' '.join(first[1:])}, so it was retried with the file "
                       f"name first: {' '.join(cmd[1:])}")
        # sps.exe writes the protocol as it goes; give the file system a moment to show the last lines
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
    if stopped():
        summary["status"] = "stopped"
        summary["reason"] = "The calculation was stopped on request; results are incomplete."
    elif timed_out:
        summary["status"] = "timed out"
        summary["reason"] = (f"Stopped after {timeout_s / 60:.0f} minutes (settings.json \"run_timeout_minutes\"). "
                             "The calculation was killed; results are incomplete.")
    elif not fresh(prt):
        summary["reason"] = "sps.exe wrote no new .prt protocol, so the calculation did not run."
    elif summary["status"] in OK_STATUSES and exit_code not in (0, None):
        summary["status"] = f"check: exit code {exit_code}"
        summary["reason"] = (f"sps.exe ended with exit code {exit_code} although the protocol shows no errors. "
                             "Do not use the results until the .prt / .erg have been checked.")
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
