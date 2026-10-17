"""Shared fixtures.  The suite runs without SOFiSTiK (Windows or Linux, Python 3.10+)."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import fake_sps  # noqa: E402

from sofistik_mcp import config  # noqa: E402


def make_settings(tmp_path, **over) -> dict:
    """load_settings() result with every folder list pointing into tmp_path (nothing on the real PC)."""
    s = config.load_settings(str(tmp_path / "no-settings.json"))
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    s.update(work_folders=[str(work)], read_folders=[], examples_folders=[], manual_folders=[])
    s.update(over)
    return s


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def sps(tmp_path):
    """Path of a fake sps launcher (see tests/fake_sps.py)."""
    return fake_sps.make(tmp_path / "bin")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def server_mod(monkeypatch, tmp_path, settings, sps):
    """sofistik_mcp.server with test settings, fake sps and a fake install; job state reset after."""
    import fake_cdb

    from sofistik_mcp import server
    info = {"root": str(tmp_path / "sofistik"), "version": "2027", "sps": sps,
            "dll": str(tmp_path / "sofistik" / "sof_cdb_w-2027.dll"), "dll_dirs": [],
            "daten": fake_cdb.DATEN_PATH, "searched": []}
    monkeypatch.setattr(server, "_settings", lambda: settings)
    monkeypatch.setattr(server, "_install", lambda s=None: dict(info))
    monkeypatch.setattr(server, "WAIT_S", 2.0)
    monkeypatch.setattr(server, "_manuals", None)
    monkeypatch.setattr(server, "_examples", None)
    server._test_info = info
    yield server
    job = server._calc["job"]
    if job is not None and not job["done"].is_set():
        server._calc["stop"] = True
        if server._calc["proc"] is not None:
            server.solver._kill_tree(server._calc["proc"])
        job["done"].wait(30)
    server._calc.update(job=None, proc=None, stop=False, cdb=None)
    server._jobs.clear()


def write_hook_config(tmp_path, monkeypatch, settings_dict, install, fake="build_frame", wait_s=None) -> str:
    """Settings file + hook config for subprocesses (tests/sitehook/sitecustomize.py); sets the env."""
    sp = tmp_path / "settings.json"
    sp.write_text(json.dumps(settings_dict), encoding="utf-8")
    cfg = {"root": ROOT, "tests": HERE, "settings": str(sp), "install": install, "fake_cdb": fake,
           "wait_s": wait_s}
    cp = tmp_path / "hook.json"
    cp.write_text(json.dumps(cfg), encoding="utf-8")
    hook_dir = os.path.join(HERE, "sitehook")
    monkeypatch.setenv("SOFMCP_TEST_HOOK", str(cp))
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(p for p in (hook_dir, os.environ.get("PYTHONPATH")) if p))
    return str(cp)


class FastClock:
    """time for solver.py whose sleep() only advances the clock, so run()'s 15 s wait for the end of
    the protocol passes at once in tests where nothing more will be written."""

    def __init__(self):
        import time as _t
        self._t = _t
        self.offset = 0.0

    def time(self):
        return self._t.time() + self.offset

    def sleep(self, s):
        self.offset += s


@pytest.fixture
def fast_clock(monkeypatch):
    from sofistik_mcp import solver
    clock = FastClock()
    monkeypatch.setattr(solver, "time", clock)
    return clock


def core(extreme: dict) -> dict:
    """An extreme value without its "concurrent" components, for exact comparisons."""
    return {k: v for k, v in extreme.items() if k != "concurrent"}
