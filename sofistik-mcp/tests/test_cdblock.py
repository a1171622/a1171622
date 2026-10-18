"""Who holds a .cdb, ending programs left behind by a stopped run, SOFiSTiK's Clean Locks, and the
run watcher that makes a stop end every program of a run."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time

import psutil
import pytest

from sofistik_mcp import cdblock, solver


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)

HOLD = "import sys, time\nf = open(sys.argv[1], 'rb')\nprint('open', flush=True)\ntime.sleep(60)\n"


def fake_program(tmp_path, name: str) -> str:
    """A copy of the Python interpreter called name (so the process is named like a SOFiSTiK program)."""
    if os.name == "nt":  # pragma: no cover - Windows names the copy name.exe
        dst = str(tmp_path / (name + ".exe"))
    else:
        dst = str(tmp_path / name)
    shutil.copy2(os.path.realpath(sys.executable), dst)
    return dst


def hold(exe: str, path: str, tmp_path) -> subprocess.Popen:
    script = tmp_path / "hold.py"
    script.write_text(HOLD)
    p = subprocess.Popen([exe, str(script), path], stdout=subprocess.PIPE, cwd=str(tmp_path))
    assert p.stdout is not None and p.stdout.readline().strip() == b"open"
    return p


@pytest.fixture
def cdb(tmp_path):
    p = tmp_path / "m.cdb"
    p.write_bytes(b"\0" * 1024)
    return str(p)


def test_nothing_holds_a_closed_cdb(cdb):
    r = cdblock.check(cdb)
    assert r["exists"] and not r["locked"] and r["holders"] == [] and r["advice"] == []
    assert cdblock.check(cdb + "x") == {"cdb": cdb + "x", "exists": False, "locked": False, "holders": [],
                                        "advice": []}


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_a_running_calculation_is_never_ended(tmp_path, cdb):
    p = hold(fake_program(tmp_path, "bdk"), cdb, tmp_path)
    try:
        r = cdblock.check(cdb)
        assert r["locked"] and [h["kind"] for h in r["holders"]] == ["run"]     # its parent (pytest) is alive
        assert r["holders"][0]["name"].lower().startswith("bdk") and "still running" in r["advice"][0]
        c = cdblock.clear(cdb)
        assert c["ended"] == [] and c["locked_now"] and p.poll() is None
    finally:
        p.kill()
        p.wait()


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_an_orphan_is_ended_and_the_lock_cleared(tmp_path, cdb, monkeypatch):
    p = hold(fake_program(tmp_path, "bdk"), cdb, tmp_path)
    monkeypatch.setattr(cdblock, "_chain", lambda pid, table: [])            # its sps.exe has ended
    try:
        before = cdblock.check(cdb)
        assert [h["kind"] for h in before["holders"]] == ["orphan"] and "clear_cdb_lock" in before["advice"][0]
        c = cdblock.clear(cdb)
        assert [e["pid"] for e in c["ended"]] == [p.pid] and c["locked_before"] and not c["locked_now"]
        assert p.wait(10) is not None
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_windows_and_other_programs_are_reported_not_ended(tmp_path, cdb, monkeypatch):
    p = hold(fake_program(tmp_path, "wingraf"), cdb, tmp_path)
    q = hold(sys.executable, cdb, tmp_path)                                   # another Python program: ignored
    monkeypatch.setattr(cdblock, "_chain", lambda pid, table: [])
    try:
        r = cdblock.clear(cdb)
        assert [h["kind"] for h in r["holders_before"]] == ["window"] and r["ended"] == []
        assert "close the model there" in r["advice"][0] and p.poll() is None and q.poll() is None
        c = cdblock.clear(cdb, clean_flag=True)
        assert c["clean_locks"]["cleaned"] is False and "still has the .cdb open" in c["clean_locks"]["error"]
    finally:
        for x in (p, q):
            x.kill()
            x.wait()


def _row(pid, name, ppid, ct, sofistik=True):
    return {"pid": pid, "name": name, "ppid": ppid, "create_time": ct, "sofistik": sofistik}


@pytest.mark.parametrize("chain, kind", [
    ([], "orphan"),                                                  # parent ended
    ([("WPSJOB.exe", True)], "orphan"),                              # only a SOFiSTiK wrapper is left
    ([("WPSJOB.exe", True), ("sps.exe", True)], "run"),             # sps.exe still runs it
    ([("Teddy.exe", True)], "run"),                                  # started from Teddy
    ([("cmd.exe", False)], "run"),                                   # started by hand / a script
])
def test_kind_from_the_parent_chain(chain, kind):
    table = {10: _row(10, "BDK.exe", 11 if chain else 99, 100.0)}
    for i, (name, sof) in enumerate(chain):
        table[11 + i] = _row(11 + i, name, 12 + i, 90.0 - i, sof)
    assert cdblock._kind(table[10], table, set()) == kind


def test_kind_of_programs_themselves():
    t = {1: _row(5, "WinGRAF.exe", 0, 1.0), 2: _row(6, "sps.exe", 0, 1.0), 3: _row(7, "python.exe", 0, 1.0, False),
         4: _row(8, "excel.exe", 0, 1.0, False)}
    t[3]["cmdline"] = ["python", "-m", "sofistik_mcp.cdb_worker", "a", "b"]
    assert [cdblock._kind(r, {}, set()) for r in t.values()] == ["window", "run", "reader", "other"]
    assert cdblock._kind(_row(9, "ase.exe", 0, 1.0), {}, {9}) == "reader"


def test_a_reused_parent_number_is_not_a_parent():
    table = {10: _row(10, "BDK.exe", 11, 100.0), 11: _row(11, "sps.exe", 0, 200.0)}   # started after its "child"
    assert cdblock._chain(10, table) == [] and cdblock._kind(table[10], table, set()) == "orphan"


def write_fake_dbinfo(folder) -> str:
    os.makedirs(folder, exist_ok=True)
    log = os.path.join(folder, "dbinfo_calls.txt")
    path = os.path.join(folder, "dbinfo.exe")
    with open(path, "w") as f:
        f.write(f"#!{sys.executable}\nimport sys\nopen({log!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                "print('locks cleaned')\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


@pytest.mark.skipif(os.name == "nt", reason="the fake dbinfo is a script")
def test_clean_locks_runs_dbinfo_z_from_the_sofistik_folder(tmp_path, cdb):
    root = str(tmp_path / "sofistik")
    write_fake_dbinfo(root)
    r = cdblock.clean_locks(cdb, root)
    assert r["cleaned"] and "dbinfo.exe" in r["source"] and r["output"] == "locks cleaned"
    assert open(os.path.join(root, "dbinfo_calls.txt")).read() == f"{cdb} z\n"


def test_clean_locks_refuses_a_program_outside_the_sofistik_folder(tmp_path, cdb):
    other = write_fake_dbinfo(str(tmp_path / "elsewhere"))
    r = cdblock.clean_locks(cdb, str(tmp_path / "sofistik"), configured=f'"{other}" "%1" z')
    assert not r["cleaned"] and "not inside the SOFiSTiK folder" in r["source"] and "Clean Locks" in r["error"]
    r = cdblock.clean_locks(cdb, None)
    assert not r["cleaned"] and "Teddy" in r["error"]


@pytest.mark.skipif(os.name == "nt", reason="the fake dbinfo is a script")
def test_clean_locks_timeout_and_start_failure(tmp_path, cdb, monkeypatch):
    root = str(tmp_path / "sofistik")
    exe = write_fake_dbinfo(root)
    with open(exe, "a") as f:
        f.write("import time\ntime.sleep(30)\n")
    monkeypatch.setattr(cdblock, "CLEAN_TIMEOUT_S", 1)
    r = cdblock.clean_locks(cdb, root)
    assert not r["cleaned"] and "did not finish" in r["error"]
    os.chmod(exe, 0o644)
    r = cdblock.clean_locks(cdb, root, configured=f'"{exe}" %1')
    assert not r["cleaned"] and "PermissionError" in r["error"]


def test_no_registry_off_windows():
    if os.name != "nt":
        assert cdblock.clean_locks_menu_entries() == []
    assert cdblock._exe_of('"C:\\a b\\x.exe" "%1" z') == "C:\\a b\\x.exe" and cdblock._exe_of("x.exe %1") == "x.exe"


# ------------------------------------------------------------------------------------------------
# solver: the watcher, a complete stop, and the lock retry
# ------------------------------------------------------------------------------------------------

def test_watcher_records_programs_ram_and_timeline(tmp_path, sps):
    ticks = []
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")
    old = solver.POLL_S
    solver.POLL_S = 0.5
    try:
        r = solver.run(dat, sps, 60, on_tick=lambda wt: ticks.append((wt.ram_mb, len(wt.timeline))))
    finally:
        solver.POLL_S = old
    assert r["status"] == "ok" and ticks and r["peak_ram_mb"] > 0
    assert [m["program"] for m in r["module_times"]] == ["ASE"] and r["module_times"][0]["seconds"] >= 0


def test_stop_ends_a_program_that_left_the_job(tmp_path):
    """A grandchild that outlives its parent (as BDK did) is still ended by a stop."""
    code = ("import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "time.sleep(60)\n")
    proc = subprocess.Popen([sys.executable, "-c", code], **solver._popen_kw())
    watch = solver._Watch(proc)
    proc._mcp_watch = watch
    deadline = time.time() + 10
    while not watch.seen and time.time() < deadline:
        watch.snapshot()
        time.sleep(0.2)
    kid = next(iter(watch.seen))
    proc.kill()                                     # only the parent dies: the child is left behind ...
    proc.wait()
    assert psutil.pid_exists(kid)
    solver._kill_tree(proc)                         # ... and the stop still ends it
    assert proc._mcp_survivors == []
    assert not psutil.pid_exists(kid) or psutil.Process(kid).status() == psutil.STATUS_ZOMBIE


def test_lock_abort_is_cleaned_and_rerun(tmp_path, sps, monkeypatch):
    root = str(tmp_path / "sofistik")
    write_fake_dbinfo(root)
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE print=CDBASE:_WAIT_FOR_LOCK_ABORTED_BY_USER\n")
    (tmp_path / "m.cdb").write_bytes(b"\0" * 64)
    if os.name == "nt":  # pragma: no cover
        pytest.skip("the fake dbinfo is a script")
    r = solver.run(dat, sps, 60, sofistik_root=root)
    calls = open(os.path.join(root, "dbinfo_calls.txt")).read().splitlines()
    assert calls == [f"{tmp_path / 'm.cdb'} z"]                                   # cleaned once
    assert any("Clean Locks" in x and "run again" in x for x in r["server_warnings"])
    assert r["cdb_lock"]["after_lock_error"]["clean_locks"]["cleaned"]
    off = solver.run(dat, sps, 60, sofistik_root=root, auto_clear_locks=False)
    assert "auto_clear_cdb_locks" not in off.get("reason", "") or off["status"] in solver.OK_STATUSES
    assert len(open(os.path.join(root, "dbinfo_calls.txt")).read().splitlines()) == 1   # not again


def test_lock_abort_reason_when_it_cannot_be_cleaned(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=errors\n$ FAKE print=WAIT_FOR_LOCK\n")
    (tmp_path / "m.cdb").write_bytes(b"\0" * 64)
    r = solver.run(dat, sps, 60, sofistik_root=str(tmp_path / "nosofistik"))
    assert "locked (WAIT FOR LOCK)" in r["reason"] and "Teddy" in r["reason"]


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_run_refused_while_a_live_calculation_holds_the_cdb(tmp_path, sps):
    cdb = tmp_path / "m.cdb"
    cdb.write_bytes(b"\0" * 64)
    p = hold(fake_program(tmp_path, "ase"), str(cdb), tmp_path)
    try:
        r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
        assert r["status"] == "not run" and "still running" in r["reason"] and r["cdb_lock"]["holders"]
    finally:
        p.kill()
        p.wait()


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_orphan_holding_the_cdb_is_ended_before_the_run(tmp_path, sps, monkeypatch):
    cdb = tmp_path / "m.cdb"
    cdb.write_bytes(b"\0" * 64)
    p = hold(fake_program(tmp_path, "bdk"), str(cdb), tmp_path)
    real = cdblock._chain
    monkeypatch.setattr(cdblock, "_chain", lambda pid, table: [] if pid == p.pid else real(pid, table))
    try:
        r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
        assert r["status"] == "ok" and [e["pid"] for e in r["cdb_lock"]["ended"]] == [p.pid]
        assert p.wait(10) is not None
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_no_time_limit(tmp_path, sps):
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=1\n"), sps, None)
    assert r["status"] == "ok"


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_a_program_left_running_after_sps_ended_is_ended(tmp_path):
    import fake_sps
    bdk = fake_program(tmp_path, "bdk")
    script = tmp_path / "sps_leaves_bdk.py"
    script.write_text(f"import subprocess, sys\nsys.path.insert(0, {os.path.dirname(fake_sps.__file__)!r})\n"
                      "import fake_sps\n"
                      f"subprocess.Popen([{bdk!r}, '-c', 'import time; time.sleep(60)'])\n"
                      "sys.exit(fake_sps.main(sys.argv))\n")
    sps = fake_sps.make(tmp_path / "bin", script=str(script))
    old = solver.POLL_S
    solver.POLL_S = 0.3
    try:
        r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=2\n"), sps, 60)
    finally:
        solver.POLL_S = old
    assert r["status"] == "ok"
    assert any("still running after sps.exe ended and were ended" in x for x in r["server_warnings"])
    assert not any(p.name() == "bdk" and p.status() != psutil.STATUS_ZOMBIE for p in psutil.process_iter())


def test_survivors_are_reported(tmp_path, sps, monkeypatch):
    real = solver._launch

    def launch(*a, **k):
        proc, out, timed_out, problem = real(*a, **k)
        proc._mcp_survivors = [{"pid": 4242, "name": "BDK.exe"}]
        return proc, out, timed_out, problem
    monkeypatch.setattr(solver, "_launch", launch)
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
    assert r["left_running"] == [{"pid": 4242, "name": "BDK.exe"}]
    assert any("could not be ended" in x for x in r["server_warnings"])


@pytest.mark.skipif(os.name == "nt", reason="the copied interpreter needs its DLLs next to it on Windows")
def test_working_folder_is_the_hint_when_open_files_are_refused(tmp_path, cdb, monkeypatch):
    (tmp_path / "other.txt").write_text("x")
    p = hold(fake_program(tmp_path, "ase"), str(tmp_path / "other.txt"), tmp_path)   # runs in the .cdb's folder

    def denied(self):
        raise psutil.AccessDenied(self.pid)
    monkeypatch.setattr(psutil.Process, "open_files", denied)
    try:
        r = cdblock.check(cdb)
        hint = [h["how"] for h in r["holders"] if h["pid"] == p.pid]
        assert hint == ["working folder (its open files could not be listed)"]
    finally:
        p.kill()
        p.wait()


def test_end_skips_a_reused_number_and_reports_kill_failures(cdb, monkeypatch):
    me = psutil.Process()
    assert cdblock._end(me.pid, me.create_time() + 100) is None                 # another process now
    assert cdblock._end(2**22 + 12345, 0) is None                               # gone
    fake = {"pid": 1, "name": "BDK.exe", "kind": "orphan", "create_time": 0, "started": "x", "ram_mb": 1,
            "parent": None, "how": "open file"}
    monkeypatch.setattr(cdblock, "holders", lambda *a, **k: [fake])

    def boom(pid, ct):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(cdblock, "_end", boom)
    r = cdblock.clear(cdb)
    assert r["ended"] == [] and "AccessDenied" in r["failed"][0]["error"]
    assert cdblock._advice(dict(fake, kind="reader")).startswith("This server is reading it")
    assert "close that program" in cdblock._advice(dict(fake, kind="other"))


def test_open_elsewhere_is_reported(cdb, monkeypatch):
    monkeypatch.setattr(cdblock, "open_elsewhere", lambda p: True)
    r = cdblock.check(cdb)
    assert r["locked"] and "cannot see" in r["advice"][0]
    monkeypatch.setattr(cdblock, "check", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert "Could not check" in solver._pre_run_lock(cdb, None, True)["warning"]


def test_pre_run_warning_for_an_open_window(cdb, monkeypatch):
    h = {"pid": 5, "name": "WinGRAF.exe", "kind": "window", "create_time": 0, "started": "x", "ram_mb": 1,
         "parent": None, "how": "open file"}
    monkeypatch.setattr(cdblock, "holders", lambda *a, **k: [h])
    r = solver._pre_run_lock(cdb, None, True)
    assert "refuse" not in r and "close the model there" in r["warning"]


@pytest.mark.skipif(os.name != "nt", reason="the registry is Windows only")
def test_registry_lookup_runs_on_windows():  # pragma: no cover - windows-latest CI
    entries = cdblock.clean_locks_menu_entries()
    assert isinstance(entries, list) and all({"key", "label", "command"} <= set(e) for e in entries)
    cmd, source = cdblock.clean_locks_command(None)
    assert cmd is None and source
