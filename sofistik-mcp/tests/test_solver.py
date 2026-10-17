"""solver.py: the +SYS / #INCLUDE safety scan and running sps.exe (a fake one, tests/fake_sps.py)."""
from __future__ import annotations

import os
import threading
import time

import pytest

from sofistik_mcp import solver


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------- scan_dat: +SYS

@pytest.mark.parametrize("line", ["+SYS del *.*", "+sys dir", "   +SYS dir", "\t+ sys dir", "+Sys",
                                  "  +  SYS copy a b"])
def test_sys_detected(tmp_path, line):
    sc = solver.scan_dat(w(tmp_path / "m.dat", f"+PROG ASE\nEND\n{line}\n"))
    assert len(sc["sys_lines"]) == 1
    assert sc["sys_lines"][0] == {"file": str(tmp_path / "m.dat"), "line": 3, "text": line.strip()}


@pytest.mark.parametrize("line", ["$ +SYS dir", "! +SYS dir", "HEAD +SYS in a title", "+SYSTEM", "-SYS dir"])
def test_not_a_sys_line(tmp_path, line):
    assert solver.scan_dat(w(tmp_path / "m.dat", f"+PROG ASE\n{line}\n"))["sys_lines"] == []


def test_sys_crlf_file(tmp_path):
    p = tmp_path / "m.dat"
    p.write_bytes(b"+PROG ASE\r\nEND\r\n+SYS dir\r\n")
    sc = solver.scan_dat(str(p))
    assert sc["sys_lines"][0]["line"] == 3 and sc["sys_lines"][0]["text"] == "+SYS dir"


def test_sys_three_levels_of_includes(tmp_path):
    w(tmp_path / "m.dat", "+PROG ASE\n#include a\nEND\n")
    w(tmp_path / "a.dat", "$ level 1\n#INCLUDE b.dat\n")
    w(tmp_path / "b.dat", "$ level 2\n+APPLY c\n")
    w(tmp_path / "c.dat", "$ level 3\n\n   +sys rmdir /s x\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert sc["includes"] == [str(tmp_path / n) for n in ("a.dat", "b.dat", "c.dat")]
    assert sc["sys_lines"] == [{"file": str(tmp_path / "c.dat"), "line": 3, "text": "+sys rmdir /s x"}]
    assert sc["missing_includes"] == []


def test_too_deep_include_is_refused(tmp_path, sps):
    w(tmp_path / "m.dat", "+PROG ASE\n#include a\nEND\n")
    w(tmp_path / "a.dat", "#include b\n")
    w(tmp_path / "b.dat", "#include c\n")
    w(tmp_path / "c.dat", "#include d\n")
    w(tmp_path / "d.dat", "+SYS del *.*\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert sc["sys_lines"] or sc["missing_includes"]


def test_include_cycle_terminates(tmp_path):
    w(tmp_path / "m.dat", "+PROG ASE\n#include a\n")
    w(tmp_path / "a.dat", "#include m\n#include a\n+SYS x\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert len(sc["sys_lines"]) == 1
    assert sc["includes"] == [str(tmp_path / "a.dat"), str(tmp_path / "m.dat"), str(tmp_path / "a.dat")]


# ---------------------------------------------------------------- scan_dat: include names

@pytest.mark.parametrize("line, found", [
    ('#include "my inc.dat"', "my inc.dat"),
    ("#include 'my inc'", "my inc.dat"),
    ("#include inc $ comment after the name", "inc.dat"),
    ("#include inc ! comment", "inc.dat"),
    ("#include inc;", "inc.dat"),
    ("#include inc.dat   ", "inc.dat"),
    ("  +apply inc", "inc.dat"),
    ("#INCLUDE sub/inc2.dat", os.path.join("sub", "inc2.dat")),
])
def test_include_names(tmp_path, line, found):
    for n in ("my inc.dat", "inc.dat", os.path.join("sub", "inc2.dat")):
        w(tmp_path / n, "$ empty\n")
    sc = solver.scan_dat(w(tmp_path / "m.dat", f"+PROG ASE\n{line}\n"))
    assert sc["missing_includes"] == []
    assert [os.path.normpath(x) for x in sc["includes"]] == [os.path.join(str(tmp_path), found)]


def test_include_absolute_path(tmp_path):
    inc = w(tmp_path / "lib" / "loads.dat", "+SYS x\n")
    sc = solver.scan_dat(w(tmp_path / "m" / "m.dat", f"+PROG ASE\n#include {inc}\n"))
    assert sc["includes"] == [inc] and sc["sys_lines"][0]["file"] == inc


def test_include_relative_to_including_file(tmp_path):
    w(tmp_path / "m.dat", "+PROG ASE\n#include sub/a\n")
    w(tmp_path / "sub" / "a.dat", "#include b\n")
    w(tmp_path / "sub" / "b.dat", "+SYS x\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert sc["missing_includes"] == [] and len(sc["sys_lines"]) == 1


@pytest.mark.parametrize("line, name", [("#include $(dir)\\other.dat", "$(dir)\\other.dat"),
                                        ("#include nothere", "nothere"),
                                        ('#include "$(PROJECT)/loads.dat"', "$(PROJECT)/loads.dat")])
def test_missing_include_listed(tmp_path, line, name):
    sc = solver.scan_dat(w(tmp_path / "m.dat", f"+PROG ASE\n{line}\n"))
    assert sc["missing_includes"] == [name] and sc["includes"] == []


def test_empty_include_name_ignored(tmp_path):
    sc = solver.scan_dat(w(tmp_path / "m.dat", "+PROG ASE\n#include \"\"\n#include ''\n"))
    assert sc["missing_includes"] == [] and sc["includes"] == []
    # a bare comment after #include is taken as a file name and refused: safe side
    assert solver.scan_dat(w(tmp_path / "n.dat", "#include $ c\n"))["missing_includes"] == ["$ c"]


# ---------------------------------------------------------------- scan_dat: +PROG / urs

def test_programs_and_urs(tmp_path):
    w(tmp_path / "inc.dat", "+PROG ase urs:3\n")
    sc = solver.scan_dat(w(tmp_path / "m.dat",
                           "+PROG AQUA urs:1\nEND\n-PROG SOFIMSHA urs:2\nEND\n  +prog sofiload URS : 12 $ x\n"
                           "+ PROG RESULTS\n+PROG\n#include inc\n"))
    assert sc["programs"] == [
        {"program": "AQUA", "urs": 1, "file": "m.dat", "line": 1},
        {"program": "SOFILOAD", "urs": 12, "file": "m.dat", "line": 5},
        {"program": "RESULTS", "urs": None, "file": "m.dat", "line": 6},
        {"program": "ASE", "urs": 3, "file": "inc.dat", "line": 1}]


# ---------------------------------------------------------------- run(): refusals

def test_run_refusals(tmp_path, sps):
    assert "not found" in solver.run(str(tmp_path / "none.dat"), sps, 60)["reason"]
    txt = w(tmp_path / "m.txt", "+PROG ASE\n")
    assert solver.run(txt, sps, 60)["reason"] == "Only .dat files can be run."
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n")
    r = solver.run(dat, str(tmp_path / "no-sps.exe"), 60)
    assert r["status"] == "not run" and "sps.exe not found" in r["reason"] and "sofistik_dir" in r["reason"]
    assert solver.run(dat, "", 60)["status"] == "not run"
    assert not (tmp_path / "fake_sps_calls.txt").exists()


def test_run_refuses_sys_unless_allowed(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n#include inc\n")
    w(tmp_path / "inc.dat", "+SYS notepad\n")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "not run" and "+SYS" in r["reason"] and "allow_sys_commands" in r["reason"]
    assert r["sys_lines"][0]["file"] == str(tmp_path / "inc.dat")
    assert not (tmp_path / "fake_sps_calls.txt").exists()
    r = solver.run(dat, sps, 60, allow_sys=True)
    assert r["status"] == "ok" and (tmp_path / "fake_sps_calls.txt").exists()


def test_run_refuses_missing_include(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\n#include $(dir)\\other.dat\nEND\n")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "not run" and r["missing_includes"] == ["$(dir)\\other.dat"]
    assert "could not be found" in r["reason"] and "$(dir)\\other.dat" in r["reason"]
    assert not (tmp_path / "fake_sps_calls.txt").exists()


def test_run_refuses_no_active_prog(tmp_path, sps):
    r = solver.run(w(tmp_path / "m.dat", "-PROG ASE\nEND\n$ +PROG AQUA\n"), sps, 60)
    assert r["status"] == "not run" and "No active +PROG" in r["reason"]


# ---------------------------------------------------------------- run(): end to end with the fake sps

def calls(folder):
    p = folder / "fake_sps_calls.txt"
    return p.read_text().splitlines() if p.exists() else []


def test_run_ok(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG AQUA\nEND\n+PROG ASE urs:4\nLC 1\nEND\n$ FAKE print=hello_from_sps\n")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "ok" and r["errors"] == 0 and r["warnings"] == 0 and r["finished"] is True
    assert [p["program"] for p in r["programs"]] == ["aqua", "ase"]
    assert [p["program"] for p in r["programs_in_input"]] == ["AQUA", "ASE"]
    assert calls(tmp_path) == ["-B0 m.dat"]                         # one attempt, -B0 first
    assert r["exit_code"] == 0 and r["cdb_existed_before_run"] is False
    assert r["prt"] == str(tmp_path / "m.prt") and r["erg"] == str(tmp_path / "m.erg")
    assert set(r["files"]) == {"cdb", "prt", "erg", "plb"}
    assert all(f["updated_by_this_run"] for f in r["files"].values())
    assert r["files"]["cdb"]["path"] == str(tmp_path / "m.cdb") and r["files"]["cdb"]["size_kb"] == 0.1
    assert r["sps_console_tail"] == "hello from sps"
    assert r["dat"] == dat and r["command"].endswith("-B0 m.dat") and r["seconds"] < 30
    assert r["missing_includes"] == [] and "reason" not in r


def test_run_options(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE urs:4\nEND\n")
    r = solver.run(dat, sps, 60, continue_on_error=True, only_urs=4)
    assert calls(tmp_path) == ["-B0 -R -urs:4 m.dat"] and r["status"] == "ok"


def test_run_command_quotes_paths_with_spaces(tmp_path):
    import fake_sps
    sps = fake_sps.make(tmp_path / "Program Files" / "SOFiSTiK")
    dat = w(tmp_path / "my model" / "m.dat", "+PROG ASE\nEND\n")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "ok" and r["command"].startswith(f'"{sps}" ')


def test_run_warnings(tmp_path, sps):
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=warnings\n"), sps, 60)
    assert r["status"] == "ok with warnings" and r["warnings"] == 1 and r["errors"] == 0
    assert r["messages"] == [{"kind": "warning", "number": 2430, "program": "ase", "line": 6,
                              "text": "mass load case only converts nodal loads TIME NEEDED         0 SECONDS, "
                                      "TOTAL         0 SECONDS DATE       2026-10-14, 00:15:04"}]
    assert r["erg_messages"][0]["number"] == 2430
    assert r["erg_messages"][0]["input_before"][-1].strip() == "$ FAKE mode=warnings"


def test_run_errors(tmp_path, sps):
    dat = w(tmp_path / "m.dat",
            "+PROG AQB\nHEAD steel check\nBEAM 1 TYPE ULS\nEND\n$ FAKE mode=errors\n$ FAKE exit=1\n")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "errors" and r["errors"] == 1 and r["exit_code"] == 1
    assert r["messages"][0]["number"] == 10001 and r["messages"][0]["program"] == "aqb"
    assert any("PROGRAM ABORTED" in a["text"] for a in r["aborted"])
    em = r["erg_messages"][0]
    assert em["number"] == 10001 and "not found or erroneous" in em["text"]
    before = [x.strip() for x in em["input_before"]]
    assert "HEAD steel check" in before and "BEAM 1 TYPE ULS" in before


def test_run_unfinished_protocol_is_not_ok(tmp_path, sps, fast_clock):
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=unfinished\n"), sps, 60)
    assert r["status"] == "not finished" and r["finished"] is False


def test_run_waits_for_end_marker_written_late(tmp_path, sps):
    """sps.exe may return before the protocol's last line is on disk: run() waits for it (up to 15 s)."""
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=unfinished\n")
    prt = tmp_path / "m.prt"

    def finish_later():
        t_end = time.time() + 20
        while time.time() < t_end and not (prt.exists() and calls(tmp_path)):
            time.sleep(0.05)
        time.sleep(1.0)
        with open(prt, "a") as f:
            f.write("    +++++    0 errors and    0 warnings +++++\n   *** Stop : Program ase\n"
                    "   *** End of Calculation!\n")
    t = threading.Thread(target=finish_later)
    t.start()
    r = solver.run(dat, sps, 60)
    t.join()
    assert r["status"] == "ok" and r["finished"] is True and r["seconds"] < 10


def test_run_no_protocol_retries_once_then_says_so(tmp_path, sps, fast_clock):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=none\n")
    (tmp_path / "m.prt").write_text("*** End of Calculation!\n")      # stale protocol of an old run
    os.utime(tmp_path / "m.prt", (1, 1))
    r = solver.run(dat, sps, 60)
    assert calls(tmp_path) == ["-B0 m.dat", "m.dat -B0"]
    assert r["status"] == "no protocol" and "did not run" in r["reason"] and r["prt"] is None
    assert r["files"]["prt"]["updated_by_this_run"] is False


def test_run_retry_with_file_name_first(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE reject_options_first=1\n")
    r = solver.run(dat, sps, 60, continue_on_error=True)
    assert calls(tmp_path) == ["-B0 -R m.dat", "m.dat -B0 -R"]
    assert r["status"] == "ok" and r["command"].endswith("m.dat -B0 -R") and r["exit_code"] == 0


def test_run_old_cdb_not_updated(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE nocdb=1\n")
    for ext in ("cdb", "lst"):
        (tmp_path / f"m.{ext}").write_bytes(b"old" * 400)
        os.utime(tmp_path / f"m.{ext}", (1_000_000, 1_000_000))
    r = solver.run(dat, sps, 60)
    assert r["status"] == "ok" and r["cdb_existed_before_run"] is True
    assert r["files"]["cdb"]["updated_by_this_run"] is False and r["files"]["lst"]["updated_by_this_run"] is False
    assert r["files"]["cdb"]["size_kb"] == 1.2 and r["files"]["prt"]["updated_by_this_run"] is True


def test_run_existing_cdb_replaced(tmp_path, sps):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n")
    (tmp_path / "m.cdb").write_bytes(b"old")
    os.utime(tmp_path / "m.cdb", (1_000_000, 1_000_000))
    r = solver.run(dat, sps, 60)
    assert r["cdb_existed_before_run"] is True and r["files"]["cdb"]["updated_by_this_run"] is True


def test_run_timeout_kills(tmp_path, sps):
    procs = []
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n")
    t0 = time.time()
    r = solver.run(dat, sps, 1.5, on_start=procs.append)
    assert time.time() - t0 < 30
    assert r["status"] == "timed out" and r["exit_code"] is None and "killed" in r["reason"]
    assert "run_timeout_minutes" in r["reason"]
    assert len(procs) == 1 and procs[0].poll() is not None          # no retry, process gone
    assert calls(tmp_path) == ["-B0 m.dat"] and not (tmp_path / "m.prt").exists()


def test_run_stop(tmp_path, sps):
    procs, flag = [], {"stop": False}
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n")
    out = {}
    th = threading.Thread(target=lambda: out.update(r=solver.run(dat, sps, 120, on_start=procs.append,
                                                                 stopped=lambda: flag["stop"])))
    t0 = time.time()
    th.start()
    while not calls(tmp_path) and time.time() - t0 < 20:
        time.sleep(0.05)
    assert procs, "sps did not start"
    flag["stop"] = True
    solver._kill_tree(procs[0])
    th.join(30)
    r = out["r"]
    assert r["status"] == "stopped" and "stopped on request" in r["reason"]
    assert time.time() - t0 < 30 and len(procs) == 1 and procs[0].poll() is not None
    assert not (tmp_path / "m.prt").exists()


def test_kill_tree_tolerates_dead_process(tmp_path, sps):
    import subprocess
    import sys
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    solver._kill_tree(p)                                     # must not raise
    assert p.poll() == 0
