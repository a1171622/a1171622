"""SOFiSTiK MCP server (stdio).  Lets Claude write CADINP .dat files, run them with SOFiSTiK in batch
mode, read the errors, read results from the .cdb, and search the manuals and shipped examples.

Started by Claude Desktop / Claude Code through run_server.py.  Nothing may be printed to stdout
(that is the MCP channel): logging goes to stderr, SOFiSTiK runs in a child process with its output
captured, and the .cdb is read in a separate worker process (cdb_worker.py).
"""
from __future__ import annotations

import datetime
import fnmatch
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import anyio
from mcp.server.fastmcp import FastMCP

from . import cdblock, config, dashboard, docsearch, install, messages, solver

try:
    import psutil
except ImportError:                                  # pragma: no cover - psutil is in requirements.txt
    psutil = None

log = logging.getLogger("sofistik-mcp")
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VERSION = "1.3.0"

INSTRUCTIONS = """\
Tools for SOFiSTiK 2027 on this PC (structural FEA).  Typical loop:
1. Look up syntax: search_examples (shipped .dat examples) and search_manuals / read_manual_page.
2. write_dat_file: write the CADINP input (.dat) inside a work folder.
3. run_calculation: SOFiSTiK solves it in batch mode (sps.exe).  A long run returns
   status 'running' with a job_id: call get_job_result(job_id) until it is finished (each call waits
   up to 40 s).  There is no time limit unless settings.json sets one: a big model can run for hours.
   ALWAYS read the final status, errors and warnings; 'errors' means the results are not valid.
   stop_calculation stops a run (if it answers 'stopping', get_job_result gives the final state).
   Several models can run at the same time (settings.json "max_parallel_runs", and only while enough
   RAM stays free).  To run several checks on one model at once, clone_cdb copies the model's .cdb to
   the name of each check's .dat; run those .dat files in parallel.  While a calculation runs,
   write_dat_file refuses to change its input files.  Big .cdb reads can also return a job_id.
   A .cdb that SOFiSTiK reports as locked ("WAIT FOR LOCK"): check_cdb_lock says which program holds
   it; programs left behind by a stopped run are ended automatically before each run (clear_cdb_lock
   does it on request).  Never end other programs yourself.
4. cdb_overview / cdb_load_cases, then cdb_node_results, cdb_support_reactions, cdb_beam_forces,
   cdb_truss_cable_forces, cdb_envelope to read results from the .cdb.
Units returned: displacements mm, rotations mrad, forces kN, moments kNm, coordinates m.
Results are only as good as the input: report errors and warnings to the engineer, check that the
sum of support reactions matches the applied load, and never present unchecked numbers as final.
Writing and running is limited to the work folders in settings.json; files are never overwritten
without overwrite=true (a .bak copy is kept).
Dashboard: the engineer watches a live page (http://localhost:8765) showing the running module, CPU/RAM,
token use, recent runs and checks.  During a multi-step check, call report_check at the start, after
each step (status, step, progress) and for every key finding (level pass / warn / fail with the member,
value and load case), and once at the end with status passed / failed / attention / done.
dashboard_status returns the same information as text, e.g. when the engineer asks how a run is going."""

mcp = FastMCP("sofistik", instructions=INSTRUCTIONS)

WAIT_S = 40            # Claude Desktop gives a tool call about 60 s; answer before that
STOP_WAIT_S = 5        # stop_calculation waits this long for the end, then answers "stopping"
MAX_ROWS = 5000        # upper limit for max_rows / max_entries
MAX_CDB_JOBS = 4       # .cdb reads running at the same time (each is a worker process)
_jobs: dict = {}
_calcs: dict = {}      # job id -> {"job", "proc", "stop", "cdb", "dat", "inputs"} of the calculations started
_latest: dict = {"id": None}
_copying: dict = {}    # normalised .cdb path -> clone job label, for as long as clone_cdb copies it
_last_run: dict = {}   # normalised .cdb path -> {"status", "cdb_updated"} of the last run in this server
BAD_RUN_STATUSES = ("errors", "not finished", "no protocol", "timed out", "stopped")
_root_cache: dict = {}


def _sofistik_root():
    """SOFiSTiK program folder for the dashboard's process list (looked up once per minute)."""
    if time.time() - _root_cache.get("t", 0) > 60:
        try:
            _root_cache.update(t=time.time(), root=_install().get("root"))
        except Exception:
            _root_cache.update(t=time.time(), root=None)
    return _root_cache.get("root")


_state = dashboard.ServerState(lambda: _settings(), VERSION)
_collector = dashboard.Collector(lambda: _settings(), _sofistik_root)


def _cap(n, default: int) -> int:
    try:
        return max(1, min(int(n), MAX_ROWS))
    except (TypeError, ValueError):
        return default


def _running() -> list[dict]:
    """The calculations still running, oldest first."""
    return [c for c in _calcs.values() if not c["job"]["done"].is_set()]


def _forget_finished() -> None:
    for k in [k for k, c in _calcs.items() if c["job"]["done"].is_set() and k != _latest["id"]]:
        _calcs.pop(k, None)


def _settings():
    return config.load_settings()


def _start_job(kind: str, label: str, fn, before=None) -> dict:
    job: dict = {"id": f"{kind}-{uuid.uuid4().hex[:8]}", "kind": kind, "label": label, "started": time.time(),
                 "result": None, "done": threading.Event()}

    def work():
        try:
            job["result"] = fn()
        except Exception as e:                      # report, never crash the server
            job["result"] = {"error": f"{type(e).__name__}: {e}"}
        finally:
            job["done"].set()

    _jobs[job["id"]] = job
    for old in sorted(_jobs.values(), key=lambda j: j["started"])[:-50]:
        if old["done"].is_set():
            _jobs.pop(old["id"], None)
    if before is not None:
        before(job)
    threading.Thread(target=work, daemon=True).start()
    return job


async def _wait(job: dict, seconds: float | None = None) -> dict:
    seconds = max(0.0, min(float(WAIT_S if seconds is None else seconds), 50.0))
    await anyio.to_thread.run_sync(lambda: job["done"].wait(seconds))
    if job["done"].is_set():
        return job["result"]
    return {"status": "running", "job_id": job["id"], "what": job["label"],
            "elapsed_s": round(time.time() - job["started"]),
            "next": f"Still working. Call get_job_result(job_id='{job['id']}') to wait for the result."}


def _not_in_server_folder(full: str):
    if config.is_inside(full, [config.ROOT]):
        raise config.AccessError(f"{full} is inside the MCP server's own folder ({config.ROOT}); "
                                 "use another folder for models.")


def _install(settings=None):
    try:
        return install.find(settings or _settings())
    except install.SofistikNotFound as e:
        return {"error": str(e), "root": None, "sps": None, "dll": None, "daten": None, "dll_dirs": []}


def _err(e: Exception) -> dict:
    return {"error": str(e)}


# ------------------------------------------------------------------------------------------------
# status and files
# ------------------------------------------------------------------------------------------------

@mcp.tool()
async def sofistik_status() -> dict:
    """Check the setup: where SOFiSTiK is, which folders this server may read and write, and whether
    the manual index is available.  Call this first if anything fails."""
    s = _settings()
    info = _install(s)
    return {"server_version": VERSION, "python": sys.version.split()[0], "settings_file": s.get("_path"),
            "sofistik": info, "work_folders": s["work_folders"], "read_folders": s["read_folders"],
            "examples_folders": s["examples_folders"], "manual_folders": s["manual_folders"],
            "allow_sys_commands": s["allow_sys_commands"],
            "run_timeout_minutes": s["run_timeout_minutes"] or "no limit",
            "max_parallel_runs": s["max_parallel_runs"], "min_free_ram_gb": s["min_free_ram_gb"],
            "auto_clear_cdb_locks": s["auto_clear_cdb_locks"],
            "manual_index_shipped": os.path.isfile(docsearch.SHIPPED_INDEX)}


@mcp.tool()
async def list_folder(path: str, pattern: str = "*", recursive: bool = False, max_entries: int = 300) -> dict:
    """List files in a folder (for finding .dat / .cdb / .prt files).  pattern is a wildcard such as
    '*.cdb'.  recursive=True also looks in sub-folders."""
    s = _settings()
    try:
        full = config.check_read(path, s, _install(s).get("root"))
    except config.AccessError as e:
        return _err(e)
    if not os.path.isdir(full):
        return {"error": f"Not a folder: {full}"}
    max_entries = _cap(max_entries, 300)
    rows = []
    walker = os.walk(full) if recursive else [
        (full, [d for d in os.listdir(full) if os.path.isdir(os.path.join(full, d))],
         [f for f in os.listdir(full) if os.path.isfile(os.path.join(full, f))])]
    folders = []
    for dirpath, dirs, files in walker:
        if not recursive:
            folders = sorted(dirs)
        for f in sorted(files):
            if fnmatch.fnmatch(f.lower(), pattern.lower()):
                p = os.path.join(dirpath, f)
                st = os.stat(p)
                rows.append({"path": p, "size_kb": round(st.st_size / 1024, 1),
                             "modified": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
                if len(rows) > max_entries:
                    break
        if len(rows) > max_entries:
            break
    return {"folder": full, "sub_folders": folders, "files": rows[:max_entries],
            "truncated": len(rows) > max_entries}


@mcp.tool()
async def read_text_file(path: str, start_line: int = 1, max_lines: int = 400) -> dict:
    """Read part of a text file (.dat, .prt, .erg, .lst, .txt, .csv, .md).  Lines are numbered from 1;
    use start_line to page through long files."""
    s = _settings()
    try:
        full = config.check_read(path, s, _install(s).get("root"))
    except config.AccessError as e:
        return _err(e)
    if not os.path.isfile(full):
        return {"error": f"File not found: {full}"}
    if full.lower().endswith((".cdb", ".plb", ".pdf", ".exe", ".dll")):
        return {"error": "That is a binary file. Use the cdb_* tools for .cdb results and the manual tools for PDFs."}
    lines = messages.read_text(full).split("\n")
    a = max(1, int(start_line))
    b = min(len(lines), a + max(1, min(int(max_lines), 2000)) - 1)
    return {"path": full, "total_lines": len(lines), "from_line": a, "to_line": b,
            "text": "\n".join(f"{i}: {lines[i - 1]}" for i in range(a, b + 1))}


@mcp.tool()
async def write_dat_file(path: str, content: str, overwrite: bool = False) -> dict:
    """Write a SOFiSTiK CADINP input file (.dat) inside a work folder.  Refuses to replace an existing
    file unless overwrite=True; when it does replace one, the old file is kept as <name>.dat.bak-<time>."""
    s = _settings()
    bad = config.bad_file_name(path)          # before abspath: Windows would quietly change such a name
    if bad:
        return {"error": bad}
    try:
        full = config.check_write(path, s)
        _not_in_server_folder(full)
    except config.AccessError as e:
        return _err(e)
    if not full.lower().endswith(".dat"):
        return {"error": "The file name must end in .dat."}
    for c in _running():
        # SOFiSTiK reads #INCLUDE / +APPLY files while it runs: nothing it uses may change under it.  Until
        # its input check is done every file in its folder counts as its input.
        mine = config._norm(full)
        if mine in c["inputs"] or (c["inputs_pending"] and config._norm(os.path.dirname(full)) == c["folder"]):
            j = c["job"]
            return {"error": f"A calculation that reads this file is running ({j['label']}); it cannot be "
                             f"written until that has finished. Wait with get_job_result('{j['id']}') or stop "
                             "it with stop_calculation."}
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    if not s["allow_sys_commands"]:
        found = solver.sys_lines_in_text(text, full, config.readable_folders(s, _install(s).get("root")))
        if found:
            return {"error": "The content has lines that can make SOFiSTiK run Windows commands (+SYS / *SYS, or "
                             "$(...) substitution that could build one), which settings.json does not allow "
                             "(\"allow_sys_commands\": false). Remove them; if the engineer really needs them, they "
                             "can set \"allow_sys_commands\": true in settings.json and restart Claude.",
                    "sys_lines": found}
    try:
        data = (text if text.endswith("\n") else text + "\n").replace("\n", "\r\n").encode("utf-8")
    except UnicodeEncodeError as e:
        return {"error": f"The content cannot be saved as UTF-8 ({e.reason} at character {e.start}); nothing was "
                         "written."}
    if os.path.exists(full) and not overwrite:
        return {"error": f"{full} already exists. Use another name, or overwrite=True (a backup is kept)."}
    folder = os.path.dirname(full)
    os.makedirs(folder, exist_ok=True)
    backup = None
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(full) + ".", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if os.path.exists(full):
            backup = config.backup_name(full)
            shutil.copy2(full, backup)               # the old file stays in place until the new one replaces it
        os.replace(tmp, full)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    non_ascii = sorted({ch for ch in text if ord(ch) > 127})
    out = {"written": full, "lines": text.count("\n") + 1, "backup_of_previous": backup}
    if non_ascii:
        out["warning"] = ("The file contains non-ASCII characters " + "".join(non_ascii[:20]) +
                          "; saved as UTF-8. If SOFiSTiK shows strange characters, replace them.")
    return out


# ------------------------------------------------------------------------------------------------
# calculation
# ------------------------------------------------------------------------------------------------

@mcp.tool()
async def run_calculation(dat_path: str, continue_on_error: bool = False, only_block_urs: int | None = None,
                          timeout_minutes: float | None = None) -> dict:
    """Run a .dat with SOFiSTiK in batch mode (sps.exe, no window).  Returns the status, every error
    and warning (with the input lines before it from the .erg), the programs that ran and the output
    files (.cdb, .prt, .erg, .plb).  If it takes longer than about 40 s it returns status 'running'
    and a job_id: then call get_job_result(job_id).  continue_on_error=True keeps going after an error
    (-R).  only_block_urs runs only the +PROG block with that urs number.  One calculation at a time."""
    s = _settings()
    bad = config.bad_file_name(dat_path)
    if bad:
        return {"status": "not run", "reason": bad}
    try:
        full = config.check_write(dat_path, s)
        _not_in_server_folder(full)
    except config.AccessError as e:
        return _err(e)
    info = _install(s)
    if not info.get("sps"):
        return {"status": "not run", "reason": info.get("error") or "sps.exe not found", "sofistik": info}
    limit = s["run_timeout_minutes"] or None              # None: no time limit
    if timeout_minutes is not None and float(timeout_minutes) > 0:
        limit = max(1.0, float(timeout_minutes) if limit is None else min(float(timeout_minutes), limit))
    cdb_key = config._norm(os.path.splitext(full)[0] + ".cdb")
    busy = _parallel_refusal(full, cdb_key, s)
    if busy:
        return busy
    _forget_finished()
    entry: dict = {"job": None, "proc": None, "stop": False, "cdb": cdb_key, "dat": config._norm(full),
                   "dat_path": full, "folder": config._norm(os.path.dirname(full)), "inputs": {config._norm(full)},
                   "inputs_pending": True}

    def on_start(proc):
        entry["proc"] = proc
        _state.job_process(proc.pid, key=entry["job"]["id"])

    def on_scan(scan):
        entry["inputs"] = {config._norm(p) for p in scan.get("hashes", {})} | {config._norm(full)}
        entry["inputs_pending"] = False
        _state.job_programs(1 if only_block_urs is not None else len(scan.get("programs") or []) or None,
                            key=entry["job"]["id"])

    def work():
        log.info("run %s", full)
        r: dict = {}
        try:
            r = solver.run(full, info["sps"], None if limit is None else limit * 60,
                           allow_sys=s["allow_sys_commands"],
                           continue_on_error=continue_on_error, only_urs=only_block_urs,
                           on_start=on_start, stopped=lambda: entry["stop"],
                           readable=config.readable_folders(s, info.get("root")),
                           on_tick=lambda w: _state.job_progress(w, key=entry["job"]["id"]),
                           sofistik_root=info.get("root"), auto_clear_locks=s["auto_clear_cdb_locks"],
                           on_scan=on_scan, clean_cmd=str(s.get("clean_locks_command") or ""))
            if r.get("status") != "not run":
                _last_run[cdb_key] = {"status": r.get("status"),
                                      "cdb_updated": bool(r.get("files", {}).get("cdb", {}).get("updated_by_this_run"))}
            return r
        finally:
            entry["proc"] = None
            _state.job_finished(r, key=entry["job"]["id"])

    with _start_lock:
        busy = _parallel_refusal(full, cdb_key, s)          # again, now that no other start can slip in
        if busy:
            return busy
        job = _start_job("calc", os.path.basename(full), work, before=lambda j: _register(j, entry, full))
    return await _wait(job)


_start_lock = threading.Lock()


def _register(job: dict, entry: dict, full: str) -> None:
    entry["job"] = job
    _calcs[job["id"]] = entry
    _latest["id"] = job["id"]
    _state.job_started(full, key=job["id"])


def _parallel_refusal(full: str, cdb_key: str, s: dict) -> dict | None:
    """Why this calculation may not start now (None: it may)."""
    if cdb_key in _copying:
        return {"status": "not run", "reason": f"This model's .cdb is being copied ({_copying[cdb_key]}); start it "
                                               "after the copy has finished."}
    running = _running()
    for c in running:
        if c["cdb"] == cdb_key:
            j = c["job"]
            return {"status": "not run", "job_id": j["id"],
                    "reason": f"This model is already being calculated ({j['label']}). Wait with "
                              f"get_job_result('{j['id']}') or stop it with stop_calculation."}
    if not running:
        return None
    labels = ", ".join(f"{c['job']['label']} ({c['job']['id']})" for c in running)
    if len(running) >= s["max_parallel_runs"]:
        return {"status": "not run", "running": [c["job"]["id"] for c in running],
                "reason": f"{len(running)} calculation(s) already running ({labels}); settings.json "
                          f"\"max_parallel_runs\" allows {s['max_parallel_runs']}. Wait for one with get_job_result."}
    ram = _ram_check(full, running, s)
    if ram:
        return {"status": "not run", "running": [c["job"]["id"] for c in running], "reason": ram}
    return None


def _ram_check(full: str, running: list, s: dict) -> str | None:
    """A second calculation only starts if the RAM it needed last time (or, never run here, what the
    calculations now running need) fits next to what the running ones may still grow to, with
    min_free_ram_gb to spare."""
    if psutil is None:                                     # pragma: no cover
        return None
    hist = _state.history()
    avail = psutil.virtual_memory().available / 2**20
    growth = 0.0
    biggest = 0.0
    spare = s["min_free_ram_gb"] * 1024
    for c in running:
        job = _state.job_info(c["job"]["id"]) or {}
        now_mb = float(job.get("ram_mb") or 0)
        # never run here: at least the spare (its RAM is only known after it has run a while)
        peak = float((hist.peak_ram_mb(c["dat_path"]) if hist else None) or max(job.get("peak_ram_mb") or 0, spare))
        growth += max(peak - now_mb, 0.0)
        biggest = max(biggest, peak)
    last = hist.peak_ram_mb(full) if hist else None
    basis = ("what it needed last time" if last else
             "the largest calculation running now, as this file has not run here")
    need = float(last or max(biggest, spare))
    if avail - growth - need < spare:
        return (f"Not enough free RAM to start a second calculation: {avail / 1024:.1f} GB free, the running "
                f"calculation(s) may still need {growth / 1024:.1f} GB more, this one about {need / 1024:.1f} GB "
                f"({basis}), and settings.json \"min_free_ram_gb\" keeps {s['min_free_ram_gb']:g} GB spare. "
                "Wait for the running calculation with get_job_result.")
    return None


@mcp.tool()
async def get_job_result(job_id: str | None = None, wait_seconds: float = 40) -> dict:
    """Wait (up to wait_seconds, max 50) for a calculation or .cdb read that answered 'running', and
    return its result.  Without job_id: the latest calculation."""
    job = _jobs.get(job_id) if job_id else (_calcs.get(_latest["id"]) or {}).get("job")
    if job is None:
        return {"error": f"No job {job_id or '(no calculation started yet)'}. Jobs are forgotten when Claude restarts."}
    return await _wait(job, wait_seconds)


@mcp.tool()
async def stop_calculation(job_id: str | None = None) -> dict:
    """Stop a running SOFiSTiK calculation (kills sps.exe and every program it started).  job_id: which
    one (needed when several run; job_id="all" stops every one).  Answers within a few seconds:
    'stopped' with the result, or 'stopping' (then get_job_result gives the final state)."""
    running = _running()
    if job_id and job_id != "all":
        running = [c for c in running if c["job"]["id"] == job_id]
    if not running:
        return {"status": "nothing running" + (f" with job_id {job_id}" if job_id else "")}
    if not job_id and len(running) > 1:
        return {"status": "not stopped", "running": [{"job_id": c["job"]["id"], "what": c["job"]["label"]}
                                                     for c in running],
                "reason": "Several calculations are running: give the job_id of the one to stop, or job_id='all'."}
    for c in running:
        c["stop"] = True
        if c["proc"] is not None:
            solver.kill_tree_async(c["proc"])
    out = []
    for c in running:
        job = c["job"]
        r = await _wait(job, STOP_WAIT_S)
        if r.get("status") == "running":
            r = {"status": "stopping", "job_id": job["id"],
                 "next": f"SOFiSTiK is being stopped. Call get_job_result(job_id='{job['id']}') for the final state."}
        out.append(r)
    return out[0] if len(out) == 1 else {"status": "stopped several", "results": out}


@mcp.tool()
async def read_calculation_messages(path: str) -> dict:
    """Errors, warnings and end state of an earlier calculation.  path: the .dat, .prt or .erg."""
    s = _settings()
    try:
        full = config.check_read(path, s, _install(s).get("root"))
    except config.AccessError as e:
        return _err(e)
    stem = os.path.splitext(full)[0]
    return messages.summarize_run(stem + ".prt", stem + ".erg")


def _cdb_path(path: str) -> str:
    return path[:-4] + ".cdb" if path.lower().endswith(".dat") else path


@mcp.tool()
async def check_cdb_lock(cdb_path: str) -> dict:
    """Is a .cdb locked, and by which program?  Each program that has it open is one of: run (a
    calculation still running: wait), window (open in WinGRAF / Teddy / SSD ...: close it there),
    reader (this server reading results), orphan (left behind by a stopped or crashed run:
    clear_cdb_lock ends it), other.  cdb_path: the .cdb or its .dat."""
    s = _settings()
    info = _install(s)
    try:
        full = config.check_read(_cdb_path(cdb_path), s, info.get("root"))
    except config.AccessError as e:
        return _err(e)
    if not full.lower().endswith(".cdb"):
        return {"error": "Give the .cdb file (or its .dat)."}
    r = await anyio.to_thread.run_sync(lambda: cdblock.check(full, info.get("root")))
    r["calculating_here"] = [c["job"]["id"] for c in _running() if c["cdb"] == config._norm(full)]
    return r


@mcp.tool()
async def clear_cdb_lock(cdb_path: str, clean_stored_locks: bool = True) -> dict:
    """Clear a stale lock on a .cdb.  First ends only the SOFiSTiK programs left behind by a stopped or
    crashed run that still hold it (kind 'orphan' in check_cdb_lock).  Then, once no program has it
    open, resets the locks a killed run leaves written INSIDE the .cdb (SOFiSTiK error "WAIT FOR LOCK"
    / "another process is writing the key"; a copy of the file is locked too) with SOFiSTiK's own
    Clean Locks (clean_stored_locks=False skips that).  Running calculations, SOFiSTiK windows and
    other programs are never ended: the answer says what to close instead.  run_calculation does all
    this by itself when SOFiSTiK reports the lock (settings.json "auto_clear_cdb_locks")."""
    s = _settings()
    info = _install(s)
    try:
        full = config.check_write(_cdb_path(cdb_path), s)
    except config.AccessError as e:
        return _err(e)
    if not full.lower().endswith(".cdb"):
        return {"error": "Give the .cdb file (or its .dat)."}
    for c in _running():
        if c["cdb"] == config._norm(full):
            return {"error": f"This .cdb is being calculated right now ({c['job']['id']}): that is not a stale "
                             "lock. Stop it with stop_calculation if it must end."}
    r = await anyio.to_thread.run_sync(lambda: cdblock.clear(full, info.get("root"), clean_flag=clean_stored_locks,
                                                             clean_cmd=str(s.get("clean_locks_command") or "")))
    if r["ended"]:
        log.info("cleared lock on %s: ended %s", full, r["ended"])
    return r


CLONE_SPARE_BYTES = 1 * 2**30


@mcp.tool()
async def clone_cdb(cdb_path: str, new_name: str, overwrite: bool = False) -> dict:
    """Copy a model's .cdb so that several checks can run on it at the same time.  SOFiSTiK uses the
    .cdb with the same name as the .dat, so new_name is the name of the check's .dat (or a full path to
    it, or to the new .cdb): e.g. clone_cdb("C:\\...\\26016.cdb", "26016_bdk_part2") gives
    26016_bdk_part2.cdb next to it; then run 26016_bdk_part2.dat.  The copy is refused while the
    model is being calculated or locked.  overwrite=True replaces an existing copy (not a .cdb that is
    being calculated or is open)."""
    s = _settings()
    info = _install(s)
    try:
        src = config.check_read(_cdb_path(cdb_path), s, info.get("root"))
    except config.AccessError as e:
        return _err(e)
    if not src.lower().endswith(".cdb") or not os.path.isfile(src):
        return {"error": f"Source .cdb not found: {src}"}
    name = str(new_name).strip()
    if not name:
        return {"error": "new_name: give the name of the check's .dat, e.g. 26016_bdk_part2."}
    if not (os.path.isabs(name) or config.is_full_path(name)):
        name = os.path.join(os.path.dirname(src), name)
    base = os.path.splitext(name)[0] if name.lower().endswith((".dat", ".cdb")) else name
    target = base + ".cdb"
    bad = config.bad_file_name(target)
    if bad:
        return {"error": bad}
    try:
        target = config.check_write(target, s)
        _not_in_server_folder(target)
    except config.AccessError as e:
        return _err(e)
    if config._norm(target) == config._norm(src):
        return {"error": "new_name gives the same .cdb as the source."}
    if os.path.exists(target) and not overwrite:
        return {"error": f"{target} already exists. Use another name, or overwrite=True."}
    keys = (config._norm(src), config._norm(target))
    label = f"clone {os.path.basename(src)} -> {os.path.basename(target)}"
    with _start_lock:                                     # no calculation of either may start during the copy
        for c in _running():
            if c["cdb"] in keys:
                return {"error": f"{os.path.basename(c['cdb'])} is being calculated right now ({c['job']['id']}); "
                                 "copy it after the calculation has finished."}
        for k in keys:
            if k in _copying:
                return {"error": f"{os.path.basename(k)} is being copied right now ({_copying[k]})."}
        for k in keys:
            _copying[k] = label

    def work():
        try:
            return copy()
        finally:
            for k in keys:
                _copying.pop(k, None)

    def copy():
        for p, what in ((src, "source"), (target, "target")):
            if os.path.isfile(p):
                chk = cdblock.check(p, info.get("root"))
                if chk["locked"]:
                    return {"error": f"The {what} {os.path.basename(p)} is open in another program, so a copy may be "
                                     "half-written: " + " ".join(chk["advice"]), "holders": chk["holders"]}
        size = os.path.getsize(src)
        free = shutil.disk_usage(os.path.dirname(target)).free
        if free < size + CLONE_SPARE_BYTES:
            return {"error": f"Not enough disk space: the copy needs {size / 2**30:.1f} GB and leaves less than "
                             f"1 GB free ({free / 2**30:.1f} GB free now)."}
        t0 = time.time()
        for old in glob.glob(glob.escape(target) + ".*.copying"):   # left by a copy that was cut off
            try:
                os.remove(old)
            except OSError:
                pass
        tmp = target + f".{os.getpid()}.copying"
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        dat = base + ".dat"
        return {"copied": src, "to": target, "size_mb": round(size / 2**20, 1), "seconds": round(time.time() - t0, 1),
                "dat_to_run": dat, "dat_exists": os.path.isfile(dat),
                "note": "Run dat_to_run with run_calculation; it reads and writes this copy, not the original."}

    job = _start_job("copy", label, work)
    return await _wait(job)


# ------------------------------------------------------------------------------------------------
# results (.cdb), read in a worker process
# ------------------------------------------------------------------------------------------------

def _cdb_call(op: str, cdb_path: str, args: dict, timeout_s: float = 900) -> dict:
    s = _settings()
    info = _install(s)
    try:
        full = config.check_read(cdb_path, s, info.get("root"))
    except config.AccessError as e:
        return _err(e)
    if full.lower().endswith(".dat"):
        full = full[:-4] + ".cdb"
    if not full.lower().endswith(".cdb"):
        return {"error": "Give the .cdb file (or its .dat)."}
    for c in _running():
        if c["cdb"] == config._norm(full):
            return {"error": "This .cdb is being calculated right now. Wait for the calculation "
                             f"(get_job_result('{c['job']['id']}')) and read it afterwards."}
    if not os.path.isfile(full):
        return {"error": f".cdb not found: {full}. Run the calculation first."}
    if not info.get("dll") or not info.get("daten"):
        return {"error": "SOFiSTiK CDB interface not found (sof_cdb_w-20xx.dll / sofistik_daten.py).", "sofistik": info}
    with tempfile.TemporaryDirectory(prefix="sofmcp_") as tmp:
        req, ans = os.path.join(tmp, "req.json"), os.path.join(tmp, "ans.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump({"op": op, "cdb": full, "info": info, "args": args}, f)
        kw: dict = {"cwd": config.ROOT, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                    "stderr": subprocess.STDOUT, "timeout": timeout_s}
        if os.name == "nt":
            kw["creationflags"] = solver.CREATE_NO_WINDOW
        try:
            p = subprocess.run([sys.executable, "-m", "sofistik_mcp.cdb_worker", req, ans], **kw)
        except subprocess.TimeoutExpired:
            return {"error": f"Reading the .cdb took longer than {timeout_s / 60:.0f} minutes; narrow the request."}
        if not os.path.isfile(ans):
            tail = (p.stdout or b"").decode("utf-8", errors="replace")[-1500:]
            return {"error": f"The .cdb reader stopped without an answer (exit code {p.returncode}). "
                             "SOFiSTiK's DLL may have crashed or the .cdb is locked by another program.",
                    "output": tail}
        with open(ans, encoding="utf-8") as f:
            a = json.load(f)
    if not a.get("ok"):
        return {"error": a.get("error"), **({"traceback": a["traceback"]} if a.get("traceback") else {})}
    res = a["result"]
    if isinstance(res, list):
        res = {"rows": res}
    res["cdb"] = full
    stale = _stale_warnings(full)
    if stale:
        res["stale_results_warning"] = stale
    return res


STALE_TOLERANCE_S = 60


def _stale_warnings(cdb: str) -> list[str]:
    """Reasons to doubt that the .cdb belongs to the current .dat / last calculation."""
    out = []
    stem = os.path.splitext(cdb)[0]
    try:
        t_cdb = os.path.getmtime(cdb)
        for ext, what in ((".prt", "protocol"), (".dat", "input")):
            p = stem + ext
            if os.path.isfile(p) and os.path.getmtime(p) > t_cdb + (STALE_TOLERANCE_S if ext == ".prt" else 0):
                out.append(f"The .cdb is older than the {what} {os.path.basename(p)} next to it: these results may "
                           "come from an earlier calculation.")
    except OSError:
        pass
    last = _last_run.get(config._norm(cdb))
    if last:
        if last["status"] in BAD_RUN_STATUSES or str(last["status"]).startswith("check"):
            out.append(f"The last calculation of this model in this session ended with status '{last['status']}': "
                       "the results are not valid until it runs cleanly.")
        elif not last["cdb_updated"]:
            out.append("The last calculation of this model in this session did not update the .cdb.")
    return out


async def _cdb(op, cdb_path, **args):
    busy = [j for j in _jobs.values() if j["kind"] == "cdb" and not j["done"].is_set()]
    if len(busy) >= MAX_CDB_JOBS:
        return {"error": f"{len(busy)} .cdb reads are still running (at most {MAX_CDB_JOBS} at a time). Wait for "
                         "them with get_job_result(" + ", ".join(repr(j["id"]) for j in busy) + ") first."}
    job = _start_job("cdb", f"{op} {os.path.basename(str(cdb_path))}", lambda: _cdb_call(op, cdb_path, args))
    return await _wait(job)


@mcp.tool()
async def cdb_overview(cdb_path: str) -> dict:
    """Summary of a .cdb: project, element counts, materials, sections (A, Iy, Iz), groups and every
    load case (title, action, sum of reactions, eigenfrequency, which results exist)."""
    return await _cdb("overview", cdb_path)


@mcp.tool()
async def cdb_load_cases(cdb_path: str, load_cases: str | None = None) -> dict:
    """Load cases in the .cdb.  load_cases filters, e.g. '101-118,201'."""
    return await _cdb("load_cases", cdb_path, lcs=load_cases)


@mcp.tool()
async def cdb_nodes(cdb_path: str, nodes: str | None = None, max_rows: int = 500) -> dict:
    """Node coordinates [m] (e.g. nodes='1-100')."""
    return await _cdb("nodes", cdb_path, ids=nodes, max_rows=_cap(max_rows, 500))


@mcp.tool()
async def cdb_node_results(cdb_path: str, load_case: int, nodes: str | None = None, max_rows: int = 200,
                           include_coords: bool = False) -> dict:
    """Node displacements [mm], rotations [mrad] and support forces for one load case, with the
    extreme values over all selected nodes."""
    return await _cdb("node_results", cdb_path, lc=load_case, ids=nodes, max_rows=_cap(max_rows, 200),
                      include_coords=include_coords)


@mcp.tool()
async def cdb_support_reactions(cdb_path: str, load_case: int, nodes: str | None = None, max_rows: int = 500) -> dict:
    """Support reactions [kN, kNm] for one load case, their sum, and the sum SOFiSTiK stored, as a check.
    With a node filter the sum is a partial sum of those nodes only (sum_is_partial); compare totals with
    sum_stored_by_sofistik_kN.  Each extreme also gives the other components at the same node."""
    return await _cdb("support_reactions", cdb_path, lc=load_case, ids=nodes, max_rows=_cap(max_rows, 500))


@mcp.tool()
async def cdb_beam_forces(cdb_path: str, load_case: int, beams: str | None = None, groups: str | None = None,
                          structural_lines: str | None = None, ends_only: bool = False, max_rows: int = 300) -> dict:
    """Beam internal forces N, Vy, Vz [kN], Mt, My, Mz [kNm] at every result station for one load case,
    filtered by beam numbers, groups or structural line (SLN) numbers, with the extremes.  Group = element
    number // SYST GDIV when GDIV > 0, else the structural line's group, else the one beam group range
    containing the beam; beams whose group is ambiguous are left out of a group filter and listed in a
    warning.  Each extreme also gives the concurrent forces at the same station."""
    return await _cdb("beam_forces", cdb_path, lc=load_case, beams=beams, groups=groups, slns=structural_lines,
                      ends_only=ends_only, max_rows=_cap(max_rows, 300))


@mcp.tool()
async def cdb_truss_cable_forces(cdb_path: str, load_case: int, element_type: str = "truss",
                                 elements: str | None = None, max_rows: int = 300) -> dict:
    """Axial forces [kN] of truss or cable elements (element_type 'truss' or 'cable') for one load case."""
    if element_type not in ("truss", "cable"):
        return {"error": "element_type must be 'truss' or 'cable'."}
    return await _cdb("axial_forces", cdb_path, lc=load_case, element_type=element_type, ids=elements,
                      max_rows=_cap(max_rows, 300))


@mcp.tool()
async def cdb_envelope(cdb_path: str, load_cases: str, what: str = "beam", ids: str | None = None,
                       groups: str | None = None, structural_lines: str | None = None) -> dict:
    """Max and min of every component over several load cases (e.g. '101-118') with the governing load
    case and location.  what: 'beam', 'node', 'support', 'truss' or 'cable'.  load_cases_found are the
    cases that gave values; load_cases_without_data, load_cases_missing and eigen_load_cases_skipped list
    the rest.  Extremes of different components are not concurrent: each extreme carries the other
    components of its own row under 'concurrent'."""
    if what not in ("beam", "node", "support", "truss", "cable"):
        return {"error": "what must be beam, node, support, truss or cable."}
    return await _cdb("envelope", cdb_path, lcs=load_cases, what=what, ids=ids, groups=groups,
                      slns=structural_lines)


@mcp.tool()
async def cdb_read_key(cdb_path: str, kwh: int, kwl: int, class_name: str | None = None,
                       max_records: int = 20, skip: int = 0) -> dict:
    """Advanced: raw records of any CDB key (kwh/kwl, see SOFiSTiK's sofistik_daten.py / CDBASE help),
    decoded with a sofistik_daten class such as 'CQUAD_FOR'.  Values are raw SI units."""
    return await _cdb("read_key", cdb_path, kwh=kwh, kwl=kwl, class_name=class_name,
                      max_records=max(1, min(int(max_records), 500)), skip=max(0, int(skip)))


# ------------------------------------------------------------------------------------------------
# manuals and examples
# ------------------------------------------------------------------------------------------------

_manuals = None
_examples = None


# ------------------------------------------------------------------------------------------------
# dashboard
# ------------------------------------------------------------------------------------------------

@mcp.tool()
async def report_check(check: str, status: str | None = None, step: str | None = None,
                       progress: str | None = None, findings: list | None = None,
                       clear_findings: bool = False) -> dict:
    """Show the progress and key findings of a check on the engineer's live dashboard.  Call it when a
    check starts, after each step and for every key finding, and once at the end.
    check: a short name, the same on every call (e.g. "26016 member checks").
    status: running | passed | failed | attention | waiting | done.
    step: what is happening now, one line (e.g. "ASE: ULS combinations 101-154").
    progress: optional, e.g. "3 of 7".
    findings: new key findings, each {"level": "info"|"pass"|"warn"|"fail", "text": "..."}; they are added
    after the earlier ones.  Give the member, the value, the limit and the load case, e.g.
    {"level": "fail", "text": "B81 UB 457x191x89: LTB ratio 1.12 > 1.0 (LC 118)"}.
    clear_findings=True starts the list again (e.g. for a rerun)."""
    try:
        s = _settings()
        return await anyio.to_thread.run_sync(
            lambda: dashboard.report_check(s, check, status, step, progress, findings, clear_findings))
    except (config.SettingsError, OSError) as e:
        return _err(e)


@mcp.tool()
async def dashboard_status() -> dict:
    """What the live dashboard shows right now, as data: the SOFiSTiK module running, the calculation and
    how long it has run, PC CPU and RAM, SOFiSTiK and Claude processes, the checks with their latest
    findings, the last calculations and today's Claude Code token use on this PC."""
    d = await anyio.to_thread.run_sync(_collector.collect)
    try:
        host, port = dashboard.dashboard_options(_settings())
    except config.SettingsError:
        host, port = "127.0.0.1", dashboard.DEFAULT_PORT
    lan = f" (same Wi-Fi: http://{d.get('host')}:{port})" if host != "127.0.0.1" else ""
    d["page"] = f"http://localhost:{port}{lan}"
    for c in d.get("checks") or []:
        c["findings"] = c.get("findings", [])[-15:]
    return d


def _man():
    global _manuals
    if _manuals is None:
        _manuals = docsearch.Manuals(_settings()["manual_folders"])
    return _manuals


def _ex():
    global _examples
    if _examples is None:
        _examples = docsearch.Examples(_settings()["examples_folders"])
    return _examples


@mcp.tool()
async def search_manuals(query: str, manuals: list[str] | None = None, max_hits: int = 15) -> dict:
    """Search the SOFiSTiK manuals (English).  All words must be on the page; use "quotes" for a
    phrase.  manuals narrows the search, e.g. ['sofiload', 'ase'].  Returns manual, PDF page, snippet."""
    return await anyio.to_thread.run_sync(lambda: _man().search(query, manuals, max_hits))


@mcp.tool()
async def read_manual_page(manual: str, page: int, count: int = 1) -> dict:
    """Text of a manual page (PDF page number from search_manuals), up to 5 pages at once."""
    return await anyio.to_thread.run_sync(lambda: _man().page(manual, page, count))


@mcp.tool()
async def list_manuals() -> dict:
    """The manual PDFs found and whether each is in the search index."""
    return {"manuals": await anyio.to_thread.run_sync(lambda: _man().status())}


@mcp.tool()
async def index_manual(manual: str) -> dict:
    """Add one manual PDF (file name from list_manuals) to the search index.  Takes up to a minute."""
    try:
        return await anyio.to_thread.run_sync(lambda: _man().build(manual))
    except Exception as e:
        return _err(e)


@mcp.tool()
async def search_examples(query: str, max_files: int = 15) -> dict:
    """Search the shipped SOFiSTiK example .dat files (about 1,200) for CADINP syntax.  All words must
    be in the file; use "quotes" for a phrase.  English examples are listed first."""
    return await anyio.to_thread.run_sync(lambda: _ex().search(query, max_files))


def main():
    log.info("SOFiSTiK MCP server %s starting (Python %s)", VERSION, sys.version.split()[0])
    _start_dashboard()
    try:
        mcp.run()
    finally:
        _state.remove()


def _start_dashboard():
    """Serve the live page in a background thread (best effort: never stops the server starting)."""
    try:
        _state.started()
        host, port = dashboard.dashboard_options(_settings())
        if dashboard.start(_collector, host, port):
            log.info("dashboard on http://localhost:%s", port)
        else:
            log.info("dashboard not started here (port %s taken or switched off)", port)
    except Exception as e:                          # pragma: no cover - logged, never fatal
        log.warning("dashboard not started: %s", e)


if __name__ == "__main__":
    main()
