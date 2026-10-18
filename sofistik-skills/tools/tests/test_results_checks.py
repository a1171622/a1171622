import copy

from _util import MINI, dump, ids, run, tmpdir
from mutation_drill import Drill


def lc_table():
    # R = force of the supports on the structure; LC1 self weight, 2 SDL, 3 live
    R = {1: [0, 0, 100.0], 2: [1.0, 0, 50.0], 3: [0, -2.0, 30.0]}
    R[101] = [1.35 * R[2][j] + 1.5 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    R[102] = [1.35 * R[2][j] + 1.5 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    dl = {1: 1.0, 101: 1.35, 102: 1.35}
    return {"rows": [{"lc": n, "title": "", "kind": 1, "kind_name": "calculated", "factor": 1.0,
                      "dead_load_factors": [0, 0, -dl.get(n, 0.0)], "sum_reactions_kN": r,
                      "has_results": ["nodes"]} for n, r in R.items()], "cdb": "mini.cdb"}


def test_combo_check_pass_and_fail():
    d = tmpdir()
    t = lc_table()
    code, o = run("combo_check.py", MINI, dump(d, "lc.json", {"result": t}), "--workdir", d)
    v = ids(o)
    assert code == 2 and v["C1_101"] == v["C1_102"] == v["C4_101"] == v["C4_102"] == "PASS", o["checks"]
    assert v["C5_self_equilibrating"] == "ESCALATE"     # no --expected: blind spot stated, never PASS
    t2 = copy.deepcopy(t)
    t2["rows"][3]["sum_reactions_kN"][2] *= 1.01
    code, o = run("combo_check.py", MINI, dump(d, "lc2.json", t2))
    assert code == 1 and ids(o)["C1_101"] == "FAIL"
    t3 = copy.deepcopy(t)
    t3["rows"][3]["dead_load_factors"] = [0, 0, -1.5]
    code, o = run("combo_check.py", MINI, dump(d, "lc3.json", t3))
    assert code == 1 and ids(o)["C1_101"] == "FAIL"


def test_combo_check_missing_field_cannot_run():
    d = tmpdir()
    t = lc_table()
    del t["rows"][1]["sum_reactions_kN"]
    code, o = run("combo_check.py", MINI, dump(d, "lc.json", t))
    assert code == 1 and "sum_reactions_kN missing" in str(o["checks"])


def test_equilibrium():
    d = tmpdir()
    exp = {"load_cases": {"2": {"F_kN": [-1.0, 0, -50.0], "gross_kN": 50.0, "gross_kN_xyz": [1.0, 0, 50.0],
                                "kind": "applied"},
                          "3": {"F_kN": [0, 2.0, -30.0], "gross_kN": 30.0, "gross_kN_xyz": [0, 2.0, 30.0],
                                "kind": "applied"},
                          "17": {"F_kN": [0, 0, 0], "gross_kN": 40.0, "gross_kN_xyz": [40.0, 0, 0], "kind": "applied"}},
           "not_expected": {"1": "self weight: estimate"}, "combinations": [101, 102]}
    t = lc_table()
    t["rows"].append({"lc": 17, "kind": 1, "sum_reactions_kN": [0, 0, 0.01], "has_results": ["nodes"]})
    pe = dump(d, "exp.json", exp)
    code, o = run("equilibrium_check.py", dump(d, "lc.json", t), pe)
    v = ids(o)
    assert v["E1_2"] == "PASS" and v["E1_3"] == "PASS"
    assert v["E1_17"] == "ESCALATE"          # vacuous: net applied load 0
    assert v["E1_1"] == "ESCALATE"           # calculated, no expected value
    assert o["delegated_to_combo_check"] == [101, 102]
    t["rows"][1]["sum_reactions_kN"] = [1.0, 0, -50.0]   # sign flipped
    code, o = run("equilibrium_check.py", dump(d, "lc2.json", t), pe)
    assert code == 1 and ids(o)["E1_2"] == "FAIL"


def test_canary():
    d = tmpdir()
    clean = Drill.canary_clean()
    code, o = run("canary_check.py", dump(d, "c.json", clean), "--workdir", d)
    assert code == 0, [c for c in o["checks"] if c["verdict"] != "PASS"]
    bad = copy.deepcopy(clean)
    bad["g0_support_lc1"]["rows"][0]["pz"] = 1.0
    code, o = run("canary_check.py", dump(d, "c2.json", bad))
    assert code == 1 and ids(o)["K3_support_lc1_pz"] == "FAIL"
    miss = copy.deepcopy(clean)
    del miss["g0_load_cases_1_2"]                    # A-24: the load-case sums are required
    code, o = run("canary_check.py", dump(d, "c3.json", miss))
    assert code == 3


def test_coverage_census():
    d = tmpdir()
    ok = {"source": "t", "bdk_checked": [10], "aqb_checked_slns": [12], "excluded": {},
          "aqb_only_reasons": {"G1": "short chord, LTB negligible (lead)"}}
    code, o = run("coverage_census.py", MINI, dump(d, "ok.json", ok))
    assert code == 0, o["checks"]
    code, o = run("coverage_census.py", MINI, dump(d, "b.json", dict(ok, aqb_checked_slns=[])))
    assert code == 1 and ids(o)["H1_unaccounted"] == "FAIL"
    code, o = run("coverage_census.py", MINI, dump(d, "c.json", dict(ok, aqb_checked_slns=[],
                                                                       excluded={"12": "stub 0.1 m"})))
    assert code == 0
    code, o = run("coverage_census.py", MINI, dump(d, "e.json", {"bdk_checked": [10]}))
    assert code == 3
    no_reason = dict(ok)
    del no_reason["aqb_only_reasons"]                  # A-04: AQB-only without a reason -> ESCALATE
    code, o = run("coverage_census.py", MINI, dump(d, "nr.json", no_reason))
    assert code == 2 and ids(o)["H1_aqb_only_reason"] == "ESCALATE"


def test_make_expected_26016_real():
    import json
    import os
    from _util import Skip, real
    dat = real("26016_loads_unified.dat")
    if not os.path.isdir("/mnt/project-files/26016/audit/generator"):
        raise Skip("generator not present")
    d = tmpdir()
    out = os.path.join(d, "expected.json")
    code, o = run("make_expected_26016.py", dat, out)
    assert code == 0, o["checks"]
    e = json.load(open(out))["load_cases"]
    assert abs(e["2"]["F_kN"][2] - (-886.6)) < 0.05          # 26016_load_audit.md Appendix A
    assert abs(e["11"]["F_kN"][2] - (-2160.7)) < 0.05
    assert abs(e["17"]["gross_kN"] - 450.1) < 0.05
