"""settings.json: the GTK app writes it, paced reads it. Missing file or key → defaults (contract section 2)."""

import json

from pace.settings import DEFAULTS, Settings


def write(tmp_path, monkeypatch, obj):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "pace").mkdir(exist_ok=True)
    (tmp_path / "pace" / "settings.json").write_text(json.dumps(obj))


def test_no_file_gives_the_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = Settings().data
    assert s == DEFAULTS
    assert (s["panel_text"], s["refresh_minutes"], s["notify"]["daily"]) == ("hours", 15, {"on": True, "at": "20:00"})


def test_a_partial_file_keeps_defaults_for_the_rest_even_inside_notify(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, {"panel_text": "percent", "notify": {"friday": {"at": "15:00"}}})
    s = Settings().data
    assert s["panel_text"] == "percent"
    assert s["notify"]["friday"] == {"on": True, "at": "15:00"}
    assert s["notify"]["daily"] == {"on": True, "at": "20:00"}


def test_a_broken_file_or_bad_value_falls_back_to_the_default(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, {"panel_text": "sparkles", "refresh_minutes": "soon"})
    s = Settings().data
    assert (s["panel_text"], s["refresh_minutes"]) == ("hours", 15)
    (tmp_path / "pace" / "settings.json").write_text("{nope")
    assert Settings().data == DEFAULTS


def test_rules_default_to_dhihrms_values_and_convert_to_minutes(tmp_path, monkeypatch):
    from pace.engine import Rules

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert DEFAULTS["rules"] == {"daily_target_h": 8.5, "full_day_h": 9.0, "part_day_h": 5.0}
    assert Settings().rules() == Rules(510, 540, 300)
    write(tmp_path, monkeypatch, {"rules": {"daily_target_h": 8, "full_day_h": 8, "part_day_h": 4}})
    assert Settings().rules() == Rules(480, 480, 240)


def test_bad_rules_fall_back_to_the_defaults(tmp_path, monkeypatch):
    bad = [
        {"part_day_h": 9.0, "full_day_h": 9.0},  # part must be below full
        {"part_day_h": 0},
        {"full_day_h": 25},
        {"daily_target_h": 0},
        {"daily_target_h": 24.5},
        {"full_day_h": "nine"},
        {"part_day_h": 10},  # part above the default full
    ]
    for rules in bad:
        write(tmp_path, monkeypatch, {"rules": rules})
        assert Settings().data["rules"] == DEFAULTS["rules"], rules


def test_reload_picks_up_a_change(tmp_path, monkeypatch):
    write(tmp_path, monkeypatch, {})
    s = Settings()
    write(tmp_path, monkeypatch, {"refresh_minutes": 5})
    s.reload()
    assert s.data["refresh_minutes"] == 5


def test_watch_calls_back_when_the_app_saves_the_file(tmp_path, monkeypatch):
    from gi.repository import GLib

    write(tmp_path, monkeypatch, {})
    seen = []
    s = Settings()
    monitor = s.watch(lambda: seen.append(s.data["panel_text"]))
    loop = GLib.MainLoop()
    GLib.timeout_add(50, lambda: write(tmp_path, monkeypatch, {"panel_text": "gap"}) or False)
    GLib.timeout_add(600, lambda: loop.quit() or False)
    loop.run()
    assert seen and seen[-1] == "gap"
    monitor.cancel()
