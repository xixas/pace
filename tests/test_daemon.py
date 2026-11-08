"""paced's cycle: paint the cached status at login before any network call, then poll, save, publish and nudge."""

from datetime import datetime, timedelta

import pytest
from test_poll import MON, DownApi, FakeApi, billed

from pace.client import Offline, SignedOut
from pace.daemon import Daemon
from pace.files import read_json, state_dir


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def test_boot_paints_the_saved_week_without_touching_the_network():
    clock = Clock(datetime(2026, 11, 3, 18, 30))
    Daemon(FakeApi(billed(MON)), clock).tick()  # yesterday's session: Mon billed

    clock.now = datetime(2026, 11, 4, 9, 0)  # next login, before the first poll
    api = FakeApi(billed(MON))
    Daemon(api, clock).boot()
    assert api.calls == []
    assert read_json(state_dir() / "status.json")["text"] == "8.5 / 42.5 h"


def test_tick_polls_and_saves_both_files():
    Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30))).tick()
    assert read_json(state_dir() / "status.json")["state"] == "on_track"
    assert read_json(state_dir() / "state.json")["as_of"] == "2026-11-03T18:30:00"


def test_listeners_hear_every_status_that_is_written():
    heard = []
    d = Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30)))
    d.listeners.append(heard.append)
    d.tick()
    assert [s["state"] for s in heard] == ["on_track"]


def test_settings_pick_the_panel_text():
    config = state_dir().parent.parent / "config" / "pace"
    config.mkdir(parents=True)
    (config / "settings.json").write_text('{"panel_text": "percent"}')
    Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30))).tick()
    assert read_json(state_dir() / "status.json")["text"] == "20%"


def test_snooze_lasts_until_midnight_and_unsnooze_undoes_it_without_a_poll():
    api = FakeApi(billed(MON))
    d = Daemon(api, Clock(datetime(2026, 11, 3, 18, 30)))
    d.tick()
    api.calls.clear()
    d.snooze()
    assert read_json(state_dir() / "status.json")["snoozed_until"] == "2026-11-04T00:00:00"
    d.unsnooze()
    assert read_json(state_dir() / "status.json")["snoozed_until"] is None
    assert api.calls == []


def test_refresh_asks_for_fresh_data_at_most_once_a_minute():
    clock = Clock(datetime(2026, 11, 3, 18, 30))
    api = FakeApi(billed(MON))
    d = Daemon(api, clock)
    d.refresh()
    clock.now += timedelta(seconds=30)
    d.refresh()
    clock.now += timedelta(seconds=40)
    d.refresh()
    fresh = [c[3:] == (True,) for c in api.calls if c[0] == "my_hours"]
    assert fresh == [True, False, True]


def test_nudges_go_out_once_even_over_many_polls():
    sent = []
    clock = Clock(datetime(2026, 11, 6, 16, 30))  # Friday
    d = Daemon(FakeApi(billed(*(MON + timedelta(i) for i in range(4)))), clock, send=sent.append)
    d.tick()
    clock.now += timedelta(minutes=15)
    d.tick()
    assert [n.key for n in sent] == ["friday"]
    assert Daemon(FakeApi(billed(MON)), clock, send=sent.append).state["sent"] == {"2026-11-06": ["friday"]}


def test_snoozed_and_offline_polls_send_nothing():
    sent = []
    clock = Clock(datetime(2026, 11, 6, 16, 30))
    d = Daemon(FakeApi(billed(*(MON + timedelta(i) for i in range(4)))), clock, send=sent.append)
    d.snooze()
    d.tick()
    assert sent == []
    d.unsnooze()
    d.api = DownApi(Offline("no route"))
    d.tick()
    assert sent == []


def test_signed_out_sends_one_notification_until_the_next_sign_in():
    sent = []
    clock = Clock(datetime(2026, 11, 3, 9, 40))
    api = FakeApi(billed(MON))
    d = Daemon(api, clock, send=sent.append)
    d.tick()
    d.api = DownApi(SignedOut("refresh rejected"))
    d.tick()
    d.tick()
    assert [n.key for n in sent] == ["signed_out"]
    assert sent[0].body.endswith("Numbers are paused at 09:40.")
    d.api = api
    d.tick()
    d.api = DownApi(SignedOut("again"))
    d.tick()
    assert [n.key for n in sent] == ["signed_out", "signed_out"]


def test_no_mapping_shows_when_the_profile_says_pinestem_is_not_linked():
    (state_dir()).mkdir(parents=True)
    (state_dir() / "profile.json").write_text('{"name": "V", "pinestem_mapped": false}')
    Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30))).tick()
    assert read_json(state_dir() / "status.json")["state"] == "no_mapping"


def test_actions_from_buttons_and_the_tray():
    opened, spawned, calls = [], [], []
    d = Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30)), open_url=opened.append, spawn=spawned.append)
    d.sign_in = lambda: calls.append("sign_in")
    d.on_quit = lambda: calls.append("quit")
    d.tick()
    for name in ["pinestem", "snooze", "dashboard", "widget", "signin", "quit", "dismiss"]:
        d.action(name)
    assert opened == ["https://pinestem.com/dashboard.html#/tasks"]
    assert spawned == [["pace"], ["pace", "widget"]]
    assert calls == ["sign_in", "quit"]
    assert read_json(state_dir() / "status.json")["snoozed_until"] == "2026-11-04T00:00:00"
