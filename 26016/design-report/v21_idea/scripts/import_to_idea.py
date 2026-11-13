"""Import IDEA Open Model (.xml) joints into IDEA StatiCa Connection, check every load effect, summarise.

Runs on Wing's PC (needs IDEA StatiCa 26.0 installed).
Usage:  python import_to_idea.py <joint.xml or folder of .xml> [more ...] [--no-calc]
Output: one .ideaCon next to each .xml (calculated, so results show when you open it), and
        joint_check_summary.csv next to the first file: one row per joint with pass/fail, the highest
        utilisation per check (plates, bolts, welds, ...) and the load effect that governs it.
A single file is opened in IDEA StatiCa Connection at the end.
"""
import asyncio, csv, glob, os, sys
from ideastatica_connection_api.connection_api_service_runner import ConnectionApiServiceRunner

def find_idea():
    hits = sorted(glob.glob(r"C:\Program Files\IDEA StatiCa\StatiCa 26*\IdeaStatiCa.ConnectionRestApi.exe"))
    if not hits:
        sys.exit("Could not find IDEA StatiCa 26 under C:\\Program Files\\IDEA StatiCa. Edit find_idea() with your install folder.")
    return os.path.dirname(hits[-1])

def check_one(api, pid, c, row, check_names):
    effects = api.load_effect.get_load_effects(pid, c.id) or []
    le_name = {e.id: e.name for e in effects}
    row["load_effects"] = len(effects)
    print(f"   {len(effects)} load effects, running CBFEM check...")
    res = (api.calculation.calculate(pid, [c.id]) or [None])[0]
    if res is None:
        raise RuntimeError("IDEA returned no result (no load effects?)")
    worst, worst_name, worst_le = None, "", ""
    for chk in res.result_summary or []:
        if chk.skipped or chk.check_value is None:
            continue
        name, val = chk.name or "check", float(chk.check_value)
        if name not in check_names:
            check_names.append(name)
        if val > row.get(name + " max %", float("-inf")):
            row[name + " max %"] = round(val, 1)
            row[name + " governing"] = le_name.get(chk.load_case_id, chk.load_case_id or "")
        if worst is None or val > worst:
            worst, worst_name, worst_le = val, name, le_name.get(chk.load_case_id, chk.load_case_id or "")
    row["passed"] = "PASS" if res.passed else "FAIL"
    row["max_utilisation_%"] = "" if worst is None else round(worst, 1)
    row["governing_check"], row["governing_load_effect"] = worst_name, worst_le
    print(f"   {row['passed']}" + ("" if worst is None else f", max {worst:.1f}% ({worst_name}, {worst_le})"))

def import_one(api, xml, do_calc, rows, check_names):
    out = os.path.splitext(xml)[0] + ".ideaCon"
    api.project.open_project_from_filepath(xml)
    pid = api.project.active_project_id
    for c in api.connection.get_connections(pid):
        ops = api.operation.get_operations(pid, c.id)
        print(f"  connection '{c.name}': {len(ops)} operations")
        row = {"joint": os.path.basename(xml).replace("_joint.xml", ""), "connection": c.name}
        rows.append(row)
        if do_calc:
            try:
                check_one(api, pid, c, row, check_names)
            except Exception as e:
                row["error"] = str(e).splitlines()[0][:200]
                print("   check FAILED:", row["error"])
    api.project.download_project(pid, out)
    print("  saved", out)
    return out

def write_summary(path, rows, check_names):
    cols = ["joint", "connection", "load_effects", "passed", "max_utilisation_%", "governing_check", "governing_load_effect"]
    for k in check_names:
        cols += [k + " max %", k + " governing"]
    cols.append("error")
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print("Summary:", path)
    except PermissionError:
        print(f"Could not write {path} - is it open in Excel? Close it and run again.")

async def main(args):
    do_calc = "--no-calc" not in args
    files = []
    for p in [a for a in args if a != "--no-calc"]:
        p = os.path.abspath(p)
        files += sorted(glob.glob(os.path.join(p, "*.xml"))) if os.path.isdir(p) else [p]
    if not files:
        sys.exit("Drag one or more joint .xml files (or a folder) onto run_import.bat.")
    idea_dir = find_idea()
    print("IDEA StatiCa folder:", idea_dir)
    done, failed, rows, check_names = [], [], [], []
    async with ConnectionApiServiceRunner(idea_dir, "SofistikJointBuilder") as runner:
        with runner.create_api_client() as api:
            for xml in files:
                print(os.path.basename(xml))
                try:
                    done.append(import_one(api, xml, do_calc, rows, check_names))
                except Exception as e:
                    print("  FAILED:", e)
                    failed.append(xml)
                    rows.append({"joint": os.path.basename(xml), "error": "import failed: " + str(e).splitlines()[0][:200]})
    print(f"{len(done)} imported, {len(failed)} failed")
    if do_calc and rows:
        write_summary(os.path.join(os.path.dirname(files[0]), "joint_check_summary.csv"), rows, check_names)
        bad = [r["joint"] for r in rows if r.get("passed") != "PASS"]
        print("All joints PASS" if not bad else "Check these joints: " + ", ".join(bad))
    if len(done) == 1:
        pass  # v21: do not open the GUI

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
