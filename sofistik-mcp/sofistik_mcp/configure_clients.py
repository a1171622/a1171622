"""Register (or remove) the SOFiSTiK MCP server in Claude Desktop and Claude Code on this PC.

    python -m sofistik_mcp.configure_clients            register
    python -m sofistik_mcp.configure_clients --remove   remove

Claude Desktop reads claude_desktop_config.json from %APPDATA%\\Claude, or, for the Microsoft Store
build, from %LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Roaming\\Claude.  Every such folder that
exists is updated; the file is backed up first and only the "sofistik" entry under "mcpServers" is
changed, so other servers and settings are kept.  Claude Code is updated with "claude mcp add" if the
claude command is installed.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import shutil
import subprocess
import sys

NAME = "sofistik"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "run_server.py")


def desktop_config_dirs() -> list[str]:
    dirs = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(os.path.join(appdata, "Claude"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs += glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude"))
    existing = [d for d in dirs if os.path.isdir(d)]
    if not existing and appdata:
        existing = [os.path.join(appdata, "Claude")]          # Claude Desktop not started yet: create it
    return existing


def update_desktop(python_exe: str, remove: bool = False) -> list[str]:
    report = []
    for d in desktop_config_dirs():
        path = os.path.join(d, "claude_desktop_config.json")
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    txt = f.read()
                data = json.loads(txt) if txt.strip() else {}
            except (OSError, json.JSONDecodeError) as e:
                report.append(f"NOT CHANGED {path}: it is not valid JSON ({e}). Fix or rename it and run again.")
                continue
            if not isinstance(data, dict):
                report.append(f"NOT CHANGED {path}: unexpected content.")
                continue
            backup = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(path, backup)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        if remove:
            servers.pop(NAME, None)
        else:
            servers[NAME] = {"command": python_exe, "args": [ENTRY]}
        data["mcpServers"] = servers
        os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
        report.append(("Removed from " if remove else "Registered in ") + path)
    return report


def update_claude_code(python_exe: str, remove: bool = False) -> list[str]:
    exe = shutil.which("claude")
    if not exe:
        return ["Claude Code (claude command) not found: skipped. That is fine if you only use Claude Desktop."]
    report = []
    run = lambda args: subprocess.run([exe] + args, capture_output=True, text=True, timeout=60)  # noqa: E731
    try:
        run(["mcp", "remove", NAME, "--scope", "user"])
        if remove:
            return ["Removed from Claude Code (user scope)."]
        r = run(["mcp", "add", "--scope", "user", NAME, "--", python_exe, ENTRY])
        if r.returncode == 0:
            report.append("Registered in Claude Code (user scope).")
        else:
            report.append("Claude Code registration failed: " + (r.stderr or r.stdout).strip()[-400:] +
                          f'\n  Do it by hand:  claude mcp add --scope user {NAME} -- "{python_exe}" "{ENTRY}"')
    except Exception as e:
        report.append(f"Claude Code registration failed: {e}")
    return report


def main(argv):
    remove = "--remove" in argv
    python_exe = sys.executable
    lines = update_desktop(python_exe, remove) + update_claude_code(python_exe, remove)
    for ln in lines:
        print("  " + ln)
    return 0 if not any(ln.startswith("NOT CHANGED") for ln in lines) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
