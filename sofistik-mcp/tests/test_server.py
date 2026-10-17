"""Tests that run without SOFiSTiK (Linux CI / cloud).  python -m pytest tests"""
from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import textwrap

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from sofistik_mcp import config, messages, results, solver  # noqa: E402
import fake_cdb  # noqa: E402

D = fake_cdb.daten


# ---------------------------------------------------------------- messages (real files from Wing's PC)

def test_parse_real_error_prt():
    r = messages.summarize_run(os.path.join(HERE, "sample_error.prt"), os.path.join(HERE, "sample_error.erg"))
    assert r["status"] == "errors"
    assert r["errors"] == 1 and r["warnings"] == 0
    m = r["messages"][0]
    assert m["kind"] == "error" and m["number"] == 10001 and m["program"] == "aqb"
    assert "not found or erroneous" in m["text"]
    assert r["finished"] is True
    assert any("PROGRAM ABORTED" in a["text"] for a in r["aborted"])
    assert r["programs"][0]["program"] == "aqb" and r["programs"][0]["errors"] == 1
    assert r["erg_messages"][0]["number"] == 10001


def test_parse_long_form_and_ok():
    txt = textwrap.dedent("""\
        *** Start: Program Calculation - Version 2027-0.0.139
        *** Start: Program ASE
        ++++ WARNING NO. 2430 IN PROGRAM ASE
        mass load case only converts nodal loads
         +++++    0 errors and    1 warnings +++++
        *** Stop : Program ASE
        *** End of Calculation!
        """)
    p = messages.parse_protocol(txt)
    assert p["warnings"] == 1 and p["errors"] == 0
    assert p["messages"][0]["program"] == "ASE" and p["messages"][0]["number"] == 2430
    assert p["finished"]


def test_read_text_strips_nul_and_cp1252(tmp_path):
    f = tmp_path / "a.dat"
    f.write_bytes(b"HEAD Tr\xe4ger\r\n\x00END\r\n")
    assert messages.read_text(str(f)) == "HEAD Tr\u00e4ger\nEND\n"


# ---------------------------------------------------------------- config / access rules

def test_access_rules(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    s = config.load_settings(str(tmp_path / "missing.json"))
    s["work_folders"] = [str(work)]
    s["read_folders"] = []
    s["examples_folders"] = []
    s["manual_folders"] = []
    assert config.check_write(str(work / "a.dat"), s)
    with pytest.raises(config.AccessError):
        config.check_write(str(work / ".." / "evil.dat"), s)
    with pytest.raises(config.AccessError):
        config.check_read(str(tmp_path / "other.cdb"), s)
    # a folder whose name only starts like the work folder is not inside it
    with pytest.raises(config.AccessError):
        config.check_write(str(tmp_path / "work2" / "a.dat"), s)


def test_settings_comments_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"_help": "x", "work_folders": "C:\\a", "run_timeout_minutes": "bad"}))
    s = config.load_settings(str(p))
    assert s["work_folders"] == ["C:\\a"] and s["run_timeout_minutes"] == 60.0 and "_help" not in s


def test_default_settings_file_valid():
    s = config.load_settings(os.path.join(ROOT, "settings.default.json"))
    assert s["work_folders"] == [r"C:\Sofistik workflow"] and s["allow_sys_commands"] is False


# ---------------------------------------------------------------- dat scanning / solver

def test_scan_sys_and_includes(tmp_path):
    (tmp_path / "inc.dat").write_text("+sys del *.*\n")
    (tmp_path / "m.dat").write_text("+PROG AQUA urs:1\nEND\n-PROG ASE\n#include inc\n$ +SYS in comment? no\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert [p["program"] for p in sc["programs"]] == ["AQUA"]
    assert sc["programs"][0]["urs"] == 1
    assert len(sc["sys_lines"]) == 1 and sc["sys_lines"][0]["text"] == "+sys del *.*"


def _fake_sps(tmp_path, body):
    sps = tmp_path / "sps.exe"
    sps.write_text("#!" + sys.executable + "\n" + body)
    sps.chmod(sps.stat().st_mode | stat.S_IEXEC)
    return str(sps)


FAKE_OK = r'''
import sys, os
name = sys.argv[-1]
stem = os.path.splitext(name)[0]
open("args.txt", "w").write(" ".join(sys.argv[1:]))
open(stem + ".prt", "w").write("""   *** Start: Program Calculation - Version 2027-0.0.139
   *** Start: Program ASE
   +++++ warning no. 77
   something to look at
    +++++    0 errors and    1 warnings +++++
   *** Stop : Program ASE
   *** End of Calculation!
""")
open(stem + ".cdb", "wb").write(b"x")
'''


def test_run_ok(tmp_path):
    sps = _fake_sps(tmp_path, FAKE_OK)
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE urs:4\nLC 1\nEND\n")
    r = solver.run(str(dat), sps, 60, continue_on_error=True, only_urs=4)
    assert r["status"] == "ok with warnings", r
    assert r["warnings"] == 1 and r["files"]["cdb"]["updated_by_this_run"]
    assert (tmp_path / "args.txt").read_text() == "-B0 -R -urs:4 m.dat"


def test_run_refuses_sys(tmp_path):
    sps = _fake_sps(tmp_path, FAKE_OK)
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE\nEND\n+SYS notepad\n")
    r = solver.run(str(dat), sps, 60)
    assert r["status"] == "not run" and "+SYS" in r["reason"]
    assert not (tmp_path / "args.txt").exists()


def test_run_no_protocol(tmp_path):
    sps = _fake_sps(tmp_path, "import sys\n")
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE\nEND\n")
    (tmp_path / "m.prt").write_text("*** End of Calculation!\n")      # stale protocol from an old run
    os.utime(tmp_path / "m.prt", (1, 1))
    r = solver.run(str(dat), sps, 60)
    assert r["status"] == "no protocol" and "did not run" in r["reason"]


def test_run_timeout(tmp_path):
    sps = _fake_sps(tmp_path, "import time\ntime.sleep(30)\n")
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE\nEND\n")
    r = solver.run(str(dat), sps, 1)
    assert r["status"] == "timed out"


# ---------------------------------------------------------------- results (fake cdb)

def test_overview():
    c = fake_cdb.FakeCdb()
    ov = results.overview(c, D)
    assert ov["system"]["project"] == "SELFTEST"
    assert ov["element_counts"]["nodes"] == 7 and ov["element_counts"]["beams"] == 6
    s = ov["sections"][0]
    assert s["title"] == "HEA 200" and s["A_cm2"] == pytest.approx(53.8) and s["Iy_cm4"] == pytest.approx(3692, rel=1e-6)
    lc = {x["lc"]: x for x in ov["load_cases"]}
    assert lc[1]["title"] == "self-test tip load 1 kN" and lc[1]["sum_reactions_kN"][2] == pytest.approx(1.0)
    assert set(lc[1]["has_results"]) == {"nodes", "beams", "trusses"}
    assert lc[2001]["kind"] == 4 and lc[2001]["frequency_Hz"] == pytest.approx(2.5, rel=1e-5)


def test_node_results_units():
    c = fake_cdb.FakeCdb()
    r = results.node_results(c, D, 1, ids="7", include_coords=True)
    expect_mm = 1.0 * 6 ** 3 / (3 * 2.1e8 * 3692e-8) * 1000
    assert r["rows"][0]["uz"] == pytest.approx(expect_mm, rel=1e-4)
    assert r["rows"][0]["x"] == pytest.approx(6.0)
    assert r["extremes"]["uz"]["max"]["node"] == 7


def test_support_reactions():
    c = fake_cdb.FakeCdb()
    r = results.support_reactions(c, D, 1)
    assert [x["node"] for x in r["rows"]] == [1]
    assert r["sum_kN"]["pz"] == pytest.approx(1.0) and r["rows"][0]["my"] == pytest.approx(6.0)
    assert r["sum_stored_by_sofistik_kN"][2] == pytest.approx(1.0)


def test_beam_forces_filters_and_undefined():
    c = fake_cdb.FakeCdb()
    r = results.beam_forces(c, D, 1)
    assert r["beams"] == 6 and r["stations"] == 18
    assert r["extremes"]["My"]["min"]["value"] == pytest.approx(-6.0)
    assert r["extremes"]["My"]["min"]["beam"] == 1 and r["extremes"]["My"]["min"]["x"] == 0.0
    assert r["rows"][0]["Mz"] is None                     # 1e35 = undefined
    assert results.beam_forces(c, D, 1, beams="2-3")["beams"] == 2
    assert results.beam_forces(c, D, 1, groups_="0")["beams"] == 6
    assert results.beam_forces(c, D, 1, groups_="5")["beams"] == 0
    assert results.beam_forces(c, D, 1, ends_only=True)["stations"] == 12


def test_missing_lc_message():
    c = fake_cdb.FakeCdb()
    assert "No beam results for load case 99" in results.beam_forces(c, D, 99)["error"]


def test_envelope():
    c = fake_cdb.FakeCdb()
    r = results.envelope(c, D, "1-3", what="beam")
    assert r["load_cases_found"] == [1] and r["load_cases_missing"] == [2, 3]
    assert r["overall"]["My"]["min"]["lc"] == 1


def test_axial_and_read_key():
    c = fake_cdb.FakeCdb()
    assert results.axial_forces(c, D, 1, "truss")["rows"][0]["N"] == pytest.approx(12.5)
    k = results.read_key(c, D, 1, 1, class_name="CMAT_STEE")
    assert any(x["m_emod"] == pytest.approx(2.1e8) for x in k["records"])
    k2 = results.read_key(c, D, 9, 1)
    assert k2["record_count"] == 2 and "ints" in k2["records"][0]


def test_parse_ids():
    assert results.parse_ids("1-3, 7;10") == {1, 2, 3, 7, 10}
    assert results.parse_ids(None) is None
    with pytest.raises(ValueError):
        results.parse_ids("abc")


# ---------------------------------------------------------------- worker + MCP protocol

def test_worker_handle(monkeypatch, tmp_path):
    from sofistik_mcp import cdb_worker, cdbio
    monkeypatch.setattr(cdbio, "Cdb", lambda path, info: fake_cdb.FakeCdb())
    req = {"op": "beam_forces", "cdb": "x.cdb", "info": {"daten": fake_cdb.DATEN_PATH}, "args": {"lc": 1}}
    a = cdb_worker.handle(req)
    assert a["ok"] and a["result"]["beams"] == 6
    json.dumps(a)                                          # must be JSON-serialisable


def test_mcp_stdio_lists_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=[os.path.join(ROOT, "run_server.py")])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = [t.name for t in (await s.list_tools()).tools]
                st = await s.call_tool("sofistik_status", {})
                srch = await s.call_tool("search_manuals", {"query": "LTB", "manuals": ["bdk"]})
                bad = await s.call_tool("write_dat_file", {"path": "/etc/x.dat", "content": "x"})
                return names, st, srch, bad

    names, st, srch, bad = asyncio.run(go())
    for n in ("run_calculation", "write_dat_file", "cdb_beam_forces", "cdb_envelope", "search_examples"):
        assert n in names
    assert not st.isError
    hits = json.loads(srch.content[0].text)
    assert hits["hits"] and hits["hits"][0]["manual"] == "bdk_1.pdf"
    assert "outside the work folders" in bad.content[0].text


# ---------------------------------------------------------------- review fixes

def test_run_refuses_missing_include(tmp_path):
    sps = _fake_sps(tmp_path, FAKE_OK)
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE\n#include $(dir)\\other.dat\nEND\n")
    r = solver.run(str(dat), sps, 60)
    assert r["status"] == "not run" and "could not be found" in r["reason"]


def test_run_retries_option_order(tmp_path):
    # a fake sps that only accepts the file name first
    body = FAKE_OK.replace("name = sys.argv[-1]", "name = sys.argv[1]\nif name.startswith('-'): sys.exit(3)")
    sps = _fake_sps(tmp_path, body)
    dat = tmp_path / "m.dat"
    dat.write_text("+PROG ASE\nEND\n")
    r = solver.run(str(dat), sps, 60)
    assert r["status"] == "ok with warnings" and r["command"].endswith("m.dat -B0")


def test_bad_settings_json_message(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"work_folders": ["D:\\26016"]}')
    with pytest.raises(config.SettingsError) as e:
        config.load_settings(str(p))
    assert "double backslashes" in str(e.value) and "line 1" in str(e.value)


def test_sln_filter_warns_when_nothing_matches():
    c = fake_cdb.FakeCdb()
    r = results.beam_forces(c, D, 1, slns="7")
    assert r["beams"] == 0 and "none (m_nref is 0" in r["warning"] and "sln_note" in r


def test_envelope_forgets_records():
    class Forgetful(fake_cdb.FakeCdb):
        forgotten = []

        def forget(self, kwh, kwl):
            self.forgotten.append((kwh, kwl))
    c = Forgetful()
    results.envelope(c, D, "1", what="beam")
    assert (102, 1) in c.forgotten


def test_examples_only_shipped_folders(tmp_path):
    from sofistik_mcp import docsearch
    (tmp_path / "ase.dat" / "english").mkdir(parents=True)
    (tmp_path / "ase.dat" / "english" / "ex.dat").write_text("!#!Info  Example: frame\nSYST PROB TH2\n")
    (tmp_path / "wind-loads").mkdir()
    (tmp_path / "wind-loads" / "mine.dat").write_text("SYST PROB TH2\n")
    (tmp_path / "top.dat").write_text("SYST PROB TH2\n")
    r = docsearch.Examples([str(tmp_path)]).search("prob th2")
    assert [h["file"] for h in r["hits"]] == [str(tmp_path / "ase.dat" / "english" / "ex.dat")]
    assert r["hits"][0]["title"] == "frame"


def test_server_job_flow(monkeypatch, tmp_path):
    """A slow calculation answers 'running' with a job id; get_job_result returns the summary."""
    from sofistik_mcp import server
    work = tmp_path / "work"
    work.mkdir()
    sps = _fake_sps(tmp_path, "import time\ntime.sleep(3)\n" + FAKE_OK)
    s = config.load_settings(str(tmp_path / "none.json"))
    s.update(work_folders=[str(work)], read_folders=[], examples_folders=[], manual_folders=[])
    monkeypatch.setattr(server, "_settings", lambda: s)
    monkeypatch.setattr(server, "_install", lambda settings=None: {"sps": sps, "root": None})
    monkeypatch.setattr(server, "WAIT_S", 0.5)
    (work / "m.dat").write_text("+PROG ASE\nEND\n")

    async def go():
        first = await server.run_calculation(str(work / "m.dat"))
        busy = await server.run_calculation(str(work / "m.dat"))
        locked = server._cdb_call("overview", str(work / "m.cdb"), {})
        done = await server.get_job_result(first["job_id"], 20)
        return first, busy, locked, done

    first, busy, locked, done = asyncio.run(go())
    assert first["status"] == "running" and first["job_id"].startswith("calc-")
    assert busy["status"] == "not run" and "still running" in busy["reason"]
    assert "being calculated right now" in locked["error"]
    assert done["status"] == "ok with warnings"


def test_write_refuses_server_folder():
    from sofistik_mcp import server
    s = config.load_settings(os.path.join(ROOT, "settings.default.json"))
    s["work_folders"] = [ROOT]

    async def go():
        server_settings = server._settings
        server._settings = lambda: s
        try:
            return await server.write_dat_file(os.path.join(ROOT, "selftest", "x.dat"), "END")
        finally:
            server._settings = server_settings
    assert "server's own folder" in asyncio.run(go())["error"]
