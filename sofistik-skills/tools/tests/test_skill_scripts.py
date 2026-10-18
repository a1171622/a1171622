"""Tests for the scripts that replace the inline E / V / H one-liners, and dat_lint's native #INCLUDE."""
import json
import os
import subprocess
import sys

from _util import MINI, TOOLS, dump, ids, run, tmpdir


def raw(script, *args):
    p = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, script)] + [str(a) for a in args],
                       capture_output=True, text=True, timeout=300)
    lines = p.stdout.strip().splitlines()
    return p.returncode, lines[:-1], json.loads(lines[-1])


def setup_master(d, nested=False):
    a = os.path.join(d, "a_cloud.dat")
    b = os.path.join(d, "b_cloud.dat")
    open(a, "w").write("$ file a\r\nline a2\n")
    open(b, "w").write("$ file b\nline b2\n" + ("#INCLUDE c.dat\n" if nested else ""))
    m = os.path.join(d, "m.dat")
    open(m, "w").write("$ master\n#INCLUDE a.dat\n#INCL b.dat  $ comment\n+PROG X\nEND\n")
    tsv = os.path.join(d, "sources.tsv")
    open(tsv, "w").write(f"a.dat\t{a}\nb.dat\t{b}\nm.dat\t{m}\n")
    return m, tsv, a, b


def test_expand_master_like_script_e():
    d = tmpdir()
    m, tsv, a, b = setup_master(d)
    x = os.path.join(d, "x.dat")
    code, pre, o = raw("expand_master.py", m, x, tsv, "--workdir", d)
    assert code == 0 and pre == ["EXPANDED 7"], pre
    assert open(x).read() == "$ master\n$ file a\nline a2\n$ file b\nline b2\n+PROG X\nEND\n"
    assert os.path.exists(os.path.join(d, "proofs.jsonl"))


def test_expand_master_missing_source_and_nested():
    d = tmpdir()
    m, tsv, a, b = setup_master(d, nested=True)
    open(tsv, "w").write(f"a.dat\t{a}\n")
    code, pre, o = raw("expand_master.py", m, os.path.join(d, "x.dat"), tsv)
    assert code == 3 and pre[0].startswith("EXPAND_ERROR") and not os.path.exists(os.path.join(d, "x.dat"))
    m, tsv, a, b = setup_master(d, nested=True)
    code, pre, o = raw("expand_master.py", m, os.path.join(d, "x.dat"), tsv)
    assert code == 2 and pre[0].startswith("EXPANDED") and ids(o)["E2_no_nested_include"] == "ESCALATE"


def test_transfer_check_ok_and_first_diff():
    d = tmpdir()
    m, tsv, a, b = setup_master(d)
    rd = os.path.join(d, "raw")
    os.makedirs(rd)
    open(os.path.join(rd, "xfer__1__a.dat.txt"), "w").write("1: $ file a\n2: line a2\n")
    open(os.path.join(rd, "xfer__2__a.dat.txt"), "w").write("2:line a2   \n")
    open(os.path.join(rd, "xfer__p1__unknown.dat.txt"), "w").write("1: zzz\n")
    code, pre, o = raw("transfer_check.py", rd, tsv)
    assert code == 0 and pre[-1] == "TRANSFER_OK" and "a.dat 2 lines compared" in pre, pre
    open(os.path.join(rd, "xfer__3__b.dat.txt"), "w").write("1: $ file b\n2: line B2\n")
    code, pre, o = raw("transfer_check.py", rd, tsv)
    assert code == 1 and pre[-1] == "TRANSFER_BAD first=b.dat:2" and "DIFF b.dat line 2" in pre, pre
    code, pre, o = raw("transfer_check.py", os.path.join(d, "empty"), tsv)
    assert code == 1 and pre[-1] == "TRANSFER_BAD first=none"


def test_run_history_tail_same_earlier_none():
    d = tmpdir()
    runs = {"runs": [
        {"dat": "D:\\p\\26016_v1.dat", "finished": "x", "status": "ok", "seconds": 600.0, "peak_ram_mb": 3000},
        {"dat": "D:\\p\\26016_v2.dat", "finished": "x", "status": "error", "seconds": 20.0, "peak_ram_mb": 5000},
        {"dat": "D:\\p\\other.dat", "finished": "x", "status": "ok", "seconds": 60.0, "peak_ram_mb": None}]}
    text = "\n".join(f"{i}: {l}" for i, l in enumerate(json.dumps(runs, indent=1).split("\n"), 40))
    t = os.path.join(d, "tail.txt")
    open(t, "w").write(text)
    code, pre, o = raw("run_history_tail.py", t, "26016_v3.dat")
    assert code == 0 and pre == ["HIST earlier version minutes=10.0 peak_gb=4.9"], pre
    code, pre, o = raw("run_history_tail.py", t, "D:\\p\\26016_V2.dat")
    assert pre == ["HIST same file minutes=none peak_gb=4.9"], pre
    code, pre, o = raw("run_history_tail.py", t, "nothing.dat")
    assert code == 0 and pre == ["HIST none"]


def test_dat_lint_native_include_and_src():
    d = tmpdir()
    body = open(MINI).read()
    inc = os.path.join(d, "mini_cloud.dat")
    open(inc, "w").write(body.replace("COPY NO 3 FACT #GQ", "COPY NO 3 FACT #GQ\nLC 999 TYPE G\n" + "X" * 260, 1))
    m = os.path.join(d, "m.dat")
    open(m, "w").write("$ master\n#INCLUDE mini.dat\n")
    tsv = os.path.join(d, "sources.tsv")
    open(tsv, "w").write(f"mini.dat\t{inc}\n")
    code, o = run("dat_lint.py", m, "--sources", tsv)
    s3 = [c for c in o["checks"] if c["id"] == "S3"][0]
    assert s3["verdict"] == "FAIL" and s3["findings"][0]["src"].startswith("mini_cloud.dat:"), s3
    # not found -> S15 FAIL; --no-include on a master is never a vacuous PASS
    code, o = run("dat_lint.py", m)
    assert ids(o)["S15"] == "FAIL" and code == 1
    code, o = run("dat_lint.py", m, "--no-include")
    assert ids(o)["S15"] == "FAIL"
    # a master and its expanded copy give the same findings
    x = os.path.join(d, "x.dat")
    raw("expand_master.py", m, x, tsv)
    _, ox = run("dat_lint.py", x)
    _, om = run("dat_lint.py", m, "--sources", tsv)
    strip = lambda o: {c["id"]: [(f["line"], f["msg"]) for f in c.get("findings", [])] for c in o["checks"]}
    assert strip(ox) == strip(om)
