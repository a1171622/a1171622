"""Find the SOFiSTiK installation: sps.exe (batch calculation), the CDB DLL and sofistik_daten.py.

Search order: settings.json "sofistik_dir", environment variable SOFISTIK_DIR, then
<Program Files>\\SOFiSTiK\\<version>\\SOFiSTiK <version> for 2027, 2026, 2025.
Layout seen on Wing's PC (2026-10-17):
  C:\\Program Files\\SOFiSTiK\\2027\\SOFiSTiK 2027\\interfaces\\64bit\\sof_cdb_w-2027.dll
  C:\\Program Files\\SOFiSTiK\\2027\\SOFiSTiK 2027\\interfaces\\examples\\python\\sofistik_daten.py
SOFiSTiK's own Python example adds both ...\\interfaces\\64bit and the program folder as DLL folders.
"""
from __future__ import annotations

import glob
import os

VERSIONS = ("2027", "2026", "2025")


class SofistikNotFound(RuntimeError):
    pass


def candidate_roots(settings: dict | None = None) -> list[str]:
    roots = []
    if settings and settings.get("sofistik_dir"):
        roots.append(settings["sofistik_dir"])
    if os.environ.get("SOFISTIK_DIR"):
        roots.append(os.environ["SOFISTIK_DIR"])
    bases = [os.environ[v] for v in ("ProgramFiles", "ProgramW6432") if os.environ.get(v)]
    bases.append(r"C:\Program Files")
    for b in bases:
        for v in VERSIONS:
            roots.append(os.path.join(b, "SOFiSTiK", v, f"SOFiSTiK {v}"))
            roots.append(os.path.join(b, "SOFiSTiK", v))
    seen, out = set(), []
    for r in roots:
        r = os.path.normpath(r)
        # a path to ...\interfaces\64bit or to sps.exe itself is accepted too
        if r.lower().endswith(".exe") or r.lower().endswith(".dll"):
            r = os.path.dirname(r)
        if os.path.basename(r).lower() == "64bit":
            r = os.path.dirname(os.path.dirname(r))
        if r.lower() not in seen:
            seen.add(r.lower())
            out.append(r)
    return out


def find(settings: dict | None = None) -> dict:
    """dict(root, version, sps, dll, dll_dirs, daten).  sps / dll / daten may be None if missing;
    root is the first folder that has sps.exe or the CDB DLL."""
    searched = []
    for root in candidate_roots(settings):
        searched.append(root)
        if not os.path.isdir(root):
            continue
        sps = os.path.join(root, "sps.exe")
        sps = sps if os.path.isfile(sps) else None
        dll_dirs = [d for d in (os.path.join(root, "interfaces", "64bit"), root) if os.path.isdir(d)]
        dll = None
        for d in dll_dirs:
            hits = [h for h in sorted(glob.glob(os.path.join(d, "sof_cdb_w-*.dll")), reverse=True)
                    if "_edu" not in os.path.basename(h).lower()]
            if hits:
                dll = hits[0]
                break
        if not sps and not dll:
            continue
        daten = None
        for pat in (os.path.join(root, "interfaces", "examples", "python", "sofistik_daten.py"),
                    os.path.join(root, "interfaces", "examples", "python", "*", "sofistik_daten.py")):
            hits = sorted(glob.glob(pat))
            if hits:
                daten = hits[0]
                break
        version = next((v for v in VERSIONS if v in root), "")
        return {"root": root, "version": version, "sps": sps, "dll": dll, "dll_dirs": dll_dirs,
                "daten": daten, "searched": searched}
    raise SofistikNotFound(
        "SOFiSTiK was not found. Searched:\n  " + "\n  ".join(searched) +
        "\nPut the SOFiSTiK program folder (the one holding sps.exe) in \"sofistik_dir\" in settings.json, "
        r"e.g. C:\Program Files\SOFiSTiK\2027\SOFiSTiK 2027, and restart Claude.")
