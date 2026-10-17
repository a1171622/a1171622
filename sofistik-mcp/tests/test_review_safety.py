"""Security / robustness review fixes (threat model: the model calling the tools can be steered by
untrusted content).  Each test failed before its fix.  Windows-only parts run on windows-latest in CI
and are skipped elsewhere with the reason."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest
from conftest import ROOT, run, write_hook_config

from sofistik_mcp import config, configure_clients, messages, solver

WINDOWS = sys.platform == "win32"


def w(path, text, encoding="utf-8"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return str(path)


def sys_whys(path, **kw):
    return [x["why"] for x in solver.scan_dat(str(path), **kw)["sys_lines"]]


def calls(folder):
    p = folder / "fake_sps_calls.txt"
    return p.read_text().splitlines() if p.exists() else []


# ================================================================ 1. +SYS guard

@pytest.mark.parametrize("line", [
    "*SYS del *.*",                     # runs if the last PROG was active (cadinp_1 1.9.7)
    "* sys dir",
    "\ufeff+SYS calc.exe",              # BOM on a later line (decoded text keeps it)
    "\u00a0+SYS calc.exe",              # NBSP
    "\v+SYS calc.exe",
    "\u200b+SYS calc.exe",              # zero-width space
    "\u3000+SYS calc.exe",              # ideographic space
    "\uff0bSYS calc.exe",               # fullwidth plus (NFKC)
    "LET#1 1 ; +SYS calc.exe",          # ; starts a new record
    "SYS calc.exe",                     # bare SYS word
    "+SYSTEM calc.exe",
])
def test_sys_variants_flagged(tmp_path, line):
    p = w(tmp_path / "m.dat", f"+PROG AQUA\nEND\n{line}\n")
    sc = solver.scan_dat(p)
    assert [x["line"] for x in sc["sys_lines"]] == [3], sc


def test_bom_at_file_start_is_ignored_for_the_check(tmp_path):
    p = tmp_path / "m.dat"
    p.write_bytes(b"\xef\xbb\xbf+SYS calc.exe\r\n+PROG AQUA\r\nEND\r\n")
    sc = solver.scan_dat(str(p))
    assert sc["sys_lines"][0]["line"] == 1 and sc["sys_lines"][0]["text"] == "+SYS calc.exe"


def test_form_feed_splits_lines(tmp_path):
    p = tmp_path / "m.dat"
    p.write_bytes(b"+PROG AQUA\fEND\f+SYS calc\n")
    assert solver.scan_dat(str(p))["sys_lines"]


@pytest.mark.parametrize("text", [
    "#define X=+SYS\n+PROG AQUA\nEND\n$(X) calc.exe\n",
    "#DEFINE S = sys\n+PROG AQUA\nEND\n+$(S) calc.exe\n",
    "#define A=+S\n#define B=YS\n+PROG AQUA\nEND\n$(A)$(B) calc.exe\n",     # no SYS in any one value
    "+PROG AQUA\nEND\n$(UNDEFINED_SOMEWHERE) calc\n",                           # could come from SOFISTIK.DEF
    "#define N=12\n#define N=+SYS\n+PROG AQUA\n$(N) x\n",                        # one of two definitions
    "#define N=1\n+PROG AQUA\n$(N)SYS x\n",
    "$BLOCK SET X=+SYS calc\n+PROG AQUA\nEND\n",
])
def test_substitution_that_can_build_sys_is_flagged(tmp_path, text):
    assert solver.scan_dat(w(tmp_path / "m.dat", text))["sys_lines"]


def test_numeric_substitution_at_line_start_is_fine(tmp_path):
    # a table row built from a numeric #define, as in the shipped examples
    text = ("#define NRQ =  91\n#define DH = ($(NRQ)*2) $ comment with words\n+PROG AQUA\n"
            "    $(NRQ)   1     2\n $(DH) 3\nEND\n")
    assert solver.scan_dat(w(tmp_path / "m.dat", text))["sys_lines"] == []


def test_sys_inside_define_block_is_flagged(tmp_path):
    text = "#define B\n+SYS calc\n#enddef\n+PROG AQUA\n#include B\nEND\n"
    sc = solver.scan_dat(w(tmp_path / "m.dat", text))
    assert len(sc["sys_lines"]) == 1 and sc["missing_includes"] == []


def test_prog_with_a_path_as_program_name_is_flagged(tmp_path):
    assert sys_whys(w(tmp_path / "m.dat", "+PROG ..\\..\\evil\nEND\n")) == [
        "PROG with a program name that is not a plain name"]
    assert sys_whys(w(tmp_path / "n.dat", "+PROG $(P)\nEND\n"))


@pytest.mark.parametrize("line", ["$ +SYS dir", "! +SYS dir", "// +SYS dir", "HEAD +SYS in a title",
                                  "-SYS dir", "SYST GIRD", "TXA System of units", "#include sys_loads"])
def test_sys_rule_does_not_flag_ordinary_lines(tmp_path, line):
    w(tmp_path / "sys_loads.dat", "$ loads\n")
    assert solver.scan_dat(w(tmp_path / "m.dat", f"+PROG ASE\n{line}\nEND\n"))["sys_lines"] == []


def test_refusal_message_names_the_setting(tmp_path, sps):
    r = solver.run(w(tmp_path / "m.dat", "+PROG AQUA\nEND\n*SYS calc\n"), sps, 60)
    assert r["status"] == "not run" and "allow_sys_commands" in r["reason"] and "*SYS" in r["reason"]
    assert calls(tmp_path) == []


# ================================================================ 2. includes

def test_every_candidate_is_scanned(tmp_path):
    # SPS may take b next to the including file or next to the main .dat: both are checked
    w(tmp_path / "m.dat", "+PROG ASE\n#include sub/a\nEND\n")
    w(tmp_path / "sub" / "a.dat", "#include b\n")
    w(tmp_path / "sub" / "b.dat", "$ harmless\n")
    w(tmp_path / "b.dat", "+SYS calc\n")
    sc = solver.scan_dat(str(tmp_path / "m.dat"))
    assert sorted(os.path.normpath(x) for x in sc["includes"]) == sorted(
        os.path.normpath(str(x)) for x in (tmp_path / "sub" / "a.dat", tmp_path / "sub" / "b.dat",
                                           tmp_path / "b.dat"))
    assert [x["file"] for x in sc["sys_lines"]] == [os.path.join(str(tmp_path), "b.dat")]


def test_name_and_name_dat_both_scanned(tmp_path):
    w(tmp_path / "inc", "$ no extension\n")
    w(tmp_path / "inc.dat", "+SYS calc\n")
    sc = solver.scan_dat(w(tmp_path / "m.dat", "+PROG ASE\n#include inc\n"))
    assert len(sc["includes"]) == 2 and len(sc["sys_lines"]) == 1


def test_include_of_in_memory_block(tmp_path):
    text = "#define SECT\nPOLY UPZ\n#enddef\n+PROG AQUA\n#include sect\n#INCLUDE SECT\nEND\n"
    sc = solver.scan_dat(w(tmp_path / "m.dat", text))
    assert sc["missing_includes"] == [] and sc["sys_lines"] == []
    sc = solver.scan_dat(w(tmp_path / "n.dat", text.replace("#include sect", "#undef sect\n#include sect")))
    assert sc["missing_includes"] == ["sect", "SECT"]


def test_dollar_name_is_the_dat_stem(tmp_path):
    p = w(tmp_path / "bridge.dat", '+PROG CSM\nEND\n+APPLY "$(NAME)_csm.dat" $ contains +PROG\n+PROG ASE\nEND\n')
    assert solver.scan_dat(p)["missing_includes"] == ["$(NAME)_csm.dat (= bridge_csm.dat)"]
    w(tmp_path / "bridge_csm.dat", "+PROG ASE\n+SYS calc\nEND\n")
    sc = solver.scan_dat(p)
    assert sc["missing_includes"] == [] and sc["sys_lines"][0]["file"] == str(tmp_path / "bridge_csm.dat")


@pytest.mark.parametrize("text", ['+APPLY "$(PROJECT).dat"\n', "#define NAME=x\n#include $(NAME)\n",
                                  "#include C:relative.dat\n"])
def test_unresolvable_include_stays_missing(tmp_path, text):
    w(tmp_path / "x.dat", "$ x\n")
    w(tmp_path / "m.dat.dat", "$ x\n")
    assert solver.scan_dat(w(tmp_path / "m.dat", "+PROG ASE\n" + text))["missing_includes"]


def test_unsigned_apply_and_abbreviated_include_are_followed(tmp_path):
    w(tmp_path / "evil.dat", "+SYS calc\n")
    for t in ("APPLY evil.dat\n", "#INCL evil.dat\n", "+ apply evil\n"):
        assert solver.scan_dat(w(tmp_path / "m.dat", "+PROG AQUA\nEND\n" + t))["sys_lines"], t


def test_include_outside_readable_folders_is_refused_even_with_allow_sys(tmp_path, sps):
    secret = w(tmp_path / "private" / "secret.dat", "$ the engineer's private notes\n+SYS whoami\n")
    work = tmp_path / "work"
    dat = w(work / "m.dat", f"+PROG ASE\n#include {secret}\nEND\n")
    sc = solver.scan_dat(dat, readable=[str(work)])
    assert sc["blocked_includes"][0]["kind"] == "outside" and sc["sys_lines"] == []      # not even read
    assert secret not in sc["hashes"]
    r = solver.run(dat, sps, 60, allow_sys=True, readable=[str(work)])
    assert r["status"] == "not run" and "outside the folders" in r["reason"] and calls(work) == []
    assert solver.scan_dat(dat, readable=[str(work), str(tmp_path / "private")])["blocked_includes"] == []


def test_file_bigger_than_the_read_limit_is_refused(tmp_path, sps, monkeypatch):
    w(tmp_path / "inc.dat", "$ " + "x" * 400 + "\n+SYS calc\n")
    dat = w(tmp_path / "m.dat", "+PROG ASE\n#include inc\nEND\n")
    sc = solver.scan_dat(dat, max_bytes=300)
    assert sc["blocked_includes"][0]["kind"] == "unscannable" and "too big" in sc["blocked_includes"][0]["why"]
    monkeypatch.setattr(solver, "SCAN_MAX_BYTES", 300)
    r = solver.run(dat, sps, 60)
    assert r["status"] == "not run" and "too big" in r["reason"] and calls(tmp_path) == []
    monkeypatch.setattr(solver, "SCAN_MAX_BYTES", 10)                      # the main .dat itself
    assert solver.run(dat, sps, 60)["status"] == "not run"


def test_include_that_is_a_folder_is_refused(tmp_path, sps):
    (tmp_path / "loads").mkdir()
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\n#include loads\nEND\n"), sps, 60)
    assert r["status"] == "not run" and "folder" in r["reason"]


def test_prog_without_plus_is_a_program(tmp_path, sps):
    p = w(tmp_path / "m.dat", "PROG AQUA\nEND\n  prog ase urs:2\nEND\n-PROG SOFIMSHA\n$PROG X\n")
    assert [(x["program"], x["urs"]) for x in solver.scan_dat(p)["programs"]] == [("AQUA", None), ("ASE", 2)]
    assert solver.run(p, sps, 60)["status"] == "ok"


# ================================================================ 3. TOCTOU

def test_input_changed_during_run_is_reported(tmp_path, sps):
    inc = w(tmp_path / "inc.dat", "$ harmless\n")
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n+APPLY inc.dat\n")

    def swap(proc):
        with open(inc, "w") as f:
            f.write("+SYS calc.exe\n")
    r = solver.run(dat, sps, 60, on_start=swap)
    assert r["status"] == "check: input changed during run" and r["changed_during_run"] == [inc]
    assert any("changed while the calculation ran" in x for x in r["server_warnings"])


def test_write_refused_while_a_calculation_runs(server_mod, settings):
    work = settings["work_folders"][0]
    first = run(server_mod.run_calculation(w_dat(work, "slow.dat", "+PROG ASE\nEND\n$ FAKE sleep=5\n")))
    assert first["status"] == "running"
    r = run(server_mod.write_dat_file(os.path.join(work, "inc.dat"), "+PROG ASE\nEND\n"))
    assert "calculation is running" in r["error"] and not os.path.exists(os.path.join(work, "inc.dat"))
    assert run(server_mod.get_job_result(first["job_id"], 30))["status"] == "ok"
    assert "written" in run(server_mod.write_dat_file(os.path.join(work, "inc.dat"), "+PROG ASE\nEND\n"))


def w_dat(folder, name, text):
    p = os.path.join(folder, name)
    with open(p, "w") as f:
        f.write(text)
    return p


# ================================================================ 4. write_dat_file

def test_write_uses_defines_from_existing_includes(server_mod, settings):
    work = settings["work_folders"][0]
    assert "written" in run(server_mod.write_dat_file(os.path.join(work, "defs.dat"), "#define NRQ = 91\n"))
    p = os.path.join(work, "m.dat")
    body = "+PROG AQUA\n  $(NRQ) 1 2\nEND\n"
    assert "allow_sys_commands" in run(server_mod.write_dat_file(p, body))["error"]       # NRQ unknown
    assert "written" in run(server_mod.write_dat_file(p, "#include defs\n" + body))
    r = run(server_mod.write_dat_file(os.path.join(work, "n.dat"), "#include m\n+PROG AQUA\nEND\n"))
    assert "written" in r
    with open(os.path.join(work, "evil.dat"), "w") as f:
        f.write("+SYS calc\n")                                  # planted by hand, not by the server
    r = run(server_mod.write_dat_file(os.path.join(work, "x.dat"), "+PROG AQUA\n#include evil\nEND\n"))
    assert r["sys_lines"][0]["file"].endswith("evil.dat")


def test_write_refuses_sys_content_unless_allowed(server_mod, settings):
    p = os.path.join(settings["work_folders"][0], "m.dat")
    r = run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n*SYS calc.exe\n"))
    assert "allow_sys_commands" in r["error"] and r["sys_lines"][0]["line"] == 3 and not os.path.exists(p)
    settings["allow_sys_commands"] = True
    assert run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n*SYS calc.exe\n"))["written"] == p


@pytest.mark.parametrize("name, why", [
    ("m.dat:hidden.dat", "':'"), ("sub./m.dat", "ends with a dot"), ("sub /m.dat", "ends with a dot or a space"),
    ("CON.dat", "reserved"), ("nul.dat", "reserved"), ("Com1.dat", "reserved"), ("lpt9.x.dat", "reserved"),
    ("aux .dat", "reserved"), ("-B0.dat", "start with '-'"), ("a|b.dat", "does not allow"),
    ("COM\u00b9.dat", "reserved")])
def test_write_refuses_bad_windows_names(server_mod, settings, name, why):
    p = os.path.join(settings["work_folders"][0], name)
    r = run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n"))
    assert why in r["error"], r
    assert sorted(os.listdir(settings["work_folders"][0])) == []


def test_bad_file_name_rules():
    assert config.bad_file_name(r"C:\work\m.dat") is None
    assert config.bad_file_name(r"\\server\share\m.dat") is None
    assert config.bad_file_name(r"C:\work\..\work\m.dat") is None
    assert config.bad_file_name(r"C:\work\CONSOLE.dat") is None and config.bad_file_name(r"C:\w\COM10.dat") is None
    assert "device paths" in config.bad_file_name("\\\\?\\C:\\work\\m.dat")
    assert "':'" in config.bad_file_name(r"C:\work\m.dat::$DATA")


def test_run_refuses_a_name_starting_with_dash(tmp_path, sps):
    r = solver.run(w(tmp_path / "-R.dat", "+PROG ASE\nEND\n"), sps, 60)
    assert r["status"] == "not run" and "'-'" in r["reason"] and calls(tmp_path) == []


def test_failed_write_keeps_the_original(server_mod, settings):
    work = settings["work_folders"][0]
    p = os.path.join(work, "a.dat")
    run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n"))
    r = run(server_mod.write_dat_file(p, "x\ud800", overwrite=True))              # lone surrogate
    assert "cannot be saved as UTF-8" in r["error"]
    with open(p, "rb") as f:
        assert f.read() == b"+PROG AQUA\r\nEND\r\n"
    assert os.listdir(work) == ["a.dat"]                                           # no backup, no temp file


def test_write_failing_at_replace_keeps_the_original(server_mod, settings, monkeypatch):
    work = settings["work_folders"][0]
    p = os.path.join(work, "a.dat")
    run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n"))

    def boom(a, b):
        raise OSError("disk full")
    monkeypatch.setattr(server_mod.os, "replace", boom)
    with pytest.raises(OSError):
        run(server_mod.write_dat_file(p, "+PROG ASE\nEND\n", overwrite=True))
    monkeypatch.undo()
    with open(p, "rb") as f:
        assert f.read() == b"+PROG AQUA\r\nEND\r\n"
    assert not [n for n in os.listdir(work) if n.endswith(".tmp")]


# ================================================================ 5. orphaned sps.exe and lock files

HELPER = textwrap.dedent("""\
    import os, sys, threading, time
    sys.path.insert(0, sys.argv[1])
    from sofistik_mcp import solver
    pidfile = sys.argv[2]
    child = "import os, time; open(%r, 'w').write(str(os.getpid())); time.sleep(120)" % pidfile
    threading.Thread(target=lambda: solver._launch([sys.executable, "-c", child], os.path.dirname(pidfile),
                                                   300, None), daemon=True).start()
    t = time.time() + 60
    while not (os.path.exists(pidfile) and open(pidfile).read()) and time.time() < t:
        time.sleep(0.05)
    print("ready", flush=True)
    sys.stdin.readline()                  # the test has seen the child alive
    if sys.argv[3] == "exit":
        sys.exit(0)                       # normal end of the server: atexit
    time.sleep(120)                       # wait to be killed
    """)


def _wait_dead(pid, seconds=20):
    t = time.time() + seconds
    while time.time() < t:
        if not solver.pid_alive(pid):
            return True
        time.sleep(0.1)
    return False


@pytest.mark.parametrize("how", ["exit", "kill"] if WINDOWS else ["exit"])
def test_sps_dies_with_the_server(tmp_path, how):
    """POSIX: process group killed at exit (atexit).  Windows: job object with KILL_ON_JOB_CLOSE, which
    also covers a server that is killed outright (TerminateProcess, no atexit)."""
    helper = tmp_path / "helper.py"
    helper.write_text(HELPER)
    pidfile = tmp_path / "child.pid"
    h = subprocess.Popen([sys.executable, str(helper), ROOT, str(pidfile), how], stdout=subprocess.PIPE,
                         stdin=subprocess.PIPE)
    try:
        assert h.stdout is not None and h.stdout.readline().strip() == b"ready"
        child = int(pidfile.read_text())
        assert solver.pid_alive(child)
        assert h.stdin is not None
        h.stdin.write(b"go\n")
        h.stdin.flush()
        if how == "kill":
            h.kill()
        h.wait(30)
        assert _wait_dead(child), "sps stand-in survived the server"
    finally:
        if h.poll() is None:
            h.kill()


# the per-run job object is tested in test_round3_safety.test_windows_job_per_run_kill_on_close_and_terminate


@pytest.mark.skipif(WINDOWS, reason="POSIX: sps runs in its own session so its whole group can be killed")
def test_posix_sps_in_own_process_group(tmp_path, sps):
    seen = []
    solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60, on_start=lambda p: seen.append(os.getpgid(p.pid)
                                                                                              == p.pid))
    assert seen == [True]


def test_pid_alive():
    assert solver.pid_alive(os.getpid())
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not solver.pid_alive(p.pid)


def test_lock_file_written_during_run_and_removed(tmp_path, sps):
    seen = {}

    def look(proc):
        lock = tmp_path / ("m" + solver.LOCK_EXT)
        seen["lock"] = json.loads(lock.read_text())
        seen["proc"] = proc.pid
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60, on_start=look)
    assert r["status"] == "ok" and [p for p, _ in seen["lock"]["procs"]] == [os.getpid(), seen["proc"]]
    assert seen["lock"]["host"] == solver.HOST and seen["lock"]["started"]
    assert seen["lock"]["procs"][0][1] == solver.proc_start_time(os.getpid())
    assert not list(tmp_path.glob("*" + solver.LOCK_EXT))


def test_live_lock_of_another_process_refuses_run(tmp_path, sps):
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (tmp_path / ("other" + solver.LOCK_EXT)).write_text(f"{other.pid}\n")
        r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
        assert r["status"] == "not run" and "Another calculation is running in this folder" in r["reason"]
        assert calls(tmp_path) == []
    finally:
        other.kill()
        other.wait()
    r = solver.run(str(tmp_path / "m.dat"), sps, 60)                       # now stale: removed, run goes on
    assert r["status"] == "ok" and not list(tmp_path.glob("*" + solver.LOCK_EXT))


def test_stale_lock_with_own_pid_and_garbage_is_removed(tmp_path, sps):
    (tmp_path / ("a" + solver.LOCK_EXT)).write_text(f"{os.getpid()}\n")         # not written by this run
    garbage = tmp_path / ("b" + solver.LOCK_EXT)
    garbage.write_text("garbage\n")
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n")
    # an empty / unreadable lock may be one another server is writing right now: respected for 10 s
    assert solver.run(dat, sps, 60)["status"] == "not run" and garbage.exists()
    os.utime(garbage, (time.time() - 60, time.time() - 60))
    assert solver.run(dat, sps, 60)["status"] == "ok"
    assert not list(tmp_path.glob("*" + solver.LOCK_EXT))


def test_cleanup_at_exit_kills_and_unlocks(tmp_path):
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **solver._popen_kw())
    lock = str(tmp_path / ("x" + solver.LOCK_EXT))
    open(lock, "w").close()
    solver._ACTIVE.add(p)
    solver._LOCKS.add(lock)
    try:
        solver._cleanup_at_exit()
        assert p.poll() is not None and not os.path.exists(lock) and lock not in solver._LOCKS
    finally:
        solver._ACTIVE.discard(p)
        if p.poll() is None:
            p.kill()


# ================================================================ 6. run status

def test_nonzero_exit_code_with_a_clean_protocol_is_a_warning(tmp_path, sps):
    # round 3 (R1): sps.exe's exit codes are not documented, so a clean protocol decides the status
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=warnings\n$ FAKE exit=3\n"), sps, 60)
    assert r["status"] == "ok with warnings" and r["exit_code"] == 3 and r["messages"][0]["number"] == 2430
    assert "sps.exe exit code 3, meaning not verified" in r["server_warnings"][0] and "reason" not in r


def test_program_without_stop_is_not_finished_without_totals_is_a_note():
    txt = ("*** Start: Program Calculation\n*** Start: Program ASE\n    +++++    0 errors and    0 warnings +++++\n"
           "*** Stop : Program ASE\n*** Start: Program AQB\n*** Stop : Program AQB\n*** End of Calculation!\n")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.prt")
        with open(p, "w") as f:
            f.write(txt)
        r = messages.summarize_run(p)
        # round 3 (R1): a missing totals line is only a note; a missing Stop line still means not finished
        assert r["status"] == "ok" and r["unfinished_programs"] == [] and r["programs_without_totals"] == ["AQB"]
        assert "AQB" in r["notes"][0]
        with open(p, "w") as f:
            f.write(txt.replace("*** Stop : Program AQB\n", "    +++++    0 errors and    0 warnings +++++\n"))
        r = messages.summarize_run(p)
        assert r["status"] == "not finished" and r["unfinished_programs"] == ["AQB"] and "notes" not in r


def test_protocol_written_just_before_the_run_is_not_fresh(tmp_path, sps, fast_clock):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE mode=none\n")
    w(tmp_path / "m.prt", "   *** Start: Program Calculation\n   *** End of Calculation!\n")   # mtime: now
    r = solver.run(dat, sps, 60)
    assert r["status"] == "no protocol" and r["files"]["prt"]["updated_by_this_run"] is False


def test_retry_is_reported(tmp_path, sps):
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE reject_options_first=1\n"), sps, 60)
    assert r["status"] == "ok" and "retried with the file name first: m.dat -B0" in r["retried"]
    assert "retried" not in solver.run(w(tmp_path / "n.dat", "+PROG ASE\nEND\n"), sps, 60)


# ================================================================ 7. stop answers fast

def test_stop_answers_stopping_at_once(server_mod, settings, monkeypatch):
    real = server_mod.solver._kill_tree
    gate = threading.Event()

    def slow_kill(proc):
        gate.wait(20)
        real(proc)
    monkeypatch.setattr(server_mod.solver, "_kill_tree", slow_kill)
    monkeypatch.setattr(server_mod, "STOP_WAIT_S", 0.5)
    first = run(server_mod.run_calculation(w_dat(settings["work_folders"][0], "long.dat",
                                                 "+PROG ASE\nEND\n$ FAKE sleep=60\n")))
    assert first["status"] == "running"
    t0 = time.time()
    r = run(server_mod.stop_calculation())
    assert r["status"] == "stopping" and r["job_id"] == first["job_id"] and time.time() - t0 < 5
    gate.set()
    final = run(server_mod.get_job_result(first["job_id"], 30))
    assert final["status"] == "stopped"


# ================================================================ 8. caps

def test_row_caps(server_mod, monkeypatch):
    assert server_mod._cap(10 ** 9, 1) == 5000 and server_mod._cap(-3, 1) == 1 and server_mod._cap("x", 7) == 7
    seen = []

    async def fake(op, cdb_path, **args):
        seen.append(args["max_rows"])
        return {}
    monkeypatch.setattr(server_mod, "_cdb", fake)
    for t in (server_mod.cdb_nodes("x.cdb", max_rows=10 ** 9),
              server_mod.cdb_node_results("x.cdb", 1, max_rows=10 ** 9),
              server_mod.cdb_support_reactions("x.cdb", 1, max_rows=10 ** 9),
              server_mod.cdb_beam_forces("x.cdb", 1, max_rows=10 ** 9),
              server_mod.cdb_truss_cable_forces("x.cdb", 1, max_rows=10 ** 9)):
        run(t)
    assert seen == [5000] * 5


def test_list_folder_cap(server_mod, settings):
    for i in range(3):
        w_dat(settings["work_folders"][0], f"{i}.dat", "x")
    r = run(server_mod.list_folder(settings["work_folders"][0], max_entries=-5))
    assert len(r["files"]) == 1 and r["truncated"] is True


def test_at_most_four_cdb_jobs(server_mod):
    blockers = []
    for i in range(4):
        ev = threading.Event()
        blockers.append(ev)
        server_mod._start_job("cdb", f"read {i}", lambda ev=ev: ev.wait(30) and {})
    try:
        r = run(server_mod.cdb_overview("x.cdb"))
        assert "at most 4" in r["error"]
    finally:
        for ev in blockers:
            ev.set()


def test_console_output_is_capped(tmp_path):
    code = "import sys\nfor i in range(20000): sys.stdout.write('line %06d ' % i + 'x' * 80 + '\\n')\nprint('LAST')"
    proc, out, timed_out, _ = solver._launch([sys.executable, "-c", code], str(tmp_path), 60, None, cap=4096)
    assert not timed_out and len(out) <= 4096 and out.rstrip().endswith(b"LAST") and proc.returncode == 0


# ================================================================ 9. stale results

@pytest.fixture
def cdb_env(server_mod, settings, tmp_path, monkeypatch):
    write_hook_config(tmp_path, monkeypatch, {}, install=None, fake="build_frame")
    c = os.path.join(settings["work_folders"][0], "frame.cdb")
    with open(c, "wb") as f:
        f.write(b"fake")
    os.utime(c, (1_000_000, 1_000_000))
    return c


def test_stale_cdb_warnings(server_mod, cdb_env):
    assert "stale_results_warning" not in run(server_mod.cdb_overview(cdb_env))
    stem = cdb_env[:-4]
    for ext in (".prt", ".dat"):
        with open(stem + ext, "w") as f:
            f.write("x")
    r = run(server_mod.cdb_overview(cdb_env))
    assert len(r["stale_results_warning"]) == 2 and "older than the protocol" in r["stale_results_warning"][0]
    os.utime(stem + ".prt", (1_000_030, 1_000_030))                 # 30 s after the .cdb: same run
    os.utime(stem + ".dat", (999_000, 999_000))
    assert "stale_results_warning" not in run(server_mod.cdb_overview(cdb_env))
    server_mod._last_run[config._norm(cdb_env)] = {"status": "errors", "cdb_updated": True}
    r = run(server_mod.cdb_overview(cdb_env))
    assert "ended with status 'errors'" in r["stale_results_warning"][0]
    server_mod._last_run[config._norm(cdb_env)] = {"status": "ok", "cdb_updated": False}
    assert "did not update the .cdb" in run(server_mod.cdb_overview(cdb_env))["stale_results_warning"][0]
    server_mod._last_run.clear()


def test_last_run_is_recorded(server_mod, settings):
    d = w_dat(settings["work_folders"][0], "e.dat", "+PROG AQB\nEND\n$ FAKE mode=errors\n$ FAKE exit=1\n")
    assert run(server_mod.run_calculation(d))["status"] == "errors"
    assert server_mod._last_run[config._norm(d[:-4] + ".cdb")] == {"status": "errors", "cdb_updated": True}
    server_mod._last_run.clear()


# ================================================================ 10. relative folders in settings.json

@pytest.mark.parametrize("key, value", [("work_folders", ["models"]), ("read_folders", "C:models"),
                                        ("examples_folders", ["\\examples"]), ("manual_folders", [".\\man"]),
                                        ("sofistik_dir", "SOFiSTiK\\2027")])
def test_relative_folders_refused(tmp_path, key, value):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({key: value}))
    with pytest.raises(config.SettingsError, match="not a full path"):
        config.load_settings(str(p))


def test_full_paths_accepted(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"work_folders": ["D:\\26016 HPC", "\\\\server\\share\\x", "C:/fwd"],
                             "read_folders": [str(tmp_path)], "sofistik_dir": "C:\\Program Files\\SOFiSTiK"}))
    assert config.load_settings(str(p))["work_folders"][0] == "D:\\26016 HPC"


# ================================================================ 11. install.bat (static checks; cmd.exe is not run)

def bat(name):
    with open(os.path.join(ROOT, name), "rb") as f:
        return f.read().decode("ascii").replace("\r\n", "\n")


def test_install_bat_quotes_cd_and_checks_errorlevels():
    text = bat("install.bat")
    for ln in text.split("\n"):
        if "%CD%" in ln:
            assert '"%CD%"' in ln, ln               # & and ( ) in the folder name stay literal
    lines = text.split("\n")
    i = lines.index('".venv\\Scripts\\python.exe" -m sofistik_mcp.configure_clients')
    assert lines[i + 1] == "if %errorlevel% neq 0 goto regfailed"
    assert ":regfailed" in lines and "exit /b 1" in lines[lines.index(":regfailed"):]


def test_install_bat_python_order():
    text = bat("install.bat")
    order = [ln.split(" ", 1)[1] for ln in text.split("\n") if ln.startswith(("call :try", "if not defined PY call"))]
    assert [o.replace("call ", "").replace("PY ", "") for o in order][0] == ":trypy -3.13"
    tried = [x.split()[-1] for x in order]
    assert tried == ["-3.13", "-3.12", "-3.11", "-3.10", "-3", ":trypython"]
    assert '%CHECK%' in text and "sys.maxsize > 2**32" in text and "(3, 10)" in text
    labels = {ln[1:] for ln in text.split("\n") if ln.startswith(":")}
    for target in ("trypy", "trypython"):
        assert target in labels
    # subroutines are only reached by call: the main flow ends before them
    assert text.index("exit /b 0") < text.index("\n:trypy\n")


# ================================================================ 12. configure_clients

@pytest.fixture
def dirs(monkeypatch, tmp_path):
    appdata, local = tmp_path / "Roaming", tmp_path / "Local"
    appdata.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(configure_clients.shutil, "which", lambda name: None)
    return appdata


def test_remove_does_not_create_a_config(dirs):
    rep = configure_clients.update_desktop("py.exe", remove=True)
    assert rep[0].startswith("Nothing to remove") and not (dirs / "Claude").exists()


def test_only_three_backups_kept(dirs, monkeypatch):
    (dirs / "Claude").mkdir()
    p = dirs / "Claude" / "claude_desktop_config.json"
    p.write_text("{}")
    (dirs / "Claude" / "claude_desktop_config.json.bak-mine").write_text("user's own copy")
    stamps = iter(range(10))
    monkeypatch.setattr(configure_clients, "backup_name",
                        lambda path: f"{path}.bak-20261017-0930{next(stamps):02d}")
    for _ in range(6):
        configure_clients.update_desktop("py.exe")
    baks = sorted(n for n in os.listdir(dirs / "Claude") if ".bak-" in n)
    assert baks == ["claude_desktop_config.json.bak-20261017-093003", "claude_desktop_config.json.bak-20261017-093004",
                    "claude_desktop_config.json.bak-20261017-093005", "claude_desktop_config.json.bak-mine"]


def test_prune_orders_numbered_backups(tmp_path):
    p = str(tmp_path / "c.json")
    for suf in ("-090000", "-090000-2", "-090000-10", "-090001"):
        open(p + ".bak-20261017" + suf, "w").close()
    configure_clients.prune_backups(p, keep=2)
    assert sorted(os.listdir(tmp_path)) == ["c.json.bak-20261017-090000-10", "c.json.bak-20261017-090001"]


@pytest.mark.parametrize("exe, py, runs_add", [
    ("C:\\npm\\claude.cmd", "C:\\R&D\\venv\\python.exe", False),
    ("C:\\npm\\claude.CMD", "C:\\x\\100%\\python.exe", False),
    ("C:\\npm\\claude.bat", "C:\\a^b\\python.exe", False),
    ("C:\\npm\\claude.cmd", "C:\\plain\\python.exe", True),
    ("C:\\bin\\claude.exe", "C:\\R&D\\venv\\python.exe", True)])
def test_claude_cmd_metacharacters(monkeypatch, exe, py, runs_add):
    calls_ = []
    monkeypatch.setattr(configure_clients.shutil, "which", lambda name: exe)
    monkeypatch.setattr(configure_clients.subprocess, "run",
                        lambda args, **kw: calls_.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
    rep = configure_clients.update_claude_code(py)
    assert any(c[1:3] == ["mcp", "add"] for c in calls_) is runs_add
    if not runs_add:
        assert "by hand" in rep[0] and f'"{py}"' in rep[0]


# ================================================================ 13. README

def test_readme_safety_rules_updated():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    rules = text[text.index("## Safety rules"):text.index("## Limits")]
    for s in ("*SYS", "outside the folders", "refuses to write anything", ".mcp-running", "full path"):
        assert s in rules, s


# ================================================================ edge paths

def test_unreadable_include_refuses(tmp_path, sps, monkeypatch):
    inc = w(tmp_path / "inc.dat", "$ x\n")
    real = os.path.getsize

    def size(p):
        if os.path.normcase(str(p)) == os.path.normcase(inc):
            raise PermissionError(13, "Permission denied")
        return real(p)
    monkeypatch.setattr(solver.os.path, "getsize", size)
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\n#include inc\nEND\n"), sps, 60)
    assert r["status"] == "not run" and "cannot be read (Permission denied)" in r["reason"]


def test_recursive_define_at_line_start_is_flagged(tmp_path):
    p = w(tmp_path / "m.dat", "#define A=$(B)\n#define B=$(A)\n+PROG AQUA\n$(A) 1\nEND\n")
    assert solver.scan_dat(p)["sys_lines"]


def test_include_deleted_during_run_counts_as_changed(tmp_path, sps):
    inc = w(tmp_path / "inc.dat", "$ x\n")
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n+APPLY inc\n"), sps, 60,
                   on_start=lambda p: os.remove(inc))
    assert r["changed_during_run"] == [inc]


def test_containment_problem_is_reported(tmp_path, sps, monkeypatch):
    monkeypatch.setattr(solver, "_new_job", lambda: solver._NoJob("no job object here"))
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
    assert r["status"] == "ok" and "no job object here" in r["server_warnings"][0]
    monkeypatch.setattr(solver, "_new_job", lambda: 1 / 0)                  # creating the job fails
    r = solver.run(str(tmp_path / "m.dat"), sps, 60)
    assert r["status"] == "ok" and "ZeroDivisionError" in r["server_warnings"][0]

    class BadAssign(solver._NoJob):
        def assign(self, proc):
            raise OSError("assign failed")
    monkeypatch.setattr(solver, "_new_job", BadAssign)
    r = solver.run(str(tmp_path / "m.dat"), sps, 60)
    assert r["status"] == "ok" and "assign failed" in r["server_warnings"][0]


def test_lock_races(tmp_path, sps, monkeypatch):
    dat = w(tmp_path / "m.dat", "+PROG ASE\nEND\n")
    real = solver.live_lock
    # both servers checked at once (the check before the lock is written saw nothing)
    monkeypatch.setattr(solver, "live_lock", lambda folder, skip=None: None if skip is None else real(folder, skip))
    (tmp_path / ("m" + solver.LOCK_EXT)).write_text("")
    r = solver.run(dat, sps, 60)
    assert r["status"] == "not run" and "appeared just now" in r["reason"]
    os.remove(tmp_path / ("m" + solver.LOCK_EXT))
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (tmp_path / ("o" + solver.LOCK_EXT)).write_text(f"{other.pid}\n")
        r = solver.run(dat, sps, 60)
        assert r["status"] == "not run" and "at the same moment" in r["reason"] and calls(tmp_path) == []
        assert not (tmp_path / ("m" + solver.LOCK_EXT)).exists()
    finally:
        other.kill()
        other.wait()


def test_stop_before_sps_started_still_stops(tmp_path, sps):
    t0 = time.time()
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE sleep=60\n"), sps, 120, stopped=lambda: True)
    assert r["status"] == "stopped" and time.time() - t0 < 30


def test_kill_tree_survives_errors():
    class Broken:
        pid = 2 ** 22 + 12345

        def kill(self):
            raise OSError("gone")

        def wait(self, timeout=None):
            raise OSError("gone")
    solver._kill_tree(Broken())                                             # must not raise
    solver.kill_tree_async(Broken()).join(10)
