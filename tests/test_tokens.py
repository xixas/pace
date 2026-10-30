"""Where the HRMS session lives between runs. FileStore is the no-keyring fallback (decision 8, mock A9)."""

import stat

from pace.tokens import FileStore


def test_file_store_round_trips_in_a_mode_600_file_under_xdg_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = FileStore()
    assert store.load() is None
    store.save({"access": "A1", "refresh": "R1"})
    path = tmp_path / "pace" / "session.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert FileStore().load() == {"access": "A1", "refresh": "R1"}
    store.clear()
    assert not path.exists() and store.load() is None
