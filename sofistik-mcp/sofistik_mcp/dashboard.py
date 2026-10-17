"""Live dashboard for the SOFiSTiK MCP workflow: a small read-only web page on this PC.

What it shows, and where each number comes from
  PC resources        CPU and RAM of the whole PC (psutil).
  SOFiSTiK programs   every running process started from the SOFiSTiK program folder (or with a known
                      SOFiSTiK program name), with its CPU and RAM.  The newest one started by sps.exe is
                      "the module running now" (AQUA, SOFIMSHA, SOFILOAD, ASE, BDK, MAXIMA ...).
  Calculations        what each running MCP server writes to <first work folder>\\_dashboard\\server-<pid>.json:
                      the calculation it is running and the last 20 runs (status, errors, warnings, time).
  Checks              <first work folder>\\_dashboard\\checks\\<name>.json, written by a checking session
                      with the report_check tool (or directly as a file, format in CHECK_FORMAT below).
  Claude token usage  Claude Code sessions on THIS PC only: the usage lines Claude Code records in
                      %USERPROFILE%\\.claude\\projects\\...\\*.jsonl (today, local time).  Claude Desktop chats
                      and claude.ai / cloud sessions do not record usage on this PC, and the plan's usage
                      limit is not visible anywhere on the PC.

The page is served by the MCP server itself (a thread, started when Claude starts the server) and by
dashboard.bat (on its own, for when Claude is closed).  Whichever binds the port first serves it.
Only GET requests for the page and its JSON are answered; nothing on the page can change anything.
By default only this PC can open it (http://localhost:8765).  "dashboard_lan": true in settings.json
lets a phone or laptop on the same Wi-Fi open http://<PC name>:8765 (Windows asks once to allow it).
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psutil
except ImportError:                                  # pragma: no cover - psutil is in requirements.txt
    psutil = None

from . import config

DIR_NAME = "_dashboard"
DEFAULT_PORT = 8765
RECENT_RUNS = 20
MAX_FINDINGS = 100
TOKEN_WINDOW_S = 36 * 3600                           # only session files touched in the last 36 h are read
CHECK_STATUSES = ("running", "passed", "failed", "attention", "waiting", "done")
FINDING_LEVELS = ("info", "pass", "warn", "fail")
# SOFiSTiK GUI programs: shown in the list, never "the module running now"
GUI_PROGRAMS = {"ssd", "teddy", "wingraf", "animator", "sofiplus", "resultviewer", "sofistik"}
SOFISTIK_NAMES = {"sps", "aqua", "aqb", "sofimsha", "sofimshb", "sofimshc", "sofiload", "ase", "bdk", "maxima",
                  "dyna", "csm", "template", "talpa", "hydra", "sir", "sofilod", "tendon", "geos", "ell", "bemess",
                  "result", "wingraf", "teddy", "ssd", "animator", "dolfyn", "simulate", "colu", "foot",
                  "plbconverter"}

CHECK_FORMAT = """\
{
  "check": "26016 member checks",          name shown on the dashboard (also the file name)
  "status": "running",                     running | passed | failed | attention | waiting | done
  "step": "ASE: ULS combinations 101-154", what is happening now (one line)
  "progress": "3 of 7",                    optional, free text
  "updated": "2026-10-17T23:20:00",        local time, ISO format
  "findings": [                            newest last; level info | pass | warn | fail
    {"time": "2026-10-17T23:18:00", "level": "fail", "text": "B81 UB 457x191x89: LTB ratio 1.12 (LC 118)"}
  ]
}"""

_lock = threading.Lock()


# ------------------------------------------------------------------------------------------------
# where the files are
# ------------------------------------------------------------------------------------------------

def state_dir(settings: dict) -> str:
    """<first work folder>\\_dashboard: inside a work folder, so a checking session may write there."""
    folders = settings.get("work_folders") or []
    base = folders[0] if folders else config.ROOT
    return os.path.join(base, DIR_NAME)


def _now() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _write_json(path: str, data) -> None:
    """Write via a temporary file and rename, so a reader never sees half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------
# written by the MCP server: the running calculation and the last runs
# ------------------------------------------------------------------------------------------------

class ServerState:
    """The calculation this server is running and its last runs, kept in server-<pid>.json.
    Every write is best effort: the dashboard must never make a calculation fail."""

    def __init__(self, settings_fn, version: str):
        self._settings_fn = settings_fn
        self.data: dict = {"pid": os.getpid(), "host": socket.gethostname(), "version": version,
                           "started": _now(), "updated": _now(), "job": None, "recent_runs": []}

    def path(self) -> str | None:
        try:
            return os.path.join(state_dir(self._settings_fn()), f"server-{os.getpid()}.json")
        except Exception:                            # unreadable settings.json: no dashboard file
            return None

    def _save(self) -> None:
        p = self.path()
        if not p:
            return
        self.data["updated"] = _now()
        try:
            with _lock:
                _write_json(p, self.data)
        except OSError:
            pass

    def started(self) -> None:
        self._save()

    def job_started(self, dat: str) -> None:
        self.data["job"] = {"dat": dat, "started": _now(), "t0": time.time(), "sps_pid": None}
        self._save()

    def job_process(self, pid: int) -> None:
        if self.data.get("job"):
            self.data["job"]["sps_pid"] = pid
            self._save()

    def job_finished(self, result: dict) -> None:
        job = self.data.get("job") or {}
        r = result if isinstance(result, dict) else {}
        run = {"dat": job.get("dat") or r.get("dat"), "finished": _now(),
               "status": r.get("status") or ("server error" if r.get("error") or not r else "?"),
               "errors": _count(r.get("errors")), "warnings": _count(r.get("warnings")),
               "seconds": r.get("seconds") if r.get("seconds") is not None
               else (round(time.time() - job["t0"], 1) if job.get("t0") else None),
               "first_error": _first_error(r), "reason": r.get("reason") or r.get("error")}
        self.data["recent_runs"] = ([run] + list(self.data.get("recent_runs") or []))[:RECENT_RUNS]
        self.data["job"] = None
        self._save()

    def remove(self) -> None:
        p = self.path()
        if p:
            try:
                os.remove(p)
            except OSError:
                pass


def _count(v) -> int:
    """The protocol gives counts as numbers; accept a list of messages too."""
    if isinstance(v, list):
        return len(v)
    return _int(v)


def _first_error(r: dict) -> str | None:
    """'E 123 ASE: text' of the first error message of a run, for the recent-runs table."""
    for m in r.get("messages") or []:
        if isinstance(m, dict) and m.get("kind") == "error":
            head = " ".join(str(x) for x in ("E", m.get("number"), m.get("program")) if x not in (None, ""))
            return f"{head}: {m.get('text') or ''}".strip(": ")[:300]
    return None


# ------------------------------------------------------------------------------------------------
# checks: written by a checking session (report_check tool, or the file directly)
# ------------------------------------------------------------------------------------------------

def check_file_name(check: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(check).strip()).strip("-.")[:80]
    return (slug or "check") + ".json"


def report_check(settings: dict, check: str, status: str | None = None, step: str | None = None,
                 progress: str | None = None, findings: list | None = None, clear_findings: bool = False) -> dict:
    """Create or update one check's file.  New findings are added after the earlier ones (newest last,
    at most MAX_FINDINGS kept).  Returns the saved check, or {"error": ...}."""
    if not str(check or "").strip():
        return {"error": "check: give the check a name, e.g. '26016 member checks'."}
    if status is not None and status not in CHECK_STATUSES:
        return {"error": f"status must be one of {', '.join(CHECK_STATUSES)}."}
    new = []
    for f in findings or []:
        if isinstance(f, str):
            f = {"text": f}
        if not isinstance(f, dict) or not str(f.get("text") or "").strip():
            return {"error": "each finding needs a text, e.g. {'level': 'fail', 'text': 'B81: ratio 1.12'}."}
        level = str(f.get("level") or "info").lower()
        if level not in FINDING_LEVELS:
            return {"error": f"finding level must be one of {', '.join(FINDING_LEVELS)}."}
        new.append({"time": _now(), "level": level, "text": str(f["text"]).strip()[:500]})
    path = os.path.join(state_dir(settings), "checks", check_file_name(check))
    with _lock:
        old = _read_json(path)
        cur = old if isinstance(old, dict) else {}
        cur["check"] = str(check).strip()
        if status is not None:
            cur["status"] = status
        cur.setdefault("status", "running")
        if step is not None:
            cur["step"] = str(step)[:300]
        if progress is not None:
            cur["progress"] = str(progress)[:100]
        kept = [] if clear_findings else [x for x in cur.get("findings") or [] if isinstance(x, dict)]
        cur["findings"] = (kept + new)[-MAX_FINDINGS:]
        cur["updated"] = _now()
        _write_json(path, cur)
    return {"saved": path, "check": cur}


# ------------------------------------------------------------------------------------------------
# collected by the dashboard on every page refresh
# ------------------------------------------------------------------------------------------------

class Collector:
    """Gathers everything the page shows.  Keeps psutil process objects between calls (CPU % needs
    two samples) and reads the Claude Code session files incrementally."""

    def __init__(self, settings_fn, sofistik_root_fn=lambda: None, claude_dir: str | None = None):
        self._settings_fn = settings_fn
        self._root_fn = sofistik_root_fn
        self.claude_dir = claude_dir or os.path.join(os.path.expanduser("~"), ".claude", "projects")
        self._procs: dict = {}
        self._token_files: dict = {}                 # path -> {"size", "offset", "msgs": {id: (ts, usage)}, ...}
        if psutil is not None:
            psutil.cpu_percent(None)

    # --- PC and processes -------------------------------------------------------------------------
    def resources(self) -> dict:
        if psutil is None:                           # pragma: no cover
            return {"error": "psutil is not installed: run install.bat again."}
        vm = psutil.virtual_memory()
        return {"cpu_percent": psutil.cpu_percent(None), "cpu_count": psutil.cpu_count(),
                "ram_used_gb": round((vm.total - vm.available) / 2**30, 1), "ram_total_gb": round(vm.total / 2**30, 1),
                "ram_percent": vm.percent}

    def _is_sofistik(self, name: str, exe: str, root: str | None) -> bool:
        if root and exe and config.is_inside(exe, [root]):
            return True
        return os.path.splitext(name.lower())[0] in SOFISTIK_NAMES

    def processes(self) -> dict:
        """SOFiSTiK processes and Claude processes with CPU and RAM."""
        if psutil is None:                           # pragma: no cover
            return {"sofistik": [], "claude": [], "module": None}
        root = self._root_fn()
        sof: list[dict] = []
        claude: list[dict] = []
        seen: set = set()
        for p in psutil.process_iter(["pid", "name", "exe", "create_time", "ppid"]):
            try:
                info = p.info
                name = info.get("name") or ""
                low = name.lower()
                is_claude = low.startswith("claude")
                if not is_claude and not self._is_sofistik(name, info.get("exe") or "", root):
                    continue
                pid = info["pid"]
                seen.add(pid)
                keep = self._procs.get(pid)
                if keep is None or keep.create_time() != info.get("create_time"):
                    keep = self._procs[pid] = p
                    keep.cpu_percent(None)           # first sample: 0, the next call gives the real value
                    cpu = 0.0
                else:
                    cpu = keep.cpu_percent(None)
                row = {"pid": pid, "name": os.path.splitext(name)[0].upper() if not is_claude else name,
                       "cpu_percent": round(cpu / max(1, psutil.cpu_count() or 1), 1),
                       "ram_mb": round(keep.memory_info().rss / 2**20),
                       "started": datetime.datetime.fromtimestamp(info.get("create_time") or 0).strftime("%H:%M:%S"),
                       "create_time": info.get("create_time") or 0, "ppid": info.get("ppid")}
                (claude if is_claude else sof).append(row)
            except Exception:                        # process ended or access denied while reading it
                continue
        for pid in list(self._procs):
            if pid not in seen:
                self._procs.pop(pid, None)
        return {"sofistik": sorted(sof, key=lambda r: r["create_time"]),
                "claude": sorted(claude, key=lambda r: -r["ram_mb"]), "module": running_module(sof)}

    # --- MCP servers and checks ------------------------------------------------------------------
    def servers(self, folder: str) -> list[dict]:
        out = []
        for path in sorted(glob.glob(os.path.join(folder, "server-*.json"))):
            data = _read_json(path)
            if not isinstance(data, dict):
                continue
            pid = data.get("pid")
            alive = _pid_alive(pid)
            if not alive and not data.get("recent_runs"):
                continue
            data["alive"] = alive
            job = data.get("job")
            if isinstance(job, dict) and job.get("t0"):
                job["elapsed_s"] = round(time.time() - float(job["t0"]))
                if not alive:
                    job["note"] = "the server that ran it has closed"
            out.append(data)
        return out

    def checks(self, folder: str) -> list[dict]:
        out = []
        for path in glob.glob(os.path.join(folder, "checks", "*.json")):
            data = _read_json(path)
            if isinstance(data, dict):
                data.setdefault("check", os.path.splitext(os.path.basename(path))[0])
                data["findings"] = [f for f in data.get("findings") or [] if isinstance(f, dict)]
                out.append(data)
        return sorted(out, key=lambda c: str(c.get("updated") or ""), reverse=True)

    # --- Claude Code token usage -----------------------------------------------------------------
    def tokens(self) -> dict:
        today = datetime.date.today()
        cutoff = time.time() - TOKEN_WINDOW_S
        sessions: list[dict] = []
        tot = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
        files = glob.glob(os.path.join(self.claude_dir, "**", "*.jsonl"), recursive=True)
        for path in files:
            try:
                st = os.stat(path)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                continue
            rec = self._read_tokens(path, st.st_size)
            day = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
            for ts, u in rec["msgs"].values():
                if ts and ts.date() == today:
                    for k in day:
                        day[k] += u[k]
            if not any(day.values()):
                continue
            for k in tot:
                tot[k] += day[k]
            sessions.append({"project": rec.get("cwd") or _project_name(path), "session": rec.get("session"),
                             "subagent": "subagents" in path.replace("\\", "/").split("/"),
                             "last": rec["last"].strftime("%H:%M") if rec.get("last") else None,
                             "last_ts": rec["last"].timestamp() if rec.get("last") else 0, **day})
        sessions.sort(key=lambda s: -s["last_ts"])
        return {"today": tot, "total_today": sum(tot.values()), "sessions": sessions[:12],
                "note": "Claude Code sessions on this PC only (today, local time). Claude Desktop chats and "
                        "claude.ai / cloud sessions are not recorded on this PC; the plan's usage limit is not "
                        "visible here."}

    def _read_tokens(self, path: str, size: int) -> dict:
        rec = self._token_files.get(path)
        if rec is None or size < rec["offset"]:      # new file, or it was rewritten
            rec = self._token_files[path] = {"offset": 0, "msgs": {}, "cwd": None, "session": None, "last": None}
        if size == rec["offset"]:
            return rec
        try:
            with open(path, "rb") as f:
                f.seek(rec["offset"])
                chunk = f.read()
        except OSError:
            return rec
        end = chunk.rfind(b"\n") + 1                 # an unfinished last line is read next time
        for line in chunk[:end].splitlines():
            if b'"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") if isinstance(d, dict) else None
            if not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                continue
            usage = msg["usage"]
            ts = _parse_ts(d.get("timestamp"))
            key = msg.get("id") or d.get("requestId") or d.get("uuid") or f"{rec['offset']}-{len(rec['msgs'])}"
            rec["msgs"][key] = (ts, {"input": _int(usage.get("input_tokens")),
                                     "output": _int(usage.get("output_tokens")),
                                     "cache_write": _int(usage.get("cache_creation_input_tokens")),
                                     "cache_read": _int(usage.get("cache_read_input_tokens"))})
            rec["cwd"] = d.get("cwd") or rec["cwd"]
            rec["session"] = (d.get("sessionId") or rec["session"] or "")[:8] or None
            if ts and (rec["last"] is None or ts > rec["last"]):
                rec["last"] = ts
        rec["offset"] += end
        return rec

    # --- everything ------------------------------------------------------------------------------
    def collect(self) -> dict:
        notes = []
        try:
            settings = self._settings_fn()
            folder = state_dir(settings)
        except Exception as e:
            settings, folder = {}, ""
            notes.append(f"settings.json could not be read: {e}")
        procs = self.processes()
        return {"time": _now(), "host": socket.gethostname(), "resources": self.resources(),
                "processes": procs, "servers": self.servers(folder) if folder else [],
                "checks": self.checks(folder) if folder else [], "tokens": self.tokens(),
                "status_folder": folder, "notes": notes}


def running_module(sofistik_rows: list[dict]) -> str | None:
    """The SOFiSTiK program doing the work now: the newest process started by sps.exe, else the newest
    non-GUI SOFiSTiK process other than sps.exe."""
    sps = {r["pid"] for r in sofistik_rows if r["name"] == "SPS"}
    work = [r for r in sofistik_rows if r["name"] != "SPS" and r["name"].lower() not in GUI_PROGRAMS]
    children = [r for r in work if r.get("ppid") in sps]
    pick = children or work
    if not pick:
        return "SPS" if sps else None
    return max(pick, key=lambda r: r["create_time"])["name"]


def _pid_alive(pid) -> bool:
    if not isinstance(pid, int) or psutil is None:
        return False
    try:
        return psutil.pid_exists(pid)
    except Exception:                                # pragma: no cover
        return False


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _parse_ts(v):
    """ISO time (Claude Code writes UTC with Z) as local naive datetime, or None."""
    if not isinstance(v, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _project_name(path: str) -> str:
    return os.path.basename(os.path.dirname(path))


# ------------------------------------------------------------------------------------------------
# the web page
# ------------------------------------------------------------------------------------------------

PAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


def make_handler(collector: Collector):
    class Handler(BaseHTTPRequestHandler):
        server_version = "sofistik-dashboard"

        def log_message(self, format, *args):        # never print: stdout is the MCP channel
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route in ("/", "/index.html"):
                try:
                    with open(PAGE_PATH, "rb") as f:
                        body = f.read()
                except OSError:
                    return self._send(500, b"dashboard.html is missing", "text/plain; charset=utf-8")
                return self._send(200, body, "text/html; charset=utf-8")
            if route == "/api/state":
                try:
                    data = collector.collect()
                except Exception as e:               # pragma: no cover - shown on the page, never fatal
                    data = {"time": _now(), "notes": [f"{type(e).__name__}: {e}"]}
                return self._send(200, json.dumps(data, default=str).encode("utf-8"),
                                  "application/json; charset=utf-8")
            return self._send(404, b"not found", "text/plain; charset=utf-8")

    return Handler


class _Server(ThreadingHTTPServer):
    """Binds the port exclusively.  HTTPServer sets SO_REUSEADDR, which on Windows lets a second process
    bind the same port too (both 'serve', requests go to either), so the second copy would not notice."""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):    # Windows
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def dashboard_options(settings: dict) -> tuple[str, int]:
    try:
        port = int(settings.get("dashboard_port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    lan = settings.get("dashboard_lan") is True
    return ("0.0.0.0" if lan else "127.0.0.1"), port


def start(collector: Collector, host: str, port: int):
    """Serve the page in a background thread.  Returns the server, or None if the port is taken
    (another Claude window or dashboard.bat already serves it) or the port is 0 (switched off)."""
    if not port:
        return None
    try:
        httpd = _Server((host, port), make_handler(collector))
    except OSError:
        return None
    threading.Thread(target=httpd.serve_forever, name="dashboard", daemon=True).start()
    return httpd


def main(argv=None) -> int:
    """dashboard.bat: serve the page on its own and open it in the browser."""
    import webbrowser

    from . import install

    def root():
        try:
            return install.find(config.load_settings()).get("root")
        except Exception:
            return None

    settings = config.load_settings()
    host, port = dashboard_options(settings)
    httpd = start(Collector(config.load_settings, root), host, port or DEFAULT_PORT)
    url = f"http://localhost:{port or DEFAULT_PORT}"
    if httpd is None:
        print(f"The dashboard is already running (Claude serves it): {url}")
    else:
        print(f"SOFiSTiK dashboard: {url}")
        if host == "0.0.0.0":
            print(f"From a phone on the same Wi-Fi: http://{socket.gethostname()}:{port}")
        print("Leave this window open; close it to stop the dashboard.")
    if "--no-browser" not in (argv or sys.argv[1:]):
        webbrowser.open(url)
    if httpd is None:
        return 0
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":                           # pragma: no cover
    sys.exit(main())
