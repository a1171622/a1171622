"""install.bat / selftest.bat / uninstall.bat / dashboard.bat: Windows cmd needs CRLF and plain ASCII, and every
'.venv\\Scripts\\python.exe -m X' must name a module that exists."""
from __future__ import annotations

import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BATS = sorted(n for n in os.listdir(ROOT) if n.lower().endswith(".bat"))


def test_the_bat_files_exist():
    assert BATS == ["dashboard.bat", "install.bat", "selftest.bat", "uninstall.bat"]


def raw(name):
    with open(os.path.join(ROOT, name), "rb") as f:
        return f.read()


@pytest.mark.parametrize("name", BATS)
def test_crlf_only(name):
    b = raw(name)
    assert b.endswith(b"\r\n"), "last line must end with CRLF"
    assert b.count(b"\n") == b.count(b"\r\n") and b.count(b"\r") == b.count(b"\r\n")


@pytest.mark.parametrize("name", BATS)
def test_ascii_only(name):
    bad = [(i, c) for i, c in enumerate(raw(name)) if c > 127 or (c < 32 and c not in (9, 10, 13))]
    assert bad == []


@pytest.mark.parametrize("name", BATS)
def test_modules_exist(name):
    text = raw(name).decode("ascii")
    mods = re.findall(r'\.venv\\Scripts\\python\.exe"?\s+-m\s+([\w.]+)', text)
    assert mods, "expected at least one python -m call"
    for m in mods:
        if m in ("pip", "venv"):
            continue
        path = os.path.join(ROOT, *m.split(".")) + ".py"
        assert os.path.isfile(path), f"{name}: module {m} not found ({path})"
        with open(path, encoding="utf-8") as f:
            assert '__name__ == "__main__"' in f.read(), f"{m} cannot run with -m"


@pytest.mark.parametrize("name", BATS)
def test_starts_in_own_folder_and_labels_exist(name):
    text = raw(name).decode("ascii")
    assert text.startswith("@echo off\r\n") and 'cd /d "%~dp0"' in text
    labels = set(re.findall(r"^:(\w+)", text, re.MULTILINE))
    for target in re.findall(r"\bgoto\s+(\w+)", text, re.IGNORECASE):
        assert target in labels, f"{name}: goto {target} has no label"


def test_install_bat_files_it_uses_exist():
    text = raw("install.bat").decode("ascii")
    assert "-r requirements.txt" in text and os.path.isfile(os.path.join(ROOT, "requirements.txt"))
    assert "settings.default.json settings.json" in text
    assert os.path.isfile(os.path.join(ROOT, "settings.default.json"))
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as f:
        reqs = f.read().lower()
    assert "mcp" in reqs
