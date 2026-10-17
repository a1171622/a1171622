"""SOFiSTiK MCP server (stdio).  Lets Claude write CADINP .dat files, run them with SOFiSTiK in batch
mode, read the errors, read results from the .cdb, and search the manuals and shipped examples.

Started by Claude Desktop / Claude Code through run_server.py.  Nothing may be printed to stdout
(that is the MCP channel): logging goes to stderr, SOFiSTiK runs in a child process with its output
captured, and the .cdb is read in a separate worker process (cdb_worker.py).
"""
from __future__ import annotations

import datetime
import fnmatch
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

from . import config, docsearch, install, messages, solver

log = logging.getLogger("sofistik-mcp")
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VERSION = "1.0.0"

INSTRUCTIONS = """\
Tools for SOFiSTiK 2027 on this PC (structural FEA).  Typical loop:
1. Look up syntax: search_examples (shipped .dat examples) and search_manuals / read_manual_page.
2. write_dat_file: write the CADINP input (.dat) inside a work folder.
3. run_calculation: SOFiSTiK solves it in batch mode (sps.exe).  A long run returns
   status 'running' with a job_id: call get_job_result(job_id) until it is finished (each call waits
   up to 40 s).  ALWAYS read the final status, errors and warnings; 'errors' means the results are
   not valid.  stop_calculation stops a run (if it answers 'stopping', get_job_result gives the final
   state).  While a calculation runs, write_dat_file refuses to write.  Big .cdb reads can also
   return a job_id.
4. cdb_overview / cdb_load_cases, then cdb_node_results, cdb_support_reactions, cdb_beam_forces,
   cdb_truss_cable_forces, cdb_envelope to read results from the .cdb.
Units returned: displacements mm, rotations mrad, forces kN, moments kNm, coordinates m.
Results are only as good as the input: report errors and warnings to the engineer, check that the
sum of support reactions matches the applied load, and never present unchecked numbers as final.
Writing and running is limited to the work folders in settings.json; files are never overwritten
without overwrite=true (a .bak copy is kept)."""

mcp = FastMCP("sofistik", instructions=INSTRUCTIONS)

WAIT_S = 40            # Claude Desktop gives a tool call about 60 s; answer before that
STOP_WAIT_S = 5        # stop_calculation waits this long for the end, then answers "stopping"
MAX_ROWS = 5000        # upper limit for max_rows / max_entries
MAX_CDB_JOBS = 4       # .cdb reads running at the same time (each is a worker process)
_jobs: dict = {}
_calc: dict = {"job": None, "proc": None, "stop": False, "cdb": None}
_last_run: dict = {}   # normalised .cdb path -> {"status", "cdb_updated"} of the last run in this server
BAD_RUN_STATUSES = ("errors", "not finished", "no protocol", "timed out", "stopped")


def _cap(n, default: int) -> int:
    try:
        return max(1, min(int(n), MAX_ROWS))
    except (TypeError, ValueError):
        return default


def _calc_running():
    cur = _calc["job"]
    return cur if cur is not None and not cur["done"].is_set() else None


def _settings():
    return config.load_settings()


def _start_job(kind: str, label: str, fn) -> dict:
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
            "allow_sys_commands": s["allow_sys_commands"], "run_timeout_minutes": s["run_timeout_minutes"],
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
    cur = _calc_running()
    if cur is not None:
        # SOFiSTiK reads #INCLUDE / +APPLY files while it runs: nothing may change under it
        return {"error": f"A calculation is running ({cur['label']}); files cannot be written until it has "
                         f"finished. Wait with get_job_result('{cur['id']}') or stop it with stop_calculation."}
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
    limit = s["run_timeout_minutes"]
    if timeout_minutes is not None:
        limit = max(1.0, min(float(timeout_minutes), limit))
    cur = _calc["job"]
    if cur is not None and not cur["done"].is_set():
        return {"status": "not run", "reason": f"Another calculation is still running ({cur['label']}). "
                f"Wait with get_job_result('{cur['id']}') or stop it with stop_calculation.",
                "job_id": cur["id"]}
    cdb_key = config._norm(os.path.splitext(full)[0] + ".cdb")
    _calc.update(stop=False, proc=None, cdb=cdb_key)

    def on_start(proc):
        _calc["proc"] = proc

    def work():
        log.info("run %s", full)
        try:
            r = solver.run(full, info["sps"], limit * 60, allow_sys=s["allow_sys_commands"],
                           continue_on_error=continue_on_error, only_urs=only_block_urs,
                           on_start=on_start, stopped=lambda: _calc["stop"],
                           readable=config.readable_folders(s, info.get("root")))
            if r.get("status") != "not run":
                _last_run[cdb_key] = {"status": r.get("status"),
                                      "cdb_updated": bool(r.get("files", {}).get("cdb", {}).get("updated_by_this_run"))}
            return r
        finally:
            _calc["proc"] = None

    job = _start_job("calc", os.path.basename(full), work)
    _calc["job"] = job
    return await _wait(job)


@mcp.tool()
async def get_job_result(job_id: str | None = None, wait_seconds: float = 40) -> dict:
    """Wait (up to wait_seconds, max 50) for a calculation or .cdb read that answered 'running', and
    return its result.  Without job_id: the latest calculation."""
    job = _jobs.get(job_id) if job_id else _calc["job"]
    if job is None:
        return {"error": f"No job {job_id or '(no calculation started yet)'}. Jobs are forgotten when Claude restarts."}
    return await _wait(job, wait_seconds)


@mcp.tool()
async def stop_calculation() -> dict:
    """Stop the running SOFiSTiK calculation (kills sps.exe and the programs it started).  Answers within
    a few seconds: 'stopped' with the result, or 'stopping' (then get_job_result gives the final state)."""
    job, proc = _calc["job"], _calc["proc"]
    if job is None or job["done"].is_set():
        return {"status": "nothing running"}
    _calc["stop"] = True
    if proc is not None:
        solver.kill_tree_async(proc)
    r = await _wait(job, STOP_WAIT_S)
    if r.get("status") == "running":
        return {"status": "stopping", "job_id": job["id"],
                "next": f"SOFiSTiK is being stopped. Call get_job_result(job_id='{job['id']}') for the final state."}
    return r


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
    cur = _calc["job"]
    if cur is not None and not cur["done"].is_set() and _calc["cdb"] == config._norm(full):
        return {"error": "This .cdb is being calculated right now. Wait for the calculation "
                         f"(get_job_result('{cur['id']}')) and read it afterwards."}
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
    mcp.run()


if __name__ == "__main__":
    main()
