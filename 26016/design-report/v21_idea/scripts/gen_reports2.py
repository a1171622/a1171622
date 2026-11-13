"""Stamp COPIES of the .ideaCon projects with the CaSE project data and generate the IDEA Connection PDF report.
For each source .ideaCon: copy to <proj_dir>, open the copy, set project data (name, number, author, description = joint
code, date), generate the PDF; if the report has no check summary (results not kept), calculate and generate again;
save the stamped copy. The source files are never opened for writing.
Usage: py -3.15 gen_reports2.py <proj_dir> <pdf_dir> <file.ideaCon> [...]"""
import asyncio, csv, glob, os, sys, time, shutil, io, datetime
from ideastatica_connection_api.connection_api_service_runner import ConnectionApiServiceRunner
from ideastatica_connection_api.models.con_project_data import ConProjectData


def find_idea():
    return os.path.dirname(sorted(glob.glob(r"C:\Program Files\IDEA StatiCa\StatiCa 26*\IdeaStatiCa.ConnectionRestApi.exe"))[-1])


def has_summary(data):
    # the PDF text is compressed; a calculated report is clearly larger than an uncalculated one and carries the
    # check pages: test by size only here, the merge script re-reads every Summary page with pypdf
    return len(data) > 200_000


async def main(pdir, odir, files):
    os.makedirs(pdir, exist_ok=True); os.makedirs(odir, exist_ok=True)
    log = os.path.join(odir, "gen_log.csv")
    async with ConnectionApiServiceRunner(find_idea(), "Appendix26016b") as runner:
        with runner.create_api_client() as api:
            for f in files:
                j = os.path.splitext(os.path.basename(f))[0]; t0 = time.time(); note = []
                cp = os.path.join(pdir, j + ".ideaCon")
                try:
                    shutil.copy2(f, cp)
                    api.project.open_project_from_filepath(cp)
                    pid = api.project.active_project_id
                    pd = api.project.get_project_data(pid).project_info
                    pd.name = "26016 Concourse Viewing Platform"; pd.project_number = "26016"; pd.author = "CaSE"
                    pd.description = j; pd.var_date = datetime.datetime(2026, 11, 13, 12, 0)
                    api.project.update_project_data(pid, pd)
                    c = api.connection.get_connections(pid)[0]
                    r = api.report.generate_pdf_without_preload_content(pid, c.id, _request_timeout=900)
                    data = r.data
                    if r.status != 200 or not has_summary(data):
                        res = (api.calculation.calculate(pid, [c.id]) or [None])[0]
                        note.append("recalculated " + ("PASS" if res and res.passed else "FAIL"))
                        r = api.report.generate_pdf_without_preload_content(pid, c.id, _request_timeout=900); data = r.data
                    open(os.path.join(odir, j + ".pdf"), "wb").write(data)
                    api.project.download_project(pid, cp)
                    api.project.close_project(pid)
                    ok = "ok"
                except Exception as e:
                    ok = "FAILED"; note.append(str(e).splitlines()[0][:200])
                row = [j, f, cp, ok, "; ".join(note) or "stored results", round(time.time() - t0, 1)]
                print(*row, flush=True)
                with open(log, "a", newline="") as fh: csv.writer(fh).writerow(row)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
