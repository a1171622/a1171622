import json
import os

from _util import dump, ids, run, tmpdir

GATES = ("canary_check", "G2_protocol", "A7_run_identity", "equilibrium_check", "mutation_drill", "combo_check",
         "R6_member_lcs", "G6_alpha_cr", "coverage_census", "G8_plausibility", "A12_assumptions")


def test_receipts_add_audit_verify():
    d = tmpdir()
    raw = dump(d, "raw/lc.json", {"rows": [{"lc": 2, "sum_reactions_kN": [0.0, 0.0, 886.6139]}]})
    base = ["--value", "886.6139", "--unit", "kN", "--tool", "cdb_load_cases", "--args", '{"load_cases": "2"}',
            "--cdb", "x.cdb", "--cdb-mtime", "2026-10-18T00:00", "--raw", raw, "--workdir", d,
            "--path", "rows[0].sum_reactions_kN[2]"]
    code, o = run("receipts.py", "add", *base)
    assert code == 0 and o["receipt_id"] == "r1"
    bad = list(base)
    bad[1] = "886.6"
    code, o = run("receipts.py", "add", *bad)
    assert code == 1
    code, o = run("receipts.py", "audit", "--workdir", d, "--n", "5")
    assert code == 0 and o["recall"][0]["id"] == "r1"
    assert o["recall"][0]["mcp_call"] == 'cdb_load_cases(load_cases="2")'          # L10
    code, o = run("receipts.py", "verify", "--workdir", d, "--id", "r1", "--raw", raw)
    assert code == 0
    code, o = run("receipts.py", "add", "--workdir", d, "--value", "1")
    assert code == 3                                   # missing fields never defaulted


def test_receipts_help():
    import subprocess, sys
    from _util import TOOLS
    p = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "receipts.py"), "--help"], capture_output=True,
                       text=True)
    assert p.returncode == 0 and "audit" in p.stdout


def scorecard(lines, ledger):
    d = tmpdir()
    with open(os.path.join(d, "proofs.jsonl"), "w") as f:
        for o in lines:
            f.write(json.dumps(o) + "\n")
    if ledger is not None:
        with open(os.path.join(d, "ledger.md"), "w") as f:
            f.write(f"assumptions_agreed: {ledger}\n")
    return run("scorecard.py", d)


def clean():
    out = [{"tool": g, "verdict": "PASS", "checks": []} for g in GATES]
    out += [{"tool": "member_check", "action": "pick", "verdict": "PASS", "checks": [],
             "picks": [{"member": "10", "lc": 101}], "stats": {"n_eta_gt_1": 0}},
            {"tool": "member_check", "action": "hand", "member": "10", "lc": 101, "verdict": "PASS", "checks": []},
            {"tool": "receipts", "action": "audit", "verdict": "PASS", "checks": []}]
    return out


def test_scorecard_grades():
    code, o = scorecard(clean(), "yes")
    assert code == 0 and o["score"] == "GREEN"
    code, o = scorecard(clean(), None)
    assert code == 2 and o["score"] == "AMBER"          # never GREEN without agreed assumptions
    code, o = scorecard([x for x in clean() if x["tool"] != "G6_alpha_cr"], "yes")
    assert code == 1 and o["score"] == "RED"
    lines = clean() + [{"tool": "member_check", "action": "hand", "verdict": "FAIL", "checks": []}]
    code, o = scorecard(lines, "yes")
    assert code == 1
    code, o = scorecard([], "yes")
    assert code == 3
