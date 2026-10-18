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

import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # folder holding run_server.py and settings.json
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
DEFAULT_SETTINGS_PATH = os.path.join(ROOT, "settings.default.json")

DEFAULTS = {
    "sofistik_dir": "",
    "work_folders": [r"C:\Sofistik workflow"],
    "read_folders": [],
    "allow_sys_commands": False,
    "run_timeout_minutes": 0,
    "auto_clear_cdb_locks": True,
    "clean_locks_command": "",
    "max_parallel_runs": 2,
    "min_free_ram_gb": 4,
    "examples_folders": [r"C:\Sofistik workflow"],
    "manual_folders": [r"C:\Sofistik workflow"],
    "dashboard_port": 8765,
    "dashboard_lan": False,
}


class SettingsError(ValueError):
    """settings.json cannot be read (message is meant for the engineer)."""


class AccessError(PermissionError):
    """A path is outside the folders settings.json allows (message is meant for the engineer)."""


def load_settings(path: str | None = None) -> dict:
    """settings.json merged over DEFAULTS.  Keys starting with '_' are comments and are ignored."""
    s: dict = dict(DEFAULTS)
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
        for x in s[k]:
            if any(ord(ch) < 32 for ch in x):
                raise SettingsError(
                    f"{p}: the folder {x!r} in {k} contains a single backslash before t, n, r, b or f, "
                    r'which JSON reads as a control character. Use double backslashes, e.g. "C:\\temp". '
                    "Fix it in Notepad, save, and restart Claude.")
    for k in ("work_folders", "read_folders", "examples_folders", "manual_folders"):
        for x in s[k]:
            if not is_full_path(x):
                raise SettingsError(
                    f"{p}: the folder {x!r} in {k} is not a full path, so it would depend on the folder Claude "
                    r'was started from. Give the whole path with the drive, e.g. "D:\\26016 HPC". '
                    "Fix it in Notepad, save, and restart Claude.")
    a = s.get("allow_sys_commands")
    # only a real JSON true (or the word "true") switches the +SYS guard off; "false", 0, "no" never do
    s["allow_sys_commands"] = a is True or (isinstance(a, str) and a.strip().lower() == "true")
    if s.get("sofistik_dir") and any(ord(ch) < 32 for ch in str(s["sofistik_dir"])):
        raise SettingsError(f"{p}: sofistik_dir contains a single backslash before t, n, r, b or f. "
                            "Use double backslashes. Fix it in Notepad, save, and restart Claude.")
    if s.get("sofistik_dir") and not is_full_path(str(s["sofistik_dir"])):
        raise SettingsError(f"{p}: sofistik_dir {s['sofistik_dir']!r} is not a full path. Give the whole path, "
                            r'e.g. "C:\\Program Files\\SOFiSTiK\\2027". Fix it in Notepad, save, and restart Claude.')
    try:                                          # 0 (or empty): no time limit
        t = float(s.get("run_timeout_minutes") or 0)
        s["run_timeout_minutes"] = max(1.0, t) if t > 0 else 0.0
    except (TypeError, ValueError):
        s["run_timeout_minutes"] = 0.0
    c = s.get("auto_clear_cdb_locks")
    s["auto_clear_cdb_locks"] = not (c is False or (isinstance(c, str) and c.strip().lower() == "false"))
    try:
        s["max_parallel_runs"] = max(1, min(8, int(s.get("max_parallel_runs") or 1)))
    except (TypeError, ValueError):
        s["max_parallel_runs"] = 1
    try:
        s["min_free_ram_gb"] = max(0.0, float(s.get("min_free_ram_gb") or 0))
    except (TypeError, ValueError):
        s["min_free_ram_gb"] = 4.0
    s["_path"] = p if os.path.isfile(p) else ""
    return s


def is_full_path(p: str) -> bool:
    """A path that does not depend on the current folder: C:\\x or \\\\server\\share (also /x off Windows).
    "C:x" (current folder of drive C:) and "\\x" (current drive) are not full paths."""
    p = os.path.expanduser(str(p).strip())
    if re.match(r"^[A-Za-z]:[\\/]", p) or re.match(r"^[\\/]{2}[^\\/]", p):
        return True
    return os.name != "nt" and p.startswith("/")


_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{d}{i}" for d in ("COM", "LPT") for i in list("123456789") + ["\u00b9", "\u00b2", "\u00b3"]}


def bad_file_name(path: str) -> str | None:
    """Why Windows would not store path as the plain file it looks like (None if it is fine):
    ':' after the drive (an NTFS alternate data stream), a name ending in '.' or ' ' (Windows drops them),
    a reserved device name (CON, NUL, COM1, LPT1 ... with any extension), characters Windows forbids,
    or a file name starting with '-' (sps.exe would read it as an option)."""
    p = str(path)
    if p.startswith(("\\\\?\\", "\\\\.\\", "//?/", "//./")):
        return f"{p}: device paths (\\\\?\\ or \\\\.\\) are not accepted; give a normal path."
    rest = p[2:] if re.match(r"^[A-Za-z]:", p) else p
    if ":" in rest:
        return f"{p}: a ':' is only allowed after the drive letter (it would write a hidden NTFS stream)."
    if any(ord(ch) < 32 or ch in '<>"|?*' for ch in rest):
        return (f"{p}: the name contains a character Windows does not allow in file names "
                "(< > \" | ? * or a control character).")
    parts = [x for x in re.split(r"[\\/]", rest) if x not in ("", ".", "..")]
    for part in parts:
        if part != part.rstrip(". "):
            return f"{p}: '{part}' ends with a dot or a space, which Windows silently drops."
        if part.split(".")[0].strip().upper() in _RESERVED:
            return f"{p}: '{part}' is a reserved Windows device name (CON, PRN, AUX, NUL, COM1-9, LPT1-9)."
    if parts and parts[-1].startswith("-"):
        return f"{p}: a file name must not start with '-' (sps.exe would read it as an option)."
    return None


def backup_name(path: str) -> str:
    """A .bak-<time> name next to path that does not exist yet (never replaces an earlier backup)."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    cand, n = f"{path}.bak-{stamp}", 1
    while os.path.exists(cand):
        n += 1
        cand = f"{path}.bak-{stamp}-{n}"
    return cand


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
