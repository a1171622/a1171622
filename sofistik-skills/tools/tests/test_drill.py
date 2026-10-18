from _util import MINI, real, run, tmpdir


def test_drill_mini_all_caught():
    code, o = run("mutation_drill.py", MINI, "--workdir", tmpdir())
    assert code == 0, o["checks"]
    res = {(r["checker"], r["mutant"]): r["result"] for r in o["matrix"]}
    assert all(v in ("caught", "n/a", "BLIND") for v in res.values()), res
    assert res[("dat_lint", "S11")] == "caught" and res[("combo_check", "double_atom")] == "caught"


def test_drill_real_loads_unified():
    dat = real("26016_loads_unified.dat")
    code, o = run("mutation_drill.py", dat, "--workdir", tmpdir(), "--only", "dat_lint,combo_check")
    assert code == 0, o["checks"]
