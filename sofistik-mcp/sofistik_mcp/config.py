"""Settings for the SOFiSTiK MCP server and the folder rules every tool obeys.

settings.json sits next to run_server.py.  install.bat creates it from settings.default.json the
first time; after that the installer never overwrites it, so your edits are kept.

Folder rules
  work_folders   the server may write .dat files and run calculations only inside these folders
                 (and their sub-folders).
  read_folders   extra folders the server may read (results, .dat, .prt) but never write.
  The SOFiSTiK program folder is always readable (manuals, examples, sofistik_daten.py).
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # folder holding run_server.py and settings.json
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
DEFAULT_SETTINGS_PATH = os.path.join(ROOT, "settings.default.json")

DEFAULTS = {
    "sofistik_dir": "",
    "work_folders": [r"C:\Sofistik workflow"],
    "read_folders": [],
    "allow_sys_commands": False,
    "run_timeout_minutes": 60,
    "examples_folders": [r"C:\Sofistik workflow"],
    "manual_folders": [r"C:\Sofistik workflow"],
}


class SettingsError(ValueError):
    """settings.json cannot be read (message is meant for the engineer)."""


class AccessError(PermissionError):
    """A path is outside the folders settings.json allows (message is meant for the engineer)."""


def load_settings(path: str | None = None) -> dict:
    """settings.json merged over DEFAULTS.  Keys starting with '_' are comments and are ignored."""
    s = dict(DEFAULTS)
    p = path or SETTINGS_PATH
    if not os.path.isfile(p) and path is None and os.path.isfile(DEFAULT_SETTINGS_PATH):
        p = DEFAULT_SETTINGS_PATH
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8-sig") as f:
                user = json.load(f)
        except json.JSONDecodeError as e:
            raise SettingsError(
                f"{p} has a typing error on line {e.lineno}, column {e.colno} ({e.msg}). Paths need double "
                r'backslashes, e.g. "D:\\26016 HPC"; every item except the last in a list needs a comma. '
                "Fix it in Notepad, save, and restart Claude.") from e
        if not isinstance(user, dict):
            raise SettingsError(f"{p} must contain {{ ... }} settings.")
        for k, v in user.items():
            if not k.startswith("_"):
                s[k] = v
    for k in ("work_folders", "read_folders", "examples_folders", "manual_folders"):
        v = s.get(k) or []
        s[k] = [v] if isinstance(v, str) else [str(x) for x in v if str(x).strip()]
    s["allow_sys_commands"] = bool(s.get("allow_sys_commands"))
    try:
        s["run_timeout_minutes"] = max(1.0, float(s.get("run_timeout_minutes") or 60))
    except (TypeError, ValueError):
        s["run_timeout_minutes"] = 60.0
    s["_path"] = p if os.path.isfile(p) else ""
    return s


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(str(p)))))


def is_inside(path: str, folders) -> bool:
    """True if path is one of folders or inside one of them (case-insensitive on Windows,
    symlinks and '..' resolved first, so '..' cannot climb out)."""
    p = _norm(path)
    for f in folders:
        if not f:
            continue
        r = _norm(f)
        try:
            if os.path.commonpath([p, r]) == r:
                return True
        except ValueError:                           # different drives on Windows
            continue
    return False


def readable_folders(settings: dict, sofistik_root: str | None = None) -> list[str]:
    out = list(settings["work_folders"]) + list(settings["read_folders"])
    out += list(settings.get("examples_folders") or []) + list(settings.get("manual_folders") or [])
    if sofistik_root:
        out.append(sofistik_root)
    return out


def check_read(path: str, settings: dict, sofistik_root: str | None = None) -> str:
    full = os.path.abspath(os.path.expanduser(str(path)))
    if not is_inside(full, readable_folders(settings, sofistik_root)):
        raise AccessError(
            f"{full} is outside the folders this server may read. Allowed: "
            + "; ".join(readable_folders(settings, sofistik_root))
            + f". To allow it, add the folder to \"read_folders\" (read only) or \"work_folders\" "
              f"in {SETTINGS_PATH} and restart Claude.")
    return full


def check_write(path: str, settings: dict) -> str:
    full = os.path.abspath(os.path.expanduser(str(path)))
    if not is_inside(full, settings["work_folders"]):
        raise AccessError(
            f"{full} is outside the work folders, where this server may write and run calculations. "
            f"Work folders: {'; '.join(settings['work_folders'])}. To allow it, add the folder to "
            f"\"work_folders\" in {SETTINGS_PATH} and restart Claude.")
    return full
