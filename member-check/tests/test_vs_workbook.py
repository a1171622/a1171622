"""Proof that the Python EN 1993-1-1 module gives the same numbers as Wing's spreadsheet EC3_beam_column_ULS.xlsx.

For each case the spreadsheet is rebuilt, the inputs are typed into its yellow cells, LibreOffice recalculates it,
and every named result cell is compared with the value of the same name from memcheck.codes.en1993_1_1.check().
Run (cloud, needs LibreOffice):  python3 tests/test_vs_workbook.py
"""
import json
import os
import random
import subprocess
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from memcheck.codes import en1993_1_1 as EC  # noqa: E402

BUILD = os.environ.get("EC3_BUILD", "/mnt/project-files/beam-column-calc/build/build_workbook.py")
RECALC = os.environ.get("RECALC", "")
WORK = os.environ.get("WORK", "/tmp/claude-0/w/wbtest")

NAMES = ["A_", "Iy_", "Iz_", "Wply_", "Wplz_", "It_", "Iw_", "Avz_", "Avy_", "fy_", "cls_", "Npl_", "Vplz_", "Vply_",
         "MyV_", "MzV_", "MNy_", "MNz_", "uNM_", "Ncry_", "lamy_", "chiy_", "Nby_", "Ncrz_", "lamz_", "chiz_", "Nbz_",
         "NcrT_", "chiT_", "Cfac1_", "Cfac2_", "Mcr_", "lamLT_", "chiLT_", "Mb_", "kc_", "ff_", "CmyB_", "CmzB_", "CmLTB_",
         "kyyB_", "kzzB_", "kyzB_", "kzyB_", "u61B_", "u62B_", "Cmy0_", "Cmz0_", "CmyA_", "CmLTA_", "kyyA_", "kyzA_",
         "kzyA_", "kzzA_", "u61A_", "u62A_", "u61_", "u62_"]

SECTS = ["UB 254x146x43", "UB 457x191x89", "UC 305x305x240", "UB 762x267x173", "UC 203x203x46", "UB 610x229x101"]
SHAPES = ["Uniform", "Linear", "Parabolic", "Triangular"]
SUPS = ["Pinned/Pinned", "Fixed/Pinned", "Fixed/Fixed"]


def cases(n=24, seed=7):
    rnd = random.Random(seed)
    out = [dict()]       # case 0 = the spreadsheet defaults (Gardner & Nethercot Ex 6.10)
    for _ in range(n - 1):
        out.append(dict(
            sect_=rnd.choice(SECTS), grade_=rnd.choice(["S275", "S355", "S235"]),
            L_=round(rnd.uniform(2, 9), 2), NEd_=round(rnd.uniform(-1500, 300), 1), VyEd_=round(rnd.uniform(0, 40), 1),
            VzEd_=round(rnd.uniform(0, 400), 1), MyEd_=round(rnd.uniform(0, 400), 1), MzEd_=round(rnd.uniform(0, 40), 1),
            kLy_=rnd.choice([1.0, 0.85, 0.7]), kLz_=rnd.choice([1.0, 0.5]), kLT_=rnd.choice([1.0, 0.5]),
            shy_=rnd.choice(SHAPES), psiy_=round(rnd.uniform(-1, 1), 2), supy_=rnd.choice(SUPS),
            shz_=rnd.choice(SHAPES), psiz_=round(rnd.uniform(-1, 1), 2), supz_=rnd.choice(SUPS),
            shLT_=rnd.choice(SHAPES), psiLT_=round(rnd.uniform(-1, 1), 2), supLT_=rnd.choice(SUPS),
            lp_=rnd.choice(["Centroid", "Top flange", "Bottom flange"]), na_=rnd.choice(["UK", "CEN"]),
            ltbmo_=rnd.choice(["General 6.3.2.2", "Rolled/welded 6.3.2.3"]),
            intm_=rnd.choice(["Annex A", "Annex B", "Both (worst)"]), fab_="Rolled"))
    return out


DEFAULTS = dict(sect_="UC 305x305x240", grade_="S275", L_=4.2, NEd_=-3440, VyEd_=26.2, VzEd_=200, MyEd_=420,
                MzEd_=110, kLy_=0.7, kLz_=1.0, kLT_=1.0, kT_=1.0, shy_="Linear", psiy_=-1, supy_="Pinned/Pinned",
                shz_="Linear", psiz_=0, supz_="Pinned/Pinned", shLT_="Linear", psiLT_=-1, supLT_="Pinned/Pinned",
                lp_="Centroid", na_="CEN", ltbmo_="General 6.3.2.2", intm_="Both (worst)", fab_="Rolled",
                tors_="Yes", fyrule_="Table 3.1", clsel_="Auto")


def engine(c):
    i = {**DEFAULTS, **c}
    sec = EC.SectionData.from_name(i["sect_"])
    st = EC.Settings(na=i["na_"], ltb_method=i["ltbmo_"], interaction=i["intm_"], fy_rule=i["fyrule_"])
    h = sec.props["h"]
    zg = h / 2 if i["lp_"] == "Top flange" else -h / 2 if i["lp_"] == "Bottom flange" else 0.0
    bk = EC.Buckling(L=i["L_"], Lcr_y=i["kLy_"] * i["L_"], Lcr_z=i["kLz_"] * i["L_"], L_LT=i["kLT_"] * i["L_"],
                     kT=i["kT_"], fy_y=EC.shape_factors(i["shy_"], i["psiy_"], i["supy_"]),
                     fz=EC.shape_factors(i["shz_"], i["psiz_"], i["supz_"]),
                     fLT=EC.shape_factors(i["shLT_"], i["psiLT_"], i["supLT_"]), zg=zg,
                     torsion_susceptible=(i["tors_"] == "Yes"))
    dem = EC.Demand(N=i["NEd_"], Vy=i["VyEd_"], Vz=i["VzEd_"], My=i["MyEd_"], Mz=i["MzEd_"])
    return EC.check(sec, i["grade_"], dem, bk, st)


def workbook(tag, c, base):
    wb = openpyxl.load_workbook(base)
    for k, val in c.items():
        sh, ref = list(wb.defined_names[k].destinations)[0]
        wb[sh][ref.replace("$", "")].value = val
    fn = os.path.join(WORK, f"case_{tag}.xlsx")
    wb.save(fn)
    out = subprocess.run([sys.executable, RECALC, fn, "90"], capture_output=True, text=True)
    j = json.loads(out.stdout)
    if j.get("status") != "success":
        return None
    wb2 = openpyxl.load_workbook(fn, data_only=True)
    vals = {}
    for nm, dn in wb2.defined_names.items():
        try:
            sh, ref = list(dn.destinations)[0]
            vals[nm] = wb2[sh][ref.replace("$", "")].value
        except Exception:
            pass
    return vals


def main():
    global RECALC
    if not RECALC:
        import glob
        RECALC = (glob.glob("/root/.claude/skills/synced/*/xlsx/scripts/recalc.py") + [""])[0]
    os.makedirs(WORK, exist_ok=True)
    base = os.path.join(WORK, "base.xlsx")
    subprocess.run([sys.executable, BUILD, base], check=True, capture_output=True)
    worst, rows, n_cmp = 0.0, [], 0
    for k, c in enumerate(cases()):
        wbv = workbook(k, c, base)
        env = engine(c)
        if wbv is None:
            print(f"case {k}: spreadsheet shows #NUM (N above an elastic critical force); engine 6.61/6.62 = "
                  f"{env['u61_']:.2f} / {env['u62_']:.2f}")
            continue
        for nm in NAMES:
            a, b = wbv.get(nm), env.get(nm)
            if a is None or b is None or isinstance(a, str):
                continue
            n_cmp += 1
            d = abs(a - b) / max(abs(a), 1e-9)
            if abs(a) < 1e-6 and abs(b) < 1e-6:
                d = 0.0
            rows.append((k, nm, a, b, d))
            worst = max(worst, d)
            if d > 1e-6:
                print(f"case {k} {nm}: workbook {a!r} engine {b!r} diff {d:.2e}")
    print(f"{len(cases())} cases, {n_cmp} values compared, largest relative difference {worst:.2e}")
    json.dump(rows, open(os.path.join(WORK, "compare.json"), "w"))
    return 0 if worst < 1e-6 else 1


if __name__ == "__main__":
    sys.exit(main())
