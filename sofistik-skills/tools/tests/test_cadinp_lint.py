import os

from _util import MINI, ids, real, run, tmpdir
import _cadinp as C


def test_model_mini():
    m = C.Model(C.Dat.from_file(MINI))
    assert m.lcs[101].facd == 1.35
    assert [(s, f) for s, f, *_ in m.lcs[101].copies] == [(2, 1.35), (3, 1.5)]
    assert [s for s, *_ in m.lcs[102].copies] == [2, 3]          # LOOP + LET# expanded
    assert m.sections == {2: "UB 254x146x43"} and m.materials == {3: "S 275"} and m.section_mno == {2: 3}
    b = m.bdk_members()
    assert len(b) == 1 and b[0]["id"] == 10 and b[0]["cont"] == [11] and b[0]["lcst"] == 9100


def test_lint_clean_mini():
    code, o = run("dat_lint.py", MINI)
    assert code == 0, o


def test_lint_catches_faults():
    text, _ = C.read_text(MINI)
    cases = {
        "S1": text.replace("TYPE PG #SDL", "TYPE PG 2.5"),
        "S2": text.replace("COPY NO 2 FACT 1.35", "COPY NO 77 FACT 1.35"),
        "S4": text.replace("STO#GQ 1.5", "STO#GQ 1.5\nSTO#NDIV 8"),
        "S7": text.replace("COPY NO 3 FACT #GQ", "COPY NO 3 FACT #GQ\n  COPY NO 3 FACT #GQ"),
        "S8": text.replace("COPY NO 3 FACT #GQ", "COPY NO 3 FACT #GQ*1"),
        "S11": text.replace("LC 101,102", "LC 101"),
        "S14": text.replace("TYPE PG #GQ", "TYPE PG #NOPE"),
    }
    d = tmpdir()
    for rule, t in cases.items():
        p = os.path.join(d, rule + ".dat")
        with open(p, "w") as f:
            f.write(t)
        code, o = run("dat_lint.py", p)
        assert code == 1 and ids(o)[rule] == "FAIL", (rule, o["checks"])


def test_lint_nul_cr_tolerated():
    d = tmpdir()
    p = os.path.join(d, "crlf.dat")
    with open(MINI, "rb") as f:
        raw = f.read()
    with open(p, "wb") as f:
        f.write(raw.replace(b"\n", b"\r\n") + b"\x00\x00")
    code, o = run("dat_lint.py", p)
    assert code == 0, o


def test_lint_real_files_clean():
    for name in ("26016_loads_unified.dat", "26016_check_v2.dat"):
        code, o = run("dat_lint.py", real(name))
        assert code == 0, (name, [c for c in o["checks"] if c["verdict"] != "PASS"][:3])
