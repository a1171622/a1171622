"""configure_clients.py: registering the server in Claude Desktop / Claude Code without breaking them."""
from __future__ import annotations

import datetime
import glob
import json
import os
import subprocess

import pytest

from sofistik_mcp import configure_clients as cc

PY = os.path.join("C:", "venv", "python.exe")


@pytest.fixture
def dirs(monkeypatch, tmp_path):
    appdata, local = tmp_path / "Roaming", tmp_path / "Local"
    appdata.mkdir()
    local.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(cc.shutil, "which", lambda name: None)       # no Claude Code by default
    return appdata, local


def cfg_path(d):
    return os.path.join(str(d), "claude_desktop_config.json")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_creates_config_when_claude_never_started(dirs):
    appdata, _ = dirs
    rep = cc.update_desktop(PY)
    p = cfg_path(appdata / "Claude")
    assert rep == ["Registered in " + p]
    assert load(p) == {"mcpServers": {"sofistik": {"command": PY, "args": [cc.ENTRY]}}}
    assert cc.ENTRY == os.path.join(cc.ROOT, "run_server.py") and os.path.isfile(cc.ENTRY)
    assert glob.glob(p + ".bak-*") == [] and not os.path.exists(p + ".tmp")


def test_merge_keeps_other_servers_and_keys_and_backs_up(dirs):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    original = {"globalShortcut": "Ctrl+Space", "mcpServers": {
        "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\x"]},
        "sofistik": {"command": "old.exe", "args": ["old.py"]}}, "preferences": {"theme": "dark"}}
    raw = json.dumps(original, indent=4)
    with open(p, "w", encoding="utf-8-sig") as f:                  # BOM, as Notepad may save it
        f.write(raw)
    cc.update_desktop(PY)
    new = load(p)
    assert new["globalShortcut"] == "Ctrl+Space" and new["preferences"] == {"theme": "dark"}
    assert new["mcpServers"]["filesystem"] == original["mcpServers"]["filesystem"]
    assert new["mcpServers"]["sofistik"] == {"command": PY, "args": [cc.ENTRY]}
    baks = glob.glob(p + ".bak-*")
    assert len(baks) == 1
    with open(baks[0], encoding="utf-8-sig") as f:
        assert f.read() == raw                                        # byte-for-byte copy of the old file
    assert not os.path.exists(p + ".tmp")


def test_remove_only_removes_sofistik(dirs):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {"a": {"command": "a"}, "sofistik": {"command": "x"}}, "k": 1}, f)
    rep = cc.update_desktop(PY, remove=True)
    assert rep == ["Removed from " + p]
    assert load(p) == {"mcpServers": {"a": {"command": "a"}}, "k": 1}
    cc.update_desktop(PY, remove=True)                              # removing twice is fine
    assert load(p) == {"mcpServers": {"a": {"command": "a"}}, "k": 1}


@pytest.mark.parametrize("content", ["", "   \n", "{}", '{"mcpServers": null}', '{"mcpServers": []}'])
def test_empty_or_odd_configs(dirs, content):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    cc.update_desktop(PY)
    assert load(p)["mcpServers"] == {"sofistik": {"command": PY, "args": [cc.ENTRY]}}


@pytest.mark.parametrize("content, why", [("{bad json", "not valid JSON"), ('["a list"]', "unexpected content")])
def test_broken_config_is_not_touched(dirs, content, why):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    rep = cc.update_desktop(PY)
    assert len(rep) == 1 and rep[0].startswith("NOT CHANGED " + p) and why in rep[0]
    with open(p, encoding="utf-8") as f:
        assert f.read() == content
    assert glob.glob(p + ".bak-*") == []


def test_msix_store_build_found(dirs):
    appdata, local = dirs
    msix = local / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
    msix.mkdir(parents=True)
    (local / "Packages" / "NotClaude_1" / "LocalCache" / "Roaming" / "Claude").mkdir(parents=True)
    assert cc.desktop_config_dirs() == [str(msix)]                   # APPDATA\Claude absent: not created
    cc.update_desktop(PY)
    assert load(cfg_path(msix))["mcpServers"]["sofistik"]["command"] == PY
    assert not (appdata / "Claude").exists()
    (appdata / "Claude").mkdir()
    assert cc.desktop_config_dirs() == [str(appdata / "Claude"), str(msix)]
    rep = cc.update_desktop(PY)
    assert len(rep) == 2 and os.path.isfile(cfg_path(appdata / "Claude"))


def test_no_appdata_at_all(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert cc.desktop_config_dirs() == [] and cc.update_desktop(PY) == []


def test_write_is_atomic(dirs, monkeypatch):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"mcpServers": {"a": {}}, "keep": true}')

    def boom(data, f, **kw):
        f.write('{"mcpServers": {"half')
        raise OSError("disk full")
    monkeypatch.setattr(cc.json, "dump", boom)
    with pytest.raises(OSError):
        cc.update_desktop(PY)
    with open(p, encoding="utf-8") as f:
        assert f.read() == '{"mcpServers": {"a": {}}, "keep": true}'   # the real file is never half-written


class FrozenDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 17, 9, 30, 0)


def test_original_config_survives_two_runs_in_one_second(dirs, monkeypatch):
    appdata, _ = dirs
    (appdata / "Claude").mkdir()
    p = cfg_path(appdata / "Claude")
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"original": true}')
    monkeypatch.setattr(datetime, "datetime", FrozenDatetime)
    cc.update_desktop(PY)
    cc.update_desktop(PY)
    contents = []
    for b in glob.glob(p + ".bak-*"):
        with open(b, encoding="utf-8") as f:
            contents.append(f.read())
    assert '{"original": true}' in contents


# ---------------------------------------------------------------- Claude Code

def test_claude_code_absent(dirs):
    assert cc.update_claude_code(PY) == [
        "Claude Code (claude command) not found: skipped. That is fine if you only use Claude Desktop."]


@pytest.fixture
def claude_cli(monkeypatch):
    calls = []
    result = {"rc": 0, "err": ""}
    monkeypatch.setattr(cc.shutil, "which", lambda name: "/bin/claude" if name == "claude" else None)

    def run(args, **kw):
        calls.append(args)
        if result.get("raise"):
            raise subprocess.TimeoutExpired(args, 60)
        rc = result["rc"] if args[1:3] == ["mcp", "add"] else 0
        return subprocess.CompletedProcess(args, rc, stdout="", stderr=result["err"])
    monkeypatch.setattr(cc.subprocess, "run", run)
    return calls, result


def test_claude_code_register(claude_cli):
    calls, _ = claude_cli
    assert cc.update_claude_code(PY) == ["Registered in Claude Code (user scope)."]
    assert calls == [["/bin/claude", "mcp", "remove", "sofistik", "--scope", "user"],
                     ["/bin/claude", "mcp", "add", "--scope", "user", "sofistik", "--", PY, cc.ENTRY]]


def test_claude_code_remove(claude_cli):
    calls, _ = claude_cli
    assert cc.update_claude_code(PY, remove=True) == ["Removed from Claude Code (user scope)."]
    assert calls == [["/bin/claude", "mcp", "remove", "sofistik", "--scope", "user"]]


def test_claude_code_failure_reported(claude_cli):
    calls, result = claude_cli
    result.update(rc=1, err="permission denied\n")
    rep = cc.update_claude_code(PY)
    assert rep[0].startswith("Claude Code registration failed: permission denied")
    assert f'claude mcp add --scope user sofistik -- "{PY}" "{cc.ENTRY}"' in rep[0]
    result["raise"] = True
    assert cc.update_claude_code(PY)[0].startswith("Claude Code registration failed: Command")


def test_main_exit_codes_and_output(dirs, capsys):
    appdata, _ = dirs
    assert cc.main(["x"]) == 0
    out = capsys.readouterr().out
    assert "Registered in" in out and "Claude Code (claude command) not found" in out
    assert cc.main(["x", "--remove"]) == 0 and "Removed from" in capsys.readouterr().out
    assert load(cfg_path(appdata / "Claude"))["mcpServers"] == {}
    with open(cfg_path(appdata / "Claude"), "w") as f:
        f.write("{broken")
    assert cc.main(["x"]) == 1 and "NOT CHANGED" in capsys.readouterr().out
