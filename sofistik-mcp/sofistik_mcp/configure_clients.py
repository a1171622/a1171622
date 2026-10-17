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

import glob
import json
import os
import re
import shutil
import subprocess
import sys

from .config import backup_name

NAME = "sofistik"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "run_server.py")
KEEP_BACKUPS = 3
CMD_METACHARS = set('&|<>^%!()"')         # characters cmd.exe would act on in a .cmd / .bat argument


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
        data: dict = {}
        if remove and not os.path.isfile(path):
            report.append(f"Nothing to remove: {path} does not exist.")
            continue
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
            backup = backup_name(path)
            shutil.copy2(path, backup)
            prune_backups(path)
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


_BAK_RE = re.compile(r"\.bak-(\d{8}-\d{6})(?:-(\d+))?$")


def prune_backups(path: str, keep: int = KEEP_BACKUPS) -> list[str]:
    """Delete all but the newest `keep` <path>.bak-<time> copies made by backup_name (other files are left)."""
    mine = []
    for b in glob.glob(glob.escape(path) + ".bak-*"):
        m = _BAK_RE.search(b[len(path):])
        if m and b[len(path):] == m.group(0):
            mine.append(((m.group(1), int(m.group(2) or 1)), b))
    mine.sort()
    removed = []
    for _, b in mine[:-keep] if keep > 0 else mine:
        try:
            os.remove(b)
            removed.append(b)
        except OSError:
            pass
    return removed


def manual_command(python_exe: str) -> str:
    return f'claude mcp add --scope user {NAME} -- "{python_exe}" "{ENTRY}"'


def update_claude_code(python_exe: str, remove: bool = False) -> list[str]:
    exe = shutil.which("claude")
    if not exe:
        return ["Claude Code (claude command) not found: skipped. That is fine if you only use Claude Desktop."]
    report = []
    run = lambda args: subprocess.run([exe] + args, capture_output=True, text=True, timeout=60)  # noqa: E731
    via_cmd = exe.lower().endswith((".cmd", ".bat"))
    try:
        run(["mcp", "remove", NAME, "--scope", "user"])
        if remove:
            return ["Removed from Claude Code (user scope)."]
        if via_cmd and any(ch in CMD_METACHARS for a in (python_exe, ENTRY) for ch in a):
            # claude is a .cmd script: cmd.exe would misread & | < > ^ % in the paths, so do not run it
            return ["Claude Code not registered automatically: a path contains characters that cmd.exe would "
                    "misread (& | < > ^ % ! ( ) \"). Do it by hand in a terminal:\n  " + manual_command(python_exe)]
        r = run(["mcp", "add", "--scope", "user", NAME, "--", python_exe, ENTRY])
        if r.returncode == 0:
            report.append("Registered in Claude Code (user scope).")
        else:
            report.append("Claude Code registration failed: " + (r.stderr or r.stdout).strip()[-400:] +
                          "\n  Do it by hand:  " + manual_command(python_exe))
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
