"""Where the HRMS session ({"access", "refresh"}) lives between runs: the keyring, or a mode 600 file without one."""

from __future__ import annotations

import json

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
