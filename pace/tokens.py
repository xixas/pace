"""Where the HRMS session ({"access", "refresh"}) lives between runs: the keyring, or a mode 600 file without one."""

from __future__ import annotations

import json
import threading

from pace.files import data_dir, read_json, write_json


class FileStore:
    """No-keyring fallback (decision 8): ~/.local/share/pace/session.json, mode 600, like rclone.conf."""

    def __init__(self):
        self.path = data_dir() / "session.json"

    def load(self) -> dict | None:
        return read_json(self.path)

    def save(self, tokens: dict) -> None:
        write_json(self.path, tokens)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


class KeyringStore:
    """Secret Service (GNOME Keyring, KWallet) via libsecret. available() is False on COSMIC, or on KDE until a default wallet exists."""

    def __init__(self, account: str = "hrms-session"):
        import gi

        gi.require_version("Secret", "1")
        from gi.repository import Secret

        self.secret = Secret
        self.schema = Secret.Schema.new(
            "io.github.xixas.Pace", Secret.SchemaFlags.NONE, {"account": Secret.SchemaAttributeType.STRING}
        )
        self.attrs = {"account": account}

    def available(self) -> bool:
        """A Secret Service is running and has a default collection. On a KDE profile with no wallet yet, storing would open
        KWallet's "create a new wallet" wizard (blocking, with a GPG choice), so that counts as no keyring: the file fallback applies."""
        try:
            service = self.secret.Service.get_sync(self.secret.ServiceFlags.NONE, None)
            return self.secret.Collection.for_alias_sync(service, "default", self.secret.CollectionFlags.NONE, None) is not None
        except Exception:
            return False

    def load(self) -> dict | None:
        text = self.secret.password_lookup_sync(self.schema, self.attrs, None)
        return json.loads(text) if text else None

    def save(self, tokens: dict) -> None:
        self.secret.password_store_sync(
            self.schema, self.attrs, self.secret.COLLECTION_DEFAULT, "Pace HRMS session", json.dumps(tokens), None
        )

    def clear(self) -> None:
        self.secret.password_clear_sync(self.schema, self.attrs, None)


class MemoryStore:
    """A9 "sign in each login": the session lives only as long as this process."""

    def __init__(self):
        self.tokens = None

    def load(self):
        return self.tokens

    def save(self, tokens):
        self.tokens = tokens

    def clear(self):
        self.tokens = None


class KeyringFirst:
    """The keyring, still finding a session saved to the file while there was no keyring (a tray sign-in on a KDE profile
    with no wallet yet). The next save moves it into the keyring."""

    def __init__(self, keyring, file):
        self.keyring, self.file = keyring, file

    def load(self):
        return self.keyring.load() or self.file.load()

    def save(self, tokens):
        self.keyring.save(tokens)
        self.file.clear()

    def clear(self):
        self.keyring.clear()
        self.file.clear()


class BackgroundStore:
    """paced's session store, opened on a worker thread. A locked KWallet answers only once the person unlocks it, and a
    keyring read on paced's main loop froze the tray and the panel until then. Until the store answers, load() raises
    WalletLocked, which polls treat like offline (keep the numbers, retry). make() builds the real store (cli.session_store)."""

    def __init__(self, make, wait: float = 0.5):
        self.wait = wait
        self._done = threading.Event()
        self._store = None
        self._tokens = None
        self._error: BaseException | None = None

        def open_store():
            try:
                self._store = make()
                self._tokens = self._store.load() if self._store is not None else None
            except BaseException as e:  # reported to the next load(), never lost
                self._error = e
            finally:
                self._done.set()

        threading.Thread(target=open_store, name="pace-session-store", daemon=True).start()

    def _ready(self):
        from pace.client import WalletLocked

        if not self._done.wait(self.wait):
            raise WalletLocked("Waiting for the wallet")
        if self._error is not None:
            raise self._error
        return self._store

    def load(self):
        store = self._ready()
        if self._tokens is not None:  # the first read, made on the worker thread
            tokens, self._tokens = self._tokens, None
            return tokens
        return store.load() if store is not None else None

    def save(self, tokens):
        self._ready().save(tokens)

    def clear(self):
        self._ready().clear()
