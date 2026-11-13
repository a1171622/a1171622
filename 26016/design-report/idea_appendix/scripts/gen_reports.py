"""Generate IDEA StatiCa Connection PDF reports from existing .ideaCon files (read only: the .ideaCon is
opened in the API service and never saved back). If the opened project has no stored results, the
connection is calculated first (same CBFEM check as the original run).
Usage: py -3.15 gen_reports.py <out_dir> <file.ideaCon> [...]
Writes <out_dir>/<joint>.pdf and appends to <out_dir>/gen_log.csv."""
import asyncio, csv, glob, os, sys, time
from ideastatica_connection_api.connection_api_service_runner import ConnectionApiServiceRunner


def find_idea():
    hits = sorted(glob.glob(r"C:\Program Files\IDEA StatiCa\StatiCa 26*\IdeaStatiCa.ConnectionRestApi.exe"))
    return os.path.dirname(hits[-1])


async def main(out, files):
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, "gen_log.csv")
    async with ConnectionApiServiceRunner(find_idea(), "Appendix26016") as runner:
        with runner.create_api_client() as api:
            for f in files:
                j = os.path.splitext(os.path.basename(f))[0]; t0 = time.time(); note = ""
                try:
                    api.project.open_project_from_filepath(f)
                    pid = api.project.active_project_id
                    cons = api.connection.get_connections(pid)
                    c = cons[0]
                    try:
                        r = api.report.generate_pdf_without_preload_content(pid, c.id, _request_timeout=900)
                        data = r.data if hasattr(r, "data") else r.read()
                        if r.status != 200 or len(data) < 1000: raise RuntimeError(f"status {r.status}")
                        note = "stored results"
                    except Exception as e1:
                        res = (api.calculation.calculate(pid, [c.id]) or [None])[0]
                        r = api.report.generate_pdf_without_preload_content(pid, c.id, _request_timeout=900)
                        data = r.data if hasattr(r, "data") else r.read()
                        note = f"recalculated ({'PASS' if res and res.passed else 'FAIL'}) after: {str(e1)[:80]}"
                    open(os.path.join(out, j + ".pdf"), "wb").write(data)
                    api.project.close_project(pid)
                    ok = "ok"
                except Exception as e:
                    ok = "FAILED"; note = str(e).splitlines()[0][:200]
                row = [j, f, ok, note, round(time.time() - t0, 1)]
                print(*row, flush=True)
                with open(log, "a", newline="") as fh: csv.writer(fh).writerow(row)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
