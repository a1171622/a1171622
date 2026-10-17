"""config.py: settings.json and the folder rules every tool obeys."""
from __future__ import annotations

import json
import ntpath
import os
import types

import pytest

from sofistik_mcp import config


def write(p, text):
    p.write_text(text, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------- load_settings

def test_merge_over_defaults_and_comment_keys_ignored(tmp_path):
    p = write(tmp_path / "s.json", json.dumps({
        "_help": "comment", "_work_folders": "comment too",
        "work_folders": ["D:\\26016 HPC", "  ", ""], "read_folders": "E:\\ref",
        "run_timeout_minutes": 30, "allow_sys_commands": True, "my_extra": 5}))
    s = config.load_settings(p)
    assert s["work_folders"] == ["D:\\26016 HPC"]                  # blanks dropped
    assert s["read_folders"] == ["E:\\ref"]                         # a single string becomes a list
    assert s["run_timeout_minutes"] == 30.0 and s["allow_sys_commands"] is True
    assert s["examples_folders"] == [r"C:\Sofistik workflow"]       # default kept
    assert s["sofistik_dir"] == "" and s["my_extra"] == 5
    assert not any(k.startswith("_") and k != "_path" for k in s)
    assert s["_path"] == p


def test_utf8_bom_accepted(tmp_path):
    p = tmp_path / "s.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"work_folders": ["D:\\x"]}).encode())
    assert config.load_settings(str(p))["work_folders"] == ["D:\\x"]


@pytest.mark.parametrize("value, expected", [("bad", 60.0), (None, 60.0), (0, 60.0), (-5, 1.0), (0.5, 1.0),
                                             ("30", 30.0), (120, 120.0), ([1], 60.0)])
def test_timeout_values(tmp_path, value, expected):
    p = write(tmp_path / "s.json", json.dumps({"run_timeout_minutes": value}))
    assert config.load_settings(p)["run_timeout_minutes"] == expected


def test_missing_file_gives_defaults(tmp_path):
    s = config.load_settings(str(tmp_path / "none.json"))
    assert s["work_folders"] == [r"C:\Sofistik workflow"] and s["allow_sys_commands"] is False
    assert s["run_timeout_minutes"] == 60.0 and s["_path"] == ""


def test_no_settings_json_falls_back_to_settings_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    s = config.load_settings()
    assert s["_path"] == config.DEFAULT_SETTINGS_PATH and s["work_folders"] == [r"C:\Sofistik workflow"]
    write(tmp_path / "settings.json", json.dumps({"work_folders": ["D:\\p"]}))
    s = config.load_settings()
    assert s["_path"] == str(tmp_path / "settings.json") and s["work_folders"] == ["D:\\p"]


def test_bad_json_friendly_message_with_line_and_column(tmp_path):
    p = write(tmp_path / "s.json", '{\n  "work_folders": ["C:\\Sofistik workflow"],\n  "x": 1\n}')
    with pytest.raises(config.SettingsError) as e:
        config.load_settings(p)
    msg = str(e.value)
    assert "line 2, column" in msg and "double backslashes" in msg and p in msg and "restart Claude" in msg
    assert isinstance(e.value, ValueError)


def test_missing_comma_message(tmp_path):
    p = write(tmp_path / "s.json", '{"work_folders": ["C:\\\\a" "D:\\\\b"]}')
    with pytest.raises(config.SettingsError, match=r"line 1, column 27 \(Expecting .,. delimiter\)"):
        config.load_settings(p)


def test_settings_must_be_an_object(tmp_path):
    with pytest.raises(config.SettingsError, match="must contain"):
        config.load_settings(write(tmp_path / "s.json", '["C:\\\\a"]'))


def test_double_backslash_paths_read_correctly(tmp_path):
    p = write(tmp_path / "s.json", '{"work_folders": ["C:\\\\Sofistik workflow", "D:\\\\26016 HPC Kier BAM JV"]}')
    assert config.load_settings(p)["work_folders"] == [r"C:\Sofistik workflow", r"D:\26016 HPC Kier BAM JV"]


def test_single_backslash_control_escape_is_refused(tmp_path):
    p = write(tmp_path / "s.json", '{"work_folders": ["C:\\temp\\\\models"], "read_folders": ["D:\\new"]}')
    with pytest.raises(config.SettingsError, match="double backslashes"):
        config.load_settings(p)


def test_default_settings_file_is_valid_and_safe():
    s = config.load_settings(config.DEFAULT_SETTINGS_PATH)
    assert s["allow_sys_commands"] is False and s["run_timeout_minutes"] == 60.0
    assert s["work_folders"] == [r"C:\Sofistik workflow"] and s["read_folders"] == []


def test_allow_sys_commands_string_false_stays_false(tmp_path):
    p = write(tmp_path / "s.json", '{"allow_sys_commands": "false"}')
    assert config.load_settings(p)["allow_sys_commands"] is False


# ---------------------------------------------------------------- is_inside / check_read / check_write

def test_is_inside_basic(tmp_path):
    w = tmp_path / "work"
    (w / "sub").mkdir(parents=True)
    assert config.is_inside(str(w), [str(w)])
    assert config.is_inside(str(w / "sub" / "a.dat"), [str(w)])
    assert config.is_inside(str(w / "new" / "b.dat"), [str(w)])            # not yet existing
    assert not config.is_inside(str(tmp_path / "a.dat"), [str(w)])
    assert not config.is_inside(str(w / "a.dat"), [])
    assert not config.is_inside(str(w / "a.dat"), ["", None])


def test_dotdot_cannot_climb_out(tmp_path):
    w = tmp_path / "work"
    (w / "sub").mkdir(parents=True)
    assert not config.is_inside(str(w / ".." / "x.dat"), [str(w)])
    assert not config.is_inside(str(w / "sub" / ".." / ".." / "work2" / "x.dat"), [str(w)])
    assert config.is_inside(str(w / "sub" / ".." / "x.dat"), [str(w)])
    assert config.is_inside(str(w / "x.dat"), [str(w / "sub" / "..")])


def test_prefix_trickery(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    (tmp_path / "work2").mkdir()
    assert not config.is_inside(str(tmp_path / "work2" / "a.dat"), [str(w)])
    assert not config.is_inside(str(tmp_path / "work.dat"), [str(w)])
    assert not config.is_inside(str(tmp_path / "wor"), [str(w)])


def test_relative_paths_resolve_against_cwd(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path)
    assert config.is_inside(os.path.join("work", "a.dat"), [str(tmp_path / "work")])
    assert not config.is_inside("a.dat", [str(tmp_path / "work")])


@pytest.fixture
def windows_paths(monkeypatch):
    """Run config's path logic with Windows rules (ntpath) on any OS."""
    if os.name == "nt":
        return
    fake_os = types.SimpleNamespace(path=ntpath, environ=os.environ, name="nt")
    monkeypatch.setattr(config, "os", fake_os)


def test_windows_case_insensitive(windows_paths):
    assert config.is_inside(r"C:\WORK\Models\A.DAT", [r"c:\work"])
    assert config.is_inside(r"c:\work\a.dat", [r"C:\Work\\"])


def test_windows_prefix_trickery_and_drives(windows_paths):
    assert not config.is_inside(r"C:\work2\a.dat", [r"C:\work"])
    assert not config.is_inside(r"C:\work\..\work2\a.dat", [r"C:\work"])
    assert not config.is_inside(r"D:\work\a.dat", [r"C:\work"])              # other drive: ValueError path
    assert config.is_inside(r"D:\work\a.dat", [r"C:\work", r"D:\work"])
    assert config.is_inside(r"C:/work/sub/a.dat", [r"C:\work"])               # forward slashes


@pytest.fixture
def link_out(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.dat").write_text("x")
    try:
        os.symlink(str(outside), str(w / "link"), target_is_directory=True)
        os.symlink(str(outside / "secret.dat"), str(w / "file_link.dat"))
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here (Windows without developer mode)")
    return w


def test_symlink_out_of_work_folder_is_outside(link_out):
    w = link_out
    assert not config.is_inside(str(w / "link" / "secret.dat"), [str(w)])
    assert not config.is_inside(str(w / "link" / "new.dat"), [str(w)])
    assert not config.is_inside(str(w / "file_link.dat"), [str(w)])


def test_symlinked_work_folder_itself_is_fine(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    try:
        os.symlink(str(real), str(tmp_path / "alias"), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    assert config.is_inside(str(real / "a.dat"), [str(tmp_path / "alias")])
    assert config.is_inside(str(tmp_path / "alias" / "a.dat"), [str(real)])


def _rules(tmp_path):
    s = config.load_settings(str(tmp_path / "none.json"))
    for n in ("work", "read", "ex", "man", "sof"):
        (tmp_path / n).mkdir()
    s.update(work_folders=[str(tmp_path / "work")], read_folders=[str(tmp_path / "read")],
             examples_folders=[str(tmp_path / "ex")], manual_folders=[str(tmp_path / "man")])
    return s


def test_check_write_only_in_work_folders(tmp_path):
    s = _rules(tmp_path)
    assert config.check_write(str(tmp_path / "work" / "a.dat"), s) == str(tmp_path / "work" / "a.dat")
    for bad in ("read", "ex", "man", "sof", "."):
        with pytest.raises(config.AccessError) as e:
            config.check_write(str(tmp_path / bad / "a.dat"), s)
        assert "outside the work folders" in str(e.value) and str(tmp_path / "work") in str(e.value)
        assert "work_folders" in str(e.value) and config.SETTINGS_PATH in str(e.value)


def test_check_read_folders(tmp_path):
    s = _rules(tmp_path)
    for ok in ("work", "read", "ex", "man"):
        assert config.check_read(str(tmp_path / ok / "a.prt"), s) == str(tmp_path / ok / "a.prt")
    with pytest.raises(config.AccessError) as e:
        config.check_read(str(tmp_path / "sof" / "x.pdf"), s)
    assert "outside the folders this server may read" in str(e.value) and "read_folders" in str(e.value)
    assert config.check_read(str(tmp_path / "sof" / "x.pdf"), s, sofistik_root=str(tmp_path / "sof"))
    with pytest.raises(config.AccessError):
        config.check_read(str(tmp_path / "read" / ".." / "x.cdb"), s)
    assert issubclass(config.AccessError, PermissionError)


def test_check_returns_absolute_path(tmp_path, monkeypatch):
    s = _rules(tmp_path)
    monkeypatch.chdir(tmp_path / "work")
    assert config.check_write("a.dat", s) == str(tmp_path / "work" / "a.dat")


def test_readable_folders_order(tmp_path):
    s = _rules(tmp_path)
    assert config.readable_folders(s, "SOF") == [str(tmp_path / n) for n in ("work", "read", "ex", "man")] + ["SOF"]
    assert config.readable_folders(s) == [str(tmp_path / n) for n in ("work", "read", "ex", "man")]
