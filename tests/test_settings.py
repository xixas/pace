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
