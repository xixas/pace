"""Config and entry points: pace (sign-in, status, everything else to the GTK app) and paced (the daemon)."""

import json
import sys
import types

import pytest

from pace.cli import ConfigError, load_config, main, tray_wanted


def test_config_file_fills_in_what_the_defaults_leave_open(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "pace").mkdir()
    (tmp_path / "pace" / "config.json").write_text(json.dumps({"base_url": "https://hrms.example/api", "client_id": "PACE"}))
    cfg = load_config()
    assert (cfg.base_url, cfg.client_id) == ("https://hrms.example/api", "PACE")
    assert cfg.tenant == "95ca85cb-20c9-45c5-bbfc-be2d0ac2e657"
    assert cfg.scope == "api://97152fbf-dde7-4077-a876-ea74e8b40b0f/access_as_user"


def test_missing_config_names_the_file_and_the_keys_to_set(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ConfigError, match=r"config\.json.*base_url"):
        load_config()


def test_only_the_server_needs_setting_the_pace_registration_is_built_in(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "pace").mkdir()
    (tmp_path / "pace" / "config.json").write_text(json.dumps({"base_url": "https://hrms.example/api"}))
    assert load_config().client_id == "8c8d68c3-01e3-4e4b-aeab-975858570bf9"


def test_anything_but_sign_in_and_status_goes_to_the_app(monkeypatch):
    seen = []
    ui = types.ModuleType("pace.ui")
    ui.main = lambda argv: seen.append(argv) or 7
    monkeypatch.setitem(sys.modules, "pace.ui", ui)
    assert main([]) == 7
    assert main(["widget"]) == 7
    assert seen == [[], ["widget"]]


def test_a_missing_app_says_so(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pace.ui", None)  # import raises ModuleNotFoundError
    assert main(["settings"]) == 2
    assert "pace.ui" in capsys.readouterr().err


@pytest.mark.parametrize(
    "desktop, watcher, wanted",
    [
        ("GNOME", True, False),
        ("ubuntu:GNOME", True, False),
        ("KDE", True, True),
        ("KDE", False, False),
        ("", True, True),
        ("COSMIC", True, True),
    ],
)
def test_the_tray_is_for_desktops_that_are_not_gnome_and_have_a_watcher(desktop, watcher, wanted):
    assert tray_wanted(desktop, watcher) is wanted
