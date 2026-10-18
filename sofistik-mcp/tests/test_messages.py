"""messages.py: errors, warnings and end state from SOFiSTiK's .prt / .erg text."""
from __future__ import annotations

import os
import textwrap

from sofistik_mcp import messages

HERE = os.path.dirname(os.path.abspath(__file__))

MULTI = textwrap.dedent("""\
       *** Start: Program Calculation - Version 2027-0.0.139
       *** Start: Program aqua
       +++++ warning no. 120
       Material 1 has no safety factor
        +++++    0 errors and    1 warnings +++++
       *** Stop : Program aqua
       *** Start: Program sofimsha
       +++++ error no. 1003
       Node 12 not defined
       for beam 5
       +++++ error no. 1003
       Node 13 not defined
       +++++ warning no. 77
       Beam 7 has zero length
        +++++    2 errors and    1 warnings +++++
       +++++ DATA ERRONEOUS, PROGRAM ABORTED +++++
       *** Stop : Program sofimsha
       *** Process canceled, error detected!
       *** End of Calculation!
       """)


def test_real_sample_files():
    r = messages.summarize_run(os.path.join(HERE, "sample_error.prt"), os.path.join(HERE, "sample_error.erg"))
    assert r["status"] == "errors" and r["errors"] == 1 and r["warnings"] == 0
    assert r["finished"] is True
    assert [a["text"] for a in r["aborted"]] == ["+++++ DATA ERRONEOUS, PROGRAM ABORTED +++++",
                                                 "*** Process canceled, error detected!"]
    assert r["programs"] == [{"program": "aqb", "line": 2, "stop_line": 15, "errors": 1, "warnings": 0,
                              "aborted": True}]
    m = r["messages"][0]
    assert (m["kind"], m["number"], m["program"], m["line"]) == ("error", 10001, "aqb", 6)
    # the explanation runs to the next blank line, so SOFiSTiK's timing lines come along
    assert m["text"] == ("Data base aqb_steel_check.cdb not found or erroneous "
                         "TIME NEEDED         0 SECONDS, TOTAL         0 SECONDS DATE       2026-10-14, 00:15:04")
    e = r["erg_messages"][0]
    assert e["number"] == 10001 and e["text"].startswith("Data base aqb_steel_check.cdb")
    assert e["input_before"] == ["      CaSE",
                                 "      AQB    - DESIGN OF CROSS-SECTIONS V 2027-0.0         10/14/26"
                                 "          Page:   1"]


def test_multiple_errors_and_warnings_per_program():
    p = messages.parse_protocol(MULTI)
    assert p["errors"] == 2 and p["warnings"] == 2
    assert [(m["kind"], m["number"], m["program"]) for m in p["messages"]] == [
        ("warning", 120, "aqua"), ("error", 1003, "sofimsha"), ("error", 1003, "sofimsha"),
        ("warning", 77, "sofimsha")]
    assert p["messages"][1]["text"] == "Node 12 not defined for beam 5"      # explanation lines joined
    assert p["messages"][2]["text"] == "Node 13 not defined"                 # stops at the next message
    assert [(x["program"], x["errors"], x["warnings"], x["aborted"]) for x in p["programs"]] == [
        ("aqua", 0, 1, False), ("sofimsha", 2, 1, True)]
    assert p["finished"] is True and len(p["aborted"]) == 2 and p["messages_truncated"] is False


def test_summarize_status_order(tmp_path):
    def status(text):
        f = tmp_path / "x.prt"
        f.write_text(text)
        return messages.summarize_run(str(f))["status"]

    ok = "*** Start: Program ase\n +++++    0 errors and    0 warnings +++++\n*** Stop : Program ase\n" \
         "*** End of Calculation!\n"
    assert status(ok) == "ok"
    assert status(ok.replace("0 warnings", "3 warnings")) == "ok with warnings"   # totals count
    assert status(ok.replace("0 errors", "1 errors")) == "errors"
    assert status(ok.replace("*** End of Calculation!\n", "")) == "not finished"
    canceled = "*** Start: Program ase\n*** Process canceled, error detected!\n*** End of Calculation!\n"
    assert status(canceled) == "errors"
    assert status("+++ abnormal termination of ase\n*** End of Calculation!\n") == "errors"
    assert messages.summarize_run(str(tmp_path / "missing.prt"))["status"] == "no protocol"
    assert messages.summarize_run(None)["status"] == "no protocol"


def test_totals_count_more_than_printed_messages(tmp_path):
    f = tmp_path / "x.prt"
    f.write_text("*** Start: Program ase\n+++++ warning no. 1\nw\n +++++    0 errors and   12 warnings +++++\n"
                 "*** Stop : Program ase\n*** End of Calculation!\n")
    r = messages.summarize_run(str(f))
    assert r["warnings"] == 12 and len(r["messages"]) == 1 and r["status"] == "ok with warnings"


def test_long_form_from_the_manual():
    txt = ("++++ ERROR NO. 10234 IN PROGRAM SOFILOAD\n LOAD CASE 5 NOT DEFINED\n"
           "++++ WARNING NO. 2430 IN PROGRAM ASE\nmass load case only converts nodal loads\n")
    p = messages.parse_protocol(txt)
    assert [(m["kind"], m["number"], m["program"], m["text"]) for m in p["messages"]] == [
        ("error", 10234, "SOFILOAD", "LOAD CASE 5 NOT DEFINED"),
        ("warning", 2430, "ASE", "mass load case only converts nodal loads")]
    assert p["finished"] is False


def test_message_spellings():
    for line, num in (("+++ error no.15", 15), ("+++++ ERROR No 16", 16), ("   +++++   warning   no.  17", 17)):
        p = messages.parse_protocol(line + "\n")
        assert p["messages"][0]["number"] == num, line
    assert messages.parse_protocol("++ error no. 5\n")["errors"] == 0          # two plus signs: not a message
    assert messages.parse_protocol("text +++++ error no. 5\n")["errors"] == 0  # not at line start


def test_context_before_skips_blank_lines():
    txt = "SYST PROB TH2\n\nNODE 1 0 0\nBEAM 1 1 12\n+++++ error no. 1003\nNode 12 not defined\n"
    p = messages.parse_protocol(txt, context_before=3)
    assert p["messages"][0]["input_before"] == ["NODE 1 0 0", "BEAM 1 1 12"]
    p = messages.parse_protocol(txt, context_before=6)
    assert p["messages"][0]["input_before"] == ["SYST PROB TH2", "NODE 1 0 0", "BEAM 1 1 12"]
    assert "input_before" not in messages.parse_protocol(txt)["messages"][0]


def test_max_messages_truncates_but_counts_all():
    txt = "".join(f"+++++ warning no. {i}\nw{i}\n" for i in range(1, 11)) + "+++++ error no. 99\ne\n"
    p = messages.parse_protocol(txt, max_messages=4)
    assert len(p["messages"]) == 4 and [m["number"] for m in p["messages"]] == [1, 2, 3, 4]
    assert p["warnings"] == 10 and p["errors"] == 1 and p["messages_truncated"] is True


def test_explanation_at_most_eight_lines():
    txt = "+++++ error no. 1\n" + "".join(f"l{i}\n" for i in range(12))
    assert messages.parse_protocol(txt)["messages"][0]["text"] == " ".join(f"l{i}" for i in range(8))


def test_abort_vs_end_markers():
    p = messages.parse_protocol("*** Start: Program ase\n+++++ DATA ERRONEOUS, PROGRAM ABORTED +++++\n")
    assert p["finished"] is False and p["programs"][0]["aborted"] is True
    p = messages.parse_protocol("*** end   of calculation\n")
    assert p["finished"] is True and p["aborted"] == []
    p = messages.parse_protocol("*** Start: Program ase\n*** Stop : Program ase\n*** fatal error in licence\n")
    assert p["aborted"][0]["line"] == 3 and p["programs"][0]["aborted"] is False  # after Stop: no program


def test_calculation_start_line_is_not_a_program():
    p = messages.parse_protocol("*** Start: Program Calculation - Version 2027\n*** Start: Program ase\n")
    assert [x["program"] for x in p["programs"]] == ["ase"] and p["programs"][0]["line"] == 2


def test_message_outside_program_has_no_program():
    assert messages.parse_protocol("+++++ error no. 4\nx\n")["messages"][0]["program"] == ""


def test_read_text_crlf_cp1252_nul_formfeed(tmp_path):
    f = tmp_path / "a.erg"
    f.write_bytes(b"Tr\xe4ger \xb0C\r\n\x00\x00+++++ error no. 1\r\nx\x0cpage 2\rold mac\n")
    assert messages.read_text(str(f)) == "Träger °C\n+++++ error no. 1\nx\npage 2\nold mac\n"


def test_read_text_utf8_and_undecodable(tmp_path):
    f = tmp_path / "u.prt"
    f.write_bytes("Träger µ\r\n".encode())
    assert messages.read_text(str(f)) == "Träger µ\n"
    f.write_bytes(b"\x81\x8d ok")                          # undefined in cp1252: latin-1 fallback
    assert messages.read_text(str(f)) == "\x81\x8d ok"


def test_read_text_utf16_like_nul_padding(tmp_path):
    f = tmp_path / "w.prt"
    f.write_bytes("+++++ error no. 7\r\nBad\r\n".encode("utf-16-le"))
    p = messages.parse_protocol(messages.read_text(str(f)))
    assert p["errors"] == 1 and p["messages"][0]["text"] == "Bad"


def test_read_text_max_bytes(tmp_path):
    f = tmp_path / "big.erg"
    f.write_bytes(b"a" * 100)
    assert messages.read_text(str(f), max_bytes=10) == "a" * 10


def test_summarize_erg_messages_errors_first_and_capped(tmp_path):
    prt = tmp_path / "m.prt"
    prt.write_text("*** End of Calculation!\n")
    erg = tmp_path / "m.erg"
    erg.write_text("".join(f"+++++ warning no. {i}\nw\n" for i in range(40)) +
                   "".join(f"INPUT {i}\n+++++ error no. {500 + i}\ne\n" for i in range(40)))
    r = messages.summarize_run(str(prt), str(erg))
    em = r["erg_messages"]
    # the .erg parse keeps 60 messages (40 warnings first in the file, then 20 errors): errors listed first
    assert [m["kind"] for m in em[:20]] == ["error"] * 20 and len([m for m in em if m["kind"] == "warning"]) == 30
    assert em[0]["number"] == 500 and em[0]["input_before"][-1] == "INPUT 0"
    assert r["status"] == "ok"                              # counts come from the .prt only
