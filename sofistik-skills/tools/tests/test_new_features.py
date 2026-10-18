"""Tests for the fix-round features (12_TRIAGE.md, Tools)."""
import copy
import json
import math
import os

from _util import MINI, TOOLS, Skip, dump, ids, run, tmpdir
from test_member_check import MR, OV, calib, eig_rows, forces


def test_A16_foreign_calibration_refused_without_test_env():
    d = tmpdir()
    c = calib(d, alpha_cr="omega")
    code, o = run("member_check.py", "alpha", dump(d, "lc.json", eig_rows([14.0])), "--buckling-lcs", "9201",
                  "--workdir", d, "--calibration", c, test_env=False)
    assert code == 3 and ids(o)["calibration_file"] == "CANNOT_RUN"


def test_A07_mesh_and_alpha():
    d = tmpdir()
    rows = [{"beam": 100 * s + k, "sln": s, "x": 0.0, "N": -10.0} for s in (10, 11, 12)
            for k in range(8 if s != 12 else 4)]
    bm = dump(d, "bm.json", {"lc": 101, "rows": rows, "truncated": False})
    code, o = run("member_check.py", "mesh", bm, "--dat", MINI, "--workdir", d)
    assert code == 2 and o["eigen_el_per_span"] == 4
    c = calib(d, alpha_cr="omega")
    code, o = run("member_check.py", "alpha", dump(d, "lc.json", eig_rows([14.0])), "--buckling-lcs", "9201",
                  "--beam-map", bm, "--workdir", d, "--calibration", c)
    assert ids(o)["G6_alpha_cr"] == "PASS" and ids(o)["G6_mesh"] == "ESCALATE"
    rows8 = [r for r in rows if r["sln"] != 12]
    bm8 = dump(d, "bm8.json", {"lc": 101, "rows": rows8, "truncated": False})
    code, o = run("member_check.py", "alpha", dump(d, "lc.json", eig_rows([14.0])), "--buckling-lcs", "9201",
                  "--beam-map", bm8, "--workdir", d, "--calibration", c)
    assert ids(o)["G6_mesh"] == "PASS"


def test_A13_compression_pick_own_lc_before_random():
    d = tmpdir()
    env = {"load_cases_found": [101, 102], "overall": {"N": {"min": {"value": -80.0, "lc": 101, "sln": 12}}}}
    code, o = run("member_check.py", "pick", dump(d, "mr.json", MR), dump(d, "env.json", env), "--seed", "x",
                  "--workdir", d)
    comp = [p for p in o["picks"] if "largest compression" in p["reason"]]
    assert len(comp) == 1 and comp[0]["member"] == "S12" and comp[0]["lc"] == 101
    assert o["picks"].index(comp[0]) < 3


def test_A14_extra_forces_all_member_lcs():
    d = tmpdir()
    po, pm = dump(d, "ov.json", OV), dump(d, "mr.json", MR)
    code, o = run("member_check.py", "hand", dump(d, "f1.json", forces()), po, pm, "--member", "10", "--lc",
                  "101", "--extra-forces", dump(d, "f2.json", forces(0.5, lc=102)), "--workdir", d)
    if "sofrep not importable" in json.dumps(o):
        raise Skip("sofrep not importable")
    assert o["all_member_lcs_checked"] is True and o["lcs_hand_checked"] == [101, 102] and code == 0, o["checks"]


def test_A22_fail_outranks_cannot_run():
    import _common as K
    assert K.worst("CANNOT_RUN", "FAIL") == "FAIL" and K.worst("ESCALATE", "CANNOT_RUN") == "CANNOT_RUN"


def test_A05_factor_not_en1990_fails():
    d = tmpdir()
    text = open(MINI).read().replace("COPY NO 3 FACT #GQ", "COPY NO 3 FACT 1.2")
    p = os.path.join(d, "bad.dat")
    open(p, "w").write(text)
    R = {1: [0, 0, 100.0], 2: [1.0, 0, 50.0], 3: [0, -2.0, 30.0]}
    R[101] = [1.35 * R[2][j] + 1.2 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    R[102] = [1.35 * R[2][j] + 1.5 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    dl = {1: 1.0, 101: 1.35, 102: 1.35}
    t = {"rows": [{"lc": n, "kind": 1, "dead_load_factors": [0, 0, -dl.get(n, 0)], "sum_reactions_kN": r}
                  for n, r in R.items()]}
    code, o = run("combo_check.py", p, dump(d, "lc.json", t))
    v = ids(o)
    assert code == 1 and v["C1_101"] == "PASS" and v["C4_101"] == "FAIL"


def test_A10_holding_down_sign_from_self_weight():
    d = tmpdir()
    env = {"overall": {"pz": {"max": {"value": 120.0, "lc": 201, "node": 5},
                              "min": {"value": -15.0, "lc": 131, "node": 9}}}}
    pe = dump(d, "env.json", env)
    up = dump(d, "lc_up.json", {"rows": [{"lc": 1, "kind": 1, "sum_reactions_kN": [0, 0, 500.0]}]})
    code, o = run("holding_down.py", up, pe)               # Z up (GDIR NEGZ): uplift = pz < 0
    assert code == 2 and o["uplift_kN"] == 15.0 and o["uplift_lc"] == 131
    dn = dump(d, "lc_dn.json", {"rows": [{"lc": 1, "kind": 1, "sum_reactions_kN": [0, 0, -500.0]}]})
    code, o = run("holding_down.py", dn, pe)               # Z down (GDIR POSZ): uplift = pz > 0
    assert code == 2 and o["uplift_kN"] == 120.0 and o["uplift_lc"] == 201
    env2 = {"overall": {"pz": {"max": {"value": 120.0, "lc": 201}, "min": {"value": 3.0, "lc": 1}}}}
    code, o = run("holding_down.py", up, dump(d, "env2.json", env2))
    assert code == 0


def test_A23_calibrate_bdk():
    d = tmpdir()
    recs = [{"m_nr": i, "m_scbn": 0.1 * i, "m_tcf": 0.05 * i, "m_scn": 0.2} for i in range(1, 7)]
    pg = dump(d, "p.json", {"kwh": 127, "kwl": 9100, "kexist": 2, "record_count": 6, "records": recs})
    prt = {str(i): [round(0.1 * i, 3), "nm-y" if i % 2 else "m-y"] for i in range(1, 6)}
    code, o = run("member_check.py", "calibrate-bdk", "--bdk", pg, "--prt", json.dumps(prt), "--workdir", d)
    assert code == 0 and o["paste_into_calibration_json"]["bdk"]["eta_field"] == "m_scbn"
    few = {k: v for k, v in list(prt.items())[:3]}
    code, o = run("member_check.py", "calibrate-bdk", "--bdk", pg, "--prt", json.dumps(few), "--workdir", d)
    assert code == 3


def test_L9_server_lifetime_uncalibrated():
    c = json.load(open(os.path.join(TOOLS, "calibration.json")))
    assert c["server_lifetime"]["status"] == "UNCALIBRATED" and "get_job_result" in c["server_lifetime"]["how"]
    assert c["ltb_load_height"]["status"] == "UNCALIBRATED"


def test_A18_receipt_path_required():
    d = tmpdir()
    raw = dump(d, "raw.json", {"overall": {"N": {"min": {"value": -812.0}, "max": {"value": 812.0}}}})
    base = ["add", "--workdir", d, "--value", "-812", "--unit", "kN", "--tool", "cdb_envelope", "--args",
            '{"load_cases": "101-154", "what": "beam"}', "--cdb", "x.cdb", "--cdb-mtime", "t", "--raw", raw]
    code, o = run("receipts.py", *base)
    assert code == 3                                        # no --path
    code, o = run("receipts.py", *base, "--path", "overall.N.max.value")
    assert code == 1                                        # number exists, but not at that path
    code, o = run("receipts.py", *base, "--path", "overall.N.min.value")
    assert code == 0


def test_FEX2_every_eta_ge_0_9_picked_never_capped():
    d = tmpdir()
    mr = copy.deepcopy(MR)
    base = mr["members"][0]
    ms = []
    for i in range(30):                      # 30 members at eta 0.90-0.99 plus the originals
        m = copy.deepcopy(base)
        m.update(member=f"H{i}", slns=[5000 + i], eta_bdk=round(0.90 + 0.003 * i, 3), eta_aqb=None, lc_bdk=101)
        ms.append(m)
    lo = copy.deepcopy(base)
    lo.update(member="L1", slns=[6000], eta_bdk=0.2, eta_aqb=None, lc_bdk=101)
    mr["members"] = ms + [lo] + [m for m in mr["members"] if (m.get("eta_bdk") or 0) < 0.9 and (m.get("eta_aqb") or 0) < 0.9]
    env = {"load_cases_found": [101], "overall": {"N": {"min": {"value": -80.0, "lc": 101, "sln": 6000}}}}
    code, o = run("member_check.py", "pick", dump(d, "mr.json", mr), dump(d, "env.json", env), "--seed", "x",
                  "--workdir", d)
    v = ids(o)
    picked = {p["member"] for p in o["picks"]}
    assert {f"H{i}" for i in range(30)} <= picked, sorted(picked)
    assert v["G7_high_eta_picked"] == "PASS" and v["G7_picks_over_cap"] == "ESCALATE" and code == 2
    # under the cap: high-eta members picked, no over-cap escalation
    mr2 = copy.deepcopy(mr)
    mr2["members"] = ms[:5] + mr2["members"][30:]
    code, o = run("member_check.py", "pick", dump(d, "mr2.json", mr2), dump(d, "env.json", env), "--seed", "x",
                  "--workdir", d)
    v = ids(o)
    assert {f"H{i}" for i in range(5)} <= {p["member"] for p in o["picks"]}
    assert "G7_picks_over_cap" not in v and v["G7_high_eta_picked"] == "PASS"


def test_mesh_compression_default_and_fail_closed():
    """Round 2: the mesh check measures members in compression by default (short chords in bending do not block
    alpha_cr); with no forces at all it fails closed."""
    d = tmpdir()
    rows = [{"beam": 100 * s + k, "sln": s, "x": 0.0, "N": (-50.0 if s != 12 else 5.0)} for s in (10, 11, 12)
            for k in range(8 if s != 12 else 3)]
    bm = dump(d, "bm.json", {"lc": 102, "rows": rows, "truncated": False})
    code, o = run("member_check.py", "mesh", bm, "--dat", MINI, "--workdir", d)
    assert code == 0 and o["eigen_el_per_span"] == 8 and "own LC 102" in o["mesh_basis"], o
    code, o = run("member_check.py", "mesh", bm, "--dat", MINI, "--all-members", "--workdir", d)
    assert code == 2 and o["eigen_el_per_span"] == 3
    f = dump(d, "f.json", {"lc": 145, "rows": [{"beam": 1200, "sln": 12, "x": 0.0, "N": -400.0}]})
    code, o = run("member_check.py", "mesh", bm, "--dat", MINI, "--compression-forces", f, "--workdir", d)
    assert code == 2 and o["eigen_el_per_span"] == 3                 # SLN 12 in compression under LC 145
    nof = dump(d, "bm_nof.json", {"lc": 102, "rows": [{k: v for k, v in r.items() if k != "N"} for r in rows],
                                  "truncated": False})
    code, o = run("member_check.py", "mesh", nof, "--dat", MINI, "--workdir", d)
    assert code == 2 and "fail closed" in json.dumps(o["checks"])
