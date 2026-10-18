"""Helpers for the tool tests (stdlib only).  Run all tests: python3 -I tests/run_tests.py"""
import json
import os
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
FIX = os.path.join(TESTS, "fixtures")
MINI = os.path.join(FIX, "mini.dat")
# real-file copies (NUL/CR stripped) - tests using them are skipped when absent
REAL_DIR = os.environ.get("TOOLS_REAL_DIR", "/tmp/claude-0/-home-claude-a1171622/ae4f7651-d223-504c-bd74-163a55754ecc/scratchpad/data")
sys.path.insert(0, TOOLS)


class Skip(Exception):
    pass


def run(script, *args, test_env=True):
    """Run a tool as the skill does; returns (exit code, parsed JSON object).  test_env sets TOOLS_TEST=1 (allows
    a test calibration file); test_env=False runs exactly as Haiku does."""
    env = dict(os.environ)
    env.pop("TOOLS_TEST", None)
    if test_env:
        env["TOOLS_TEST"] = "1"
    p = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, script)] + [str(a) for a in args],
                       capture_output=True, text=True, timeout=900, env=env)
    try:
        o = json.loads(p.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        raise AssertionError(f"{script} printed no JSON (exit {p.returncode}): {p.stdout[-400:]} {p.stderr[-800:]}")
    assert p.returncode == {"PASS": 0, "FAIL": 1, "ESCALATE": 2, "CANNOT_RUN": 3}[o["verdict"]], \
        f"exit {p.returncode} does not match verdict {o['verdict']}"
    return p.returncode, o


def tmpdir():
    return tempfile.mkdtemp(prefix="tooltest_")


def dump(d, name, obj):
    p = os.path.join(d, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


def ids(o):
    return {c["id"]: c["verdict"] for c in o["checks"]}


def real(name):
    p = os.path.join(REAL_DIR, name)
    if not os.path.isfile(p):
        raise Skip(f"real file {p} not present")
    return p
