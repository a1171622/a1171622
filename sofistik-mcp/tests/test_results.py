"""results.py on fake .cdb files built from SOFiSTiK's record layouts: values, units, signs, filters.

Expected numbers are written out by hand from the records in tests/fake_cdb.py (SI in the .cdb:
m, rad, kN, kNm, m2, m4) and the unit conversion the tools promise (mm, mrad, kN, kNm, cm2, cm4)."""
from __future__ import annotations

import math

import fake_cdb
import pytest
from conftest import core
from fake_cdb import rec

from sofistik_mcp import results

D = fake_cdb.daten
approx = pytest.approx


@pytest.fixture
def frame():
    return fake_cdb.FakeCdb(fake_cdb.build_frame())


@pytest.fixture
def cant():
    return fake_cdb.FakeCdb()


# ---------------------------------------------------------------- helpers

@pytest.mark.parametrize("spec, expected", [
    (None, None), ("", None), ([], None), (7, {7}), ("7", {7}), ("1-3,7", {1, 2, 3, 7}),
    ("1-3, 7;10", {1, 2, 3, 7, 10}), ("3-1", {1, 2, 3}), ("1..3", {1, 2, 3}), ("1to3", {1, 2, 3}),
    ([1, "4-5"], {1, 4, 5}), ("101-103 201", {101, 102, 103, 201}), (" 5 ", {5}), ("-2--1", {-2, -1}),
])
def test_parse_ids(spec, expected):
    assert results.parse_ids(spec) == expected


@pytest.mark.parametrize("bad", ["abc", "1-", "1,x", "1.5"])
def test_parse_ids_errors(bad):
    with pytest.raises(ValueError, match="Cannot read number list"):
        results.parse_ids(bad)


def test_parse_ids_range_too_large():
    with pytest.raises(ValueError, match="Range too large"):
        results.parse_ids("1-2000000")


def test_parse_ids_ranges_with_spaces():
    assert results.parse_ids("101 - 103") == {101, 102, 103}
    assert results.parse_ids("1 to 3") == {1, 2, 3}


@pytest.mark.parametrize("v, scale, nd, out", [
    (1.0, 1.0, 6, 1.0), (0.0012345678, 1e3, 4, 1.2346), (-0.0042, 1e3, 4, -4.2), (1e30, 1, 6, None),
    (-1e30, 1, 6, None), (1e35, 1, 6, None), (9.99e29, 1, 6, 9.99e29), (float("nan"), 1, 6, None),
    (None, 1, 6, None), ("x", 1, 6, None), (1e-13, 1, 6, 0.0), (-1e-13, 1e3, 6, 0.0),
])
def test_val(v, scale, nd, out):
    assert results.val(v, scale, nd) == out


def test_val_float32_undefined_marker():
    """1e30 stored as a C float reads back as 1.0000000150474662e30: still undefined."""
    import ctypes
    assert results.val(ctypes.c_float(1e30).value) is None
    assert results.val(ctypes.c_float(-1e30).value) is None


def test_first_int_and_as_rec_pads_short_records():
    assert results.first_int(b"") == 0 and results.first_int(b"\x07\x00\x00\x00rest") == 7
    short = rec("CN_DISP", m_nr=4, m_ux=0.5)[:12]                      # SOFiSTiK may write short records
    d = results.as_rec(D, "CN_DISP", short)
    assert d.m_nr == 4 and d.m_ux == 0.5 and d.m_uz == 0.0 and d.m_pz == 0.0


# ---------------------------------------------------------------- model data

def test_overview_frame(frame):
    ov = results.overview(frame, D)
    assert ov["system"] == {"project": "FRAME TEST", "group_divisor": 1000, "nodes": 5, "highest_node": 5,
                            "system_type": 30, "gravity_code": 0,
                            "bounding_box_m": [[0.0, 0.0, 0.0], [9.0, 0.0, 3.0]]}
    assert ov["element_counts"] == {"nodes": 5, "beams": 4, "trusses": 0, "cables": 0, "springs": 0, "quads": 0}
    assert ov["materials"] == [{"nr": 1, "title": "S 355"}, {"nr": 2, "title": "C 30/37"}]
    s1, s2 = ov["sections"]
    assert s1 == {"nr": 1, "title": "HEA 200", "A_cm2": approx(53.8), "Iy_cm4": approx(3692.0),
                  "Iz_cm4": approx(1336.0), "It_cm4": approx(20.98), "material": 1}
    assert s2["title"] == "IPE 300" and s2["A_cm2"] == approx(53.81) and s2["Iy_cm4"] == approx(8356.0)
    assert [(g["group"], g["element_code"], g["min_element"], g["max_element"], g["title"]) for g in ov["groups"]] == [
        (1, 100, 1001, 1002, "girder"), (2, 100, 2001, 2002, "columns"), (5, 150, 1001, 5002, "bracing")]
    assert [lc["lc"] for lc in ov["load_cases"]] == [1, 2, 3, 2001, 2002]
    assert ov["units"]["displacement"] == "mm" and ov["units"]["rotation"] == "mrad"
    assert ov["units"]["area"] == "cm2" and ov["units"]["second_moment"] == "cm4"


def test_sections_units_exact_values(cant):
    s = results.sections(cant, D)[0]
    assert s["A_cm2"] == 53.8 and s["Iy_cm4"] == 3692.0 and s["Iz_cm4"] == 1336.0   # rounded to 3 decimals


def test_load_cases_kinds_and_actions(frame):
    lcs = {d["lc"]: d for d in results.load_cases(frame, D)}
    g = lcs[1]
    assert g["title"] == "dead load" and g["kind"] == 0 and g["kind_name"] == "load case"
    assert g["action"] == "Permanent loads"                     # from 14/ITYP CLC_ACT
    assert g["factor"] == 1.0 and g["dead_load_factors"] == [0.0, 0.0, 1.0]
    assert g["sum_reactions_kN"] == [-2.5, 0.0, 80.0]
    assert g["has_results"] == ["nodes", "beams", "trusses", "cables"]
    assert lcs[2]["action"] == "Q" and lcs[2]["factor"] == 1.5     # no CLC_ACT: action code as text
    assert lcs[2]["has_results"] == ["nodes", "beams", "cables"]
    sup = lcs[3]
    assert sup["kind"] == 2 and sup["kind_name"].startswith("superposition") and sup["action"] == ""
    assert "sum_reactions_kN" not in sup and "factor" not in sup and sup["has_results"] == []


def test_eigen_load_cases(frame, cant):
    lcs = {d["lc"]: d for d in results.load_cases(frame, D)}
    e = lcs[2001]
    assert e["kind"] == 4 and e["kind_name"] == "eigenmode" and e["action"] == "" and e["mode"] == 1
    assert e["frequency_Hz"] == approx(4.0, rel=1e-6) and e["period_s"] == approx(0.25, rel=1e-5)
    assert "sum_reactions_kN" not in e and "factor" not in e and e["has_results"] == ["nodes"]
    assert lcs[2002]["frequency_Hz"] is None and lcs[2002]["period_s"] is None and lcs[2002]["mode"] == 2
    c = {d["lc"]: d for d in results.load_cases(cant, D)}[2001]
    assert c["frequency_Hz"] == approx(2.5, rel=1e-6) and c["period_s"] == approx(0.4, rel=1e-5)


def test_load_cases_filter(frame):
    assert [d["lc"] for d in results.load_cases(frame, D, only={2, 3, 99, 0, -1, 100000})] == [2, 3]


def test_nodes(frame):
    r = results.nodes(frame, D, ids="2-3,5")
    assert r["count"] == 3 and r["truncated"] is False and r["units"] == {"x,y,z": "m"}
    assert r["rows"][0] == {"node": 2, "x": 2.5, "y": 0.0, "z": 3.0, "fixity_code": 0}
    full = results.nodes(frame, D, max_rows=2)
    assert full["count"] == 5 and len(full["rows"]) == 2 and full["truncated"] is True
    assert full["rows"][0]["fixity_code"] == 63


def test_counts_skip_id0_records(cant):
    assert results.overview(cant, D)["element_counts"]["beams"] == 6      # CBEAM_SCT (id 0) not counted


def test_empty_cdb():
    c = fake_cdb.FakeCdb({})
    ov = results.overview(c, D)
    assert ov["system"] == {} and ov["materials"] == [] and ov["groups"] == [] and ov["load_cases"] == []
    assert results.nodes(c, D)["count"] == 0
    assert "No node results for load case 1" in results.node_results(c, D, 1)["error"]


# ---------------------------------------------------------------- node results, units and signs

def test_node_results_units_and_signs(frame):
    r = results.node_results(frame, D, 1)
    assert r["count"] == 5 and r["lc"] == 1
    rows = {x["node"]: x for x in r["rows"]}
    n2 = rows[2]
    assert (n2["ux"], n2["uy"], n2["uz"]) == (1.0, 0.0, -4.2)            # m -> mm, sign kept
    assert n2["ury"] == 1.3 and n2["urx"] == 0.0                          # rad -> mrad
    assert n2["u_total"] == approx(math.hypot(1.0, 4.2), abs=1e-4)
    assert rows[3]["uz"] == -10.5 and rows[3]["urx"] == -0.5
    assert rows[5]["uy"] == 2.1 and rows[5]["urz"] is None                # 1e35 -> None
    assert rows[1]["pz"] == 50.0 and rows[1]["my"] == -12.0               # kN, kNm unscaled
    assert rows[4]["px"] == -2.5
    assert r["units"] == {"ux,uy,uz,u_total": "mm", "urx,ury,urz": "mrad", "px,py,pz": "kN", "mx,my,mz": "kNm"}
    ex = r["extremes"]
    assert core(ex["uz"]["max"]) == {"value": 0.0, "node": 1}
    assert core(ex["uz"]["min"]) == {"value": -10.5, "node": 3}
    assert core(ex["u_total"]["max"]) == {"value": 10.5, "node": 3}
    assert core(ex["urx"]["min"]) == {"value": -0.5, "node": 3}
    assert ex["urz"]["max"]["value"] == 0.0 and ex["urz"]["max"]["node"] == 1   # node 5 undefined: skipped
    assert set(ex) == {"ux", "uy", "uz", "urx", "ury", "urz", "u_total"}       # no extremes of forces here


def test_node_results_ids_coords_and_rows(frame):
    r = results.node_results(frame, D, 2, ids="2-3", include_coords=True)
    assert [x["node"] for x in r["rows"]] == [2, 3] and r["count"] == 2
    assert r["rows"][1]["uz"] == -21.0 and (r["rows"][1]["x"], r["rows"][1]["z"]) == (5.0, 3.0)
    r = results.node_results(frame, D, 1, max_rows=1)
    assert len(r["rows"]) == 1 and r["count"] == 5 and r["truncated"] is True
    assert r["extremes"]["uz"]["min"]["node"] == 3                       # extremes over all, not shown rows


def test_node_results_cantilever_tip_deflection(cant):
    r = results.node_results(cant, D, 1, ids="7")
    expect_mm = fake_cdb.P * fake_cdb.L ** 3 / (3 * fake_cdb.E * fake_cdb.IY) * 1000      # 9.2866 mm
    assert r["rows"][0]["uz"] == approx(expect_mm, abs=2e-4) and abs(expect_mm - 9.2866) < 1e-3


def test_missing_load_case_messages(frame):
    for fn, what in ((results.node_results, "node"), (results.support_reactions, "node"),
                     (results.beam_forces, "beam")):
        e = fn(frame, D, 99)["error"]
        assert f"No {what} results for load case 99" in e and "key" in e
    assert "No truss results for load case 2" in results.axial_forces(frame, D, 2, "truss")["error"]
    assert "No cable results for load case 3" in results.axial_forces(frame, D, 3, "cable")["error"]


def test_support_reactions(frame):
    r = results.support_reactions(frame, D, 1)
    assert [x["node"] for x in r["rows"]] == [1, 4] and r["supports_with_reaction"] == 2
    assert r["sum_kN"] == {"px": -2.5, "py": 0.0, "pz": 80.0}
    assert r["sum_stored_by_sofistik_kN"] == [-2.5, 0.0, 80.0]             # matches: a good model check
    assert r["rows"][0] == {"node": 1, "px": 0.0, "py": 0.0, "pz": 50.0, "mx": 0.0, "my": -12.0, "mz": 0.0}
    assert core(r["extremes"]["pz"]["max"]) == {"value": 50.0, "node": 1}
    assert core(r["extremes"]["my"]["min"]) == {"value": -12.0, "node": 1}
    assert "ux" not in r["rows"][0] and r["units"]["mx,my,mz"] == "kNm"
    only4 = results.support_reactions(frame, D, 1, ids=[4])
    assert only4["sum_kN"] == {"px": -2.5, "py": 0.0, "pz": 30.0}


def test_support_reactions_lc2_scaled(frame):
    r = results.support_reactions(frame, D, 2)
    assert r["sum_kN"]["pz"] == 160.0 and r["sum_stored_by_sofistik_kN"][2] == 160.0


def test_support_reactions_cantilever(cant):
    r = results.support_reactions(cant, D, 1)
    assert r["rows"] == [{"node": 1, "px": 0.0, "py": 0.0, "pz": 1.0, "mx": 0.0, "my": 6.0, "mz": 0.0}]


# ---------------------------------------------------------------- beams

def test_beam_forces_values_and_meta(frame):
    r = results.beam_forces(frame, D, 1)
    assert r["beams"] == 3 and r["stations"] == 8 and r["truncated"] is False
    first = r["rows"][0]
    assert first == {"beam": 1001, "sln": 7, "group": 1, "x": 0.0, "N": -10.0, "Vy": 1.0, "Vz": 2.0,
                     "Mt": 0.1, "My": -20.0, "Mz": 3.0}
    col = [x for x in r["rows"] if x["beam"] == 2001]
    assert [x["x"] for x in col] == [0.0, 1.5, 3.0] and col[0]["sln"] is None and col[0]["group"] == 2
    assert r["rows"][2]["Mz"] is None                                     # undefined value
    ex = r["extremes"]
    assert core(ex["My"]["min"]) == {"value": -30.0, "beam": 1002, "x": 0.0, "sln": 7, "group": 1}
    assert core(ex["My"]["max"]) == {"value": 12.0, "beam": 1002, "x": 4.0, "sln": 7, "group": 1}
    assert ex["N"]["min"]["value"] == -100.0 and ex["N"]["max"]["value"] == 25.0      # compression < 0
    assert core(ex["Vz"]["min"]) == {"value": -4.0, "beam": 1002, "x": 4.0, "sln": 7, "group": 1}
    assert ex["Mz"]["max"]["value"] == 3.0
    assert r["units"] == {"x": "m from beam start", "N,Vy,Vz": "kN", "Mt,My,Mz": "kNm"}
    assert "N > 0 tension" in r["note"] and "warning" not in r and "sln_note" not in r


def test_beam_filters(frame):
    assert results.beam_forces(frame, D, 1, beams="1001")["stations"] == 3
    assert results.beam_forces(frame, D, 1, beams="1001-1002")["beams"] == 2
    g1 = results.beam_forces(frame, D, 1, groups_="1")
    assert {x["beam"] for x in g1["rows"]} == {1001, 1002}                # truss group 5 range ignored
    assert {x["beam"] for x in results.beam_forces(frame, D, 1, groups_="2")["rows"]} == {2001}
    assert results.beam_forces(frame, D, 1, groups_="5")["beams"] == 0
    s7 = results.beam_forces(frame, D, 1, slns="7")
    assert {x["beam"] for x in s7["rows"]} == {1001, 1002} and "sln_note" in s7 and "warning" not in s7
    both = results.beam_forces(frame, D, 1, groups_="1", beams="1002")
    assert {x["beam"] for x in both["rows"]} == {1002}
    assert results.beam_forces(frame, D, 1, slns="7", groups_="2")["beams"] == 0


def test_sln_nothing_matched_warning(frame, cant):
    r = results.beam_forces(frame, D, 1, slns="8,9")
    assert r["beams"] == 0 and r["warning"] == "No beam matched these structural lines. Lines known from the beams: 7"
    r = results.beam_forces(cant, D, 1, slns="7")
    assert "none (m_nref is 0 for all beams)" in r["warning"] and r["sln_note"] == results.SLN_NOTE


def test_beam_ends_only(frame):
    r = results.beam_forces(frame, D, 1, ends_only=True)
    assert [(x["beam"], x["x"]) for x in r["rows"]] == [(1001, 0.0), (1001, 5.0), (1002, 0.0), (1002, 4.0),
                                                        (2001, 0.0), (2001, 3.0)]


def test_beam_max_rows(frame):
    r = results.beam_forces(frame, D, 1, max_rows=2)
    assert len(r["rows"]) == 2 and r["stations"] == 8 and r["truncated"] is True
    assert r["extremes"]["N"]["min"]["beam"] == 2001                       # extremes over all stations


def test_beam_cantilever(cant):
    r = results.beam_forces(cant, D, 1)
    ex = r["extremes"]
    assert core(ex["My"]["min"]) == {"value": -6.0, "beam": 1, "x": 0.0, "sln": None, "group": 0}
    assert ex["My"]["max"]["value"] == 0.0 and ex["My"]["max"]["beam"] == 6 and ex["My"]["max"]["x"] == 1.0
    assert ex["Vz"]["max"]["value"] == 1.0 and "Mz" not in ex


def test_group_of_rules():
    gl = [{"group": 1, "element_code": 100, "min_element": 1001, "max_element": 1999},
          {"group": 3, "element_code": 100, "min_element": 1500, "max_element": 2500},
          {"group": 9, "element_code": 150, "min_element": 1000, "max_element": 1100}]
    assert results._group_of(1600, gl, 1000) == 1                         # GDIV > 0: always nr // GDIV
    assert results._group_of(7001, gl, 1000, sln_group=4) == 7            # ... even over the SLN group
    assert results._group_of(1600, gl, 0, sln_group=4) == 4               # GDIV 0: structural line group
    assert results._group_of(1200, gl, 0) == 1                            # one beam range
    assert results._group_of(1050, gl, 0) == 1                            # truss range 9 ignored
    assert results._group_of(1600, gl, 0) is None                         # two beam ranges: ambiguous
    assert results._group_of(7001, gl, 0) is None                         # in no range
    assert results._group_of(1050, [gl[2]], 0) is None                    # only a truss range: never used
    assert results._group_of(1050, gl, -1000) == 1                        # GDIV < 0: ranges


def test_beam_group_filter_with_ambiguous_ranges():
    keys = fake_cdb.build_frame()
    keys[(10, 0)] = [rec("CSYST", m_igdiv=0)]
    keys[(11, 0)] = [rec("CGRP", m_ng=1, m_typ=100, m_min=1001, m_max=2001),
                     rec("CGRP", m_ng=2, m_typ=100, m_min=2001, m_max=2002)]
    c = fake_cdb.FakeCdb(keys)
    r = results.beam_forces(c, D, 1, groups_="2")
    assert r["beams"] == 0 and r["beams_with_unknown_group"] == [2001] and "2001" in r["warning"]
    r = results.beam_forces(c, D, 1)
    assert {x["beam"]: x["group"] for x in r["rows"]} == {1001: 1, 1002: 1, 2001: None}


# ---------------------------------------------------------------- trusses and cables

def test_axial_forces(frame):
    r = results.axial_forces(frame, D, 1, "truss")
    assert r["rows"] == [{"element": 5001, "N": 12.5, "axial_disp": 1.0},
                         {"element": 5002, "N": -7.25, "axial_disp": -0.4}]
    assert core(r["extremes"]["N"]["max"]) == {"value": 12.5, "element": 5001}
    assert core(r["extremes"]["N"]["min"]) == {"value": -7.25, "element": 5002}
    assert r["units"] == {"N": "kN (tension +)", "axial_disp": "mm"} and r["type"] == "truss"
    assert results.axial_forces(frame, D, 1, "truss", ids="5002")["count"] == 1
    c = results.axial_forces(frame, D, 2, "cable")
    assert c["rows"] == [{"element": 6001, "N": 95.0, "axial_disp": 15.0}]
    with pytest.raises(KeyError):
        results.axial_forces(frame, D, 1, "spring")


# ---------------------------------------------------------------- envelopes

def test_envelope_beams_governing_lc(frame):
    r = results.envelope(frame, D, "1-3", what="beam")
    assert r["load_cases_found"] == [1, 2] and r["load_cases_missing"] == [3]
    o = r["overall"]
    assert core(o["My"]["max"]) == {"value": 50.0, "beam": 1002, "x": 4.0, "sln": 7, "group": 1, "lc": 2}
    assert core(o["My"]["min"]) == {"value": -45.0, "beam": 1002, "x": 0.0, "sln": 7, "group": 1, "lc": 2}
    assert core(o["N"]["max"]) == {"value": 40.0, "beam": 2001, "x": 0.0, "sln": None, "group": 2, "lc": 2}
    assert core(o["N"]["min"]) == {"value": -100.0, "beam": 2001, "x": 0.0, "sln": None, "group": 2, "lc": 1}
    assert o["Vz"]["max"]["value"] == 6.0 and o["Vz"]["max"]["lc"] == 2
    assert r["per_lc"][1]["My"]["max"]["value"] == 12.0 and r["per_lc"][2]["My"]["max"]["value"] == 50.0
    assert r["units"]["moment"] == "kNm"


def test_envelope_ties_keep_first_lc(frame):
    keys = fake_cdb.build_frame()
    keys[(102, 2)] = keys[(102, 1)]
    r = results.envelope(fake_cdb.FakeCdb(keys), D, "2,1", what="beam")
    assert r["overall"]["My"]["max"]["lc"] == 1 and r["load_cases_found"] == [1, 2]


def test_envelope_filters(frame):
    r = results.envelope(frame, D, "1-2", what="beam", groups_="1")
    assert r["overall"]["N"]["max"]["value"] == 37.5 and r["overall"]["N"]["max"]["beam"] == 1002
    r = results.envelope(frame, D, "1-2", what="beam", ids="2001")
    assert core(r["overall"]["My"]["max"]) == {"value": 3.0, "beam": 2001, "x": 0.0, "sln": None, "group": 2, "lc": 2}


def test_envelope_nodes_supports_trusses_cables(frame):
    n = results.envelope(frame, D, "1-2", what="node")
    assert core(n["overall"]["uz"]["min"]) == {"value": -21.0, "node": 3, "lc": 2}
    assert core(n["overall"]["ux"]["max"]) == {"value": 2.0, "node": 2, "lc": 2}
    s = results.envelope(frame, D, "1-2", what="support")
    assert core(s["overall"]["pz"]["max"]) == {"value": 100.0, "node": 1, "lc": 2}
    assert core(s["overall"]["px"]["min"]) == {"value": -5.0, "node": 4, "lc": 2}
    t = results.envelope(frame, D, "1-2", what="truss")
    assert t["load_cases_found"] == [1] and core(t["overall"]["N"]["min"]) == {"value": -7.25, "element": 5002, "lc": 1}
    c = results.envelope(frame, D, "1-2", what="cable")
    assert core(c["overall"]["N"]["max"]) == {"value": 95.0, "element": 6001, "lc": 2}


def test_envelope_input_errors(frame):
    assert "Give the load cases" in results.envelope(frame, D, "", what="beam")["error"]
    r = results.envelope(frame, D, "50-60", what="beam")
    assert r["load_cases_found"] == [] and r["overall"] == {} and r["load_cases_missing"] == list(range(50, 61))


def test_envelope_excludes_or_flags_eigenmodes(frame):
    r = results.envelope(frame, D, "1-2001", what="node")
    assert r["overall"]["uz"]["max"]["lc"] != 2001 or "warning" in r


def test_envelope_sln_nothing_matched_warns(frame):
    r = results.envelope(frame, D, "1-2", what="beam", slns="99")
    assert r["overall"] == {} and "warning" in r


# ---------------------------------------------------------------- read_key

def test_read_key_decoded(frame):
    k = results.read_key(frame, D, 10, 0, class_name="CSYST")
    assert k["kexist"] == 2 and k["kexist_meaning"] == "key with data" and k["record_count"] == 1
    r0 = k["records"][0]
    assert r0["_bytes"] == 352 and r0["m_txt"] == "FRAME TEST" and r0["m_igdiv"] == 1000
    assert r0["m_box"] == [0.0, 0.0, 0.0, 9.0, 0.0, 3.0]                 # 2-D array flattened
    assert "Raw CDB values" in k["note"]
    m = results.read_key(frame, D, 1, 1, class_name="CMAT_STEE", skip=1, max_records=1)
    assert len(m["records"]) == 1 and m["records"][0]["m_emod"] == approx(2.1e8)


def test_read_key_raw_and_missing(frame):
    k = results.read_key(frame, D, 152, 1)
    assert k["records"][0]["ints"][0] == 5001 and k["records"][0]["floats"][1] == 12.5
    assert k["records"][0]["bytes"] == 40
    assert results.read_key(frame, D, 999, 9) == {"kwh": 999, "kwl": 9, "kexist": 0, "kexist_meaning": "key missing"}
    e = results.read_key(frame, D, 10, 0, class_name="CNOPE")
    assert e["error"] == "No class CNOPE in sofistik_daten.py."


def test_read_key_empty_key():
    c = fake_cdb.FakeCdb({(5, 5): []})
    k = results.read_key(c, D, 5, 5)
    assert k["kexist"] == 1 and k["kexist_meaning"] == "key exists, no data" and k["records"] == []


def test_text_decoding_from_records(frame):
    assert results.system_info(frame, D)["project"] == "FRAME TEST"
    assert results._action_text(frame, D, 0) == ""
    assert results._action_text(frame, D, fake_cdb.text_ints("Q", 1)[0]) == "Q"
    assert results._action_text(frame, D, 0x01020304) == ""               # not a readable code
