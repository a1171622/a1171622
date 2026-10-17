"""Third review round, results and self-test (messages.py, solver.py, results.py, selftest.py).  Each test
failed before its fix.  The self-test functions run on fake .cdb files that stand in for real SOFiSTiK runs."""
from __future__ import annotations

import fake_cdb
import pytest
from fake_cdb import rec, text_ints

from sofistik_mcp import cdb_worker, messages, results, selftest, solver

D = fake_cdb.daten


def cdb(keys):
    return fake_cdb.FakeCdb(keys)


@pytest.fixture
def st(monkeypatch):
    monkeypatch.setattr(selftest, "fails", 0)
    monkeypatch.setattr(selftest, "lines", [])
    return selftest


def caller(keys):
    c = cdb(keys)
    return lambda op, args: cdb_worker.OPS[op](c, D, args)


def report(st):
    return "\n".join(st.lines)


# ================================================================ R1: totals line and exit code

CLEAN_NO_TOTALS = ("   *** Start: Program Calculation - Version 2027-0.0.139\n   *** Start: Program aqua\n"
                   "   TIME NEEDED  0 SECONDS\n   *** Stop : Program aqua\n   *** Start: Program ase\n"
                   "   *** Stop : Program ase\n   *** End of Calculation!\n")


def test_missing_totals_line_is_a_note_not_unfinished(tmp_path):
    p = tmp_path / "m.prt"
    p.write_text(CLEAN_NO_TOTALS)
    r = messages.summarize_run(str(p))
    assert r["status"] == "ok" and r["unfinished_programs"] == []
    assert r["programs_without_totals"] == ["aqua", "ase"] and "aqua, ase" in r["notes"][0]


def test_missing_stop_line_is_still_unfinished(tmp_path):
    p = tmp_path / "m.prt"
    p.write_text(CLEAN_NO_TOTALS.replace("   *** Stop : Program ase\n", ""))
    r = messages.summarize_run(str(p))
    assert r["status"] == "not finished" and r["unfinished_programs"] == ["ase"]


def _w(path, text):
    path.write_text(text)
    return str(path)


def test_nonzero_exit_code_keeps_a_clean_status(tmp_path, sps):
    r = solver.run(_w(tmp_path / "m.dat", "+PROG ASE\nEND\n$ FAKE exit=-1073741819\n"), sps, 60)
    assert r["status"] == "ok" and "meaning not verified" in r["server_warnings"][0]
    r = solver.run(_w(tmp_path / "e.dat", "+PROG AQB\nEND\n$ FAKE mode=errors\n$ FAKE exit=1\n"), sps, 60)
    assert r["status"] == "errors" and "server_warnings" not in r                # errors stay errors


def test_selftest_reports_exit_code_and_totals_lines(st):
    st.report_run("x.dat", {"command": "sps -B0 x.dat", "exit_code": 3, "status": "ok", "errors": 0, "warnings": 0,
                            "programs": [{"program": "ase", "errors": 0}, {"program": "aqb", "errors": None}],
                            "server_warnings": ["sps.exe exit code 3, meaning not verified"],
                            "notes": ["No 'n errors and m warnings' line for aqb"]})
    text = report(st)
    assert "[INFO] sps.exe exit code: 3" in text
    assert "[INFO] 'n errors and m warnings' totals line per program: ase yes, aqb NO" in text
    assert "warning: sps.exe exit code 3" in text and "note: No 'n errors" in text and st.fails == 0


# ================================================================ R2: the three group rules on their own

def test_beam_group_rules_agree_on_the_sln_model():
    r = results.beam_group_rules(cdb(fake_cdb.build_selftest_sln()), D)
    assert r["group_divisor"] == 1000 and len(r["beams"]) == 12
    for b in r["beams"]:
        assert b["rule1_gdiv"] == b["rule2_sln"] == b["rule3_range"] == b["beam"] // 1000, b
    assert {g["element_code"] for g in r["cgrp"]} == {100} and r["beam_element_codes"] == [0, 100, 101]


def test_beam_group_rules_without_gdiv_or_ranges():
    r = results.beam_group_rules(cdb(fake_cdb.build_interleaved(with_sln=True)), D)
    rows = {b["beam"]: (b["rule1_gdiv"], b["rule2_sln"], b["rule3_range"]) for b in r["beams"]}
    assert rows[1] == (None, 1, 1) and rows[2] == (None, 2, None) and rows[6] == (None, 2, 2)


@pytest.mark.parametrize("code", [0, 101])
def test_cgrp_codes_0_and_101_are_beam_groups(code):
    keys = fake_cdb.build_interleaved(with_sln=False)
    keys[(11, 0)] = [rec("CGRP", m_ng=4, m_typ=code, m_num=6, m_min=1, m_max=6)]
    c = cdb(keys)
    assert results.beam_forces(c, D, 1, groups_="4")["beams"] == 6
    assert {b["rule3_range"] for b in results.beam_group_rules(c, D)["beams"]} == {4}


def test_selftest_group_rule_checks_pass_and_print_mtyp(st):
    st.group_rule_checks(caller(fake_cdb.build_selftest_sln()))
    text = report(st)
    assert st.fails == 0, text
    assert "[PASS] rule 1 (GDIV) gives every beam a group: 12 of 12 beams" in text
    assert "[PASS] rule 2 (structural line, CSLN_BEAM m_nog) agrees with rule 1: 12 beams compared" in text
    assert "[PASS] rule 3 (the one beam group whose CGRP range holds the beam) agrees with rule 1" in text
    assert "[INFO] raw CGRP m_typ values: [100]" in text and "group 3 m_typ 100 elements 3001-3006 (6)" in text


def test_selftest_group_rules_absent_are_info_and_disagreement_fails(st):
    keys = fake_cdb.build_selftest_sln()
    del keys[(39, 7)], keys[(39, 8)]                                       # no CSLN_BEAM: rule 2 absent
    keys[(11, 0)] = [rec("CGRP", m_ng=3, m_typ=100, m_min=3001, m_max=3006),
                     rec("CGRP", m_ng=9, m_typ=100, m_min=4001, m_max=4006)]   # rule 3 says 9 for SLN 8
    st.group_rule_checks(caller(keys))
    text = report(st)
    assert "[INFO] rule 2 (structural line, CSLN_BEAM m_nog): gives no group for any beam" in text
    assert "[FAIL] rule 3 (the one beam group whose CGRP range holds the beam) agrees with rule 1" in text
    assert "(4001, 4, 9)" in text and st.fails == 1


def test_selftest_group_rules_partly_present_and_read_error(st):
    keys = fake_cdb.build_selftest_sln()
    keys[(11, 0)] = keys[(11, 0)][:1]                                       # only group 3 has a range
    st.group_rule_checks(caller(keys))
    assert "[INFO] rule 3 (the one beam group whose CGRP range holds the beam): no group for 6 beam(s)" in report(st)
    assert st.fails == 0
    st.group_rule_checks(lambda op, args: {"error": "boom"})
    assert "[FAIL] read the group rules: boom" in report(st)


# ================================================================ R3: GDIV group and CGRP range disagree

def test_gdiv_and_range_group_disagreeing_is_a_warning():
    keys = fake_cdb.build_selftest_sln()
    keys[(11, 0)] = [rec("CGRP", m_ng=3, m_typ=100, m_min=3001, m_max=3006),
                     rec("CGRP", m_ng=5, m_typ=100, m_min=4001, m_max=4006)]   # GDIV says 4, the range says 5
    r = results.beam_forces(cdb(keys), D, 1)
    assert {x["group"] for x in r["rows"] if x["beam"] > 4000} == {4}         # the group is not changed
    assert [d["beam"] for d in r["beams_where_group_range_differs"]] == list(range(4001, 4007))
    assert r["beams_where_group_range_differs"][0] == {"beam": 4001, "gdiv_group": 4, "range_group": 5}
    assert "beam 4001 GDIV group 4 / range group 5" in r["warning"] and "3001" not in r["warning"]
    assert "beams_where_group_range_differs" not in results.beam_forces(cdb(fake_cdb.build_selftest_sln()), D, 1)


# ================================================================ R4: how long the overview and load cases take

def test_selftest_prints_read_times(st):
    st.cantilever_checks(caller(fake_cdb.build_selftest_cantilever()))
    assert "[INFO] time to read: overview" in report(st) and ", load_cases " in report(st)
    assert "(3 load cases)" in report(st)                                    # 1, 2 and the eigenmode 2001


# ================================================================ R5: envelope over MAXIMA superpositions

def test_envelope_includes_superposition_load_cases_with_a_note():
    keys = fake_cdb.build_frame()                                           # LC 3 is CLC_CTRL kind 2
    keys[(102, 3)] = [rec("CBEAM_FOC", m_id=0), rec("CBEAM_FOR", m_nr=1001, m_x=0.0, m_my=-75.0)]
    r = results.envelope(cdb(keys), D, "1-3", what="beam")
    assert r["load_cases_found"] == [1, 2, 3] and r["overall"]["My"]["min"]["lc"] == 3
    assert r["superposition_load_cases"] == [3] and "already envelopes or combinations" in r["superposition_note"]
    assert "superposition_note" not in results.envelope(cdb(keys), D, "1-2", what="beam")


# ================================================================ R6: titles are INFO

def test_selftest_title_differing_is_info_not_fail(st):
    keys = fake_cdb.build_selftest_cantilever()
    keys[(12, 2)] = [rec("CLC_CTRL", m_kind=0, m_fact=1.0, m_rz=2.0, m_rtex=text_ints("ASE LC 2", 17))]
    st.cantilever_checks(caller(keys))
    text = report(st)
    assert st.fails == 0, text
    assert "[INFO] load case 2 title read back: 'ASE LC 2' vs 'self-test tip load 2 kN' written in SOFiLOAD " \
           "(different: ASE may have replaced it)" in text


def test_selftest_opposite_sign_of_stored_sum_is_info(st):
    keys = fake_cdb.build_selftest_cantilever()
    keys[(12, 1)] = [rec("CLC_CTRL", m_kind=0, m_rz=-1.0, m_rtex=text_ints("self-test tip load 1 kN", 17))]
    st.cantilever_checks(caller(keys))
    assert st.fails == 0 and "node 1 pz 1.0 kN: OPPOSITE signs" in report(st)
