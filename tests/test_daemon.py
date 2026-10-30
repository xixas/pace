"""paced's cycle: paint the cached status at login before any network call, then poll and save."""

from datetime import datetime

from test_poll import MON, FakeApi, billed

from pace.daemon import Daemon
from pace.files import read_json, state_dir


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def test_boot_paints_the_saved_week_without_touching_the_network(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    clock = Clock(datetime(2026, 11, 3, 18, 30))
    Daemon(FakeApi(billed(MON)), clock).tick()  # yesterday's session: Mon billed

    clock.now = datetime(2026, 11, 4, 9, 0)  # next login, before the first poll
    api = FakeApi(billed(MON))
    Daemon(api, clock).boot()
    assert api.calls == []
    assert read_json(state_dir() / "status.json")["text"] == "8.5 / 42.5 h"


def test_tick_polls_and_saves_both_files(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    Daemon(FakeApi(billed(MON)), Clock(datetime(2026, 11, 3, 18, 30))).tick()
    assert read_json(state_dir() / "status.json")["state"] == "on_track"
    assert read_json(state_dir() / "state.json")["as_of"] == "2026-11-03T18:30:00"
