"""Everything the windows need from outside the UI process, behind one object so screenshots and tests can swap it for a fake."""

from __future__ import annotations

import urllib.request
from datetime import date
from importlib import metadata

from pace.files import read_json, state_dir

BUS_NAME, BUS_PATH, BUS_IFACE = "io.github.xixas.Pace", "/io/github/xixas/Pace", "io.github.xixas.Pace1"
RELEASES_URL = "https://github.com/xixas/pace/releases"


def version() -> str:
    try:
        return metadata.version("pace")
    except metadata.PackageNotFoundError:
        return "0.1.0"


class Services:
    """The real thing: status.json and profile.json on disk, hrms-api through pace.client, paced over D-Bus."""

    def __init__(self):
        self._store = None

    # files paced and core write
    def status(self) -> dict:
        return read_json(state_dir() / "status.json") or {}

    def profile(self) -> dict | None:
        return read_json(state_dir() / "profile.json")

    # session
    def store(self):
        if self._store is None:
            from pace.cli import session_store

            self._store = session_store()
        return self._store

    def signed_in(self) -> bool:
        try:
            return bool(self.store().load())
        except Exception:
            return False

    def keyring_available(self) -> bool:
        from pace.tokens import KeyringStore

        try:
            return KeyringStore().available()
        except Exception:
            return False

    def sign_in(self, open_uri) -> None:
        """Blocks until the browser comes back; call it off the main thread. Raises what sign_in_flow raises."""
        from pace.cli import client, load_config
        from pace.signin import sign_in_flow

        cfg = load_config()
        sign_in_flow(cfg, client(cfg), open_uri=open_uri)

    def cancel_sign_in(self, redirect: str) -> None:
        from pace.ui.onboarding import cancel_url

        try:
            urllib.request.urlopen(cancel_url(redirect), timeout=3).close()
        except OSError:
            pass  # the listener is already gone

    def sign_out(self) -> None:
        self.store().clear()

    # hrms-api through pace.history (core)
    def history(self, start: date, end: date) -> list[dict]:
        from pace import history

        return history.load(start, end)

    def has_history(self) -> bool:
        try:
            from pace import history  # noqa: F401
        except ImportError:
            return False
        return True

    # paced
    def refresh(self, done) -> None:
        """Ask paced to poll now. done(ok: bool) runs on the main loop."""
        self._call("Refresh", done)

    def paced_sign_in(self, done) -> None:
        self._call("SignIn", done)

    def _call(self, method: str, done) -> None:
        from gi.repository import Gio

        def finished(conn, result):
            try:
                conn.call_finish(result)
                done(True)
            except Exception:
                done(False)

        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            conn.call(BUS_NAME, BUS_PATH, BUS_IFACE, method, None, None, Gio.DBusCallFlags.NONE, 5000, None, finished)
        except Exception:
            done(False)
