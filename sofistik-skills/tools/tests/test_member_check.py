import copy
import json
import math
import os

from _util import MINI, TOOLS, Skip, dump, ids, real, run, tmpdir


def calib(d, **status):
    with open(os.path.join(TOOLS, "calibration.json")) as f:
        c = json.load(f)
    for k, v in status.items():
        c[k]["status"] = "CALIBRATED"
        if v:
            c[k]["rule"] = v
    return dump(d, "calib.json", c)


def eig_rows(lams, first=9201):
    return {"rows": [{"lc": first + i, "title": "buckling", "kind": 4, "kind_name": "eigen", "action": "",
                      "mode": i + 1, "frequency_Hz": round(l / (2 * math.pi), 5), "period_s": 1.0,
                      "has_results": ["nodes"]} for i, l in enumerate(lams)], "cdb": "x.cdb"}


def test_shipped_calibration_is_uncalibrated_and_alpha_refuses():
    d = tmpdir()
    code, o = run("member_check.py", "alpha", dump(d, "lc.json", eig_rows([12.0, 15.0])), "--buckling-lcs",
                  "9201-9202", "--workdir", d)
    assert code == 3 and o["alpha_cr_min"] == "UNCALIBRATED"


def test_alpha_with_test_calibration():
    d = tmpdir()
    c = calib(d, alpha_cr="omega")
    code, o = run("member_check.py", "alpha", dump(d, "lc.json", eig_rows([14.0, 12.5, 30.0])), "--buckling-lcs",
                  "9201-9203", "--workdir", d, "--calibration", c)
    assert ids(o)["G6_alpha_cr"] == "PASS" and abs(o["alpha_cr_min"] - 12.5) < 1e-3 and o["alpha_cr_lc"] == 9202
    assert code == 2                                  # non-default calibration file -> never a clean PASS
    code, o = run("member_check.py", "alpha", dump(d, "lc2.json", eig_rows([4.0, 30.0])), "--buckling-lcs",
                  "9201-9203", "--workdir", d, "--calibration", c)
    assert ids(o)["G6_alpha_cr"] == "ESCALATE" and ids(o)["G6_buckling_lcs"] == "FAIL" and code == 1


def test_calibrate_alpha_be13():
    d = tmpdir()
    lc = eig_rows([38.553, 38.553, 154.215, 154.215], first=101)
    code, o = run("member_check.py", "calibrate-alpha", dump(d, "be13.json", lc), "--workdir", d)
    assert code == 0 and o["paste_into_calibration_json"]["alpha_cr"]["rule"] == "omega"


def forces(scale=1.0, lc=101):
    L, w, rows = 6.0, 20.0 * scale, []
    for e in range(3):
        for k in range(5):
            xl = k * 0.5
            x = e * 2 + xl
            rows.append({"beam": 101 + e, "sln": 10 if e < 2 else 11, "group": 1, "x": xl, "N": -50.0, "Vy": 0.0,
                         "Vz": w * (L / 2 - x), "Mt": 0.0, "My": w * x * (L - x) / 2, "Mz": 0.0})
    return {"lc": lc, "rows": rows, "truncated": False}


OV = {"sections": [{"nr": 2, "title": "UB 254x146x43", "A_cm2": 54.77, "Iy_cm4": 6544.0, "Iz_cm4": 677.0}]}
MR = {"member_lcs": [101, 102], "members": [
    {"member": "10", "slns": [10, 11], "section": "UB 254x146x43", "section_nr": 2, "material": "S 275",
     "cy_fix_from_start_m": [3.0], "eta_bdk": 0.735, "lc_bdk": None, "eta_aqb": 0.578, "lc_aqb": 101},
    {"member": "S12", "slns": [12], "section": "UB 254x146x43", "section_nr": 2, "material": "S 275",
     "cy_fix_from_start_m": [], "eta_bdk": None, "lc_bdk": None, "eta_aqb": 0.2, "lc_aqb": 102}]}


def test_hand_pass_marginal_fail_nc():
    d = tmpdir()
    po, pm = dump(d, "ov.json", OV), dump(d, "mr.json", MR)
    code, o = run("member_check.py", "hand", dump(d, "f.json", forces()), po, pm, "--member", "10", "--lc", "101",
                  "--workdir", d)
    if "sofrep not importable" in json.dumps(o):
        raise Skip("sofrep not importable")
    assert code == 0, o["checks"]
    assert abs(o["hand_aqb"] - 0.578) < 0.01 and o["length_m"] == 6.0 and o["L_LT_m"] == 3.0
    m2 = copy.deepcopy(MR)
    m2["members"][0].update(eta_aqb=0.95)
    code, o = run("member_check.py", "hand", dump(d, "f.json", forces()), po, dump(d, "m2.json", m2), "--member",
                  "10", "--lc", "101", "--workdir", d)
    assert code == 2                                   # marginal 0.9-1.1
    m3 = copy.deepcopy(MR)
    m3["members"][0].update(eta_aqb=1.27, eta_bdk=1.62)
    code, o = run("member_check.py", "hand", dump(d, "f3.json", forces(2.2)), po, dump(d, "m3.json", m3),
                  "--member", "10", "--lc", "101", "--workdir", d)
    assert code == 1, o["checks"]
    code, o = run("member_check.py", "hand", dump(d, "f4.json", forces(lc=102)), po, pm, "--member", "10", "--lc",
                  "101", "--workdir", d)
    assert code == 1 and ids(o)["G7_forces_lc"] == "FAIL"
    code, o = run("member_check.py", "hand", dump(d, "f5.json", {"error": "No beam results for load case 101"}),
                  po, pm, "--member", "10", "--lc", "101", "--workdir", d)
    assert code == 3
    m6 = copy.deepcopy(MR)
    del m6["members"][0]["eta_aqb"]
    code, o = run("member_check.py", "hand", dump(d, "f.json", forces()), po, dump(d, "m6.json", m6), "--member",
                  "10", "--lc", "101", "--workdir", d)
    assert code == 3 and "eta_aqb" in json.dumps(o)


def test_pick():
    d = tmpdir()
    env = {"load_cases_found": [101, 102], "overall": {"N": {"min": {"value": -80.0, "lc": 102, "sln": 12}}}}
    a = ["pick", dump(d, "mr.json", MR), dump(d, "env.json", env), "--seed", "run7", "--workdir", d]
    code, o = run("member_check.py", *a)
    assert code == 0
    assert [p["member"] for p in o["picks"]] == ["10", "S12"]
    assert o["picks"][1]["reason"].count("largest compression") == 1
    assert o["stats"] == {"n_members": 2, "eta_max": 0.735, "eta_min": 0.2, "n_eta_gt_1": 0, "lc_outside_set": [],
                          "members_gt_1": []}
    code2, o2 = run("member_check.py", *a)
    assert o2["picks"] == o["picks"]                   # seeded: same run id, same picks
    env["load_cases_found"] = [101, 102, 131]
    code, o = run("member_check.py", "pick", a[1], dump(d, "env2.json", env), "--seed", "run7", "--workdir", d)
    assert code == 2 and o["stats"]["lc_outside_set"] == [131]


def test_collect_and_census_mini():
    d = tmpdir()
    c = calib(d, bdk=None, aqb=None)
    bdk = dump(d, "bdk.json", {"kwh": 127, "kwl": 9100, "kexist": 2, "record_count": 2,
                               "records": [{"m_nr": 0, "m_scbn": 0}, {"m_nr": 10, "m_scbn": 0.7}]})
    aq = [dump(d, f"aqb{lc}.json", {"kwh": 107, "kwl": lc, "kexist": 2, "record_count": 3,
                                    "records": [{"m_nr": 101, "m_tcf": 0.5}, {"m_nr": 103, "m_tcf": 0.6 if lc == 102 else 0.1},
                                                {"m_nr": 120, "m_tcf": 0.3}]}) for lc in (101, 102)]
    bm = dump(d, "bm.json", {"lc": 101, "rows": [{"beam": 101, "sln": 10}, {"beam": 103, "sln": 11},
                                                  {"beam": 120, "sln": 12}], "truncated": False})
    code, o = run("member_check.py", "collect", "--dat", MINI, "--bdk", bdk, "--aqb", *aq, "--beam-map", bm,
                  "--workdir", d, "--calibration", c)
    assert code == 2 and ids(o)["H1_collect"] == "PASS", o["checks"]
    mr = json.load(open(os.path.join(d, "member_results.json")))
    m10 = next(m for m in mr["members"] if m["member"] == "10")
    assert m10["eta_bdk"] == 0.7 and m10["eta_aqb"] == 0.6 and m10["lc_aqb"] == 102 and m10["slns"] == [10, 11]
    code, o = run("coverage_census.py", MINI, os.path.join(d, "checked_members.json"))
    assert code == 2 and ids(o)["H1_aqb_only_reason"] == "ESCALATE", o["checks"]   # A-04: no reason given
    ex = dump(d, "excl.json", {"excluded": {}, "aqb_only_reasons": {"12": "stub, LTB negligible (lead)"}})
    code, o = run("member_check.py", "collect", "--dat", MINI, "--bdk", bdk, "--aqb", *aq, "--beam-map", bm,
                  "--excluded", ex, "--workdir", d, "--calibration", c)
    code, o = run("coverage_census.py", MINI, os.path.join(d, "checked_members.json"))
    assert code == 0, o["checks"]
    half = dump(d, "bdk_half.json", {"kwh": 127, "kwl": 9100, "kexist": 2, "record_count": 3,
                                     "records": [{"m_nr": 10, "m_scbn": 0.7}]})
    code, o = run("member_check.py", "collect", "--dat", MINI, "--bdk", half, "--aqb", *aq, "--beam-map", bm,
                  "--workdir", d, "--calibration", c)
    assert code == 3 and "read every page" in json.dumps(o)
    code, o = run("member_check.py", "collect", "--dat", MINI, "--bdk", bdk, "--aqb", *aq, "--beam-map", bm,
                  "--workdir", d)
    assert code == 3                                   # shipped calibration is UNCALIBRATED


def test_collect_real_check_v2_needs_every_page():
    dat = real("26016_check_v2.dat")
    d = tmpdir()
    c = calib(d, bdk=None, aqb=None)
    bdk = dump(d, "bdk.json", {"kwh": 127, "kwl": 9100, "kexist": 2, "record_count": 312,
                               "records": [{"m_nr": i, "m_scbn": 0.5} for i in range(200)]})
    code, o = run("member_check.py", "collect", "--dat", dat, "--bdk", bdk, "--aqb", bdk, "--beam-map", bdk,
                  "--workdir", d, "--calibration", c)
    assert code == 3
