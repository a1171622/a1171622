"""Test-only start-up hook for the server and cdb-worker processes the tests start (never installed).

The tests put this folder on PYTHONPATH and set SOFMCP_TEST_HOOK to a JSON file:
  {"root": <project folder>, "tests": <tests folder>,
   "settings": <settings.json to use instead of <root>/settings.json>,
   "install": {<what install.find() returns: root, sps, dll, dll_dirs, daten, ...>},
   "fake_cdb": "build" | "build_frame",     cdbio.Cdb is replaced by tests/fake_cdb.FakeCdb(<builder>())
   "wait_s": 2}                             server.WAIT_S, in the run_server.py process only
The server has no setting for its settings file or SOFiSTiK folder other than the files next to it,
so this is how a subprocess gets test values without touching the real folder.  Prints nothing.
"""
import os

_CFG = os.environ.get("SOFMCP_TEST_HOOK")

if _CFG:
    def _apply():
        import json
        import sys
        with open(_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
        for p in (cfg["root"], cfg["tests"]):
            if p not in sys.path:
                sys.path.append(p)
        from sofistik_mcp import cdbio, config, install
        if cfg.get("settings"):
            config.SETTINGS_PATH = cfg["settings"]
        if cfg.get("install") is not None:
            inst = cfg["install"]
            install.find = lambda settings=None: dict(inst)
        if cfg.get("fake_cdb"):
            import fake_cdb
            builder = getattr(fake_cdb, cfg["fake_cdb"])

            class HookCdb(fake_cdb.FakeCdb):
                def __init__(self, path, info):
                    if not os.path.isfile(path):
                        raise cdbio.CdbError(f".cdb file not found: {path}")
                    super().__init__(builder())
            cdbio.Cdb = HookCdb
        if cfg.get("wait_s") is not None and sys.argv and os.path.basename(sys.argv[0]) == "run_server.py":
            from sofistik_mcp import server
            server.WAIT_S = float(cfg["wait_s"])

    _apply()
