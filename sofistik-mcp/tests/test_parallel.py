"""Run-time estimate and run history, parallel calculations capped by RAM, clone_cdb, lock tools."""
from __future__ import annotations

import os
import time

import pytest
from conftest import run

from sofistik_mcp import dashboard


def w_dat(folder, name, text):
    p = os.path.join(str(folder), name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


# ------------------------------------------------------------------------------------------------
# estimate
# ------------------------------------------------------------------------------------------------

PREV = {"dat": "x", "finished": "2026-10-17T22:00:00", "status": "ok", "seconds": 600,
        "modules": [{"program": "AQUA", "seconds": 10}, {"program": "ASE", "seconds": 290},
                    {"program": "BDK", "seconds": 300}]}


def tl(*items):
    return [{"program": p, "t0": t0, "t1": t1} for p, t0, t1 in items]


def test_first_run_has_no_estimate():
    e = dashboard.estimate(None, tl(("AQUA", 0, None)), 5, 3, now=5)
    assert e["remaining_s"] is None and "first run" in e["basis"] and e["program"] == "AQUA"
    assert e["program_no"] == 1 and e["programs_total"] == 3


def test_estimate_follows_the_programs_of_last_run():
    now = 1000.0
    e = dashboard.estimate(PREV, tl(("AQUA", 900, 905), ("ASE", 905, None)), 100, None, now=now)
    # ASE has run 95 s of its 290 s; BDK 300 s follows
    assert e["remaining_s"] == 290 - 95 + 300 and e["program"] == "ASE" and e["program_no"] == 2
    assert e["programs_total"] == 3 and not e["slower_than_last"] and "took 10 min" in e["basis"]
    assert e["finish_at"] == time.strftime("%H:%M", time.localtime(now + 495))


def test_estimate_when_a_program_is_slower_than_last_time():
    e = dashboard.estimate(PREV, tl(("AQUA", 0, 5), ("ASE", 5, 405), ("BDK", 405, None)), 1000, 3, now=1000)
    assert e["remaining_s"] == 0 and e["slower_than_last"]


def test_estimate_with_other_programs_uses_the_total():
    e = dashboard.estimate(PREV, tl(("SOFIMSHC", 0, None)), 100, 2, now=100)
    assert e["remaining_s"] == 500 and "only the total" in e["basis"]
    e = dashboard.estimate(PREV, [], 50, None, now=50)
    assert e["remaining_s"] == 550 and "program" not in e
    assert dashboard._fmt_s(3725) == "1 h 02 min" and dashboard._fmt_s(90) == "90 s"


def test_history_last_clean_run_and_peak_ram(tmp_path):
    h = dashboard.RunHistory(str(tmp_path))
    assert h.runs() == [] and h.last_for("a.dat") is None and h.peak_ram_mb("a.dat") is None
    dat = str(tmp_path / "a.dat")
    h.add({"dat": dat, "status": "ok", "seconds": 100, "peak_ram_mb": 500, "modules": []})
    h.add({"dat": dat, "status": "errors", "seconds": 5, "peak_ram_mb": 900, "modules": []})
    h.add({"dat": str(tmp_path / "b.dat"), "status": "ok", "seconds": 7, "peak_ram_mb": 50, "modules": []})
    assert h.last_for(dat)["seconds"] == 100 and h.peak_ram_mb(dat) == 900
    (tmp_path / "run_history.json").write_text("garbage")
    assert h.runs() == []


def test_server_state_keeps_several_jobs_and_records_history(tmp_path):
    s = {"work_folders": [str(tmp_path)]}
    st = dashboard.ServerState(lambda: s, "9")
    a, b = str(tmp_path / "a.dat"), str(tmp_path / "b.dat")
    st.job_started(a, key="j1")
    st.job_started(b, key="j2")
    st.job_programs(4, key="j1")
    st.job_process(123, key="j2")

    class W:
        module, ram_mb, peak_ram_mb = "ASE", 700, 800
        timeline = [{"program": "ASE", "t0": time.time() - 3, "t1": None}]
    st.job_progress(W(), key="j1")
    saved = dashboard._read_json(st.path())
    assert [j["dat"] for j in saved["jobs"]] == [a, b] and saved["job"]["dat"] == a
    assert saved["jobs"][0]["module"] == "ASE" and saved["jobs"][0]["estimate"]["programs_total"] == 4
    assert "_prev" not in saved["jobs"][0] and saved["jobs"][1]["sps_pid"] == 123
    st.job_finished({"status": "ok", "seconds": 12.0, "peak_ram_mb": 800,
                     "module_times": [{"program": "ASE", "seconds": 11}]}, key="j1")
    saved = dashboard._read_json(st.path())
    assert [j["dat"] for j in saved["jobs"]] == [b] and saved["recent_runs"][0]["peak_ram_mb"] == 800
    assert st.history().last_for(a)["modules"] == [{"program": "ASE", "seconds": 11}]
    st.job_started(a, key="j3")                                       # the next run of a gets an estimate
    assert "took 12 s" in st.job_info("j3")["estimate"]["basis"]
    st.job_finished({"status": "not run", "reason": "x"}, key="j3")
    assert len(st.history().runs()) == 1                              # a refused run is not history


def test_closed_server_jobs_become_not_finished(tmp_path):
    folder = str(tmp_path)
    dashboard._write_json(os.path.join(folder, "server-999999.json"),
                          {"pid": 999999, "pid_started": 1, "jobs": [{"dat": "a.dat"}, {"dat": "b.dat"}],
                           "job": {"dat": "a.dat"}, "recent_runs": []})
    out = dashboard.Collector(lambda: {"work_folders": [folder]}).servers(folder)
    assert out[0]["jobs"] == [] and [r["status"] for r in out[0]["recent_runs"]] == ["not finished"] * 2


# ------------------------------------------------------------------------------------------------
# the server: parallel runs, RAM cap, clone, lock tools
# ------------------------------------------------------------------------------------------------

def test_two_models_run_at_the_same_time(server_mod, settings):
    work = settings["work_folders"][0]
    a = run(server_mod.run_calculation(w_dat(work, "a.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")))
    b = run(server_mod.run_calculation(w_dat(work, "b.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")))
    assert a["status"] == "running" and b["status"] == "running" and a["job_id"] != b["job_id"]
    assert len(server_mod._running()) == 2
    third = run(server_mod.run_calculation(w_dat(work, "c.dat", "+PROG ASE\nEND\n")))
    assert third["status"] == "not run" and "max_parallel_runs" in third["reason"]
    assert run(server_mod.get_job_result(a["job_id"], 30))["status"] == "ok"
    assert run(server_mod.get_job_result(b["job_id"], 30))["status"] == "ok"
    assert run(server_mod.get_job_result(None, 0))["dat"].endswith("b.dat")      # the latest one


def test_stop_without_job_id_stops_all(server_mod, settings):
    work = settings["work_folders"][0]
    a = run(server_mod.run_calculation(w_dat(work, "a.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n")))
    b = run(server_mod.run_calculation(w_dat(work, "b.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n")))
    one = run(server_mod.stop_calculation(job_id=a["job_id"]))
    assert one["status"] in ("stopped", "stopping") and not server_mod._calcs[b["job_id"]]["stop"]
    rest = run(server_mod.stop_calculation())
    assert rest["status"] in ("stopped", "stopping")
    assert run(server_mod.get_job_result(b["job_id"], 30))["status"] == "stopped"
    assert run(server_mod.stop_calculation(job_id="calc-nope"))["status"].startswith("nothing running")


def test_second_run_refused_when_ram_is_short(server_mod, settings, monkeypatch):
    work = settings["work_folders"][0]

    class VM:
        available = 6 * 2**30
    monkeypatch.setattr(server_mod.psutil, "virtual_memory", lambda: VM())
    hist = server_mod._state.history()
    big = os.path.join(work, "big.dat")
    hist.add({"dat": big, "status": "ok", "seconds": 5, "peak_ram_mb": 17000, "modules": []})
    a = run(server_mod.run_calculation(w_dat(work, "a.dat", "+PROG ASE\nEND\n$ FAKE sleep=5\n")))
    assert a["status"] == "running"
    r = run(server_mod.run_calculation(w_dat(work, "big.dat", "+PROG ASE\nEND\n")))
    assert r["status"] == "not run" and "Not enough free RAM" in r["reason"] and "17.0 GB" not in r["reason"]
    assert "16.6 GB" in r["reason"] and "last time" in r["reason"]
    VM.available = 40 * 2**30
    assert run(server_mod.run_calculation(big))["status"] in ("ok", "running")


def test_clone_cdb(server_mod, settings):
    work = settings["work_folders"][0]
    src = os.path.join(work, "m.cdb")
    with open(src, "wb") as f:
        f.write(b"CDB" * 1000)
    r = run(server_mod.clone_cdb(src, "m_part2"))
    assert r["to"] == os.path.join(work, "m_part2.cdb") and open(r["to"], "rb").read() == b"CDB" * 1000
    assert r["dat_to_run"].endswith("m_part2.dat") and r["dat_exists"] is False
    assert "already exists" in run(server_mod.clone_cdb(src, "m_part2.dat"))["error"]
    assert run(server_mod.clone_cdb(os.path.join(work, "m.dat"), "m_part2", overwrite=True))["size_mb"] >= 0
    assert "same .cdb" in run(server_mod.clone_cdb(src, "m"))["error"]
    assert "not found" in run(server_mod.clone_cdb(os.path.join(work, "x.cdb"), "y"))["error"]
    assert "give the name" in run(server_mod.clone_cdb(src, " "))["error"]


def test_clone_refused_while_the_source_is_calculated(server_mod, settings):
    work = settings["work_folders"][0]
    a = run(server_mod.run_calculation(w_dat(work, "a.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")))
    assert a["status"] == "running"
    with open(os.path.join(work, "a.cdb"), "wb") as f:
        f.write(b"x")
    assert "being calculated" in run(server_mod.clone_cdb(os.path.join(work, "a.cdb"), "a2"))["error"]
    run(server_mod.get_job_result(a["job_id"], 30))


def test_clone_needs_disk_space(server_mod, settings, monkeypatch):
    work = settings["work_folders"][0]
    src = w_dat(work, "m.cdb", "x")
    monkeypatch.setattr(server_mod.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    assert "Not enough disk space" in run(server_mod.clone_cdb(src, "m2"))["error"]


def test_lock_tools(server_mod, settings, tmp_path):
    work = settings["work_folders"][0]
    cdb = w_dat(work, "m.cdb", "x")
    r = run(server_mod.check_cdb_lock(os.path.join(work, "m.dat")))
    assert r["cdb"] == cdb and not r["locked"] and r["calculating_here"] == []
    c = run(server_mod.clear_cdb_lock(cdb, clean_stored_locks=False))
    assert c["ended"] == [] and "clean_locks" not in c
    c = run(server_mod.clear_cdb_lock(cdb))
    assert c["clean_locks"]["cleaned"] is False                       # no SOFiSTiK Clean Locks in the test root
    assert "outside" in run(server_mod.check_cdb_lock(str(tmp_path / "x.cdb")))["error"]
    assert ".cdb" in run(server_mod.check_cdb_lock(w_dat(work, "m.txt", "")))["error"]


def test_clear_refused_while_calculated(server_mod, settings):
    work = settings["work_folders"][0]
    a = run(server_mod.run_calculation(w_dat(work, "a.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")))
    assert "not a stale lock" in run(server_mod.clear_cdb_lock(os.path.join(work, "a.cdb")))["error"]
    run(server_mod.get_job_result(a["job_id"], 30))


@pytest.mark.parametrize("value, expected", [(None, 1), ("3", 3), (99, 8), ("x", 1)])
def test_parallel_setting(tmp_path, value, expected):
    import json

    from sofistik_mcp import config
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"max_parallel_runs": value, "min_free_ram_gb": "x", "auto_clear_cdb_locks": "false"}))
    s = config.load_settings(str(p))
    assert s["max_parallel_runs"] == expected and s["min_free_ram_gb"] == 4.0 and s["auto_clear_cdb_locks"] is False
