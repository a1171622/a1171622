"""Who holds a SOFiSTiK database (.cdb) open, and clearing a lock left by a stopped run.

SOFiSTiK's CDBASE aborts with "CDBASE: WAIT FOR LOCK ABORTED BY USER" in batch mode when another
program still has the .cdb open.  Seen on this project after a run was stopped: the calculation
program (BDK) outlived its sps.exe / WPSJOB parents and kept the database open.

Every process that has the .cdb open is sorted into one of these kinds:
  run      part of a calculation that is still running: a live parent of it is sps.exe, a SOFiSTiK
           program window (Teddy, SSD, SOFiPLUS) or any non-SOFiSTiK program (cmd, Python, Rhino ...)
           that started it.  Never touched.
  window   a SOFiSTiK program window (WinGRAF, Result Viewer, Teddy, SSD ...) that has it open itself.
           Never touched: the engineer may be looking at it, so they are asked to close it.
  reader   this MCP server's own .cdb reader (cdb_worker); it ends by itself.
  orphan   a SOFiSTiK calculation program (or WPSJOB) whose sps.exe has ended: it was left behind by a
           stopped or crashed run and nothing will ever collect its results.  Only these are ended
           (clear), and only after checking again that the process is the same one (start time).
  other    any other program (a backup or virus scanner, Excel ...).  Never touched.
On Windows the file is also opened once without sharing: if that fails while no holder was found,
some program this server cannot see (another user, an elevated program) has it open.
"""
from __future__ import annotations

import os
import sys
import time

try:
    import psutil
except ImportError:                                  # pragma: no cover - psutil is in requirements.txt
    psutil = None

from . import config

# SOFiSTiK program windows (never ended, never "orphans")
WINDOWS = {"ssd", "teddy", "wingraf", "animator", "sofiplus", "resultviewer", "sofistik", "sofiplus-x",
           "wps", "ursula"}
# programs that start a calculation: a live one makes everything below it a running calculation
LAUNCHERS = {"sps", "teddy", "ssd", "sofiplus", "sofiplus-x", "wps"}
# calculation programs known by name (also when the SOFiSTiK program folder is unknown)
CALC_NAMES = {"wpsjob", "aqua", "aqb", "sofimsha", "sofimshb", "sofimshc", "sofiload", "ase", "bdk", "maxima",
              "talpa", "dyna", "csm", "ella", "hase", "sir", "star2", "tendon", "textile", "column", "footing",
              "bemess", "dbmerg", "hydra", "rely", "plbconverter", "dolfyn", "templat", "template"}
KILL_WAIT_S = 10


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name or ""))[0].lower()


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except (OSError, ValueError):
        return False


def _is_sofistik(name: str, exe: str, root: str | None) -> bool:
    if root and exe and config.is_inside(exe, [root]):
        return True
    s = _stem(name)
    return s in CALC_NAMES or s in WINDOWS or s in LAUNCHERS


def _chain(pid: int, table: dict) -> list[dict]:
    """The live parents of pid, nearest first.  A parent only counts when it started before its child
    (Windows reuses process numbers)."""
    out: list[dict] = []
    seen = {pid}
    cur = table.get(pid)
    while cur is not None:
        par = table.get(cur.get("ppid"))
        if par is None or par["pid"] in seen or par["pid"] in (0, 1):
            break
        if (par.get("create_time") or 0) > (cur.get("create_time") or 0) + 1:
            break
        out.append(par)
        seen.add(par["pid"])
        cur = par
    return out


def _kind(row: dict, table: dict, own_pids: set) -> str:
    s = _stem(row["name"])
    if row["pid"] in own_pids:
        return "reader"
    if s in ("python", "pythonw") and any("cdb_worker" in str(a) for a in row.get("cmdline") or []):
        return "reader"
    if not row["sofistik"]:
        return "other"
    if s in LAUNCHERS - {"sps"} or (s in WINDOWS and s not in LAUNCHERS):
        return "window"
    if s == "sps":
        return "run"
    # Orphan only when every live parent is itself a SOFiSTiK calculation program (WPSJOB ...): a live
    # sps.exe, a SOFiSTiK window or any other program (cmd, Python, Rhino ...) above it is still
    # running this calculation.
    for p in _chain(row["pid"], table):
        ps = _stem(p["name"])
        if ps in LAUNCHERS or ps in WINDOWS or not p["sofistik"]:
            return "run"
    return "orphan"


def _process_table(root: str | None) -> dict:
    table: dict = {}
    for p in psutil.process_iter(["pid", "name", "exe", "ppid", "create_time"]):
        try:
            i = p.info
            table[i["pid"]] = {"pid": i["pid"], "name": i.get("name") or "", "exe": i.get("exe") or "",
                               "ppid": i.get("ppid"), "create_time": i.get("create_time") or 0,
                               "sofistik": _is_sofistik(i.get("name") or "", i.get("exe") or "", root), "proc": p}
        except Exception:                            # ended while being read
            continue
    return table


def holders(cdb: str, root: str | None = None, own_pids: set | None = None) -> list[dict]:
    """Processes that have cdb open: [{pid, name, kind, create_time, parent, ram_mb, how}].
    Only SOFiSTiK programs and Python processes are searched (reading every program's open files is
    slow and mostly refused); 'how' says whether the open file was seen or only guessed from the
    program's current folder (when Windows refused to list its files)."""
    if psutil is None:                               # pragma: no cover
        return []
    own = set(own_pids or ())
    folder = os.path.dirname(os.path.abspath(cdb))
    table = _process_table(root)
    out = []
    for row in table.values():
        s = _stem(row["name"])
        if not row["sofistik"] and s not in ("python", "pythonw"):
            continue
        p = row["proc"]
        how = None
        try:
            if any(_same_file(f.path, cdb) for f in p.open_files()):
                how = "open file"
        except psutil.AccessDenied:
            try:                                     # cannot list its files: its working folder is a hint
                if row["sofistik"] and s not in WINDOWS and _same_file(p.cwd(), folder):
                    how = "working folder (its open files could not be listed)"
            except Exception:
                pass
        except Exception:
            continue
        if how is None:
            continue
        if s in ("python", "pythonw"):
            try:
                row["cmdline"] = p.cmdline()
            except Exception:
                row["cmdline"] = []
        kind = _kind(row, table, own)
        if kind == "other" and s in ("python", "pythonw"):
            continue                                 # another Python program: not ours to report
        chain = _chain(row["pid"], table)
        try:
            ram = round(p.memory_info().rss / 2**20)
        except Exception:
            ram = None
        out.append({"pid": row["pid"], "name": row["name"], "kind": kind, "create_time": row["create_time"],
                    "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["create_time"])),
                    "parent": chain[0]["name"] if chain else None, "ram_mb": ram, "how": how})
    return sorted(out, key=lambda r: r["create_time"])


# Windows: open the file once without sharing, to learn whether ANY program has it open
if sys.platform == "win32":  # pragma: no cover - exercised by tests/test_cdblock.py on windows-latest
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _INVALID = wintypes.HANDLE(-1).value

    def open_elsewhere(path: str) -> bool | None:
        """True: another program has the file open (sharing violation).  None: could not tell."""
        h = _k32.CreateFileW(path, 0x80000000, 0, None, 3, 0x80, None)     # GENERIC_READ, no sharing
        if h and h != _INVALID:
            _k32.CloseHandle(h)
            return False
        err = ctypes.get_last_error()
        return True if err in (32, 33) else None                          # sharing / lock violation
else:
    def open_elsewhere(path: str) -> bool | None:
        return None                                  # POSIX has no mandatory sharing modes


def _advice(h: dict) -> str:
    if h["kind"] == "run":
        return f"{h['name']} (process {h['pid']}) is part of a calculation that is still running: wait for it."
    if h["kind"] == "window":
        return f"{h['name']} (process {h['pid']}) has it open: close the model there."
    if h["kind"] == "reader":
        return f"This server is reading it (process {h['pid']}); that ends by itself."
    if h["kind"] == "orphan":
        return (f"{h['name']} (process {h['pid']}, started {h['started']}) was left behind by a stopped or crashed "
                "run: clear_cdb_lock ends it.")
    return f"{h['name']} (process {h['pid']}) has it open; close that program."


def check(cdb: str, root: str | None = None, own_pids: set | None = None) -> dict:
    """{cdb, exists, locked, holders, open_elsewhere, advice[]}."""
    if not os.path.isfile(cdb):
        return {"cdb": cdb, "exists": False, "locked": False, "holders": [], "advice": []}
    hs = holders(cdb, root, own_pids)
    other = open_elsewhere(cdb)
    advice = [_advice(h) for h in hs]
    if other and not hs:
        advice.append("A program this server cannot see (another Windows user, or a program run as "
                      "administrator) has the file open. Close SOFiSTiK programs, or restart the PC.")
    return {"cdb": cdb, "exists": True, "locked": bool(hs) or bool(other), "holders": hs,
            "open_elsewhere": other, "advice": advice}


def _end(pid: int, create_time: float):
    """Kill pid if it is still the process that was found (same start time).  -> psutil.Process or None."""
    try:
        p = psutil.Process(pid)
        if abs(p.create_time() - create_time) > 1:
            return None                              # the number now belongs to another process
        p.kill()
        return p
    except psutil.NoSuchProcess:
        return None


def clear(cdb: str, root: str | None = None, own_pids: set | None = None, clean_flag: bool = False,
          clean_cmd: str = "") -> dict:
    """End the orphaned SOFiSTiK programs that hold cdb, then check again; with clean_flag also reset
    the locks stored inside the .cdb with SOFiSTiK's Clean Locks once no program has it open.
    -> check() result before and after, plus ended [{pid, name, started, ram_mb}], failed [] and
    clean_locks (when it ran or could not)."""
    before = check(cdb, root, own_pids)
    ended, failed, procs = [], [], []
    for h in before["holders"]:
        if h["kind"] != "orphan":
            continue
        try:
            p = _end(h["pid"], h["create_time"])
        except Exception as e:                       # access denied ...
            failed.append({"pid": h["pid"], "name": h["name"], "error": f"{type(e).__name__}: {e}"})
            continue
        if p is not None:
            procs.append(p)
        ended.append({k: h[k] for k in ("pid", "name", "started", "ram_mb")})
    if procs:
        _, alive = psutil.wait_procs(procs, timeout=KILL_WAIT_S)
        for p in alive:
            failed.append({"pid": p.pid, "name": p.name(), "error": "still running after being ended"})
            ended = [e for e in ended if e["pid"] != p.pid]
    after = check(cdb, root, own_pids) if ended or failed else before
    out = {"cdb": cdb, "locked_before": before["locked"], "holders_before": before["holders"],
           "ended": ended, "failed": failed, "locked_now": after["locked"], "holders_now": after["holders"],
           "advice": after["advice"]}
    if clean_flag and after["exists"]:
        if after["locked"]:
            out["clean_locks"] = {"cleaned": False, "error": "Not run: a program still has the .cdb open (see "
                                                             "advice)."}
        else:
            out["clean_locks"] = clean_locks(cdb, root, clean_cmd)
    return out


# ------------------------------------------------------------------------------------------------
# the lock flag inside the .cdb
# ------------------------------------------------------------------------------------------------
# A run that is killed can also leave its key locks written INSIDE the .cdb ("another process is
# writing the key 0/99"; a copy of the file is locked too, and no program holds it).  SOFiSTiK's own
# remedy is "Clean Locks" (Teddy / SSD: Home > Database Tools > Clean Locks, or right-click the .cdb in
# Explorer > SOFiSTiK 20xx > Clean Locks; FEA manual, Troubleshooting).  The manuals give no command line
# for it.  On the SOFiSTiK 2027 PC (registry, 18 Oct 2026) that menu entry runs
#     "C:\Program Files\SOFiSTiK\2027\SOFiSTiK 2027\dbinfo.exe" "<file>.cdb" z
# so the registry entry is used when it can be found, else dbinfo.exe ... z in the SOFiSTiK folder.

LOCK_WORDS = ("lock", "sperr")              # "Clean Locks", German "Sperren ..."
CLEAN_TIMEOUT_S = 120


def _reg_values(key) -> dict:  # pragma: no cover - Windows registry (windows-latest CI)
    import winreg
    out: dict = {}
    i = 0
    while True:
        try:
            name, val, _ = winreg.EnumValue(key, i)
        except OSError:
            return out
        out[name] = val
        i += 1


def _reg_walk(root, path: str, depth: int = 0):  # pragma: no cover - Windows registry (windows-latest CI)
    """(path, values) of path and its sub keys, a few levels deep."""
    import winreg
    try:
        key = winreg.OpenKey(root, path)
    except OSError:
        return
    with key:
        yield path, _reg_values(key)
        if depth >= 4:
            return
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            yield from _reg_walk(root, path + "\\" + sub, depth + 1)
            i += 1


def clean_locks_menu_entries() -> list[dict]:
    """Explorer menu entries for .cdb files whose name mentions locks: [{key, label, command}]."""
    if sys.platform != "win32":
        return []
    return _menu_entries_windows()  # pragma: no cover


def _menu_entries_windows() -> list[dict]:  # pragma: no cover - Windows registry (windows-latest CI)
    import winreg
    hkcr = winreg.HKEY_CLASSES_ROOT
    bases = [r"SystemFileAssociations\.cdb\shell", r".cdb\shell", r"*\shell"]
    try:
        with winreg.OpenKey(hkcr, ".cdb") as k:
            progid = _reg_values(k).get("")
        if progid:
            bases.insert(0, progid + r"\shell")
    except OSError:
        pass
    found, seen = [], set()
    searches = [(hkcr, b) for b in bases] + [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\CommandStore\shell")]
    for root, base in searches:
        for path, vals in _reg_walk(root, base):
            if not path.lower().endswith("\\command"):
                continue
            verb = path[:-len("\\command")]
            label = ""
            try:
                with winreg.OpenKey(root, verb) as k:
                    v = _reg_values(k)
                label = str(v.get("MUIVerb") or v.get("") or "")
            except OSError:
                pass
            text = (verb.rsplit("\\", 1)[-1] + " " + label).lower()
            cmd = str(vals.get("") or "")
            if cmd and any(w in text for w in LOCK_WORDS) and (root, path) not in seen:
                seen.add((root, path))
                found.append({"key": path, "label": label, "command": cmd})
    return found


def _exe_of(command: str) -> str:
    c = command.strip()
    if c.startswith('"'):
        return c[1:].split('"', 1)[0]
    return c.split(" ", 1)[0]


def clean_locks_command(root: str | None, configured: str = "") -> tuple[str | None, str]:
    """(command template with %1, where it came from) - only a program inside the SOFiSTiK folder."""
    cands = ([{"key": "settings.json clean_locks_command", "command": configured}] if configured else
             clean_locks_menu_entries())
    for c in cands:
        exe = os.path.expandvars(_exe_of(c["command"]))
        if root and config.is_inside(exe, [root]) and os.path.isfile(exe):
            return c["command"], c["key"]
    dbinfo = os.path.join(root, "dbinfo.exe") if root else ""
    if not configured and dbinfo and os.path.isfile(dbinfo):
        return f'"{dbinfo}" "%1" z', "dbinfo.exe in the SOFiSTiK folder (what Explorer's Clean Locks runs)"
    if cands:
        return None, ("found " + "; ".join(f"{c['key']}: {c['command']}" for c in cands) +
                      " - not used: the program is not inside the SOFiSTiK folder " + str(root))
    return None, "no 'Clean Locks' entry for .cdb files was found in the registry"


def clean_locks(cdb: str, root: str | None, configured: str = "") -> dict:
    """Run SOFiSTiK's own Clean Locks on cdb (only when no program has it open).
    -> {"cleaned": bool, "command", "source", "output"/"error"}"""
    import subprocess
    cmd, source = clean_locks_command(root, configured)
    if cmd is None:
        return {"cleaned": False, "source": source,
                "error": "SOFiSTiK's Clean Locks could not be started from here (" + source + "). Use it by hand: "
                         "open the model in Teddy, Home > Database Tools > Clean Locks (or right-click the .cdb "
                         "in Explorer > SOFiSTiK > Clean Locks)."}
    full = cmd
    for ph in ("%1", "%L", "%l", "%V", "%v"):
        full = full.replace(ph, cdb)
    if full == cmd:
        full = f'{cmd} "{cdb}"'
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                "timeout": CLEAN_TIMEOUT_S, "cwd": os.path.dirname(cdb)}
    if sys.platform == "win32":  # pragma: no cover
        kw["creationflags"] = 0x08000000
    import shlex
    args = full if sys.platform == "win32" else shlex.split(full)   # Windows: the command line as Explorer runs it
    try:
        p = subprocess.run(args, **kw)
    except subprocess.TimeoutExpired:
        return {"cleaned": False, "command": full, "source": source,
                "error": f"Clean Locks did not finish within {CLEAN_TIMEOUT_S} s (it may be waiting for a click "
                         "on this PC's screen)."}
    except OSError as e:
        return {"cleaned": False, "command": full, "source": source, "error": f"{type(e).__name__}: {e}"}
    out = (p.stdout or b"").decode("latin-1", errors="replace").strip()[-1000:]
    return {"cleaned": p.returncode == 0, "command": full, "source": source, "exit_code": p.returncode,
            "output": out}
