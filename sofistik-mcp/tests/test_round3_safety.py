"""Third review round, safety (solver.py / messages.py / server.py / install.bat).  Each test failed
before its fix.  Windows-only parts run on windows-latest in CI and are skipped elsewhere."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest
from conftest import ROOT, run

from sofistik_mcp import messages, solver

WINDOWS = sys.platform == "win32"


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def wb(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def sys_lines(path, **kw):
    return solver.scan_dat(str(path), **kw)["sys_lines"]


def calls(folder):
    p = folder / "fake_sps_calls.txt"
    return p.read_text().splitlines() if p.exists() else []


# ================================================================ S1: $(...) inside the first word

@pytest.mark.parametrize("text", [
    "#define Y=YS\n+PROG AQUA\nEND\n+S$(Y) calc.exe\n",
    "+PROG AQUA\nEND\n+SY$(UNDEF)S calc.exe\n",
    "#define Y=YS\n+PROG AQUA\nEND\n*S$(Y) calc.exe\n",
    "#define A=Y\n#define Y=YS\n+PROG AQUA\nEND\n+S$($(A)) calc.exe\n",
    "#define Y=YS\n+PROG AQUA\nEND\nHEAD x ; +S$(Y) calc.exe\n",          # first word of a later record
    "#define N=1\n+PROG AQUA\nEND\n+S$(N) calc.exe\n",                     # numeric, but a letter glued to it
    "#define N=1\n+PROG AQUA\nEND\n$(N)S calc.exe\n",
])
def test_substitution_inside_the_first_word_is_flagged(tmp_path, text):
    assert sys_lines(w(tmp_path / "m.dat", text)), text


def test_dollar_name_inside_the_first_word_is_flagged(tmp_path):
    # the reviewer's demo: $(NAME) is the .dat's own name, YS.dat makes "+S$(NAME)" a +SYS line
    found = sys_lines(w(tmp_path / "YS.dat", "+PROG AQUA\nEND\n+S$(NAME) calc.exe\n"))
    assert [x["line"] for x in found] == [3] and "first word" in found[0]["why"]


def test_server_refuses_to_write_or_run_the_midword_demo(server_mod, settings, sps):
    work = settings["work_folders"][0]
    r = run(server_mod.write_dat_file(os.path.join(work, "m.dat"), "#define Y=YS\n+PROG AQUA\nEND\n+S$(Y) calc.exe\n"))
    assert "allow_sys_commands" in r["error"] and not os.path.exists(os.path.join(work, "m.dat"))
    with open(os.path.join(work, "YS.dat"), "w") as f:
        f.write("+PROG AQUA\nEND\n+S$(NAME) calc.exe\n")
    r = solver.run(os.path.join(work, "YS.dat"), sps, 60)
    assert r["status"] == "not run" and r["sys_lines"]


@pytest.mark.parametrize("text", [
    "#define NRQ=91\n+PROG AQUA\n  $(NRQ)  1  2\nEND\n",
    "#define S1=-1.00 $ [N/mm2]\n#define T=0.0\n+PROG TEMPLATE\n #($(S1),9.3)  #($(T),12.3)\nEND\n",  # shipped example
    "#define A=1\n#define B=2\n+PROG AQUA\n$(A)$(B) 3\nEND\n",
])
def test_numeric_substitution_without_letters_is_fine(tmp_path, text):
    assert sys_lines(w(tmp_path / "m.dat", text)) == []


# ================================================================ S2: encodings

BODY = "+SYS calc\r\n+PROG AQUA\r\nEND\r\n"


@pytest.mark.parametrize("data", [
    BODY.encode("utf-16"),                                       # BOM FF FE
    b"\xfe\xff" + BODY.encode("utf-16-be"),
    BODY.encode("utf-32"),
    b"\x00\x00\xfe\xff" + BODY.encode("utf-32-be"),
    ("\u00e4\r\n" + BODY).encode("utf-16"),
])
def test_utf16_and_utf32_with_bom_are_decoded(tmp_path, data):
    sc = solver.scan_dat(wb(tmp_path / "m.dat", data))
    assert [x["line"] for x in sc["sys_lines"]] in ([1], [2]) and [p["program"] for p in sc["programs"]] == ["AQUA"]
    assert sc["blocked_includes"] == []


@pytest.mark.parametrize("data, why", [
    (BODY.encode("utf-16-le"), "NUL bytes"),                     # no BOM
    (b"+PROG AQUA\r\nEND\r\n+S\x00YS calc\r\n", "NUL bytes"),
    (b"\xff\xfe" + BODY.encode("utf-16-le") + b"\x00", "not valid UTF-16"),   # odd length
    (b"\xff\xfe" + "+PROG AQUA\r\n\x00+SYS calc\r\n".encode("utf-16-le"), "NUL characters"),
    (b"+/v8" + b"+PROG AQUA\r\nEND\r\n", "byte order mark of an encoding"),       # UTF-7
])
def test_unreadable_encodings_refuse_the_run(tmp_path, sps, data, why):
    dat = wb(tmp_path / "m.dat", data)
    sc = solver.scan_dat(dat)
    assert sc["blocked_includes"] and why in sc["blocked_includes"][0]["why"] and sc["sys_lines"] == []
    r = solver.run(dat, sps, 60)
    assert r["status"] == "not run" and why in r["reason"] and calls(tmp_path) == []


def test_utf16_include_is_decoded(tmp_path):
    wb(tmp_path / "inc.dat", "$ x\r\n+SYS calc\r\n".encode("utf-16"))
    sc = solver.scan_dat(w(tmp_path / "m.dat", "+PROG ASE\n#include inc\nEND\n"))
    assert [x["line"] for x in sc["sys_lines"]] == [2] and sc["sys_lines"][0]["file"].endswith("inc.dat")


def test_utf16_without_sys_passes_the_check(tmp_path):
    sc = solver.scan_dat(wb(tmp_path / "m.dat", "+PROG ASE\r\nEND\r\n".encode("utf-16")))
    assert sc["sys_lines"] == [] and sc["blocked_includes"] == [] and sc["programs"][0]["program"] == "ASE"


def test_write_refuses_nul_characters(server_mod, settings):
    p = os.path.join(settings["work_folders"][0], "m.dat")
    r = run(server_mod.write_dat_file(p, "+PROG AQUA\nEND\n+S\x00YS calc\n"))
    assert "allow_sys_commands" in r["error"] and "NUL" in r["sys_lines"][0]["why"] and not os.path.exists(p)


def test_decode_input_plain_files_as_before():
    assert messages.decode_input(b"\xef\xbb\xbf+PROG AQUA\r\n\xe4") == ("+PROG AQUA\n\u00e4", "utf-8")
    assert messages.decode_input("ä".encode("cp1252")) == ("ä", "utf-8")
    assert messages.decode_input("a\r\nb".encode("utf-16")) == ("a\nb", "utf-16-le")


# ================================================================ S3: no false refusals for "system" in values

@pytest.mark.parametrize("text", [
    "#define EX=0.5 $ eccentricity in the local system\n+PROG AQUA\nEND\n",
    "#define T='Global system'\n+PROG AQUA\nEND\n",
    "#define T=Global system\n+PROG AQUA\nHEAD $(T)\nEND\n",
])
def test_define_values_mentioning_system_are_fine(tmp_path, text):
    assert sys_lines(w(tmp_path / "m.dat", text)) == []


@pytest.mark.parametrize("value", ["+SYS calc", "sys", " * SYS", "SYSTEM", "X+SYS", "1;+S", "a ; b"])
def test_define_values_that_can_start_sys_are_flagged(tmp_path, value):
    assert sys_lines(w(tmp_path / "m.dat", f"#define X={value}\n+PROG AQUA\nEND\n"))


# ================================================================ S4: APPL and includes after ';'

@pytest.mark.parametrize("line", ["+APPL evil", "APPL evil.dat", "END;+APPLY evil", "END ; +APPL evil",
                                  "*APPLY evil", "HEAD x;#include evil"])
def test_abbreviated_apply_and_includes_after_a_semicolon_are_followed(tmp_path, line):
    w(tmp_path / "evil.dat", "+SYS calc\n")
    sc = solver.scan_dat(w(tmp_path / "m.dat", f"+PROG AQUA\n{line}\n"))
    assert sc["sys_lines"] and sc["sys_lines"][0]["file"].endswith("evil.dat"), line


def test_skipped_apply_is_not_followed(tmp_path):
    sc = solver.scan_dat(w(tmp_path / "m.dat", "+PROG AQUA\nEND\n-APPLY nothing_here\n"))
    assert sc["missing_includes"] == [] and sc["sys_lines"] == []


# ================================================================ S5: only definitions before the line count

def test_definition_after_the_line_does_not_make_it_safe(tmp_path):
    assert sys_lines(w(tmp_path / "m.dat", "+PROG AQUA\n$(X) 1\nEND\n#define X=1\n"))
    assert sys_lines(w(tmp_path / "n.dat", "#define X=1\n+PROG AQUA\n$(X) 1\nEND\n")) == []


def test_later_redefinition_is_judged_at_its_own_line(tmp_path):
    found = sys_lines(w(tmp_path / "m.dat", "#define X=1\n+PROG AQUA\n$(X) 1\n#define X=YS\n+S$(X) x\n$(X) 2\nEND\n"))
    assert [x["line"] for x in found] == [5, 6]


# ================================================================ S8: lines longer than 255 characters

@pytest.mark.parametrize("line", [
    "HEAD " + "x" * 260 + " +SYS calc",
    "$ " + "x" * 300 + " +SYS calc",                          # a comment line too: the rest may be a new line
    "HEAD " + "\u00e4" * 130 + "+SYS calc",                    # 135 characters but 265 bytes in UTF-8
    "HEAD " + "x" * 249 + "+SYS",                              # SYS straddles character 255
])
def test_sys_beyond_the_line_limit_is_flagged(tmp_path, line):
    found = sys_lines(w(tmp_path / "m.dat", f"+PROG AQUA\n{line}\nEND\n"))
    assert [x["line"] for x in found] == [2] and "255" in found[0]["why"]


def test_line_limit_counts_bytes_of_a_utf16_file(tmp_path):
    # 150 characters are 300 bytes in UTF-16: SYS at character 140 is beyond byte 255
    line = "HEAD " + "x" * 135 + " +SYS calc"
    found = sys_lines(wb(tmp_path / "m.dat", f"+PROG AQUA\r\n{line}\r\nEND\r\n".encode("utf-16")))
    assert [x["line"] for x in found] == [2] and "255" in found[0]["why"]
    assert sys_lines(w(tmp_path / "n.dat", f"+PROG AQUA\n{line}\nEND\n")) == []      # 150 bytes in UTF-8


def test_long_line_without_sys_is_fine(tmp_path):
    assert sys_lines(w(tmp_path / "m.dat", "+PROG AQUA\nHEAD " + "x" * 400 + "\nEND\n")) == []
    assert solver._beyond_line_limit("x" * 255) == "" and solver._beyond_line_limit("x" * 256) == "xxx"


# ================================================================ S6: one job object per run

GRANDCHILD = textwrap.dedent("""\
    import os, subprocess, sys, time
    pidfile, role = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "sps")
    if role == "middle":                    # starts the grandchild and ends at once
        subprocess.Popen([sys.executable, __file__, pidfile, "grand"])
        sys.exit(0)
    if role == "grand":
        with open(pidfile + ".tmp", "w") as f:
            f.write(str(os.getpid()))
        os.replace(pidfile + ".tmp", pidfile)
        time.sleep(120)
        sys.exit(0)
    subprocess.Popen([sys.executable, __file__, pidfile, "middle"]).wait()
    time.sleep(120)
    """)


def _wait_dead(pid, seconds=20):
    t = time.time() + seconds
    while time.time() < t:
        if not solver.pid_alive(pid):
            return True
        time.sleep(0.1)
    return False


def test_stop_kills_a_grandchild_whose_parent_has_ended(tmp_path):
    """sps.exe -> (a program that ends) -> a program still running: taskkill /T cannot find it any more
    (its parent is gone); the run's job object (Windows) or process group (POSIX) still holds it."""
    script = tmp_path / "tree.py"
    script.write_text(GRANDCHILD)
    pidfile = tmp_path / "grand.pid"
    started: list = []
    t = threading.Thread(target=lambda: solver._launch([sys.executable, str(script), str(pidfile)], str(tmp_path),
                                                       300, started.append), daemon=True)
    t.start()
    deadline = time.time() + 60
    while not pidfile.exists() and time.time() < deadline:
        time.sleep(0.05)
    grand = int(pidfile.read_text())
    try:
        assert solver.pid_alive(grand) and started
        solver._kill_tree(started[0])
        assert _wait_dead(grand), "grandchild survived the stop"
        t.join(30)
        assert not t.is_alive()
    finally:
        if solver.pid_alive(grand):
            try:
                os.kill(grand, 9)
            except OSError:
                pass


class RecordingJob(solver._NoJob):
    made: list = []

    def __init__(self, kills=True):
        super().__init__()
        self.kills = kills
        self.events: list = []
        RecordingJob.made.append(self)

    def assign(self, proc):
        self.events.append(("assign", proc.pid))
        self.assigned = True
        self.proc = proc
        return None

    def terminate(self):
        self.events.append(("terminate",))
        if self.kills:
            self.proc.kill()                 # stands in for TerminateJobObject
        return self.kills


def test_job_made_before_the_process_and_used_to_stop_it(tmp_path, monkeypatch):
    order: list = []
    real_popen = subprocess.Popen

    def popen(*a, **kw):
        order.append("popen")
        return real_popen(*a, **kw)

    def new_job():
        order.append("job")
        return RecordingJob()
    monkeypatch.setattr(solver.subprocess, "Popen", popen)
    monkeypatch.setattr(solver, "_new_job", new_job)
    seen: list = []

    def on_start(proc):
        seen.append(proc)
        solver._kill_tree(proc)              # a stop: the job is terminated
    proc, _out, timed_out, problem = solver._launch([sys.executable, "-c", "import time; time.sleep(60)"],
                                                    str(tmp_path), 60, on_start)
    job = RecordingJob.made[-1]
    assert order[:2] == ["job", "popen"] and problem is None and not timed_out
    assert job.events[0] == ("assign", proc.pid) and ("terminate",) in job.events
    assert proc._mcp_job is job


def test_failed_job_terminate_falls_back_to_killing_the_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(solver, "_new_job", lambda: RecordingJob(kills=False))
    proc, _out, timed_out, _ = solver._launch([sys.executable, "-c", "import time; time.sleep(60)"],
                                              str(tmp_path), 1, None)
    assert timed_out and proc.poll() is not None and ("terminate",) in RecordingJob.made[-1].events


@pytest.mark.skipif(not WINDOWS, reason="Win32 job objects exist only on Windows")
def test_windows_job_per_run_kill_on_close_and_terminate():
    import ctypes
    from ctypes import wintypes
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        job = solver._new_job()
        assert job.error is None and job.handle and job.assign(p) is None and job.assigned
        k32 = solver._k32
        inside = wintypes.BOOL()
        h = k32.OpenProcess(0x1000, False, p.pid)
        assert k32.IsProcessInJob(h, job.handle, ctypes.byref(inside)) and inside.value
        k32.CloseHandle(h)
        info = solver._EXTENDED_LIMIT()
        assert k32.QueryInformationJobObject(job.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None)
        assert info.BasicLimitInformation.LimitFlags & 0x2000
        assert solver._new_job().handle != job.handle                 # one job per run
        assert job.terminate()
        p.wait(10)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


# ================================================================ S7: lock files with host and start time

def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_lock_from_another_pc_is_never_removed(tmp_path, sps):
    lock = tmp_path / ("m" + solver.LOCK_EXT)
    lock.write_text(json.dumps({"host": "DESIGN-PC-7", "procs": [[_dead_pid(), None]], "started": "2026-10-17 09:00"}))
    r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
    assert r["status"] == "not run" and lock.exists() and calls(tmp_path) == []
    assert "DESIGN-PC-7" in r["reason"] and "delete m.mcp-running" in r["reason"]
    assert r["lock_host"] == "DESIGN-PC-7"
    assert "2026-10-17 09:00" in r["reason"]


@pytest.mark.skipif(solver.proc_start_time(os.getpid()) is None, reason="process start times are not readable here")
def test_lock_with_a_reused_pid_is_stale(tmp_path, sps):
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        start = solver.proc_start_time(other.pid)
        assert start is not None
        lock = tmp_path / ("m" + solver.LOCK_EXT)
        lock.write_text(json.dumps({"host": solver.HOST, "procs": [[other.pid, start]]}))
        r = solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)
        # same process
        assert r["status"] == "not run" and "Another calculation of this model is running" in r["reason"]
        lock.write_text(json.dumps({"host": solver.HOST.upper(), "procs": [[other.pid, start + 12345]]}))
        r = solver.run(str(tmp_path / "m.dat"), sps, 60)                                        # PID reused
        assert r["status"] == "ok" and not lock.exists()
    finally:
        other.kill()
        other.wait()


def test_own_pid_from_an_earlier_server_is_stale(tmp_path, sps):
    me = os.getpid()
    start = solver.proc_start_time(me)
    lock = tmp_path / ("a" + solver.LOCK_EXT)
    lock.write_text(json.dumps({"host": solver.HOST, "procs": [[me, (start or 0) + 1]]}))
    assert solver.run(w(tmp_path / "m.dat", "+PROG ASE\nEND\n"), sps, 60)["status"] == "ok" and not lock.exists()


@pytest.mark.parametrize("text, procs", [
    ('{"host": "PC", "procs": [[12, 34]], "started": "x"}', [[12, 34]]),
    ('{"host": "PC", "procs": [[12, null]]}', [[12, None]]),
    ("4321 765\n", [[4321, None], [765, None]]),                  # written by an older server
    ('{"procs": "x"}', []),
    ("", []),
])
def test_read_lock_formats(tmp_path, text, procs):
    p = tmp_path / "x.mcp-running"
    p.write_text(text)
    assert solver._read_lock(str(p))["procs"] == procs
    assert solver._read_lock(str(tmp_path / "missing")) is None


def test_lock_message_for_this_pc():
    m = solver.lock_message("C:\\w\\m.mcp-running", {"host": None, "procs": [], "started": None})
    assert "another Claude window" in m and "DESIGN" not in m


# ================================================================ S9: install.bat

def bat(name):
    with open(os.path.join(ROOT, name), "rb") as f:
        return f.read().decode("ascii").replace("\r\n", "\n")


def test_install_bat_python_probe_prints_a_marker_and_checks_it():
    text = bat("install.bat")
    assert "print('PYOK' if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 'PYBAD')" in text
    for label in ("trypy", "trypython"):
        body = text[text.index(f"\n:{label}\n"):]
        body = body[:body.index("exit /b 0")]
        assert '-c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul' in body
        assert "if %errorlevel% equ 0 set" in body
        assert "if not errorlevel 1" not in body


def test_install_bat_has_no_errorlevel_1_checks():
    """"if errorlevel 1" is false for negative exit codes (a crash such as -1073741819)."""
    text = bat("install.bat")
    assert "errorlevel 1" not in text
    for ln in text.split("\n"):
        if "%errorlevel%" in ln:
            assert ln.startswith(("if %errorlevel% equ 0 ", "if %errorlevel% neq 0 ")), ln


def test_install_bat_checks_an_existing_venv_and_remakes_it():
    lines = bat("install.bat").split("\n")
    i = lines.index('if not exist ".venv\\Scripts\\python.exe" goto makevenv')
    assert lines[i + 1] == '".venv\\Scripts\\python.exe" -c "%CHECK%" 2>nul | findstr /c:"PYOK" >nul'
    assert lines[i + 2] == "if %errorlevel% equ 0 goto havevenv"
    rest = lines[i + 3:]
    assert 'rmdir /s /q ".venv"' in rest and 'if exist ".venv" goto venvbusy' in rest
    mk = lines.index(":makevenv")
    assert lines[mk + 2] == "%PY% -m venv .venv" and lines[mk + 3] == "if %errorlevel% neq 0 goto failed"
    # the new environment is checked with the same probe before anything is installed into it
    assert lines[mk + 4] == lines[i + 1] and lines[mk + 5] == "if %errorlevel% neq 0 goto failed"
    assert lines.index(":havevenv") == mk + 6
    assert lines.index(":makevenv") < lines.index(":havevenv") < lines.index("exit /b 0")
    pip = [k for k, ln in enumerate(lines) if "-m pip install" in ln][0]
    assert lines[pip + 1] == "if %errorlevel% neq 0 goto failed"
    # no ( ... ) block in the main flow: %errorlevel% inside a block is expanded before the block runs
    main = lines[:lines.index("exit /b 0")]
    assert not [ln for ln in main if ln.rstrip().endswith("(")]
