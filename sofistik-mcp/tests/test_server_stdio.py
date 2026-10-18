"""The server over the real MCP stdio protocol, as Claude Desktop starts it: run_server.py in a
subprocess, the official MCP client, test settings / fake sps / fake .cdb injected through
tests/sitehook (the server itself always reads settings.json next to run_server.py)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys

import fake_cdb
import fake_sps
import pytest
from conftest import HERE, ROOT, core, write_hook_config

TOOLS = {
    "sofistik_status", "list_folder", "read_text_file", "write_dat_file", "run_calculation", "get_job_result",
    "stop_calculation", "read_calculation_messages", "cdb_overview", "cdb_load_cases", "cdb_nodes",
    "cdb_node_results", "cdb_support_reactions", "cdb_beam_forces", "cdb_truss_cable_forces", "cdb_envelope",
    "cdb_read_key", "search_manuals", "read_manual_page", "list_manuals", "index_manual", "search_examples",
    "report_check", "dashboard_status", "check_cdb_lock", "clear_cdb_lock", "clone_cdb",
}
REQUIRED = {
    "sofistik_status": [], "list_folder": ["path"], "read_text_file": ["path"],
    "write_dat_file": ["path", "content"], "run_calculation": ["dat_path"], "get_job_result": [],
    "stop_calculation": [], "read_calculation_messages": ["path"], "cdb_overview": ["cdb_path"],
    "cdb_load_cases": ["cdb_path"], "cdb_nodes": ["cdb_path"], "cdb_node_results": ["cdb_path", "load_case"],
    "cdb_support_reactions": ["cdb_path", "load_case"], "cdb_beam_forces": ["cdb_path", "load_case"],
    "cdb_truss_cable_forces": ["cdb_path", "load_case"], "cdb_envelope": ["cdb_path", "load_cases"],
    "cdb_read_key": ["cdb_path", "kwh", "kwl"], "search_manuals": ["query"],
    "read_manual_page": ["manual", "page"], "list_manuals": [], "index_manual": ["manual"],
    "search_examples": ["query"], "report_check": ["check"], "dashboard_status": [],
    "check_cdb_lock": ["cdb_path"], "clear_cdb_lock": ["cdb_path"], "clone_cdb": ["cdb_path", "new_name"],
}


def test_readme_documents_every_tool_count():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert f"| {len(TOOLS)} tools |" in readme


def test_readme_lists_every_tool():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert [t for t in sorted(TOOLS) if f"`{t}`" not in readme] == []


@pytest.fixture
def stdio_env(tmp_path, monkeypatch):
    from test_docsearch import make_pdf
    work, ref, man, ex = (tmp_path / n for n in ("work", "ref", "man", "ex"))
    for d in (work, ref, man, ex / "ase.dat" / "english"):
        d.mkdir(parents=True)
    make_pdf(man / "zzztest_1.pdf", ["ZQX unique word", "second page ZQX ZQX"])
    (ex / "ase.dat" / "english" / "frame.dat").write_text("!#!Info  Example: frame\n+PROG ASE\nZQXEXAMPLE 1\n")
    (ref / "old.prt").write_bytes(open(os.path.join(HERE, "sample_error.prt"), "rb").read())
    (tmp_path / "secret.txt").write_text("secret")
    sps = fake_sps.make(tmp_path / "sofistik")
    info = {"root": str(tmp_path / "sofistik"), "version": "2027", "sps": sps,
            "dll": str(tmp_path / "sofistik" / "sof_cdb_w-2027.dll"), "dll_dirs": [], "daten": fake_cdb.DATEN_PATH,
            "searched": []}
    settings = {"_help": "test", "work_folders": [str(work)], "read_folders": [str(ref)],
                "examples_folders": [str(ex)], "manual_folders": [str(man)], "run_timeout_minutes": 5,
                "max_parallel_runs": 1}
    write_hook_config(tmp_path, monkeypatch, settings, install=info, fake="build_frame", wait_s=1.5)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    env = dict(os.environ)
    return {"tmp": tmp_path, "work": work, "ref": ref, "env": env, "settings": tmp_path / "settings.json"}


def session(env, body):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=[os.path.join(ROOT, "run_server.py")],
                                       env=env["env"], cwd=str(env["tmp"]))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                init = await s.initialize()

                async def call(name, **args):
                    res = await s.call_tool(name, args)
                    assert not res.isError, (name, res.content)
                    assert len(res.content) == 1 and res.content[0].type == "text"
                    return json.loads(res.content[0].text)
                return await body(s, call, init)
    return asyncio.run(asyncio.wait_for(go(), 150))


def test_protocol_tools_and_every_call(stdio_env):
    work, ref, tmp = stdio_env["work"], stdio_env["ref"], stdio_env["tmp"]

    async def body(s, call, init):
        out = {"init": init, "tools": (await s.list_tools()).tools}
        out["status"] = await call("sofistik_status")
        out["write"] = await call("write_dat_file", path=str(work / "frame.dat"),
                                  content="+PROG ASE\nHEAD frame\nEND\n$ FAKE mode=warnings\n")
        out["write_again"] = await call("write_dat_file", path=str(work / "frame.dat"), content="x")
        out["write_over"] = await call("write_dat_file", path=str(work / "frame.dat"), overwrite=True,
                                       content="+PROG ASE\nHEAD frame\nEND\n$ FAKE mode=warnings\n")
        out["write_out"] = await call("write_dat_file", path=str(tmp / "x.dat"), content="x")
        out["write_ref"] = await call("write_dat_file", path=str(ref / "x.dat"), content="x")
        out["write_srv"] = await call("write_dat_file", path=os.path.join(ROOT, "x.dat"), content="x")
        out["run"] = await call("run_calculation", dat_path=str(work / "frame.dat"))
        out["msgs"] = await call("read_calculation_messages", path=str(work / "frame.dat"))
        out["old_msgs"] = await call("read_calculation_messages", path=str(ref / "old.prt"))
        out["list"] = await call("list_folder", path=str(work), pattern="frame.*")
        out["read"] = await call("read_text_file", path=str(work / "frame.dat"), max_lines=2)
        out["read_out"] = await call("read_text_file", path=str(tmp / "secret.txt"))
        out["list_out"] = await call("list_folder", path=str(tmp))
        cdb = str(work / "frame.cdb")
        out["overview"] = await call("cdb_overview", cdb_path=cdb)
        out["lcs"] = await call("cdb_load_cases", cdb_path=cdb, load_cases="2001-2002")
        out["nodes"] = await call("cdb_nodes", cdb_path=cdb, nodes="5")
        out["node_res"] = await call("cdb_node_results", cdb_path=cdb, load_case=1, nodes="2")
        out["support"] = await call("cdb_support_reactions", cdb_path=cdb, load_case=2)
        out["beams"] = await call("cdb_beam_forces", cdb_path=cdb, load_case=1, groups="1", ends_only=True)
        out["truss"] = await call("cdb_truss_cable_forces", cdb_path=cdb, load_case=1, elements="5002")
        out["env"] = await call("cdb_envelope", cdb_path=cdb, load_cases="1-2", what="node")
        out["key"] = await call("cdb_read_key", cdb_path=cdb, kwh=20, kwl=0, class_name="CNODE", max_records=2)
        out["bad_ids"] = await call("cdb_node_results", cdb_path=cdb, load_case=1, nodes="one")
        out["cdb_out"] = await call("cdb_overview", cdb_path=str(tmp / "x.cdb"))
        out["man_list"] = await call("list_manuals")
        out["man_index"] = await call("index_manual", manual="zzztest_1.pdf")
        out["man_search"] = await call("search_manuals", query="ZQX", manuals=["zzztest"])
        out["man_page"] = await call("read_manual_page", manual="zzztest_1", page=2)
        out["examples"] = await call("search_examples", query="zqxexample")
        out["job_none"] = await call("get_job_result", job_id="calc-0000")
        out["stop_none"] = await call("stop_calculation")
        out["bad_args"] = await s.call_tool("cdb_node_results", {"cdb_path": cdb, "load_case": "not a number"})
        return out

    o = session(stdio_env, body)
    assert o["init"].serverInfo.name == "sofistik" and "SOFiSTiK 2027" in o["init"].instructions
    tools = {t.name: t for t in o["tools"]}
    assert set(tools) == TOOLS and len(o["tools"]) == 27
    for name, t in tools.items():
        assert t.description and len(t.description) > 30, name
        assert t.inputSchema["type"] == "object", name
        assert sorted(t.inputSchema.get("required", [])) == sorted(REQUIRED[name]), name
    props = tools["cdb_beam_forces"].inputSchema["properties"]
    assert props["load_case"]["type"] == "integer" and props["ends_only"]["default"] is False
    assert tools["write_dat_file"].inputSchema["properties"]["overwrite"]["default"] is False

    assert o["status"]["sofistik"]["sps"].startswith(str(stdio_env["tmp"]))
    assert o["status"]["settings_file"] == str(stdio_env["settings"]) and o["status"]["run_timeout_minutes"] == 5.0
    assert o["write"]["written"] == str(work / "frame.dat") and "already exists" in o["write_again"]["error"]
    assert o["write_over"]["backup_of_previous"].startswith(str(work / "frame.dat.bak-"))
    assert os.path.isfile(o["write_over"]["backup_of_previous"])
    assert "outside the work folders" in o["write_out"]["error"] and not (tmp / "x.dat").exists()
    assert "outside the work folders" in o["write_ref"]["error"]
    assert "outside the work folders" in o["write_srv"]["error"]
    assert o["run"]["status"] == "ok with warnings" and o["run"]["files"]["cdb"]["updated_by_this_run"]
    assert o["msgs"]["status"] == "ok with warnings" and o["msgs"]["messages"][0]["number"] == 2430
    assert o["old_msgs"]["status"] == "errors" and o["old_msgs"]["messages"][0]["number"] == 10001
    assert {os.path.basename(f["path"]) for f in o["list"]["files"]} == {
        "frame.dat", "frame.prt", "frame.erg", "frame.cdb", "frame.plb",
        os.path.basename(o["write_over"]["backup_of_previous"])}
    assert o["read"]["text"] == "1: +PROG ASE\n2: HEAD frame" and o["read"]["total_lines"] == 5
    assert "outside the folders" in o["read_out"]["error"] and "outside the folders" in o["list_out"]["error"]
    assert o["overview"]["system"]["project"] == "FRAME TEST" and o["overview"]["element_counts"]["beams"] == 4
    assert [(x["lc"], x["frequency_Hz"]) for x in o["lcs"]["rows"]] == [(2001, pytest.approx(4.0)), (2002, None)]
    assert o["nodes"]["rows"] == [{"node": 5, "x": 9.0, "y": 0.0, "z": 3.0, "fixity_code": 0}]
    assert o["node_res"]["rows"][0]["ux"] == 1.0 and o["node_res"]["rows"][0]["uz"] == -4.2
    assert o["support"]["sum_kN"]["pz"] == 160.0 and o["support"]["sum_stored_by_sofistik_kN"][2] == 160.0
    assert [(r["beam"], r["x"], r["My"]) for r in o["beams"]["rows"]] == [
        (1001, 0.0, -20.0), (1001, 5.0, -15.0), (1002, 0.0, -30.0), (1002, 4.0, 12.0)]
    assert o["truss"]["rows"] == [{"element": 5002, "N": -7.25, "axial_disp": -0.4}]
    assert core(o["env"]["overall"]["uz"]["min"]) == {"value": -21.0, "node": 3, "lc": 2}
    assert [r["m_nr"] for r in o["key"]["records"]] == [1, 2] and o["key"]["records"][1]["m_xyz"][0] == 2.5
    assert "Cannot read number list" in o["bad_ids"]["error"]
    assert "outside the folders" in o["cdb_out"]["error"]
    assert ("zzztest_1.pdf", False) in [(m["manual"], m["indexed"]) for m in o["man_list"]["manuals"]]
    assert o["man_index"] == {"manual": "zzztest_1.pdf", "pages": 2}
    assert [(h["manual"], h["pdf_page"]) for h in o["man_search"]["hits"]] == [("zzztest_1.pdf", 2),
                                                                               ("zzztest_1.pdf", 1)]
    assert o["man_page"]["text"] == "second page ZQX ZQX"
    assert o["examples"]["hits"][0]["title"] == "frame"
    assert "No job calc-0000" in o["job_none"]["error"] and o["stop_none"] == {"status": "nothing running"}
    assert o["bad_args"].isError and "validation error" in o["bad_args"].content[0].text.lower()
    assert (stdio_env["tmp"] / "Local" / "sofistik-mcp" / "manual_cache" / "zzztest_1.pdf.json.gz").is_file()


def test_protocol_jobs_running_stop_and_locks(stdio_env):
    work = stdio_env["work"]
    (work / "slow.dat").write_text("+PROG ASE\nEND\n$ FAKE sleep=4\n")
    (work / "long.dat").write_text("+PROG ASE\nEND\n$ FAKE sleep=120\n")

    async def body(s, call, init):
        out = {}
        out["first"] = await call("run_calculation", dat_path=str(work / "slow.dat"))
        out["busy"] = await call("run_calculation", dat_path=str(work / "long.dat"))
        out["locked"] = await call("cdb_beam_forces", cdb_path=str(work / "slow.cdb"), load_case=1)
        out["locked_dat"] = await call("cdb_overview", cdb_path=str(work / "slow.dat"))
        out["done"] = await call("get_job_result", job_id=out["first"]["job_id"], wait_seconds=30)
        out["after"] = await call("cdb_overview", cdb_path=str(work / "slow.cdb"))
        out["long"] = await call("run_calculation", dat_path=str(work / "long.dat"))
        out["latest"] = await call("get_job_result", wait_seconds=0.5)
        out["stop"] = await call("stop_calculation")
        out["again"] = await call("get_job_result", job_id=out["long"]["job_id"], wait_seconds=30)
        return out

    o = session(stdio_env, body)
    first = o["first"]
    assert first["status"] == "running" and re.fullmatch(r"calc-[0-9a-f]{8}", first["job_id"])
    assert first["what"] == "slow.dat"
    assert o["busy"]["status"] == "not run" and "already running" in o["busy"]["reason"]
    assert o["busy"]["running"] == [first["job_id"]]
    assert "being calculated right now" in o["locked"]["error"] and first["job_id"] in o["locked"]["error"]
    assert "being calculated right now" in o["locked_dat"]["error"]
    assert o["done"]["status"] == "ok" and o["done"]["seconds"] >= 3.5
    assert o["done"]["files"]["cdb"]["updated_by_this_run"]
    assert o["after"]["system"]["project"] == "FRAME TEST"
    assert o["long"]["status"] == "running" and o["latest"]["job_id"] == o["long"]["job_id"]
    # stop_calculation answers within a few seconds: the result, or "stopping" while the kill finishes
    assert o["stop"]["status"] in ("stopped", "stopping")
    assert o["again"]["status"] == "stopped" and "results are incomplete" in o["again"]["reason"]
    assert not (work / "long.prt").exists()
