"""End-to-end scorecard test (15_final_check.md M1/F1): proofs.jsonl is produced ONLY by running the scripts on
fixtures, the way the skills run them (the five gates that have no script are written with the skills' P-PROOF
echo template).  Expected: AMBER while the assumptions are not agreed, GREEN when agreed, RED when one input is
swapped for another run's (.dat or .cdb).

The tools are copied to a temp folder whose calibration.json is set CALIBRATED (the shipped file is never edited and
no --calibration is passed), so every script runs exactly as on a real, calibrated project."""
import copy
import glob
import json
import os
import shutil
import subprocess
import sys

from _util import FIX, MINI, TOOLS, Skip, dump, tmpdir

SOFREP = "/mnt/project-files/reports/sofistik_report"


def _tools_copy(d):
    t = os.path.join(d, "T")
    os.makedirs(t)
    for p in glob.glob(os.path.join(TOOLS, "*.py")) + [os.path.join(TOOLS, "calibration.json")]:
        shutil.copy(p, t)
    c = json.load(open(os.path.join(t, "calibration.json")))
    c["alpha_cr"].update(status="CALIBRATED", rule="omega", evidence="e2e test")
    c["bdk"].update(status="CALIBRATED", evidence="e2e test")
    c["aqb"].update(status="CALIBRATED", evidence="e2e test")
    json.dump(c, open(os.path.join(t, "calibration.json"), "w"), indent=1)
    return t


def _run(T, script, *args, ok=(0,)):
    env = dict(os.environ)
    env.pop("TOOLS_TEST", None)                       # exactly as Haiku runs them
    p = subprocess.run([sys.executable, "-I", os.path.join(T, script)] + [str(a) for a in args],
                       capture_output=True, text=True, timeout=600, env=env)
    o = json.loads(p.stdout.strip().splitlines()[-1])
    assert p.returncode in ok, f"{script} {args[:2]} exit {p.returncode}: " + json.dumps(
        [c for c in o.get("checks", []) if c.get("verdict") != "PASS"])[:1500]
    return p.returncode, o


def _pproof(W, gate, verdict, expected, got):
    # results-proof SKILL.md P-PROOF template, run through the shell like the skill does
    line = json.dumps({"tool": gate, "verdict": verdict, "checks": [{"id": gate, "verdict": verdict,
                                                                      "expected": expected, "got": got,
                                                                      "raw": "W/raw/x.json"}], "notes": []})
    subprocess.run(["bash", "-c", f"echo '{line}' >> '{os.path.join(W, 'proofs.jsonl')}'"], check=True)


def _member_forces(lc, slns, beams, w, n=-20.0, L=6.0):
    rows = []
    per = L / len(beams)
    for e, (b, s) in enumerate(zip(beams, slns)):
        for k in range(3):
            xl = k * per / 2
            x = e * per + xl
            rows.append({"beam": b, "sln": s, "group": 1, "x": xl, "N": n, "Vy": 0.0, "Vz": w * (L / 2 - x),
                         "Mt": 0.0, "My": w * x * (L - x) / 2, "Mz": 0.0})
    return {"lc": lc, "rows": rows, "truncated": False}


def _build(d):
    """Run the whole proof chain once; returns (W, T, files)."""
    T = _tools_copy(d)
    W = os.path.join(d, "W")
    os.makedirs(os.path.join(W, "raw"))
    raw = os.path.join(W, "raw")
    # master M #INCLUDEs mini.dat (cloud copy in W/src), expanded into X
    os.makedirs(os.path.join(W, "src"))
    shutil.copy(MINI, os.path.join(W, "src", "mini.dat"))
    M, X = os.path.join(W, "m.dat"), os.path.join(W, "m_expanded.dat")
    open(M, "w").write("$ master (e2e)\n#INCLUDE mini.dat\n")
    tsv = os.path.join(W, "sources.tsv")
    open(tsv, "w").write(f"mini.dat\t{os.path.join(W, 'src', 'mini.dat')}\nm.dat\t{M}\n")
    _run(T, "expand_master.py", M, X, tsv, "--workdir", W)
    _run(T, "dat_lint.py", M, "--sources", tsv, "--uls", "101-102", "--workdir", W)
    # G0 canary (selftest results)
    import mutation_drill as MD
    _run(T, "canary_check.py", dump(raw, "selftest.json", MD.Drill.canary_clean()), "--workdir", W)
    _pproof(W, "G2_protocol", "PASS", "ok", "ok")
    _pproof(W, "A7_run_identity", "PASS", "RUNID e2e-a1", "RUNID e2e-a1")
    # G4 / G5 on the load cases of the run (.cdb mini.cdb)
    R = {1: [0.0, 0.0, 100.0], 2: [0.0, 0.0, 50.0], 3: [0.0, 0.0, 30.0]}
    R[101] = [1.35 * R[2][j] + 1.5 * R[3][j] + 1.35 * R[1][j] for j in range(3)]
    R[102] = list(R[101])
    dl = {1: 1.0, 101: 1.35, 102: 1.35}
    lcs = {"rows": [{"lc": n, "title": "", "kind": 1, "kind_name": "calculated", "factor": 1.0,
                     "dead_load_factors": [0, 0, -dl.get(n, 0.0)], "sum_reactions_kN": r, "has_results": ["nodes"]}
                    for n, r in R.items()], "cdb": "C:\\p\\mini.cdb"}
    plc = dump(raw, "load_cases.json", lcs)
    exp = {"load_cases": {"2": {"F_kN": [0, 0, -50.0], "gross_kN": 50.0, "gross_kN_xyz": [0, 0, 50.0],
                                "kind": "applied", "title": "SDL"},
                          "3": {"F_kN": [0, 0, -30.0], "gross_kN": 30.0, "gross_kN_xyz": [0, 0, 30.0],
                                "kind": "applied", "title": "live"}},
           "not_expected": {"1": "self-weight"}, "selfweight_lcs": [1], "combinations": [101, 102]}
    pe = dump(W, "expected.json", exp)
    _run(T, "equilibrium_check.py", plc, pe, "--workdir", W)
    _run(T, "combo_check.py", X, plc, "--expected", pe, "--workdir", W)
    _run(T, "mutation_drill.py", X, "--workdir", W, "--expected", pe)
    _pproof(W, "R6_member_lcs", "PASS", "101-102", "all present")
    # G6 alpha_cr with the mesh from the beam map (8 elements per compression SLN)
    bm_rows = [{"beam": b, "sln": s, "x": x, "N": -10.0} for s, b0 in ((10, 101), (11, 111), (12, 121))
               for b in range(b0, b0 + 8) for x in (0.0, 0.75)]
    bm = dump(raw, "beam_map.json", {"lc": 101, "rows": bm_rows, "truncated": False, "cdb": "C:\\p\\mini.cdb"})
    import math
    eig = {"rows": [{"lc": 9201 + i, "title": "buckling", "kind": 4, "kind_name": "eigen", "action": "",
                     "mode": i + 1, "frequency_Hz": round(l / (2 * math.pi), 5), "period_s": 1.0,
                     "has_results": ["nodes"]} for i, l in enumerate([14.0, 22.0])], "cdb": "C:\\p\\mini.cdb"}
    _run(T, "member_check.py", "alpha", dump(raw, "buckling_lcs.json", eig), "--buckling-lcs", "9201-9202",
         "--beam-map", bm, "--dat", X, "--workdir", W)
    # hand values first (they set the fixture utilisations, so SOFiSTiK and hand agree as in a sound run)
    ov = dump(raw, "overview.json", {"sections": [{"nr": 2, "title": "UB 254x146x43", "A_cm2": 54.77,
                                                   "Iy_cm4": 6544.0, "Iz_cm4": 677.0}]})
    f10 = {lc: dump(raw, f"g7_10_{lc}.json", _member_forces(lc, [10, 10, 11], [101, 102, 111], w))
           for lc, w in ((101, 8.0), (102, 6.0))}
    f12 = {lc: dump(raw, f"g7_S12_{lc}.json", _member_forces(lc, [12, 12], [121, 122], w, n=n, L=3.0))
           for lc, w, n in ((101, 4.0, -5.0), (102, 6.0, -20.0))}
    return T, W, raw, X, M, plc, pe, bm, ov, f10, f12


def _members(T, W, raw, X, bm, ov, f10, f12):
    """collect -> census -> pick -> hand, with utilisations taken from a first hand pass."""
    probe = os.path.join(os.path.dirname(W), "probe")
    os.makedirs(probe, exist_ok=True)
    mr0 = {"member_lcs": [101, 102], "members": [
        {"member": "10", "slns": [10, 11], "section": "UB 254x146x43", "section_nr": 2, "material": "S 275",
         "cy_fix_from_start_m": [], "eta_bdk": 0.5, "lc_bdk": None, "eta_aqb": 0.5, "lc_aqb": 101},
        {"member": "S12", "slns": [12], "section": "UB 254x146x43", "section_nr": 2, "material": "S 275",
         "cy_fix_from_start_m": [], "eta_bdk": None, "lc_bdk": None, "eta_aqb": 0.5, "lc_aqb": 102}]}
    pm0 = dump(probe, "mr0.json", mr0)
    code, o10 = _run(T, "member_check.py", "hand", f10[101], ov, pm0, "--member", "10", "--lc", "101",
                     "--extra-forces", f10[102], "--workdir", probe, ok=(0, 1, 2, 3))
    if "sofrep not importable" in json.dumps(o10):
        raise Skip("sofrep not importable")
    _, o12 = _run(T, "member_check.py", "hand", f12[102], ov, pm0, "--member", "S12", "--lc", "102",
                  "--extra-forces", f12[101], "--workdir", probe, ok=(0, 1, 2, 3))
    a10 = {lc: v["aqb"] for lc, v in o10["per_lc"].items()}
    a12 = {lc: v["aqb"] for lc, v in o12["per_lc"].items()}
    # BDK page (member 10) and AQB pages per LC (beam records of the SLNs)
    bdk = dump(raw, "bdk_p0.json", {"kwh": 127, "kwl": 9100, "kexist": 2, "record_count": 1,
                                    "records": [{"m_nr": 10, "m_scbn": round(o10["hand_bdk"], 3)}]})
    aqb = []
    for lc in (101, 102):
        recs = [{"m_nr": 101, "m_tcf": round(a10[str(lc)], 3)}, {"m_nr": 121, "m_tcf": round(a12[str(lc)], 3)}]
        aqb.append(dump(raw, f"aqb_{lc}_p0.json", {"kwh": 107, "kwl": lc, "kexist": 2, "record_count": 2,
                                                   "records": recs}))
    ex = dump(W, "excluded.json", {"excluded": {}, "aqb_only_reasons": {"12": "stub (lead, e2e)"}})
    # member 10 is BDK MEMB SLN 10 + CONT 11 in mini.dat
    _run(T, "member_check.py", "collect", "--dat", X, "--bdk", bdk, "--aqb", *aqb, "--beam-map", bm,
         "--excluded", ex, "--workdir", W)
    _run(T, "coverage_census.py", X, os.path.join(W, "checked_members.json"), "--workdir", W)
    env = {"load_cases_found": [101, 102], "overall": {"N": {"min": {"value": -20.0, "lc": 102, "sln": 12}}}}
    _, pk = _run(T, "member_check.py", "pick", os.path.join(W, "member_results.json"),
                 dump(raw, "env_uls_beam.json", env), "--seed", "e2e", "--workdir", W)
    F = {"10": f10, "S12": f12}
    for p in pk["picks"]:
        lc = int(p["lc"])
        other = [F[p["member"]][x] for x in (101, 102) if x != lc]
        _run(T, "member_check.py", "hand", F[p["member"]][lc], ov, os.path.join(W, "member_results.json"),
             "--member", p["member"], "--lc", lc, "--extra-forces", *other, "--workdir", W)


def _finish(T, W, raw, plc, agreed):
    sup = dump(raw, "env_support.json", {"overall": {"pz": {"max": {"value": 120.0, "lc": 101, "node": 1},
                                                            "min": {"value": 5.0, "lc": 1, "node": 2}}},
                                         "cdb": "C:\\p\\mini.cdb"})
    _run(T, "holding_down.py", plc, sup, "--workdir", W)
    _pproof(W, "G8_plausibility", "PASS", "table G8", "all rows PASS")
    _pproof(W, "A12_assumptions", "PASS" if agreed else "ESCALATE", "assumptions_agreed: yes",
            "yes" if agreed else "no")
    rawr = dump(raw, "lc2.json", {"rows": [{"lc": 2, "sum_reactions_kN": [0.0, 0.0, 50.0]}], "cdb": "C:\\p\\mini.cdb"})
    _run(T, "receipts.py", "add", "--value", "50", "--unit", "kN", "--tool", "cdb_load_cases", "--args",
         '{"load_cases": "2"}', "--cdb", "C:\\p\\mini.cdb", "--cdb-mtime", "2026-10-18 09:00", "--raw", rawr,
         "--path", "rows[0].sum_reactions_kN[2]", "--workdir", W)
    _run(T, "receipts.py", "audit", "--n", "1", "--workdir", W)
    open(os.path.join(W, "LEDGER.md"), "w").write(f"assumptions_agreed: {'yes' if agreed else 'no'}\n")


def _score(T, W):
    env = dict(os.environ)
    env.pop("TOOLS_TEST", None)
    p = subprocess.run([sys.executable, "-I", os.path.join(T, "scorecard.py"), W, "--ledger",
                        os.path.join(W, "LEDGER.md")], capture_output=True, text=True, timeout=120, env=env)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1])


def test_end_to_end_amber_green_red():
    if not os.path.isdir(SOFREP):
        raise Skip("sofrep not present")
    d = tmpdir()
    T, W, raw, X, M, plc, pe, bm, ov, f10, f12 = _build(d)
    _members(T, W, raw, X, bm, ov, f10, f12)
    base = open(os.path.join(W, "proofs.jsonl")).read()
    # AMBER: everything passes, assumptions not agreed
    _finish(T, W, raw, plc, agreed=False)
    code, o = _score(T, W)
    assert code == 2 and o["score"] == "AMBER", o["notes"]
    assert all(n.startswith("AMBER") and ("assumptions" in n or "A12_assumptions" in n) for n in o["notes"]), o["notes"]
    # GREEN: the same proofs, assumptions agreed
    open(os.path.join(W, "proofs.jsonl"), "w").write(base)
    _finish(T, W, raw, plc, agreed=True)
    code, o = _score(T, W)
    assert code == 0 and o["score"] == "GREEN", o["notes"]
    green = open(os.path.join(W, "proofs.jsonl")).read()
    # RED 1: combo_check re-run on another run's load cases (other .cdb, same numbers)
    other = json.load(open(plc))
    other["cdb"] = "C:\\p\\other_run.cdb"
    _run(T, "combo_check.py", X, dump(raw, "load_cases_other.json", other), "--expected", pe, "--workdir", W)
    code, o = _score(T, W)
    assert code == 1 and any("different .cdb" in n for n in o["notes"]), o["notes"]
    # RED 2: same .cdb path but the results changed between the reads (a re-run in between)
    open(os.path.join(W, "proofs.jsonl"), "w").write(green)
    rerun = json.load(open(plc))
    rerun["rows"][1]["sum_reactions_kN"][2] += 0.5
    rerun["rows"][3]["sum_reactions_kN"][2] += 0.675
    rerun["rows"][4]["sum_reactions_kN"][2] += 0.675
    _run(T, "holding_down.py", dump(raw, "load_cases_rerun.json", rerun),
         os.path.join(raw, "env_support.json"), "--workdir", W)
    code, o = _score(T, W)
    assert code == 1 and any("results changed between the reads" in n for n in o["notes"]), o["notes"]
    # RED 3: coverage_census run on another model's .dat
    open(os.path.join(W, "proofs.jsonl"), "w").write(green)
    x2 = os.path.join(W, "other_expanded.dat")
    open(x2, "w").write(open(X).read() + "$ another run\n")
    _run(T, "coverage_census.py", x2, os.path.join(W, "checked_members.json"), "--workdir", W)
    code, o = _score(T, W)
    assert code == 1 and any("different versions of the dat file" in n for n in o["notes"]), o["notes"]
    # the legitimate relations are accepted: M (dat_lint) and X (all others) are one family; load_cases.json and
    # buckling_lcs.json from one .cdb are one family
    open(os.path.join(W, "proofs.jsonl"), "w").write(green)
    code, o = _score(T, W)
    assert code == 0
