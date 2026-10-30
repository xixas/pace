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
    """Secret Service (GNOME Keyring, KWallet) via libsecret. available() is False on COSMIC or minimal KDE without one."""

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
        try:
            self.secret.Service.get_sync(self.secret.ServiceFlags.NONE, None)
            return True
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
