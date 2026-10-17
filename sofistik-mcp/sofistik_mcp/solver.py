"""Run a SOFiSTiK .dat file in batch mode with sps.exe and report what happened.

sps.exe options used (SOFiSTiK 2027 manual, "Special Features for Start", batch-only parameters):
  -B0        show nothing of the calculation on screen
  -R         do not stop the calculation on error (only when continue_on_error=True)
  -urs:xx    run only the +PROG block with urs:xx, all others inactive
The calculation writes, next to the .dat:  name.cdb (database), name.prt (protocol: errors, warnings,
programs run), name.erg (output of the whole analysis), name.plb (report browser file).

Safety: a .dat may contain "+SYS <command>", which makes SOFiSTiK run any Windows command.  Unless
settings.json says "allow_sys_commands": true, files containing +SYS (also in files pulled in by
#INCLUDE or +APPLY, three levels deep) are refused before anything runs.
"""
from __future__ import annotations

import os
import re
import subprocess
import time

from . import messages

SYS_RE = re.compile(r"^[ \t]*\+[ \t]*sys\b", re.IGNORECASE | re.MULTILINE)
INCLUDE_RE = re.compile(r"^[ \t]*(?:#include|\+apply)[ \t]+(.+)$", re.IGNORECASE | re.MULTILINE)
PROG_RE = re.compile(r"^[ \t]*\+[ \t]*prog[ \t]+(\w+)(.*)$", re.IGNORECASE | re.MULTILINE)
CREATE_NO_WINDOW = 0x08000000
RESULT_EXTS = (".cdb", ".prt", ".erg", ".plb", ".lst")


def scan_dat(path: str, depth: int = 3, _seen=None) -> dict:
    """+SYS lines, active +PROG blocks and included files of a .dat (follows #INCLUDE / +APPLY)."""
    _seen = _seen if _seen is not None else set()
    out: dict = {"sys_lines": [], "programs": [], "includes": [], "missing_includes": []}
    key = os.path.normcase(os.path.abspath(path))
    if key in _seen:
        return out
    _seen.add(key)
    text = messages.read_text(path)
    lines = text.split("\n")
    for m in SYS_RE.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        out["sys_lines"].append({"file": path, "line": line_no, "text": lines[line_no - 1].strip()})
    for m in PROG_RE.finditer(text):
        urs = re.search(r"urs\s*:\s*(\d+)", m.group(2), re.IGNORECASE)
        out["programs"].append({"program": m.group(1).upper(), "urs": int(urs.group(1)) if urs else None,
                                "file": os.path.basename(path),
                                "line": text.count("\n", 0, m.start()) + 1})
    if depth <= 0:
        # deeper includes are not scanned for +SYS, so report them as missing and the run is refused
        out["missing_includes"].extend(
            f"{n} (nested more than 3 levels deep in {os.path.basename(path)})"
            for n in (re.split(r"\s\$(?:\s|$)|[;!]", m.group(1))[0].strip().strip("\"'").strip()
                      for m in INCLUDE_RE.finditer(text)) if n)
    else:
        base = os.path.dirname(os.path.abspath(path))
        for m in INCLUDE_RE.finditer(text):
            name = re.split(r"\s\$(?:\s|$)|[;!]", m.group(1))[0].strip().strip("\"'").strip()
            if not name:
                continue
            cands = [name if os.path.isabs(name) else os.path.join(base, name)]
            if not os.path.splitext(name)[1]:
                cands.append(cands[0] + ".dat")
            hit = next((c for c in cands if os.path.isfile(c)), None)
            if hit is None:
                out["missing_includes"].append(name)
                continue
            out["includes"].append(hit)
            sub = scan_dat(hit, depth - 1, _seen)
            for k in out:
                out[k].extend(sub[k])
    return out


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        else:
            proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def _launch(cmd, folder, timeout_s, on_start):
    """Start sps.exe, wait for it (killing the whole process tree on timeout).  -> (proc, output, timed_out)"""
    kw = {"cwd": folder, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
          "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kw["creationflags"] = CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, **kw)
    if on_start:
        on_start(proc)
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        return proc, out, False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        return proc, b"", True


def run(dat_path: str, sps: str, timeout_s: float, allow_sys: bool = False,
        continue_on_error: bool = False, only_urs: int | None = None, on_start=None,
        stopped=lambda: False) -> dict:
    """Run sps.exe on dat_path (already access-checked) and return a summary dict.
    on_start(proc) is called with the running process; stopped() tells whether the caller killed it."""
    if not os.path.isfile(dat_path):
        return {"status": "not run", "reason": f".dat file not found: {dat_path}"}
    if not dat_path.lower().endswith(".dat"):
        return {"status": "not run", "reason": "Only .dat files can be run."}
    if not sps or not os.path.isfile(sps):
        return {"status": "not run", "reason": f"sps.exe not found ({sps}). Set \"sofistik_dir\" in settings.json."}
    scan = scan_dat(dat_path)
    if scan["sys_lines"] and not allow_sys:
        return {"status": "not run",
                "reason": "The input contains +SYS lines, which make SOFiSTiK run Windows commands. They are "
                          "blocked by settings.json (\"allow_sys_commands\": false). Remove them, or ask the "
                          "engineer to allow them.",
                "sys_lines": scan["sys_lines"]}
    if scan["missing_includes"] and not allow_sys:
        return {"status": "not run",
                "reason": "These #INCLUDE / +APPLY files could not be found next to the .dat, so they could not "
                          "be checked for +SYS commands: " + ", ".join(scan["missing_includes"]) +
                          ". Give their full path or copy them next to the .dat.",
                "missing_includes": scan["missing_includes"]}
    if not scan["programs"]:
        return {"status": "not run", "reason": "No active +PROG block found in the file (or its includes)."}

    folder, name = os.path.split(dat_path)
    stem = os.path.splitext(name)[0]
    prt = os.path.join(folder, stem + ".prt")
    erg = os.path.join(folder, stem + ".erg")
    cdb_before = os.path.isfile(os.path.join(folder, stem + ".cdb"))
    opts = ["-B0"]
    if continue_on_error:
        opts.append("-R")
    if only_urs is not None:
        opts.append(f"-urs:{int(only_urs)}")

    t0 = time.time()
    cmd = [sps] + opts + [name]
    proc, out, timed_out = _launch(cmd, folder, timeout_s, on_start)
    fresh = lambda p: os.path.isfile(p) and os.path.getmtime(p) >= t0 - 2  # noqa: E731
    if not timed_out and not stopped() and not fresh(prt) and time.time() - t0 < 120:
        # The order of options and file name for sps.exe is not documented: try file name first once.
        cmd = [sps, name] + opts
        proc, out2, timed_out = _launch(cmd, folder, max(1.0, timeout_s - (time.time() - t0)), on_start)
        out = (out or b"") + (out2 or b"")
    # sps.exe writes the protocol as it goes; give the file system a moment to show the last lines
    deadline = time.time() + 15
    while not timed_out and not stopped() and time.time() < deadline:
        if fresh(prt) and messages.END_RE.search(messages.read_text(prt)):
            break
        time.sleep(0.5)
    elapsed = time.time() - t0

    summary = messages.summarize_run(prt if fresh(prt) else None, erg if fresh(erg) else None)
    if stopped():
        summary["status"] = "stopped"
        summary["reason"] = "The calculation was stopped on request; results are incomplete."
    elif timed_out:
        summary["status"] = "timed out"
        summary["reason"] = (f"Stopped after {timeout_s / 60:.0f} minutes (settings.json \"run_timeout_minutes\"). "
                             "The calculation was killed; results are incomplete.")
    elif not fresh(prt):
        summary["reason"] = "sps.exe wrote no new .prt protocol, so the calculation did not run."
    files = {}
    for ext in RESULT_EXTS:
        p = os.path.join(folder, stem + ext)
        if os.path.isfile(p):
            files[ext[1:]] = {"path": p, "updated_by_this_run": fresh(p),
                              "size_kb": round(os.path.getsize(p) / 1024, 1)}
    tail = (out or b"").decode("utf-8", errors="replace").strip()[-1500:]
    summary.update({
        "dat": dat_path, "command": " ".join(f'"{c}"' if " " in c else c for c in cmd),
        "exit_code": None if timed_out else proc.returncode, "seconds": round(elapsed, 1),
        "cdb_existed_before_run": cdb_before,
        "programs_in_input": scan["programs"], "missing_includes": scan["missing_includes"],
        "files": files, "sps_console_tail": tail,
    })
    return summary
