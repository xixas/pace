import json

import pytest

from pace.files import config_dir, data_dir, state_dir
from pace.ui import config


@pytest.fixture(autouse=True)
def xdg(tmp_path, monkeypatch):
    for kind in ("CONFIG", "STATE", "DATA"):
        monkeypatch.setenv(f"XDG_{kind}_HOME", str(tmp_path / kind.lower()))
    return tmp_path


def autostart(name):
    return config.autostart_dir() / name


def test_load_settings_defaults_and_deep_merge():
    s = config.load_settings()
    assert s["panel_text"] == "hours" and s["refresh_minutes"] == 15 and s["token_store"] == "keyring"
    assert s["notify"]["friday"] == {"on": True, "at": "16:00"}
    config_dir().mkdir(parents=True)
    (config_dir() / "settings.json").write_text(json.dumps({"panel_text": "gap", "notify": {"friday": {"at": "15:30"}}}))
    s = config.load_settings()
    assert s["panel_text"] == "gap"
    assert s["notify"]["friday"] == {"on": True, "at": "15:30"}
    assert s["notify"]["daily"]["at"] == "20:00"


def test_save_settings_roundtrip_and_ignores_unknown_values():
    s = config.load_settings()
    s["refresh_minutes"] = 30
    config.save_settings(s)
    assert config.load_settings()["refresh_minutes"] == 30
    (config_dir() / "settings.json").write_text("not json")
    assert config.load_settings()["refresh_minutes"] == 15


def test_start_at_login_false_writes_hidden_override_true_deletes_it():
    s = config.load_settings()
    s["start_at_login"] = False
    config.apply_autostart(s)
    text = autostart("io.github.xixas.Pace.daemon.desktop").read_text()
    assert "Hidden=true" in text and "[Desktop Entry]" in text
    s["start_at_login"] = True
    config.apply_autostart(s)
    assert not autostart("io.github.xixas.Pace.daemon.desktop").exists()


def test_widget_at_login_writes_a_real_entry_when_on_and_hidden_when_off():
    s = config.load_settings()
    s["widget_at_login"] = True
    config.apply_autostart(s)
    on = autostart("io.github.xixas.Pace.widget.desktop").read_text()
    assert "Exec=pace widget" in on and "Hidden" not in on
    s["widget_at_login"] = False
    config.apply_autostart(s)
    assert "Hidden=true" in autostart("io.github.xixas.Pace.widget.desktop").read_text()


def test_time_validation():
    assert config.valid_time("16:00") and config.valid_time("09:05")
    assert not config.valid_time("24:00") and not config.valid_time("9") and not config.valid_time("12:60")
    assert config.format_time(9, 5) == "09:05"
    assert config.split_time("16:30") == (16, 30)


def test_targets_default_and_roundtrip():
    assert config.load_targets() == {"dailyMinimum": 8.5, "projects": []}
    t = config.load_targets()
    t["projects"].append({"code": "RES", "name": "R&D", "monthly_h": None, "prorate": False, "source": "personal"})
    config.save_targets(t)
    assert config.load_targets()["projects"][0]["code"] == "RES"


PRESET = {"from": "Anand", "projects": [{"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True}]}


def test_parse_preset_validates():
    p = config.parse_preset(json.dumps(PRESET))
    assert p["from"] == "Anand" and p["projects"][0]["code"] == "TWE"
    for bad in ("[]", "{}", json.dumps({"from": "A", "projects": [{"code": "X"}]}), "nope"):
        with pytest.raises(config.PresetError):
            config.parse_preset(bad)


def test_preset_summary_text():
    assert config.preset_summary(PRESET["projects"]) == ["Tweelin 140 h / month, prorated for leave & holidays"]
    assert config.preset_summary([{"code": "X", "name": "X", "monthly_h": 10, "prorate": False}]) == ["X 10 h / month, fixed"]


def test_merge_preset_locks_rows_and_keeps_personal():
    t = {
        "dailyMinimum": 8.5,
        "projects": [
            {"code": "RES", "name": "R&D", "monthly_h": None, "prorate": False, "source": "personal"},
            {"code": "TWE", "name": "Tweelin", "monthly_h": 100, "prorate": False, "source": "personal"},
        ],
    }
    out = config.merge_preset(t, PRESET)
    twe = next(p for p in out["projects"] if p["code"] == "TWE")
    assert twe == {"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True, "source": "lead", "lead": "Anand"}
    assert any(p["code"] == "RES" for p in out["projects"])
    assert len(out["projects"]) == 2


def test_build_preset_and_filename():
    row = {"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True, "source": "personal"}
    p = config.build_preset("Vikas K", row)
    assert p == {"from": "Vikas K", "projects": [{"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True}]}
    from datetime import date

    assert config.preset_filename("Tweelin", date(2026, 10, 29)) == "tweelin-oct.pace-targets.json"
    assert config.preset_filename("R&D Team", date(2026, 3, 1)) == "r-d-team-mar.pace-targets.json"


def test_remove_my_data_deletes_state_config_session_autostart_and_calls_keyring():
    for d in (state_dir(), config_dir(), data_dir(), config.autostart_dir()):
        d.mkdir(parents=True)
    (state_dir() / "status.json").write_text("{}")
    (config_dir() / "targets.json").write_text("{}")
    (data_dir() / "session.json").write_text("{}")
    for n in ("daemon", "widget"):
        autostart(f"io.github.xixas.Pace.{n}.desktop").write_text("x")
    other = config.autostart_dir() / "other.desktop"
    other.write_text("x")
    cleared = []
    config.remove_my_data(lambda: cleared.append(1))
    assert cleared == [1]
    assert not state_dir().exists() and not config_dir().exists() and not data_dir().exists()
    assert other.exists()
    assert not autostart("io.github.xixas.Pace.daemon.desktop").exists()


def test_remove_my_data_survives_missing_pieces_and_keyring_failure():
    def boom():
        raise RuntimeError("no keyring")

    config.remove_my_data(boom)  # nothing exists, keyring raises: still fine


def test_widget_position_roundtrip():
    assert config.load_widget_pos() is None
    config.save_widget_pos(120, 340)
    assert config.load_widget_pos() == (120, 340)
