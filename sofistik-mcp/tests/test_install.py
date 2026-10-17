"""install.py: where SOFiSTiK is looked for, in which order, and what the engineer is told if not."""
from __future__ import annotations

import os

import pytest

from sofistik_mcp import install


@pytest.fixture
def env(monkeypatch, tmp_path):
    """No SOFISTIK_DIR; Program Files points into tmp_path."""
    monkeypatch.delenv("SOFISTIK_DIR", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)
    pf = tmp_path / "Program Files"
    pf.mkdir()
    monkeypatch.setenv("ProgramFiles", str(pf))
    return pf


def tree(root, sps=True, dll="sof_cdb_w-2027.dll", daten="direct", extra_dlls=()):
    root.mkdir(parents=True, exist_ok=True)
    if sps:
        (root / "sps.exe").write_bytes(b"MZ")
    bit = root / "interfaces" / "64bit"
    bit.mkdir(parents=True, exist_ok=True)
    for d in ([dll] if dll else []) + list(extra_dlls):
        (bit / d).write_bytes(b"MZ")
    py = root / "interfaces" / "examples" / "python"
    if daten == "direct":
        py.mkdir(parents=True, exist_ok=True)
        (py / "sofistik_daten.py").write_text("# daten\n")
    elif daten == "sub":
        (py / "python_3.x").mkdir(parents=True, exist_ok=True)
        (py / "python_3.x" / "sofistik_daten.py").write_text("# daten\n")
    return root


def norm(p):
    return os.path.normpath(str(p))


def test_full_install_found(env):
    root = tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027")
    info = install.find({})
    assert info["root"] == norm(root) and info["version"] == "2027"
    assert info["sps"] == os.path.join(norm(root), "sps.exe")
    assert info["dll"] == os.path.join(norm(root), "interfaces", "64bit", "sof_cdb_w-2027.dll")
    assert info["dll_dirs"] == [os.path.join(norm(root), "interfaces", "64bit"), norm(root)]
    assert info["daten"] == os.path.join(norm(root), "interfaces", "examples", "python", "sofistik_daten.py")
    assert info["searched"][-1] == norm(root)


def test_version_order_newest_first(env):
    tree(env / "SOFiSTiK" / "2025" / "SOFiSTiK 2025")
    r26 = tree(env / "SOFiSTiK" / "2026" / "SOFiSTiK 2026")
    info = install.find(None)
    assert info["root"] == norm(r26) and info["version"] == "2026"


def test_version_folder_without_inner_folder(env):
    r = tree(env / "SOFiSTiK" / "2026")
    assert install.find({})["root"] == norm(r)


def test_settings_before_env_before_program_files(env, tmp_path, monkeypatch):
    tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027")
    env_root = tree(tmp_path / "envsof" / "SOFiSTiK 2025")
    set_root = tree(tmp_path / "setsof" / "SOFiSTiK 2026")
    monkeypatch.setenv("SOFISTIK_DIR", str(env_root))
    assert install.find({})["root"] == norm(env_root)
    assert install.find({})["version"] == "2025"
    info = install.find({"sofistik_dir": str(set_root)})
    assert info["root"] == norm(set_root) and info["searched"] == [norm(set_root)]


def test_programw6432_is_searched(env, tmp_path, monkeypatch):
    other = tmp_path / "PF64"
    r = tree(other / "SOFiSTiK" / "2027" / "SOFiSTiK 2027")
    monkeypatch.setenv("ProgramW6432", str(other))
    assert install.find({})["root"] == norm(r)


@pytest.mark.parametrize("suffix", [("sps.exe",), ("interfaces", "64bit"),
                                    ("interfaces", "64bit", "sof_cdb_w-2027.dll")])
def test_sofistik_dir_may_point_at_exe_dll_or_64bit(env, tmp_path, suffix):
    root = tree(tmp_path / "S" / "SOFiSTiK 2027")
    info = install.find({"sofistik_dir": str(root.joinpath(*suffix))})
    assert info["root"] == norm(root)


def test_candidate_roots_dedup_and_order(env, monkeypatch):
    monkeypatch.setenv("SOFISTIK_DIR", str(env / "X"))
    roots = install.candidate_roots({"sofistik_dir": str(env / "X")})
    assert roots[0] == norm(env / "X") and roots.count(norm(env / "X")) == 1
    assert roots[1] == norm(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027")
    assert roots[2] == norm(env / "SOFiSTiK" / "2027")
    assert roots[3] == norm(env / "SOFiSTiK" / "2026" / "SOFiSTiK 2026")
    assert norm(os.path.join(r"C:\Program Files", "SOFiSTiK", "2027", "SOFiSTiK 2027")) in roots   # fixed fallback


def test_only_dll_is_enough_and_edu_dll_skipped(env):
    root = tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027", sps=False, dll=None,
                extra_dlls=("sof_cdb_w_edu-2027.dll", "sof_cdb_w-2026.dll", "sof_cdb_w-2027.dll"))
    info = install.find({})
    assert info["root"] == norm(root) and info["sps"] is None
    assert os.path.basename(info["dll"]) == "sof_cdb_w-2027.dll"


def test_only_edu_dll_and_sps_missing_is_not_an_install(env):
    tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027", sps=False, dll="sof_cdb_w_edu-2027.dll")
    with pytest.raises(install.SofistikNotFound):
        install.find({})


def test_dll_in_program_folder(env):
    root = env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027"
    root.mkdir(parents=True)
    (root / "sof_cdb_w-2027.dll").write_bytes(b"MZ")
    info = install.find({})
    assert info["dll"] == os.path.join(norm(root), "sof_cdb_w-2027.dll") and info["dll_dirs"] == [norm(root)]
    assert info["daten"] is None


def test_daten_in_python_subfolder(env):
    root = tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027", daten="sub")
    assert install.find({})["daten"] == os.path.join(norm(root), "interfaces", "examples", "python",
                                                    "python_3.x", "sofistik_daten.py")


def test_sps_without_dll(env):
    root = tree(env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027", dll=None, daten=None)
    info = install.find({})
    assert info["sps"] and info["dll"] is None and info["daten"] is None and info["root"] == norm(root)


def test_not_found_lists_what_was_searched(env, tmp_path):
    (env / "SOFiSTiK" / "2027" / "SOFiSTiK 2027").mkdir(parents=True)        # empty folder: not an install
    with pytest.raises(install.SofistikNotFound) as e:
        install.find({"sofistik_dir": str(tmp_path / "wrong")})
    msg = str(e.value)
    assert msg.startswith("SOFiSTiK was not found. Searched:")
    for r in install.candidate_roots({"sofistik_dir": str(tmp_path / "wrong")}):
        assert "\n  " + r + "\n" in msg
    assert '"sofistik_dir"' in msg and "settings.json" in msg and "restart Claude" in msg
    assert issubclass(install.SofistikNotFound, RuntimeError)
