"""server.py tool functions called directly (fast, measurable): files, calculation jobs, .cdb reads
through the real worker process (with the fake .cdb via tests/sitehook), manuals and examples."""
from __future__ import annotations

import datetime
import gzip
import json
import os
import time

import pytest
from conftest import ROOT, run, write_hook_config

from sofistik_mcp import config


def work(settings):
    import pathlib
    return pathlib.Path(settings["work_folders"][0])


# ---------------------------------------------------------------- status

def test_status(server_mod, settings):
    st = run(server_mod.sofistik_status())
    assert st["server_version"] == server_mod.VERSION and st["sofistik"]["sps"] == server_mod._test_info["sps"]
    assert st["work_folders"] == settings["work_folders"] and st["allow_sys_commands"] is False
    assert st["run_timeout_minutes"] == 60.0 and isinstance(st["manual_index_shipped"], bool)


def test_install_error_is_reported_not_raised(monkeypatch, tmp_path):
    from sofistik_mcp import install, server
    monkeypatch.setattr(install, "find", lambda s=None: (_ for _ in ()).throw(install.SofistikNotFound("nope")))
    info = server._install({})
    assert info["error"] == "nope" and info["sps"] is None and info["dll_dirs"] == []


# ---------------------------------------------------------------- files

def test_write_dat_file(server_mod, settings):
    p = work(settings) / "sub" / "m.dat"
    r = run(server_mod.write_dat_file(str(p), "+PROG ASE\nHEAD test\r\nEND"))
    assert r == {"written": str(p), "lines": 3, "backup_of_previous": None}
    assert p.read_bytes() == b"+PROG ASE\r\nHEAD test\r\nEND\r\n"                # CRLF, final newline
    again = run(server_mod.write_dat_file(str(p), "new"))
    assert "already exists" in again["error"] and p.read_bytes().startswith(b"+PROG ASE")
    r = run(server_mod.write_dat_file(str(p), "+PROG AQUA\n", overwrite=True))
    bak = r["backup_of_previous"]
    assert bak.startswith(str(p) + ".bak-") and open(bak, "rb").read() == b"+PROG ASE\r\nHEAD test\r\nEND\r\n"
    assert p.read_bytes() == b"+PROG AQUA\r\n" and r["lines"] == 2


def test_write_dat_file_refusals(server_mod, settings, tmp_path):
    assert "outside the work folders" in run(server_mod.write_dat_file(str(tmp_path / "x.dat"), "x"))["error"]
    assert "must end in .dat" in run(server_mod.write_dat_file(str(work(settings) / "x.txt"), "x"))["error"]
    esc = str(work(settings) / ".." / "x.dat")
    assert "outside the work folders" in run(server_mod.write_dat_file(esc, "x"))["error"]
    assert not (tmp_path / "x.dat").exists()


def test_write_dat_file_refuses_server_folder(server_mod, settings):
    settings["work_folders"] = [os.path.dirname(ROOT)]
    r = run(server_mod.write_dat_file(os.path.join(ROOT, "selftest", "evil.dat"), "x"))
    assert "server's own folder" in r["error"] and not os.path.exists(os.path.join(ROOT, "selftest", "evil.dat"))
    r = run(server_mod.run_calculation(os.path.join(ROOT, "selftest", "selftest_cantilever.dat")))
    assert "server's own folder" in r["error"]


def test_write_dat_file_non_ascii_warning(server_mod, settings):
    r = run(server_mod.write_dat_file(str(work(settings) / "u.dat"), "HEAD Träger µ\n"))
    assert "non-ASCII" in r["warning"] and "ä" in r["warning"] and "µ" in r["warning"]
    assert (work(settings) / "u.dat").read_bytes() == "HEAD Träger µ\r\n".encode()


class FrozenDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 17, 9, 30, 0)


def test_two_overwrites_in_one_second_keep_the_original(server_mod, settings, monkeypatch):
    monkeypatch.setattr(server_mod.datetime, "datetime", FrozenDatetime)
    p = work(settings) / "m.dat"
    run(server_mod.write_dat_file(str(p), "ORIGINAL"))
    run(server_mod.write_dat_file(str(p), "v2", overwrite=True))
    run(server_mod.write_dat_file(str(p), "v3", overwrite=True))
    baks = [f for f in os.listdir(work(settings)) if f.startswith("m.dat.bak-")]
    assert any((work(settings) / b).read_text().startswith("ORIGINAL") for b in baks)


def test_read_text_file(server_mod, settings, tmp_path):
    p = work(settings) / "m.erg"
    p.write_bytes(b"line1\r\nline2\r\nline3\r\n")
    r = run(server_mod.read_text_file(str(p)))
    assert r == {"path": str(p), "total_lines": 4, "from_line": 1, "to_line": 4,
                 "text": "1: line1\n2: line2\n3: line3\n4: "}
    r = run(server_mod.read_text_file(str(p), start_line=2, max_lines=1))
    assert r["text"] == "2: line2" and (r["from_line"], r["to_line"]) == (2, 2)
    assert run(server_mod.read_text_file(str(p), start_line=-5, max_lines=0))["text"] == "1: line1"
    assert run(server_mod.read_text_file(str(p), start_line=10))["text"] == ""
    (work(settings) / "m.cdb").write_bytes(b"\0")
    assert "binary file" in run(server_mod.read_text_file(str(work(settings) / "m.cdb")))["error"]
    assert "File not found" in run(server_mod.read_text_file(str(work(settings) / "none.dat")))["error"]
    (tmp_path / "secret.txt").write_text("x")
    assert "outside the folders" in run(server_mod.read_text_file(str(tmp_path / "secret.txt")))["error"]


def test_read_text_file_read_folder_and_sofistik_root(server_mod, settings, tmp_path):
    ref = tmp_path / "ref"
    ref.mkdir()
    (ref / "a.dat").write_text("REF")
    settings["read_folders"] = [str(ref)]
    assert run(server_mod.read_text_file(str(ref / "a.dat")))["text"] == "1: REF"
    sof = tmp_path / "sofistik"
    sof.mkdir()
    (sof / "x.txt").write_text("SOF")
    assert run(server_mod.read_text_file(str(sof / "x.txt")))["text"].startswith("1: SOF")
    assert "outside the work folders" in run(server_mod.write_dat_file(str(ref / "b.dat"), "x"))["error"]


def test_list_folder(server_mod, settings, tmp_path):
    w = work(settings)
    (w / "a").mkdir()
    for n in ("m.dat", "M2.DAT", "m.cdb", os.path.join("a", "deep.dat")):
        (w / n).write_text("x" * 2048)
    r = run(server_mod.list_folder(str(w), pattern="*.dat"))
    assert [os.path.basename(f["path"]) for f in r["files"]] == ["M2.DAT", "m.dat"]     # case-insensitive
    assert r["sub_folders"] == ["a"] and r["folder"] == str(w) and r["files"][0]["size_kb"] == 2.0
    assert len(r["files"][0]["modified"]) == 16
    r = run(server_mod.list_folder(str(w), pattern="*.dat", recursive=True))
    assert sorted(os.path.basename(f["path"]) for f in r["files"]) == ["M2.DAT", "deep.dat", "m.dat"]
    assert run(server_mod.list_folder(str(w), max_entries=2))["truncated"] is True
    assert "Not a folder" in run(server_mod.list_folder(str(w / "m.dat")))["error"]
    assert "outside the folders" in run(server_mod.list_folder(str(tmp_path)))["error"]


def test_list_folder_not_truncated_when_exactly_full(server_mod, settings):
    for n in ("a.dat", "b.dat"):
        (work(settings) / n).write_text("x")
    assert run(server_mod.list_folder(str(work(settings)), max_entries=2))["truncated"] is False


# ---------------------------------------------------------------- calculation jobs

def dat(settings, name, text):
    p = work(settings) / name
    p.write_text(text)
    return str(p)


def test_fast_run_answers_directly(server_mod, settings):
    r = run(server_mod.run_calculation(dat(settings, "m.dat", "+PROG ASE\nEND\n$ FAKE mode=warnings\n"),
                                       continue_on_error=True, only_block_urs=2))
    assert r["status"] == "ok with warnings" and r["warnings"] == 1 and "-B0 -R -urs:2" in r["command"]
    m = run(server_mod.read_calculation_messages(str(work(settings) / "m.dat")))
    assert m["status"] == "ok with warnings" and m["messages"][0]["number"] == 2430
    assert run(server_mod.read_calculation_messages(str(work(settings) / "m.prt")))["warnings"] == 1
    assert run(server_mod.get_job_result())["status"] == "ok with warnings"        # latest calculation


def test_run_refusals(server_mod, settings, tmp_path, monkeypatch):
    assert "outside the work folders" in run(server_mod.run_calculation(str(tmp_path / "m.dat")))["error"]
    r = run(server_mod.run_calculation(dat(settings, "s.dat", "+PROG ASE\n+SYS del x\n")))
    assert r["status"] == "not run" and r["sys_lines"]
    monkeypatch.setattr(server_mod, "_install", lambda s=None: {"sps": None, "error": "SOFiSTiK was not found."})
    r = run(server_mod.run_calculation(dat(settings, "m.dat", "+PROG ASE\n")))
    assert r == {"status": "not run", "reason": "SOFiSTiK was not found.",
                 "sofistik": {"sps": None, "error": "SOFiSTiK was not found."}}
    assert "outside the folders" in run(server_mod.read_calculation_messages(str(tmp_path / "m.dat")))["error"]


def test_timeout_minutes_limited_by_settings(server_mod, settings, monkeypatch):
    seen = []
    monkeypatch.setattr(server_mod.solver, "run", lambda *a, **k: seen.append(a[2]) or {"status": "ok"})
    d = dat(settings, "m.dat", "+PROG ASE\n")
    for asked in (None, 0.01, 5, 600):
        run(server_mod.run_calculation(d, timeout_minutes=asked))
    assert seen == [3600.0, 60.0, 300.0, 3600.0]


def test_long_run_job_flow(server_mod, settings):
    d = dat(settings, "slow.dat", "+PROG ASE\nEND\n$ FAKE sleep=4\n")
    t0 = time.time()
    first = run(server_mod.run_calculation(d))
    assert first["status"] == "running" and first["job_id"].startswith("calc-") and first["what"] == "slow.dat"
    assert time.time() - t0 < 10 and "get_job_result" in first["next"]
    busy = run(server_mod.run_calculation(dat(settings, "other.dat", "+PROG ASE\n")))
    assert busy["status"] == "not run" and "still running" in busy["reason"] and busy["job_id"] == first["job_id"]
    for p in ("slow.cdb", "slow.dat", "SLOW.CDB" if os.name == "nt" else "slow.cdb"):
        locked = run(server_mod.cdb_overview(str(work(settings) / p)))
        assert "being calculated right now" in locked["error"]
    still = run(server_mod.get_job_result(first["job_id"], 0))
    assert still["status"] == "running" and still["elapsed_s"] >= 0
    done = run(server_mod.get_job_result(first["job_id"], 20))
    assert done["status"] == "ok" and done["seconds"] >= 3.5
    assert run(server_mod.stop_calculation()) == {"status": "nothing running"}
    assert run(server_mod.get_job_result(first["job_id"], 0))["status"] == "ok"    # result stays available


def test_stop_calculation(server_mod, settings):
    d = dat(settings, "long.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n")
    first = run(server_mod.run_calculation(d))
    assert first["status"] == "running"
    t0 = time.time()
    r = run(server_mod.stop_calculation())
    assert r["status"] == "stopped" and "stopped on request" in r["reason"] and time.time() - t0 < 30
    assert server_mod._calc["proc"] is None and not (work(settings) / "long.prt").exists()
    nxt = run(server_mod.run_calculation(dat(settings, "next.dat", "+PROG ASE\nEND\n")))
    assert nxt["status"] == "ok"                                                   # stop flag reset


def test_get_job_result_unknown(server_mod):
    assert "No job" in run(server_mod.get_job_result("calc-nope"))["error"]
    assert "no calculation started yet" in run(server_mod.get_job_result())["error"]
    assert run(server_mod.stop_calculation()) == {"status": "nothing running"}


def test_jobs_report_exceptions_and_are_pruned(server_mod):
    job = server_mod._start_job("x", "boom", lambda: 1 / 0)
    job["done"].wait(5)
    assert job["result"] == {"error": "ZeroDivisionError: division by zero"}
    for i in range(60):
        server_mod._start_job("x", str(i), lambda: {"ok": 1})["done"].wait(5)
    server_mod._start_job("x", "last", lambda: {"ok": 1})["done"].wait(5)
    assert len(server_mod._jobs) <= 51


def test_wait_clamped(server_mod):
    import threading
    ev = threading.Event()
    job = server_mod._start_job("x", "wait", lambda: ev.wait(10) and {"done": True})
    t0 = time.time()
    r = run(server_mod._wait(job, -3))
    assert r["status"] == "running" and time.time() - t0 < 1
    ev.set()
    assert run(server_mod._wait(job, 999)) == {"done": True}


# ---------------------------------------------------------------- .cdb tools (real worker process)

@pytest.fixture
def cdb_env(server_mod, settings, tmp_path, monkeypatch):
    write_hook_config(tmp_path, monkeypatch, {}, install=None, fake="build_frame")
    c = work(settings) / "frame.cdb"
    c.write_bytes(b"fake")
    return str(c)


def test_cdb_tools_through_worker(server_mod, cdb_env):
    s = server_mod
    ov = run(s.cdb_overview(cdb_env))
    assert ov["system"]["project"] == "FRAME TEST" and ov["cdb"] == cdb_env
    assert ov["sections"][0]["Iy_cm4"] == pytest.approx(3692.0)
    lcs = run(s.cdb_load_cases(cdb_env, "1-2"))
    assert [x["lc"] for x in lcs["rows"]] == [1, 2] and lcs["cdb"] == cdb_env
    assert run(s.cdb_nodes(cdb_env, "2"))["rows"][0]["x"] == 2.5
    nr = run(s.cdb_node_results(cdb_env, 1, nodes="3", include_coords=True))
    assert nr["rows"][0]["uz"] == -10.5 and nr["rows"][0]["z"] == 3.0
    sr = run(s.cdb_support_reactions(cdb_env, 1))
    assert sr["sum_kN"] == {"px": -2.5, "py": 0.0, "pz": 80.0}
    bf = run(s.cdb_beam_forces(cdb_env, 1, structural_lines="7", ends_only=True))
    assert bf["beams"] == 2 and bf["stations"] == 4 and bf["extremes"]["My"]["min"]["value"] == -30.0
    assert run(s.cdb_beam_forces(cdb_env, 1, groups="2"))["beams"] == 1
    assert run(s.cdb_beam_forces(cdb_env, 1, beams="1001", max_rows=1))["truncated"] is True
    assert run(s.cdb_truss_cable_forces(cdb_env, 1))["rows"][1]["N"] == -7.25
    assert run(s.cdb_truss_cable_forces(cdb_env, 2, element_type="cable"))["rows"][0]["N"] == 95.0
    env = run(s.cdb_envelope(cdb_env, "1-2", what="beam", groups="1"))
    assert env["overall"]["My"]["max"] == {"value": 50.0, "beam": 1002, "x": 4.0, "sln": 7, "group": 1, "lc": 2}
    assert run(s.cdb_envelope(cdb_env, "1-2", what="support"))["overall"]["pz"]["max"]["value"] == 100.0
    k = run(s.cdb_read_key(cdb_env, 12, 2001, class_name="CLC_EIGE", max_records=9999, skip=-4))
    assert k["records"][0]["m_nr_mode"] == 1 and k["records"][0]["m_rtex"] == "eigenmode 1"
    dat_path = cdb_env[:-4] + ".dat"
    assert run(s.cdb_overview(dat_path))["cdb"] == cdb_env                         # .dat -> .cdb


def test_cdb_tool_input_errors(server_mod, cdb_env, tmp_path):
    s = server_mod
    assert "element_type must be" in run(s.cdb_truss_cable_forces(cdb_env, 1, element_type="spring"))["error"]
    assert "what must be" in run(s.cdb_envelope(cdb_env, "1", what="quad"))["error"]
    assert "Cannot read number list" in run(s.cdb_node_results(cdb_env, 1, nodes="1-x"))["error"]
    assert "No node results for load case 77" in run(s.cdb_node_results(cdb_env, 77))["error"]
    assert "Give the .cdb file" in run(s.cdb_overview(cdb_env[:-4] + ".prt"))["error"]
    assert ".cdb not found" in run(s.cdb_overview(cdb_env[:-4] + "_x.cdb"))["error"]
    assert "outside the folders" in run(s.cdb_overview(str(tmp_path / "x.cdb")))["error"]


def test_cdb_interface_missing(server_mod, cdb_env, monkeypatch):
    info = dict(server_mod._test_info, dll=None)
    monkeypatch.setattr(server_mod, "_install", lambda s=None: info)
    r = run(server_mod.cdb_overview(cdb_env))
    assert "CDB interface not found" in r["error"] and r["sofistik"]["dll"] is None


def test_cdb_worker_crash_reported(server_mod, settings, tmp_path, monkeypatch):
    write_hook_config(tmp_path, monkeypatch, {}, install=None, fake="build_crash")
    c = work(settings) / "frame.cdb"
    c.write_bytes(b"fake")
    r = run(server_mod.cdb_overview(str(c)))
    assert "stopped without an answer (exit code 3)" in r["error"] and "access violation" in r["output"]


def test_cdb_worker_timeout(server_mod, cdb_env):
    r = server_mod._cdb_call("overview", cdb_env, {}, timeout_s=0.001)
    assert "took longer than" in r["error"]


def test_cdb_lock_sees_through_links(server_mod, settings, cdb_env, tmp_path):
    alias = tmp_path / "alias"
    try:
        os.symlink(str(work(settings)), str(alias), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    settings["read_folders"] = [str(alias)]
    first = run(server_mod.run_calculation(dat(settings, "frame.dat", "+PROG ASE\nEND\n$ FAKE sleep=6\n")))
    assert first["status"] == "running"
    r = run(server_mod.cdb_overview(str(alias / "frame.cdb")))
    assert "being calculated right now" in r.get("error", "")


# ---------------------------------------------------------------- manuals and examples

@pytest.fixture
def docs(server_mod, settings, tmp_path, monkeypatch):
    from test_docsearch import make_pdf

    from sofistik_mcp import docsearch
    idx = tmp_path / "idx.json.gz"
    with gzip.open(idx, "wt", encoding="utf-8") as g:
        json.dump({"manuals": {"ase_1.pdf": {"size": 1, "pages": ["ASE GRP group", "LTB here"]}}}, g)
    monkeypatch.setattr(docsearch, "SHIPPED_INDEX", str(idx))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    man = tmp_path / "man"
    man.mkdir()
    make_pdf(man / "talpa_1.pdf", ["TALPA tunnel", "GRP on page two"])
    ex = tmp_path / "ex"
    (ex / "talpa.dat" / "english").mkdir(parents=True)
    (ex / "talpa.dat" / "english" / "t.dat").write_text("!#!Info  Example: tunnel\nGRP 1\n")
    settings.update(manual_folders=[str(man)], examples_folders=[str(ex)])
    return man, ex


def test_manual_tools(server_mod, docs):
    s = server_mod
    lm = run(s.list_manuals())["manuals"]
    assert [(m["manual"], m["indexed"]) for m in lm] == [("ase_1.pdf", True), ("talpa_1.pdf", False)]
    assert run(s.search_manuals("GRP"))["hits"][0]["manual"] == "ase_1.pdf"
    assert run(s.index_manual("talpa_1.pdf")) == {"manual": "talpa_1.pdf", "pages": 2}
    hits = run(s.search_manuals("GRP", manuals=["talpa"]))["hits"]
    assert [(h["manual"], h["pdf_page"]) for h in hits] == [("talpa_1.pdf", 2)]
    assert run(s.read_manual_page("talpa_1", 1))["text"] == "TALPA tunnel"
    assert "not found" in run(s.index_manual("nope.pdf"))["error"]
    ex = run(s.search_examples("grp"))
    assert ex["hits"][0]["title"] == "tunnel" and ex["files_searched"] == 1


def test_settings_reloaded_on_every_call(server_mod, settings, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert "error" in run(server_mod.write_dat_file(str(other / "a.dat"), "x"))
    settings["work_folders"].append(str(other))
    assert run(server_mod.write_dat_file(str(other / "a.dat"), "x"))["written"]


def test_real_settings_function_reads_settings_json(monkeypatch, tmp_path):
    from sofistik_mcp import server
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"work_folders": [str(tmp_path)]}))
    monkeypatch.setattr(config, "SETTINGS_PATH", str(p))
    assert server._settings()["work_folders"] == [str(tmp_path)]
