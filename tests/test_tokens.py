"""Where the HRMS session lives between runs. FileStore is the no-keyring fallback (decision 8, mock A9)."""

import stat
import types

from pace.tokens import FileStore, KeyringStore


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


class FakeSecret:
    """Just enough of gi's Secret: a Service that is there, and a default collection that may not be."""

    class ServiceFlags:
        NONE = 0

    class CollectionFlags:
        NONE = 0

    def __init__(self, default_collection):
        self.default_collection = default_collection
        self.Service = types.SimpleNamespace(get_sync=lambda *_: "service")
        self.Collection = types.SimpleNamespace(for_alias_sync=lambda service, alias, *_: self.default_collection)


def keyring_with(secret):
    store = KeyringStore.__new__(KeyringStore)  # skip the gi import
    store.secret = secret
    return store


def test_keyring_is_available_when_the_default_collection_exists():
    assert keyring_with(FakeSecret(default_collection=object())).available()


def test_keyring_is_not_available_without_a_default_wallet_so_kwallet_never_opens_its_create_wizard():
    assert not keyring_with(FakeSecret(default_collection=None)).available()


def test_a_session_saved_to_the_file_while_there_was_no_wallet_is_still_found_once_a_wallet_exists(tmp_path, monkeypatch):
    from pace.tokens import FileStore, KeyringFirst, MemoryStore

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    FileStore().save({"access": "A", "refresh": "R"})  # signed in from the tray before any KDE wallet existed
    wallet = MemoryStore()  # the wallet that appeared later: empty
    store = KeyringFirst(wallet, FileStore())
    assert store.load() == {"access": "A", "refresh": "R"}
    store.save({"access": "A2", "refresh": "R2"})  # the next refresh moves it into the wallet
    assert wallet.load() == {"access": "A2", "refresh": "R2"} and FileStore().load() is None
    store.clear()
    assert store.load() is None
