"""Everything the windows need from outside the UI process, behind one object so screenshots and tests can swap it for a fake."""

from __future__ import annotations

import urllib.request
from datetime import date
from importlib import metadata

from gi.repository import Gio, GLib

from pace.files import read_json, state_dir

BUS_NAME, BUS_PATH, BUS_IFACE = "io.github.xixas.Pace", "/io/github/xixas/Pace", "io.github.xixas.Pace1"
RELEASES_URL = "https://github.com/xixas/pace/releases"
SHELL_EXTENSIONS = ("org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions")


def version() -> str:
    """The packaged version (make install writes pace/_version.py from the rpm spec), else the dist metadata."""
    try:
        from pace._version import VERSION

        return VERSION
    except ImportError:
        pass
    try:
        return metadata.version("pace")
    except metadata.PackageNotFoundError:
        return "dev"


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
        from pace.ui import config

        if config.load_settings()["token_store"] == "none":
            return self._sign_in_through_paced()
        cfg = load_config()
        sign_in_flow(cfg, client(cfg), open_uri=open_uri)

    def _sign_in_through_paced(self, timeout: float = 300) -> None:
        """A memory-only session has to live in paced, so paced runs the browser flow; wait for status.json to say so."""
        import time

        from pace.files import read_json, state_dir

        self._call("SignIn", lambda *_: None)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if (read_json(state_dir() / "status.json") or {}).get("state") not in (None, "signed_out"):
                return
            time.sleep(1)
        raise TimeoutError("no answer from the browser")

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

    # the GNOME panel extension, asked of the shell itself (blocking calls: run them off the main thread)
    def extension_info(self, uuid: str) -> dict | None:
        """GetExtensionInfo(uuid) as a plain dict ({} when the shell doesn't know the extension), None without a shell."""
        reply = self._shell_call("GetExtensionInfo", GLib.Variant("(s)", (uuid,)))
        return reply.unpack()[0] if reply else None

    def enable_extension(self, uuid: str) -> bool:
        reply = self._shell_call("EnableExtension", GLib.Variant("(s)", (uuid,)))
        return bool(reply and reply.unpack()[0])

    @staticmethod
    def _shell_call(method: str, args):
        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            name, path, iface = SHELL_EXTENSIONS
            return conn.call_sync(name, path, iface, method, args, None, Gio.DBusCallFlags.NONE, 5000, None)
        except GLib.Error:
            return None

    # paced
    def refresh(self, done) -> None:
        """Ask paced to poll now. done(ok: bool) runs on the main loop."""
        self._call("Refresh", done)

    def paced_sign_in(self, done) -> None:
        self._call("SignIn", done)

    def _call(self, method: str, done) -> None:
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
