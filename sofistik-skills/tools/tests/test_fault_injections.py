"""Regression tests for reviewer A's fault injections FI-1..FI-5 (10_review_A.md).  Each one got through the
tools before the fix round; each must now FAIL / ESCALATE / RED."""
import copy
import json
import os

from _util import FIX, Skip, TOOLS, dump, ids, real, run, tmpdir

FI = os.path.join(FIX, "fi")
MIXED = os.path.join(FIX, "mini_mixed.dat")


def fi(name):
    return os.path.join(FI, name)


def test_FI1_aqb_only_member_buckling_now_fails():
    # AQB-only UB 254, 8 m unrestrained, AQB 0.50; hand 6.3 1.148 (top flange 1.30): was PASS exit 0
    d = tmpdir()
    code, o = run("member_check.py", "hand", fi("fi1_forces.json"), fi("fi1_overview.json"), fi("fi1_mr.json"),
                  "--member", "S12", "--lc", "102", "--workdir", d)
    if "sofrep not importable" in json.dumps(o):
        raise Skip("sofrep not importable")
    assert code == 1 and ids(o)["G7_bdk_hand_only"] == "FAIL", o["checks"]
    assert o["hand_bdk"] > 1.1


def test_FI2_top_flange_load_now_escalates():
    # BDK 0.86; hand shear centre 0.894, top flange 1.007: was PASS exit 0
    d = tmpdir()
    code, o = run("member_check.py", "hand", fi("fi1_forces.json"), fi("fi1_overview.json"), fi("fi2_mr.json"),
                  "--member", "7", "--lc", "102", "--workdir", d)
    if "sofrep not importable" in json.dumps(o):
        raise Skip("sofrep not importable")
    assert code == 2 and ids(o)["G7_bdk"] == "ESCALATE", o["checks"]
    assert o["load_height_rule"] == "max" and o["hand_bdk"] >= o["hand_bdk_top_flange"] > 1.0


def fi3_expected(d):
    e = json.load(open(fi("fi3_expected_old.json")))
    e["load_cases"]["21"]["gross_kN_xyz"] = [277.176, 0.0, 993.3943]
    return dump(d, "exp.json", e)


def test_FI3_lateral_short_now_fails():
    d = tmpdir()
    pe = fi3_expected(d)
    for f in ("fi3_lc_6kN.json", "fi3_lc_25kN.json"):          # 2.2 % and 9 % of the lateral wind
        code, o = run("equilibrium_check.py", fi(f), pe)
        assert code == 1 and ids(o)["E1_21"] == "FAIL", (f, o["checks"])
    code, o = run("equilibrium_check.py", fi("fi3_lc_6kN.json"), fi("fi3_expected_old.json"))
    assert code == 3                                            # old expected.json without gross_kN_xyz: refused


def test_FI3_real_expected_lc21():
    dat = real("26016_loads_unified.dat")
    d = tmpdir()
    pe = os.path.join(d, "expected.json")
    if not os.path.isdir("/mnt/project-files/26016/audit/generator"):
        raise Skip("generator not present")
    run("make_expected_26016.py", dat, pe)
    e = json.load(open(pe))["load_cases"]["21"]
    R = [-x for x in e["F_kN"]]
    R[0] += 6.0
    code, o = run("equilibrium_check.py", dump(d, "lc.json", {"rows": [{"lc": 21, "kind": 1,
                  "sum_reactions_kN": R, "has_results": ["nodes"]}]}), pe)
    assert ids(o)["E1_21"] == "FAIL"


def mixed_table(scale103=1.0):
    R = {1: [0, 0, 100.0], 2: [1.0, 0, 50.0], 3: [0, -2.0, 30.0]}
    R[101] = [1.35 * R[2][j] + 1.5 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    R[102] = list(R[101])
    R[103] = [scale103 * x for x in R[101]]                     # temperature adds no net reaction
    dl = {1: 1.0, 101: 1.35, 102: 1.35, 103: 1.35}
    return {"rows": [{"lc": n, "kind": 1, "dead_load_factors": [0, 0, -dl.get(n, 0.0)], "sum_reactions_kN": r,
                      "has_results": ["nodes"]} for n, r in R.items()]}


def test_FI4_mixed_combination_now_checked():
    d = tmpdir()
    code, o = run("combo_check.py", MIXED, dump(d, "ok.json", mixed_table()))
    assert ids(o)["C1_103"] == "PASS" and code == 2, o["checks"]          # C5 ESCALATE: temperature not proven
    code, o = run("combo_check.py", MIXED, dump(d, "bad.json", mixed_table(1.5)))
    assert code == 1 and ids(o)["C1_103"] == "FAIL"


def test_FI4_real_check_v2_136_137():
    dat = real("26016_check_v2.dat")
    if not os.path.isdir("/mnt/project-files/26016/audit/generator"):
        raise Skip("generator not present")
    import mutation_drill as MD
    d = tmpdir()
    pe = os.path.join(d, "expected.json")
    run("make_expected_26016.py", real("26016_loads_unified.dat"), pe)
    D = MD.Drill(dat, os.path.join(d, "w"), pe, 1, None)
    t = D.reactions()
    for r in t["rows"]:
        if r["lc"] in (136, 137):
            r["sum_reactions_kN"] = [x * 1.5 for x in r["sum_reactions_kN"]]
    code, o = run("combo_check.py", D.clean, dump(d, "lc.json", t), "--expected", pe)
    v = ids(o)
    assert code == 1 and v["C1_136"] == v["C1_137"] == "FAIL", [c for c in o["checks"] if c["verdict"] == "FAIL"][:3]


def test_FI5_scorecard_now_red():
    d = tmpdir()
    with open(fi("fi5_proofs.jsonl")) as f, open(os.path.join(d, "proofs.jsonl"), "w") as g:
        g.write(f.read())
    led = os.path.join(d, "LEDGER.md")
    with open(fi("fi5_LEDGER.md")) as f, open(led, "w") as g:
        g.write(f.read())
    code, o = run("scorecard.py", d)                     # LEDGER.md found without --ledger (A-17/B09)
    assert code == 1 and o["score"] == "RED", o
    txt = json.dumps(o["checks"])
    assert "not hand-checked" in txt and "utilisation > 1.0" in txt
    code, o = run("scorecard.py", d, "--ledger", led)
    assert code == 1


# ---------------------------------------------------------------- round 2 (10_review_A.md "Re-verification")
def _fi6_dat(d):
    src = real("26016_check_v2.dat")
    t = open(src, encoding="utf-8", errors="replace").read()
    a = "STO#GINF   1          $"
    b = "STO#GEQU   0.9        $"
    assert a in t and b in t
    t = t.replace(a, "STO#GINF   1.35          $", 1).replace(b, "STO#GEQU   1.1        $", 1)
    p = os.path.join(d, "v2_fault.dat")
    open(p, "w", encoding="utf-8").write(t)
    return p


def test_FI6_unfavourable_G_in_uplift_and_EQU_now_fails():
    # check_v2 with STO#GINF 1.35 (uplift 107-110) and STO#GEQU 1.1 (EQU 131-134): C4 was PASS (set membership)
    d = tmpdir()
    if not os.path.isdir("/mnt/project-files/26016/audit/generator"):
        raise Skip("generator not present")
    pe = os.path.join(d, "expected.json")
    run("make_expected_26016.py", real("26016_loads_unified.dat"), pe)
    bad = _fi6_dat(d)
    code, o = run("combo_check.py", bad, fi("fi6_lc_fault.json"), "--expected", pe)
    v = ids(o)
    for n in (107, 108, 109, 110, 131, 132, 133, 134):
        assert v[f"C4_{n}"] == "FAIL", (n, [c for c in o["checks"] if c["id"] == f"C4_{n}"])
    c107 = [c for c in o["checks"] if c["id"] == "C4_107"][0]
    assert c107["intended_compared"] and any("intended 1" in e for e in c107["errors"])
    assert code == 1
    # even without expected.json the title rule ('1.0G', '0.9G') catches it
    code, o = run("combo_check.py", bad, fi("fi6_lc_fault.json"))
    v = ids(o)
    assert v["C4_107"] == v["C4_131"] == "FAIL" and code == 1
    # the clean file: every classed combination equals its intended factors
    code, o = run("combo_check.py", real("26016_check_v2.dat"), fi("fi6_lc_ok.json"), "--expected", pe)
    c4 = [c for c in o["checks"] if c["id"].startswith("C4_")]
    assert len(c4) == 74 and all(c["verdict"] == "PASS" and c["intended_compared"] for c in c4), \
        [c for c in c4 if c["verdict"] != "PASS"][:3]


def test_FI6_intended_factors_mini():
    # mini.dat 102 = 1.35 G + 1.5 Q; expected says Q is intended at 1.05 (psi0 x 1.5): allowed, but not intended
    d = tmpdir()
    from _util import MINI
    R = {1: [0, 0, 100.0], 2: [1.0, 0, 50.0], 3: [0, -2.0, 30.0]}
    R[101] = [1.35 * R[2][j] + 1.35 * R[3][j] * 0 + 1.35 * R[1][j] for j in range(3)]
    t = {"rows": [{"lc": n, "kind": 1, "dead_load_factors": [0, 0, -(1.35 if n > 100 else (1.0 if n == 1 else 0))],
                   "sum_reactions_kN": r} for n, r in R.items()]}
    exp = {"load_cases": {}, "combination_factors": {"102": {"facd": 1.35, "copies": {"2": 1.35, "3": 1.05}}}}
    code, o = run("combo_check.py", MINI, dump(d, "lc.json", t), "--expected", dump(d, "e.json", exp))
    c = [c for c in o["checks"] if c["id"] == "C4_102"][0]
    assert c["verdict"] == "FAIL" and any("intended 1.05" in e for e in c["errors"]), c


def test_FI7_aqb_only_one_lc_no_longer_passes():
    # AQB-only S12 hand-checked only at LC 102 (6.3 = 0.398); member LC 145 has N = -400 kN (6.3 = 2.249)
    d = tmpdir()
    code, o = run("member_check.py", "hand", fi("fi7_f102.json"), fi("fi7_ov.json"), fi("fi7_mr.json"),
                  "--member", "S12", "--lc", "102", "--workdir", d)
    if "sofrep not importable" in json.dumps(o):
        raise Skip("sofrep not importable")
    c = [c for c in o["checks"] if c["id"] == "G7_bdk_hand_only"][0]
    assert code == 2 and c["verdict"] == "ESCALATE" and "give --extra-forces" in c["meaning"], o["checks"]
    code, o = run("member_check.py", "hand", fi("fi7_f102.json"), fi("fi7_ov.json"), fi("fi7_mr.json"),
                  "--member", "S12", "--lc", "102", "--extra-forces", fi("fi7_f145.json"), "--workdir", d)
    assert code == 1 and ids(o)["G7_bdk_hand_only"] == "FAIL" and o["all_member_lcs_checked"] is True
