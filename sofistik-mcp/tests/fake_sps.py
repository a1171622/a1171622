"""A stand-in for SOFiSTiK's sps.exe, for tests without SOFiSTiK.

make(folder) writes a launcher next to this script (sps.cmd on Windows, an executable sh script
elsewhere) that runs this file with the current Python.  Run as

    sps [options] name.dat        (or name.dat [options], like sps.exe accepts)

it writes name.prt / name.erg / name.cdb / name.plb in the current folder (the .dat folder) with
real SOFiSTiK text (tests/sample_error.prt / .erg and an "ok" variant), and appends its argument list
to fake_sps_calls.txt.  Behaviour is chosen by CADINP comment lines in the .dat itself:

    $ FAKE mode=ok|warnings|errors|unfinished|none     (default ok; none = write nothing)
    $ FAKE sleep=5                                     (seconds before writing the protocol)
    $ FAKE exit=3                                      (exit code)
    $ FAKE reject_options_first=1                      (exit 3, write nothing, if an option comes first)
    $ FAKE nocdb=1                                     (do not write the .cdb)
    $ FAKE print=some_text                             (print "some text" on the console)
"""
from __future__ import annotations

import os
import re
import stat
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

HEAD = "   *** Start: Program Calculation - Version 2027-0.0.139\n"
OK_PROGRAM = """\
   *** Start: Program {prog}

   SOFiSTiK 2027-0.0.139    {PROG}     - GENERAL STATICS OF 3D STRUCTURES
   Output on file {stem}.plb
{warning}   TIME NEEDED         0 SECONDS, TOTAL         0 SECONDS
   DATE       2026-10-14, 00:15:04



    +++++    0 errors and    {nw} warnings +++++
   *** Stop : Program {prog}
"""
WARNING = """\
   +++++ warning no. 2430
   mass load case only converts nodal loads
"""
END = "   *** End of Calculation!\n"


def make(folder, script=None) -> str:
    """Write the platform launcher into folder and return its path (pass it to solver.run as sps).
    script: another Python file to run instead of this one."""
    folder = str(folder)
    os.makedirs(folder, exist_ok=True)
    script = str(script or os.path.join(HERE, "fake_sps.py"))
    if os.name == "nt":
        path = os.path.join(folder, "sps.cmd")
        with open(path, "w", newline="\r\n") as f:
            f.write(f'@echo off\n"{sys.executable}" "{script}" %*\nexit /b %ERRORLEVEL%\n')
    else:
        path = os.path.join(folder, "sps")
        with open(path, "w", newline="\n") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def directives(dat_text: str) -> dict:
    out = {}
    for m in re.finditer(r"^\s*\$\s*FAKE\s+(\w+)\s*=\s*(\S+)", dat_text, re.MULTILINE):
        out[m.group(1).lower()] = m.group(2)
    return out


def programs(dat_text: str) -> list[str]:
    return [m.group(1).lower() for m in re.finditer(r"^[ \t]*\+[ \t]*prog[ \t]+(\w+)", dat_text,
                                                    re.IGNORECASE | re.MULTILINE)] or ["ase"]


def write_crlf(path, text):
    with open(path, "w", encoding="cp1252", newline="\r\n") as f:
        f.write(text)


def main(argv) -> int:
    args = argv[1:]
    with open("fake_sps_calls.txt", "a", encoding="utf-8") as f:
        f.write(" ".join(args) + "\n")
    names = [a for a in args if not a.startswith("-")]
    if not names:
        return 2
    name = names[0]
    with open(name, encoding="utf-8", errors="replace") as f:
        dat = f.read()
    d = directives(dat)
    if d.get("reject_options_first") == "1" and args and args[0].startswith("-"):
        return 3
    if "print" in d:
        print(d["print"].replace("_", " "), flush=True)
    t_end = time.time() + float(d.get("sleep", 0))
    while time.time() < t_end:
        time.sleep(0.05)
    stem = os.path.splitext(name)[0]
    mode = d.get("mode", "ok")
    if mode == "none":
        return int(d.get("exit", 0))
    if mode == "errors":
        with open(os.path.join(HERE, "sample_error.prt"), "rb") as f:
            prt = f.read().decode("cp1252").replace("\r\n", "\n")
        with open(os.path.join(HERE, "sample_error.erg"), "rb") as f:
            erg_lines = f.read().decode("cp1252").replace("\r\n", "\n").split("\n")
        # ECHO of the input before the message, as SOFiSTiK prints it in the .erg
        echo = ["      " + ln for ln in dat.replace("\r\n", "\n").split("\n") if ln.strip()]
        erg = "\n".join(erg_lines[:3] + echo + erg_lines[3:])
    else:
        progs = programs(dat)
        body = ""
        for i, p in enumerate(progs):
            warn = WARNING if (mode == "warnings" and i == len(progs) - 1) else ""
            body += OK_PROGRAM.format(prog=p, PROG=p.upper(), stem=stem, warning=warn, nw=1 if warn else 0)
        prt = HEAD + body + END
        if mode == "unfinished":
            prt = HEAD + body.split("    +++++")[0]
        erg = "      " + progs[-1].upper() + "    - V 2027-0.0         10/14/26          Page:   1\n" + \
              "\n".join("      " + ln for ln in dat.split("\n") if ln.strip()) + "\n" + \
              (WARNING if mode == "warnings" else "")
    write_crlf(stem + ".prt", prt)
    write_crlf(stem + ".erg", erg)
    if d.get("nocdb") != "1":
        with open(stem + ".cdb", "wb") as f:
            f.write(b"FAKE CDB " + stem.encode() + b"\0" * 64)
    with open(stem + ".plb", "wb") as f:
        f.write(b"\0" * 16)
    return int(d.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
