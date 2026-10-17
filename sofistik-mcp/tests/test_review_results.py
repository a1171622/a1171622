"""Review fixes in results.py, cdbio.py and selftest.py: group membership, eigenmode warnings, kexist,
concurrent extremes, sof_cdb_get errors, partial reaction sums, load case kinds, MAX_LC, and the self-test
checks run on fake .cdb files that stand in for the real SOFiSTiK runs."""
from __future__ import annotations

import fake_cdb
import pytest
from fake_cdb import rec, text_ints

from sofistik_mcp import results

D = fake_cdb.daten
approx = pytest.approx


def cdb(keys):
    return fake_cdb.FakeCdb(keys)


# ---------------------------------------------------------------- 1. group membership

def beams_of(r):
    return sorted({x["beam"] for x in r["rows"]})


def test_interleaved_groups_from_structural_lines():
    """GDIV 0, groups 1 = beams 1,3,5 and 2 = 2,4,6: overlapping 11/00 ranges must not mix them."""
    c = cdb(fake_cdb.build_interleaved(with_sln=True))
    g1 = results.beam_forces(c, D, 1, groups_="1")
    g2 = results.beam_forces(c, D, 1, groups_="2")
    assert beams_of(g1) == [1, 3, 5] and beams_of(g2) == [2, 4, 6]
    assert "warning" not in g1 and "beams_with_unknown_group" not in g1
    assert results.beam_forces(c, D, 1, groups_="7")["beams"] == 0          # truss range never used
    env = results.envelope(c, D, "1", what="beam", groups_="2")
    assert env["overall"]["My"]["max"]["beam"] == 6 and env["overall"]["My"]["min"]["beam"] == 2


def test_interleaved_groups_without_structural_lines_are_excluded_with_warning():
    c = cdb(fake_cdb.build_interleaved(with_sln=False))
    g1 = results.beam_forces(c, D, 1, groups_="1")
    # beam 1 lies only in group 1's range 1-5, beams 2-5 lie in both ranges: ambiguous
    assert beams_of(g1) == [1] and g1["beams_with_unknown_group"] == [2, 3, 4, 5]
    assert "2, 3, 4, 5" in g1["warning"] and "left out of the group filter" in g1["warning"]
    g2 = results.beam_forces(c, D, 1, groups_="2")
    assert beams_of(g2) == [6] and g2["beams_with_unknown_group"] == [2, 3, 4, 5]
    allb = results.beam_forces(c, D, 1)
    assert {x["beam"]: x["group"] for x in allb["rows"]} == {1: 1, 2: None, 3: None, 4: None, 5: None, 6: 2}
    assert "warning" not in allb                                              # no group filter: nothing left out
    env = results.envelope(c, D, "1", what="beam", groups_="1")
    assert "left out of the group filter" in env["warning"]


def test_gdiv_defines_the_group_whatever_the_ranges_say():
    keys = fake_cdb.build_frame()                                            # GDIV 1000
    keys[(11, 0)] = [rec("CGRP", m_ng=1, m_typ=100, m_min=1001, m_max=2002),  # overlapping, wrong ranges
                     rec("CGRP", m_ng=2, m_typ=100, m_min=1001, m_max=2002)]
    keys[(39, 7)] = [rec("CSLN_BEAM", m_id=101, m_nog=9)]                    # SLN group ignored with GDIV
    c = cdb(keys)
    assert beams_of(results.beam_forces(c, D, 1, groups_="1")) == [1001, 1002]
    assert beams_of(results.beam_forces(c, D, 1, groups_="2")) == [2001]
    assert results.beam_forces(c, D, 1, groups_="9")["beams"] == 0


def test_sln_group_record_search_skips_other_records():
    keys = fake_cdb.build_interleaved(with_sln=True)
    keys[(39, 11)] = [rec("CSLN_BEAM", m_id=100, m_nog=5), rec("CSLN_BEAM", m_id=101, m_nog=1)]
    keys[(39, 12)] = []                                                       # key without data: no group
    c = cdb(keys)
    assert beams_of(results.beam_forces(c, D, 1, groups_="1")) == [1, 3, 5]
    g2 = results.beam_forces(c, D, 1, groups_="2")
    assert beams_of(g2) == [6] and g2["beams_with_unknown_group"] == [2, 4]   # range fallback; 2, 4 ambiguous


def test_sln_groups_without_csln_beam_class():
    class NoSln:
        pass
    assert results._sln_groups(cdb(fake_cdb.build_interleaved()), NoSln(), {11}) == {}


def test_unknown_group_warning_is_capped():
    keys = fake_cdb.build_interleaved(with_sln=False)
    keys[(11, 0)] = [rec("CGRP", m_ng=1, m_typ=100, m_min=1, m_max=200),
                     rec("CGRP", m_ng=2, m_typ=100, m_min=1, m_max=200)]
    keys[(102, 1)] = [rec("CBEAM_FOR", m_nr=i, m_my=1.0) for i in range(1, 71)]
    r = results.beam_forces(cdb(keys), D, 1, groups_="1")
    assert len(r["beams_with_unknown_group"]) == 70 and r["warning"].count(",") < 70 and " ..." in r["warning"]


# ---------------------------------------------------------------- 2. eigenmode warnings

def test_eigenmode_results_carry_a_warning():
    keys = fake_cdb.build_frame()
    keys[(102, 2001)] = [rec("CBEAM_FOR", m_nr=1001, m_my=1.0)]
    keys[(152, 2001)] = [rec("CTRUS_RES", m_nr=5001, m_n=1.0)]
    keys[(24, 2001)].append(rec("CN_DISP", m_nr=1, m_pz=0.3))
    c = cdb(keys)
    for r in (results.node_results(c, D, 2001), results.support_reactions(c, D, 2001),
              results.beam_forces(c, D, 2001), results.axial_forces(c, D, 2001, "truss")):
        assert "eigenmode" in r["warning"] and "normalised mode shape" in r["warning"] and "error" not in r
        assert r["lc"] == 2001
    for r in (results.node_results(c, D, 1), results.support_reactions(c, D, 1), results.beam_forces(c, D, 1),
              results.axial_forces(c, D, 1, "truss")):
        assert "warning" not in r


def test_lc_kind():
    c = cdb(fake_cdb.build_frame())
    assert results.lc_kind(c, D, 1) == 0 and results.lc_kind(c, D, 3) == 2 and results.lc_kind(c, D, 2001) == 4
    assert results.lc_kind(c, D, 77) is None


# ---------------------------------------------------------------- 3. kexist 1 / 2

def test_key_without_data_is_not_results():
    keys = fake_cdb.build_frame()
    keys[(24, 5)] = []
    keys[(102, 5)] = []
    keys[(162, 5)] = []
    keys[(12, 5)] = [rec("CLC_CTRL", m_kind=0, m_rtex=text_ints("empty", 17))]
    c = cdb(keys)
    for r, what in ((results.node_results(c, D, 5), "node"), (results.support_reactions(c, D, 5), "node"),
                    (results.beam_forces(c, D, 5), "beam"), (results.axial_forces(c, D, 5, "cable"), "cable")):
        assert f"No {what} results stored for load case 5" in r["error"] and "holds no data" in r["error"]
    lc5 = next(x for x in results.load_cases(c, D) if x["lc"] == 5)
    assert lc5["has_results"] == []
    assert results.scan_kwl(c, 24, 10) == [1, 2]                              # 24/5 has no data
    assert "(key 102/6 missing)" in results.beam_forces(c, D, 6)["error"]


def test_envelope_lists_load_cases_without_data():
    keys = fake_cdb.build_frame()
    keys[(102, 5)] = []                                                       # key, no data
    c = cdb(keys)
    r = results.envelope(c, D, "1-2,5,9", what="beam")
    assert r["load_cases_found"] == [1, 2] and r["load_cases_without_data"] == [5]
    assert r["load_cases_missing"] == [9] and "5 gave no values" in r["warning"]
    f = results.envelope(c, D, "1-2", what="beam", ids="1001", slns="99")     # filter matches nothing
    assert f["load_cases_found"] == [] and f["load_cases_without_data"] == [1, 2] and f["overall"] == {}
    s = results.envelope(c, D, "1-2", what="support", ids="2")                # node 2 has no reaction
    assert s["load_cases_without_data"] == [1, 2] and "1, 2 gave no values" in s["warning"]
    t = results.envelope(c, D, "1-2", what="truss", ids="5001")
    assert t["load_cases_found"] == [1] and t["load_cases_missing"] == [2] and t["load_cases_without_data"] == []


def test_envelope_partition_with_eigen():
    r = results.envelope(cdb(fake_cdb.build_frame()), D, "1-2,2001", what="node")
    assert r["load_cases_found"] == [1, 2] and r["eigen_load_cases_skipped"] == [2001]
    assert 2001 not in r["load_cases_without_data"] + r["load_cases_missing"]


# ---------------------------------------------------------------- 4. concurrent values

def test_beam_extremes_carry_concurrent_values():
    r = results.beam_forces(cdb(fake_cdb.build_frame()), D, 1)
    my = r["extremes"]["My"]["min"]                                           # 1002 x = 0: N 25, Vz 4
    assert my["value"] == -30.0 and my["beam"] == 1002 and my["x"] == 0.0     # existing keys kept
    assert my["concurrent"] == {"N": 25.0, "Vy": 0.0, "Vz": 4.0, "Mt": 0.0, "Mz": 0.0}
    n = r["extremes"]["N"]["min"]
    assert n["value"] == -100.0 and n["concurrent"] == {"Vy": 0.5, "Vz": 0.0, "Mt": 0.0, "My": 2.0, "Mz": 0.0}
    mz = r["extremes"]["Mz"]["max"]                                            # 1001 x = 0
    assert mz["concurrent"]["My"] == -20.0
    assert "not concurrent" in r["extremes_note"]


def test_node_and_support_extremes_carry_concurrent_values():
    c = cdb(fake_cdb.build_frame())
    n = results.node_results(c, D, 1)
    uz = n["extremes"]["uz"]["min"]
    assert uz["node"] == 3 and uz["concurrent"] == {"ux": 0.0, "uy": 0.0, "urx": -0.5, "ury": 0.0, "urz": 0.0}
    assert n["extremes"]["u_total"]["max"]["concurrent"]["uz"] == -10.5
    assert "urz" not in n["extremes"]["urz"]["max"]["concurrent"]             # only the other components
    assert "not concurrent" in n["extremes_note"]
    s = results.support_reactions(c, D, 1)
    pz = s["extremes"]["pz"]["max"]
    assert pz["node"] == 1 and pz["concurrent"] == {"px": 0.0, "py": 0.0, "mx": 0.0, "my": -12.0, "mz": 0.0}
    assert "not concurrent" in s["extremes_note"]


def test_envelope_keeps_concurrent_values_of_the_governing_lc():
    r = results.envelope(cdb(fake_cdb.build_frame()), D, "1-2", what="beam")
    my = r["overall"]["My"]["max"]
    assert (my["value"], my["lc"], my["beam"]) == (50.0, 2, 1002)
    assert my["concurrent"] == {"N": 37.5, "Vy": 0.0, "Vz": -6.0, "Mt": 0.0, "Mz": 0.0}
    assert "not concurrent" in r["extremes_note"]
    assert "extremes_note" not in results.envelope(cdb(fake_cdb.build_frame()), D, "1", what="truss")


def test_extremes_helper_without_concurrent():
    ex = results._extremes([{"a": 1.0, "b": 2.0, "id": 1}], ("a",), ("id",))
    assert ex == {"a": {"max": {"value": 1.0, "id": 1}, "min": {"value": 1.0, "id": 1}}}
    ex = results._extremes([{"a": 1.0, "b": None, "id": 1}], ("a",), ("id",), ("a", "b"))
    assert ex["a"]["max"]["concurrent"] == {"b": None}


# ---------------------------------------------------------------- 6. partial reaction sums

def test_support_sum_with_node_filter_is_labelled_partial():
    c = cdb(fake_cdb.build_frame())
    full = results.support_reactions(c, D, 1)
    assert full["sum_is_partial"] is False and full["sum_scope"] == "all nodes with a reaction"
    part = results.support_reactions(c, D, 1, ids="4")
    assert part["sum_is_partial"] is True and part["sum_kN"]["pz"] == 30.0
    assert "partial sum over the selected nodes" in part["sum_scope"] and "SOFiSTiK's total" in part["sum_scope"]
    assert part["sum_stored_by_sofistik_kN"] == [-2.5, 0.0, 80.0]
    assert "local (rotated) support system" in part["note"] and "not verified" in part["note"]


# ---------------------------------------------------------------- 7. load case kinds

def test_factors_only_for_kinds_0_and_1():
    keys = fake_cdb.build_frame()
    keys[(12, 4)] = [rec("CLC_CTRL", m_kind=1, m_fact=2.0, m_rz=5.0, m_rtex=text_ints("kind one", 17))]
    keys[(12, 6)] = [rec("CLC_CTRL", m_kind=7, m_fact=3.0, m_rz=9.0, m_ityp=fake_cdb.ACTION_G,
                         m_rtex=text_ints("odd kind", 17))]
    lcs = {x["lc"]: x for x in results.load_cases(cdb(keys), D)}
    assert lcs[4]["factor"] == 2.0 and lcs[4]["sum_reactions_kN"] == [0.0, 0.0, 5.0]
    assert lcs[4]["kind_name"] == "load case"
    odd = lcs[6]
    assert odd["title"] == "odd kind" and odd["kind"] == 7 and odd["action"] == ""
    assert "kind 7" in odd["kind_name"]
    assert not {"factor", "dead_load_factors", "sum_reactions_kN", "mode"} & set(odd)
    assert results.support_reactions(cdb(keys), D, 1)["sum_stored_by_sofistik_kN"] == [-2.5, 0.0, 80.0]


# ---------------------------------------------------------------- 9. MAX_LC

def test_read_key_keeps_small_raw_values():
    k = results.read_key(cdb(fake_cdb.build_frame()), D, 9, 1, class_name="CSECT")
    r0 = k["records"][0]
    assert r0["m_iy"] == approx(3692e-8, rel=1e-6) and r0["m_it"] == approx(20.98e-8, rel=1e-6)
    assert results.raw_val(1e35) is None and results.raw_val(0.0) == 0.0 and results.raw_val(2.1e8) == 2.1e8
    assert results.raw_val(1.0000001192092896) == 1.0                         # float32 noise removed


def test_max_lc_is_sofistiks_limit():
    assert results.MAX_LC == 999999
    keys = fake_cdb.build_frame()
    keys[(12, 999999)] = [rec("CLC_CTRL", m_kind=0, m_rtex=text_ints("last", 17))]
    keys[(12, 150001)] = [rec("CLC_CTRL", m_kind=0, m_rtex=text_ints("CSM", 17))]
    assert [x["lc"] for x in results.load_cases(cdb(keys), D)][-2:] == [150001, 999999]


# ---------------------------------------------------------------- 8. self-test checks on fake runs

from sofistik_mcp import cdb_worker, selftest  # noqa: E402


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


def test_selftest_cantilever_checks_pass_on_correct_results(st):
    props = st.cantilever_checks(caller(fake_cdb.build_selftest_cantilever()))
    text = report(st)
    assert st.fails == 0, text
    assert props == (approx(fake_cdb.E), approx(fake_cdb.G), approx(fake_cdb.IY), approx(fake_cdb.AZ))
    for name in ("tip rotation = P L^2 / (2 E Iy)", "load case 2 title read back", "N = 0 everywhere",
                 "Mt = 0 everywhere", "Mz = 0 everywhere", "Vy = 0 everywhere",
                 "tip moves in the direction of the load", "stored reaction sum and support node reaction",
                 "|My| grows linearly", "envelope LC 1-2: max |My| = 2 P L from LC 2",
                 "envelope LC 1-2: max |uz| = 2 x tip deflection from LC 2", "group filter: group 0"):
        assert f"[PASS] {name}" in text, name
    assert "observed: support pz = 1.0 kN" in text and "same sign as the load" in text
    assert "observed: tip rotation ury = -2.3" in text


def test_selftest_cantilever_reports_opposite_reaction_sign(st):
    keys = fake_cdb.build_selftest_cantilever()
    for lc, p in ((1, 1.0), (2, 2.0)):
        keys[(24, lc)][1] = rec("CN_DISP", m_nr=1, m_pz=-p, m_my=-p * fake_cdb.L)
        keys[(12, lc)] = [rec("CLC_CTRL", m_kind=0, m_rz=-p, m_rtex=text_ints(f"self-test tip load {p:.0f} kN", 17))]
    st.cantilever_checks(caller(keys))
    assert st.fails == 0, report(st)
    assert "opposite sign to the load" in report(st)


@pytest.mark.parametrize("break_it, failing", [
    (lambda k: k[(12, 2)].__setitem__(0, rec("CLC_CTRL", m_kind=0, m_rz=2.0, m_rtex=text_ints("x", 17))),
     "load case 2 title read back"),
    (lambda k: k.__setitem__((102, 2), k[(102, 1)]), "envelope LC 1-2: max |My| = 2 P L from LC 2"),
    (lambda k: k[(102, 1)].append(rec("CBEAM_FOR", m_nr=3, m_x=0.5, m_n=4.0, m_my=-3.5, m_vz=1.0)),
     "N = 0 everywhere"),
    (lambda k: k[(102, 1)].append(rec("CBEAM_FOR", m_nr=3, m_x=0.5, m_my=-2.0, m_vz=1.0)), "|My| grows linearly"),
    (lambda k: k[(12, 1)].__setitem__(0, rec("CLC_CTRL", m_kind=0, m_rz=-1.0,
                                             m_rtex=text_ints("self-test tip load 1 kN", 17))),
     "stored reaction sum and support node reaction"),
])
def test_selftest_cantilever_checks_catch_errors(st, break_it, failing):
    keys = fake_cdb.build_selftest_cantilever()
    break_it(keys)
    st.cantilever_checks(caller(keys))
    assert f"[FAIL] {failing}" in report(st), report(st)


def test_selftest_tip_direction_and_rotation_checks(st):
    keys = fake_cdb.build_selftest_cantilever()
    nodes = keys[(24, 1)]
    nodes[-1] = rec("CN_DISP", m_nr=7, m_uz=-0.0092866, m_ury=0.004)       # wrong direction, wrong rotation
    st.cantilever_checks(caller(keys))
    text = report(st)
    assert "[FAIL] tip moves in the direction of the load" in text and "[FAIL] tip rotation" in text


def test_selftest_cantilever_stops_on_read_errors(st):
    assert st.cantilever_checks(lambda op, args: {"error": "boom"}) is None and st.fails == 1
    keys = fake_cdb.build_selftest_cantilever()
    del keys[(9, 1)]
    assert st.cantilever_checks(caller(keys)) is None and "[FAIL] section 1 present" in report(st)


def test_selftest_sln_checks_pass_and_separate_the_lines(st):
    st.sln_result_checks(caller(fake_cdb.build_selftest_sln()), fake_cdb.E, fake_cdb.G, fake_cdb.IY, fake_cdb.AZ)
    text = report(st)
    assert st.fails == 0, text
    for name in ("filter by structural line 7 returns exactly its beams", "filter by group 4 returns exactly the "
                 "beams of SLN 8", "group 3: fixed-end moment", "group 4: fixed-end moment",
                 "sum of reactions = (w7 + w8) L", "largest tip deflection"):
        assert f"[PASS] {name}" in text, name


def test_selftest_sln_checks_catch_a_leaking_group_filter(st):
    """GDIV 0, no CSLN_BEAM, group 3's range 3001-4006 overlaps group 4's: the old range rule pulled line 8's
    beams into group 3.  Now they are ambiguous, left out with a warning, and the group 4 check fails."""
    keys = fake_cdb.build_selftest_sln()
    keys[(10, 0)] = [rec("CSYST", m_igdiv=0)]
    keys[(11, 0)] = [rec("CGRP", m_ng=3, m_typ=100, m_min=3001, m_max=4006),
                     rec("CGRP", m_ng=4, m_typ=100, m_min=4001, m_max=4006)]
    del keys[(39, 7)], keys[(39, 8)]
    st.sln_result_checks(caller(keys), fake_cdb.E, fake_cdb.G, fake_cdb.IY, fake_cdb.AZ)
    text = report(st)
    assert "[PASS] filter by group 3 returns exactly the beams of SLN 7" in text
    assert "[FAIL] filter by group 4 returns exactly the beams of SLN 8" in text and "left out" in text


def test_selftest_sln_read_error(st):
    st.sln_result_checks(lambda op, args: {"error": "x"}, 1, 1, 1, 1)
    assert st.fails == 1 and "[FAIL] read beam forces" in report(st)


def test_selftest_helpers():
    assert selftest.absmax({"My": {"max": {"value": 2.0, "lc": 1}, "min": {"value": -5.0, "lc": 2}}}, "My") == \
        (5.0, {"value": -5.0, "lc": 2})
    assert selftest.absmax({}, "My") == (0.0, {})
    assert (selftest.sign(-3), selftest.sign(0), selftest.sign(None), selftest.sign(2)) == (-1, 0, 0, 1)
