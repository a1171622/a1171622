"""The live dashboard: status files written by the server and by report_check, what the page collects
(processes, checks, runs, Claude Code token use) and the small web server that serves it."""
from __future__ import annotations

import datetime
import json
import os
import socket
import time
import urllib.error
import urllib.request

import pytest
from conftest import run

from sofistik_mcp import dashboard


@pytest.fixture
def s(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return {"work_folders": [str(work)]}


def folder(s):
    return dashboard.state_dir(s)


def w_dat(folder, name, text):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ------------------------------------------------------------------------------- server state file

def test_server_state_lifecycle(s):
    st = dashboard.ServerState(lambda: s, "9.9")
    st.started()
    path = os.path.join(folder(s), f"server-{os.getpid()}.json")
    data = json.load(open(path, encoding="utf-8"))
    assert data["pid"] == os.getpid() and data["version"] == "9.9" and data["job"] is None
    st.job_started(r"C:\work\a.dat")
    st.job_process(1234)
    data = json.load(open(path, encoding="utf-8"))
    assert data["job"]["dat"] == r"C:\work\a.dat" and data["job"]["sps_pid"] == 1234
    st.job_finished({"status": "errors", "errors": 2, "warnings": 1, "seconds": 3.5,
                     "messages": [{"kind": "warning", "number": 9, "program": "ASE", "text": "w"},
                                  {"kind": "error", "number": 123, "program": "ASE", "text": "no stiffness"}]})
    data = json.load(open(path, encoding="utf-8"))
    assert data["job"] is None
    run0 = data["recent_runs"][0]
    assert (run0["status"], run0["errors"], run0["warnings"], run0["seconds"]) == ("errors", 2, 1, 3.5)
    assert run0["first_error"] == "E 123 ASE: no stiffness"
    st.remove()
    assert not os.path.exists(path)
    st.remove()                                      # a second remove is harmless


def test_server_state_keeps_the_last_runs_and_handles_a_crashed_job(s):
    st = dashboard.ServerState(lambda: s, "1")
    for i in range(dashboard.RECENT_RUNS + 5):
        st.job_started(f"f{i}.dat")
        st.job_finished({"status": "ok", "errors": [], "warnings": [{"x": 1}]})
    assert len(st.data["recent_runs"]) == dashboard.RECENT_RUNS
    assert st.data["recent_runs"][0]["dat"] == f"f{dashboard.RECENT_RUNS + 4}.dat"
    assert st.data["recent_runs"][0]["warnings"] == 1 and st.data["recent_runs"][0]["seconds"] is not None
    st.job_started("crash.dat")
    st.job_finished({})                              # solver.run raised: the server reports {}
    assert st.data["recent_runs"][0]["status"] == "server error"
    st.job_finished({"error": "boom"})
    assert st.data["recent_runs"][0]["reason"] == "boom"
    st.job_process(5)                                # no job: nothing to do, no error


def test_server_state_never_fails_the_calculation(tmp_path):
    def bad():
        raise ValueError("settings.json broken")
    st = dashboard.ServerState(bad, "1")
    assert st.path() is None
    st.started()
    st.job_started("a.dat")
    st.job_finished({"status": "ok"})
    st.remove()
    blocked = tmp_path / "file"
    blocked.write_text("x")                          # the status folder's parent is a file: writing fails
    st2 = dashboard.ServerState(lambda: {"work_folders": [str(blocked)]}, "1")
    st2.started()


def test_state_dir_without_work_folders():
    assert dashboard.state_dir({}).endswith(dashboard.DIR_NAME)


# ------------------------------------------------------------------------------- report_check

def test_report_check_creates_and_appends(s):
    r = dashboard.report_check(s, "26016 member checks", "running", "AQUA", "1 of 3",
                               [{"level": "pass", "text": "sections read"}])
    assert r["check"]["status"] == "running"
    assert os.path.basename(r["saved"]) == dashboard.check_file_name("26016 member checks")
    assert os.path.basename(r["saved"]).startswith("26016-member-checks-")
    assert not os.path.exists(r["saved"] + ".lock")
    r = dashboard.report_check(s, "26016 member checks", step="ASE",
                               findings=["plain text finding", {"level": "FAIL", "text": "B81 ratio 1.12"}])
    c = r["check"]
    assert c["status"] == "running" and c["step"] == "ASE" and c["progress"] == "1 of 3"
    assert [f["level"] for f in c["findings"]] == ["pass", "info", "fail"]
    r = dashboard.report_check(s, "26016 member checks", "failed", clear_findings=True)
    assert r["check"]["findings"] == [] and r["check"]["status"] == "failed"
    on_disk = json.load(open(r["saved"], encoding="utf-8"))
    assert on_disk["status"] == "failed"


def test_report_check_defaults_and_limits(s):
    r = dashboard.report_check(s, "x", findings=[{"text": f"f{i}"} for i in range(dashboard.MAX_FINDINGS + 7)])
    assert r["check"]["status"] == "running"
    assert len(r["check"]["findings"]) == dashboard.MAX_FINDINGS
    assert r["check"]["findings"][-1]["text"] == f"f{dashboard.MAX_FINDINGS + 6}"
    n = dashboard.check_file_name("../..\\evil:name")
    assert n.startswith("evil-name-") and n.endswith(".json") and "/" not in n and "\\" not in n
    assert dashboard.check_file_name("...").startswith("check-")
    # names that differ only in punctuation or non-ASCII letters get their own files
    assert dashboard.check_file_name("26016 member/checks") != dashboard.check_file_name("26016 member checks")
    assert dashboard.check_file_name("Prüfung") != dashboard.check_file_name("Prüfüng")


@pytest.mark.parametrize("kw, msg", [
    ({"check": " "}, "give the check a name"),
    ({"check": "a", "status": "great"}, "status must be one of"),
    ({"check": "a", "findings": [{"level": "info"}]}, "needs a text"),
    ({"check": "a", "findings": [5]}, "needs a text"),
    ({"check": "a", "findings": [{"level": "bad", "text": "t"}]}, "level must be one of"),
])
def test_report_check_refuses_bad_input(s, kw, msg):
    assert msg in dashboard.report_check(s, **kw)["error"]


def test_report_check_replaces_an_unreadable_file(s):
    p = os.path.join(folder(s), "checks", dashboard.check_file_name("a"))
    os.makedirs(os.path.dirname(p))
    open(p, "w").write("[1, 2")
    assert dashboard.report_check(s, "a", "done")["check"]["status"] == "done"


# ------------------------------------------------------------------------------- collector

def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def test_servers_and_checks(s, tmp_path):
    f = folder(s)
    write(os.path.join(f, f"server-{os.getpid()}.json"),
          {"pid": os.getpid(), "job": {"dat": "a.dat", "t0": time.time() - 65}, "recent_runs": []})
    write(os.path.join(f, "server-999999.json"), {"pid": 999999, "job": {"dat": "b.dat", "t0": time.time()},
                                                 "recent_runs": [{"dat": "b.dat", "status": "ok"}]})
    write(os.path.join(f, "server-999998.json"), {"pid": 999998, "job": None, "recent_runs": []})
    write(os.path.join(f, "server-bad.json"), "not json")
    write(os.path.join(f, "checks", "old.json"), {"check": "old", "updated": "2026-01-01T00:00:00",
                                                  "findings": [{"text": "a"}, "junk"]})
    write(os.path.join(f, "checks", "new.json"), {"updated": "2026-10-17T00:00:00"})
    write(os.path.join(f, "checks", "broken.json"), "{")
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    servers = {x["pid"]: x for x in col.servers(f)}
    assert set(servers) == {os.getpid(), 999999}
    assert servers[os.getpid()]["alive"] and servers[os.getpid()]["job"]["elapsed_s"] >= 64
    dead = servers[999999]
    assert not dead["alive"] and dead["job"] is None
    assert dead["recent_runs"][0]["status"] == "not finished" and "closed" in dead["recent_runs"][0]["reason"]
    checks = col.checks(f)
    assert [c["check"] for c in checks] == ["new", "old"]
    assert checks[1]["findings"] == [{"text": "a"}]


def usage_line(msg_id, ts, out, inp=1, cw=10, cr=100, cwd="C:\\Sofistik workflow", session="abcdef123456"):
    return json.dumps({"type": "assistant", "timestamp": ts, "cwd": cwd, "sessionId": session,
                       "message": {"id": msg_id, "usage": {"input_tokens": inp, "output_tokens": out,
                                                           "cache_creation_input_tokens": cw,
                                                           "cache_read_input_tokens": cr}}})


def iso_today(hour=1):
    t = datetime.datetime.combine(datetime.date.today(), datetime.time(hour, 0)).astimezone()
    return t.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def test_token_usage_today_counts_each_message_once(s, tmp_path):
    proj = tmp_path / "projects" / "C--Sofistik-workflow"
    proj.mkdir(parents=True)
    f = proj / "s1.jsonl"
    yesterday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
    lines = [usage_line("m1", iso_today(), 100), usage_line("m1", iso_today(), 100),   # same message twice
             usage_line("m2", iso_today(2), 50), usage_line("m0", yesterday, 999),
             json.dumps({"type": "user", "message": {"content": "hi"}}), "{not json with \"usage\"",
             json.dumps({"message": {"usage": "odd"}, "x": "\"usage\""}),
             json.dumps({"timestamp": 5, "message": {"usage": {"output_tokens": "x"}}})]
    f.write_text("\n".join(lines) + "\n" + usage_line("m3", iso_today(3), 7)[:40])   # unfinished last line
    sub = proj / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-1.jsonl").write_text(usage_line("a1", iso_today(), 5, session="sub999") + "\n")
    old = proj / "old.jsonl"
    old.write_text(usage_line("z", iso_today(), 1000) + "\n")
    os.utime(old, (time.time() - 3 * 86400,) * 2)
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "projects"))
    t = col.tokens()
    assert t["today"] == {"input": 3, "output": 155, "cache_write": 30, "cache_read": 300}
    assert t["total_today"] == 488
    rows = {r["session"]: r for r in t["sessions"]}
    assert rows["abcdef12"]["output"] == 150 and not rows["abcdef12"]["subagent"]
    assert rows["sub999"]["subagent"] and rows["sub999"]["project"] == "C:\\Sofistik workflow"
    assert "this PC only" in t["note"]
    # the rest of the unfinished line arrives: read incrementally, the earlier lines are not counted again
    with open(f, "a") as fh:
        fh.write(usage_line("m3", iso_today(3), 7)[40:] + "\n")
    assert col.tokens()["today"]["output"] == 162
    assert col.tokens()["today"]["output"] == 162                      # nothing new: same answer
    f.write_text(usage_line("n1", iso_today(), 1) + "\n")              # file rewritten (smaller)
    assert col.tokens()["today"]["output"] == 6


def test_token_usage_unreadable_files(s, tmp_path, monkeypatch):
    proj = tmp_path / "p" / "x"
    proj.mkdir(parents=True)
    (proj / "a.jsonl").write_text(usage_line("m", iso_today(), 3) + "\n")
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "p"))
    real_open = open

    def no_open(p, *a, **k):
        if str(p).endswith(".jsonl"):
            raise OSError("locked")
        return real_open(p, *a, **k)
    monkeypatch.setattr("builtins.open", no_open)
    assert col.tokens()["total_today"] == 0
    monkeypatch.setattr(dashboard.os, "stat", lambda p: (_ for _ in ()).throw(OSError("gone")))
    assert col.tokens()["sessions"] == []


def test_parse_ts():
    assert dashboard._parse_ts(None) is None and dashboard._parse_ts("nope") is None
    assert dashboard._parse_ts("2026-10-17T05:00:00") == datetime.datetime(2026, 10, 17, 5, 0)
    assert dashboard._parse_ts("2026-10-17T05:00:00Z").tzinfo is None


def test_running_module():
    rows = [{"pid": 1, "name": "SPS", "create_time": 1, "ppid": 0},
            {"pid": 2, "name": "AQUA", "create_time": 2, "ppid": 1},
            {"pid": 3, "name": "ASE", "create_time": 3, "ppid": 1},
            {"pid": 4, "name": "TEDDY", "create_time": 9, "ppid": 0},
            {"pid": 5, "name": "WINGRAF", "create_time": 10, "ppid": 1}]
    assert dashboard.running_module(rows) == "ASE"
    assert dashboard.running_module(rows[:1]) == "SPS"
    assert dashboard.running_module([rows[3]]) is None
    assert dashboard.running_module([{"pid": 7, "name": "BDK", "create_time": 1, "ppid": 99}]) is None   # no sps
    assert dashboard.running_module([]) is None
    # SOFiSTiK 2027 runs the programs under its job wrapper WPSJOB
    wrapped = [{"pid": 1, "name": "SPS", "create_time": 1, "ppid": 0},
               {"pid": 2, "name": "WPSJOB", "create_time": 2, "ppid": 1},
               {"pid": 3, "name": "BDK", "create_time": 3, "ppid": 2}]
    assert dashboard.running_module(wrapped) == "BDK"
    assert dashboard.running_module(wrapped[:2]) == "SPS"
    loop = [{"pid": 5, "name": "ASE", "create_time": 1, "ppid": 6},
            {"pid": 6, "name": "AQUA", "create_time": 1, "ppid": 5}]
    assert dashboard.running_module(loop) is None


class FakeProc:
    def __init__(self, pid, name, exe, ppid=0, ctime=100.0, cpu=50.0, rss=2**30, fail=False):
        self.info = {"pid": pid, "name": name, "exe": exe, "create_time": ctime, "ppid": ppid}
        self._cpu, self._rss, self._fail = cpu, rss, fail

    def create_time(self):
        return self.info["create_time"]

    def cpu_percent(self, interval=None):
        return self._cpu

    def memory_info(self):
        if self._fail:
            raise RuntimeError("access denied")
        return type("M", (), {"rss": self._rss})()


def test_processes_finds_sofistik_and_claude(s, tmp_path, monkeypatch):
    root = str(tmp_path / "SOFiSTiK 2027")
    procs = [FakeProc(10, "sps.exe", os.path.join(root, "sps.exe")),
             FakeProc(11, "ase.exe", os.path.join(root, "ase.exe"), ppid=10, ctime=101.0),
             FakeProc(12, "aqua.exe", "", ppid=10, ctime=99.0),        # exe hidden: known by its name
             FakeProc(13, "claude.exe", r"C:\x\claude.exe", rss=300 * 2**20),
             FakeProc(14, "notepad.exe", r"C:\Windows\notepad.exe"),
             FakeProc(15, "maxima.exe", os.path.join(root, "maxima.exe"), fail=True)]
    monkeypatch.setattr(dashboard.psutil, "process_iter", lambda attrs=None: list(procs))
    monkeypatch.setattr(dashboard.psutil, "cpu_count", lambda: 4)
    col = dashboard.Collector(lambda: s, lambda: root, claude_dir=str(tmp_path / "none"))
    first = col.processes()
    assert [r["name"] for r in first["sofistik"]] == ["AQUA", "SPS", "ASE"]
    assert first["module"] == "ASE" and first["sofistik"][0]["cpu_percent"] == 0.0     # first sample
    assert first["claude"][0]["name"] == "claude.exe" and first["claude"][0]["ram_mb"] == 300
    second = col.processes()
    assert second["sofistik"][2]["cpu_percent"] == 12.5                                # 50 % of one core / 4
    procs.pop(1)                                                                       # ASE ended
    third = col.processes()
    assert third["module"] == "AQUA" and 11 not in col._procs


def test_collect_and_resources(s, tmp_path):
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    d = col.collect()
    assert set(d) >= {"time", "host", "resources", "processes", "servers", "checks", "tokens", "status_folder"}
    assert 0 <= d["resources"]["cpu_percent"] <= 100 and d["resources"]["ram_total_gb"] > 0

    def bad():
        raise ValueError("broken settings")
    d = dashboard.Collector(bad, claude_dir=str(tmp_path / "none")).collect()
    assert d["servers"] == [] and "broken settings" in d["notes"][0]


# ------------------------------------------------------------------------------- web server

def free_port():
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def test_web_server_serves_page_and_state(s, tmp_path, monkeypatch):
    port = free_port()
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    httpd = dashboard.start(col, "127.0.0.1", port)
    try:
        code, ctype, body = get(f"http://127.0.0.1:{port}/")
        assert code == 200 and ctype.startswith("text/html") and b"SOFiSTiK workflow" in body
        code, ctype, body = get(f"http://127.0.0.1:{port}/api/state?x=1")
        assert code == 200 and ctype.startswith("application/json") and "resources" in json.loads(body)
        assert get(f"http://127.0.0.1:{port}/etc/passwd")[0] == 404
        assert dashboard.start(col, "127.0.0.1", port) is None          # port taken: second copy steps aside
        monkeypatch.setattr(dashboard, "PAGE_PATH", str(tmp_path / "missing.html"))
        assert get(f"http://127.0.0.1:{port}/")[0] == 500
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert dashboard.start(col, "127.0.0.1", 0) is None                  # port 0 = switched off


def test_page_has_no_external_resources():
    html = open(dashboard.PAGE_PATH, encoding="utf-8").read()
    assert "http://" not in html.replace("http://localhost", "") and "https://" not in html
    assert "/api/state" in html


@pytest.mark.parametrize("settings, expected", [
    ({}, ("127.0.0.1", 8765)), ({"dashboard_lan": True, "dashboard_port": 9000}, ("0.0.0.0", 9000)),
    ({"dashboard_lan": "true", "dashboard_port": "x"}, ("127.0.0.1", 8765)), ({"dashboard_port": 0}, ("127.0.0.1", 0)),
])
def test_dashboard_options(settings, expected):
    assert dashboard.dashboard_options(settings) == expected


def test_main_when_already_running(monkeypatch, capsys, s):
    monkeypatch.setattr(dashboard.config, "load_settings", lambda: {**s, "dashboard_lan": True})
    monkeypatch.setattr(dashboard, "start", lambda *a: None)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    assert dashboard.main([]) == 0
    assert "already running" in capsys.readouterr().out and opened == ["http://localhost:8765"]


def test_main_serves_until_stopped(monkeypatch, capsys, s):
    monkeypatch.setattr(dashboard.config, "load_settings", lambda: {**s, "dashboard_lan": True, "dashboard_port": 9})

    class FakeHttpd:
        stopped = False

        def shutdown(self):
            FakeHttpd.stopped = True
    monkeypatch.setattr(dashboard, "start", lambda col, host, port: FakeHttpd())
    monkeypatch.setattr(dashboard.time, "sleep", lambda t: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert dashboard.main(["--no-browser"]) == 0
    out = capsys.readouterr().out
    assert "http://localhost:9" in out and "same Wi-Fi" in out and FakeHttpd.stopped


# ------------------------------------------------------------------------------- through the server

def test_server_tools(server_mod, settings):
    r = run(server_mod.report_check("bench", "running", "AQUA", None, [{"level": "pass", "text": "ok"}]))
    assert r["check"]["findings"][0]["text"] == "ok"
    assert "error" in run(server_mod.report_check("bench", "nope"))
    d = run(server_mod.dashboard_status())
    assert d["checks"][0]["check"] == "bench" and d["page"] == "http://localhost:8765"


def test_server_tools_lan_page_and_bad_settings(server_mod, settings, monkeypatch):
    monkeypatch.setattr(server_mod, "_settings", lambda: {**settings, "dashboard_lan": True})
    assert "same Wi-Fi" in run(server_mod.dashboard_status())["page"]

    def bad():
        raise server_mod.config.SettingsError("typing error")
    monkeypatch.setattr(server_mod, "_settings", bad)
    assert run(server_mod.report_check("a"))["error"] == "typing error"


def test_run_calculation_updates_the_dashboard(server_mod, settings):
    d = w_dat(settings["work_folders"][0], "dash.dat", "+PROG AQB\nEND\n$ FAKE mode=errors\n")
    assert run(server_mod.run_calculation(d))["status"] == "errors"
    st = server_mod._state.data
    assert st["job"] is None and st["recent_runs"][0]["dat"] == d and st["recent_runs"][0]["status"] == "errors"
    path = os.path.join(dashboard.state_dir(settings), f"server-{os.getpid()}.json")
    assert json.load(open(path, encoding="utf-8"))["recent_runs"][0]["status"] == "errors"


def test_sofistik_root_is_cached(server_mod, monkeypatch):
    server_mod._root_cache.clear()
    assert server_mod._sofistik_root() == server_mod._test_info["root"]
    monkeypatch.setattr(server_mod, "_install", lambda s=None: (_ for _ in ()).throw(RuntimeError("x")))
    assert server_mod._sofistik_root() == server_mod._test_info["root"]        # cached for a minute
    server_mod._root_cache["t"] = 0
    assert server_mod._sofistik_root() is None


def test_start_dashboard_logs(server_mod, monkeypatch, caplog):
    caplog.set_level("INFO", logger="sofistik-mcp")
    monkeypatch.setattr(server_mod.dashboard, "start", lambda *a: object())
    server_mod._start_dashboard()
    monkeypatch.setattr(server_mod.dashboard, "start", lambda *a: None)
    server_mod._start_dashboard()
    assert "dashboard on" in caplog.text and "not started here" in caplog.text


# ------------------------------------------------------------------------------- review round fixes

def test_old_dead_server_files_are_removed_and_reused_pids_are_not_alive(s, tmp_path):
    f = folder(s)
    old = os.path.join(f, "server-999997.json")
    write(old, {"pid": 999997, "job": None, "recent_runs": [{"dat": "x.dat", "status": "ok"}]})
    os.utime(old, (time.time() - 2 * 86400,) * 2)
    write(os.path.join(f, "server-reused.json"), {"pid": os.getpid(), "pid_started": 12345.0, "job": None,
                                                  "recent_runs": [{"dat": "y.dat", "status": "ok"}]})
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    servers = col.servers(f)
    assert not os.path.exists(old)
    assert [x["alive"] for x in servers] == [False]                    # same number, other process


def test_resumed_session_counts_a_message_once(s, tmp_path):
    proj = tmp_path / "projects" / "p"
    proj.mkdir(parents=True)
    first, resumed = proj / "a.jsonl", proj / "b.jsonl"
    first.write_text(usage_line("m1", iso_today(), 100, session="aaaaaaaa1") + "\n")
    resumed.write_text(usage_line("m1", iso_today(), 100, session="bbbbbbbb1") + "\n" +
                       usage_line("m2", iso_today(2), 5, session="bbbbbbbb1") + "\n")
    os.utime(first, (time.time() - 60,) * 2)
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "projects"))
    t = col.tokens()
    assert t["today"]["output"] == 105
    rows = {r["session"]: r["output"] for r in t["sessions"]}
    assert rows == {"aaaaaaaa": 100, "bbbbbbbb": 5}
    os.utime(first, (time.time() - 3 * 86400,) * 2)                    # leaves the window: forgotten
    col._files_cache = (0.0, [])
    col.tokens()
    assert str(first) not in col._token_files


def test_collect_is_serialised(s, tmp_path):
    import threading
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    inside, peak = [0], [0]
    real = col._collect

    def slow():
        inside[0] += 1
        peak[0] = max(peak[0], inside[0])
        time.sleep(0.05)
        inside[0] -= 1
        return real()
    col._collect = slow
    ts = [threading.Thread(target=col.collect) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert peak[0] == 1


def test_write_json_retries_while_a_reader_holds_the_file(tmp_path, monkeypatch):
    target = str(tmp_path / "d" / "x.json")
    real, calls = os.replace, [0]

    def flaky(a, b):
        calls[0] += 1
        if calls[0] < 3:
            raise PermissionError("[WinError 5] Access is denied")
        return real(a, b)
    monkeypatch.setattr(dashboard.os, "replace", flaky)
    monkeypatch.setattr(dashboard.time, "sleep", lambda t: None)
    dashboard._write_json(target, {"a": 1})
    assert json.load(open(target)) == {"a": 1} and calls[0] == 3
    monkeypatch.setattr(dashboard.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(PermissionError):
        dashboard._write_json(target, {"a": 2})
    assert [n for n in os.listdir(tmp_path / "d") if n.endswith(".tmp")] == []    # no tmp file left


def test_file_lock_waits_takes_over_stale_and_times_out(tmp_path, monkeypatch):
    p = str(tmp_path / "c.json")
    with dashboard._FileLock(p):
        assert os.path.exists(p + ".lock")
        with pytest.raises(TimeoutError):
            with dashboard._FileLock(p, timeout_s=0.2):
                pass
    assert not os.path.exists(p + ".lock")
    open(p + ".lock", "w").close()
    os.utime(p + ".lock", (time.time() - 60,) * 2)                     # left by a crash
    with dashboard._FileLock(p, timeout_s=0.5):
        pass


@pytest.mark.parametrize("host, lan, ok", [
    ("localhost:8765", False, True), ("127.0.0.1:8765", False, True), ("[::1]:8765", False, True),
    (socket.gethostname() + ":8765", False, True), ("evil.example.com:8765", False, False), (None, False, False),
    ("192.168.1.20:8765", False, False), ("192.168.1.20:8765", True, True), ("evil.example.com", True, False),
    ("app.localhost", False, True),
])
def test_host_allowed(host, lan, ok):
    assert dashboard.host_allowed(host, lan) is ok


def test_rebinding_request_is_refused(s, tmp_path):
    port = free_port()
    httpd = dashboard.start(dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none")), "127.0.0.1", port)
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/state", headers={"Host": "attacker.example"})
        try:
            urllib.request.urlopen(req, timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_main_port_switched_off(monkeypatch, capsys, s):
    monkeypatch.setattr(dashboard.config, "load_settings", lambda: {**s, "dashboard_port": 0})
    assert dashboard.main(["--no-browser"]) == 0
    assert "switched off" in capsys.readouterr().out


def test_claude_code_running_under_node_is_listed(s, tmp_path, monkeypatch):
    class NodeProc(FakeProc):
        def __init__(self, pid, args):
            super().__init__(pid, "node.exe", r"C:\\node\\node.exe")
            self.args = args

        def cmdline(self):
            return self.args
    procs = [NodeProc(20, ["node", r"C:\\npm\\node_modules\\@anthropic-ai\\claude-code\\cli.js"]),
             NodeProc(21, ["node", "server.js"])]
    monkeypatch.setattr(dashboard.psutil, "process_iter", lambda attrs=None: list(procs))
    col = dashboard.Collector(lambda: s, claude_dir=str(tmp_path / "none"))
    assert [r["pid"] for r in col.processes()["claude"]] == [20]
    assert dashboard._is_claude_node(object()) is False


def test_dashboard_status_with_broken_settings(server_mod, monkeypatch):
    def bad():
        raise server_mod.config.SettingsError("typing error")
    monkeypatch.setattr(server_mod, "_settings", bad)
    d = run(server_mod.dashboard_status())
    assert d["page"] == "http://localhost:8765" and "typing error" in d["notes"][0]
