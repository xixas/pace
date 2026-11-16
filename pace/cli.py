"""Entry points: `pace` (sign-in, status; the rest is the GTK app) and `paced` (the daemon). Config: $XDG_CONFIG_HOME/pace/config.json."""

from __future__ import annotations

import json
import os
import signal
import sys
import traceback

from pace.files import config_dir, read_json, state_dir

# Osmosys Entra tenant, hrms-api's registration (MS_SSO_CLIENT_ID; dev and prod share them, hrms-portal 2026-10-30)
# and Pace's own public-client registration (created 2026-11-08). Public ids, not secrets. base_url is production;
# config.json overrides it (dev: https://dev-api.dhihrms.com/api, local mock: http://127.0.0.1:8001/api).
DEFAULTS = {
    "base_url": "https://api.dhihrms.com/api",
    "tenant": "95ca85cb-20c9-45c5-bbfc-be2d0ac2e657",
    "api_client_id": "97152fbf-dde7-4077-a876-ea74e8b40b0f",
    "client_id": "8c8d68c3-01e3-4e4b-aeab-975858570bf9",
}
REQUIRED = ("base_url",)


class ConfigError(Exception):
    pass


def load_config():
    from pace.signin import Config

    path = config_dir() / "config.json"
    values = {**DEFAULTS, **(read_json(path) or {})}
    missing = [k for k in REQUIRED if not values.get(k)]
    if missing:
        raise ConfigError(f"{path}: set {', '.join(missing)} (hrms-api base URL, and the Pace Entra client id)")
    return Config(**{k: values[k] for k in ("base_url", "tenant", "client_id", "api_client_id")})


def session_store():
    """Where the session lives, per the A9 choice: keyring (falling back to the mode 600 file when there is
    none, decision 8), the file, or nowhere ("sign in each login": memory only)."""
    from pace.settings import Settings
    from pace.tokens import FileStore, KeyringFirst, KeyringStore, MemoryStore

    choice = Settings().data["token_store"]
    if choice == "none":
        return MemoryStore()
    if choice == "keyring" and (keyring := KeyringStore()).available():
        return KeyringFirst(keyring, FileStore())
    return FileStore()


def client(cfg):
    from pace.client import Client, urllib_transport

    return Client(cfg.base_url, session_store(), urllib_transport)


def sign_in(api=None) -> None:
    """The browser sign-in. Raises on failure. paced passes its own client, so a memory-only session
    (A9 "sign in each login") lands in the store it polls with."""
    import webbrowser

    from pace.signin import sign_in_flow

    cfg = load_config()
    sign_in_flow(cfg, api or client(cfg), open_uri=webbrowser.open)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["status"]:
        print(json.dumps(read_json(state_dir() / "status.json"), indent=1))
        return 0
    if args == ["sign-in"]:
        try:
            sign_in()
        except Exception as e:
            print(f"pace: sign-in failed: {e}", file=sys.stderr)
            return 1
        print("Signed in.")
        return 0
    return open_app(args)


def open_app(args: list[str]) -> int:
    """Everything else is the GTK app, imported only now so `pace status` never loads GTK."""
    try:
        from pace.ui import main as ui_main
    except ModuleNotFoundError as e:
        if e.name != "pace.ui":
            raise
        print("pace: the Pace window (pace.ui) isn't installed. Try `pace status` or `pace sign-in`.", file=sys.stderr)
        return 2
    return ui_main(args)


def tray_wanted(desktop: str, watcher_present: bool) -> bool:
    """GNOME shows the panel extension instead; every other desktop with a StatusNotifier watcher gets the tray."""
    return "GNOME" not in desktop.upper() and watcher_present


def start_tray(bus, daemon):
    """pace.tray.Tray when this desktop wants one and the module exists; None otherwise."""
    from gi.repository import Gio, GLib

    watcher = bus.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameHasOwner",
        GLib.Variant("(s)", ("org.kde.StatusNotifierWatcher",)),
        GLib.VariantType("(b)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    ).unpack()[0]
    if not tray_wanted(os.environ.get("XDG_CURRENT_DESKTOP", ""), watcher):
        return None
    try:
        from pace.tray import Tray
    except ImportError:
        return None
    tray = Tray(bus, daemon.action)
    daemon.listeners.append(tray.update)
    if daemon.status:
        tray.update(daemon.status)
    return tray


def paced(argv=None) -> int:
    """Paint the saved week, poll now, then on the settings' interval on a GLib main loop. --once polls once and exits."""
    from pace.daemon import Daemon

    try:
        api = client(load_config())
        daemon = Daemon(api, sign_in=lambda: sign_in(api))
    except ConfigError as e:
        print(f"paced: {e}", file=sys.stderr)
        return 1
    if "--once" in (sys.argv[1:] if argv is None else argv):
        daemon.boot()
        daemon.tick()
        return 0
    from gi.repository import Gio, GLib

    from pace.notify import Notifier
    from pace.service import Service

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    daemon.on_quit = loop.quit
    daemon.on_signed_in = lambda: GLib.idle_add(lambda: daemon.tick() or False)
    daemon.send = Notifier(bus, daemon.action).send
    service = Service(bus, daemon)
    daemon.listeners.append(service.status_changed)
    tray = start_tray(bus, daemon)  # noqa: F841  (kept alive for the loop's lifetime)
    timer = {}

    def schedule() -> None:
        """One timer at a time: the refresh interval, or a short backoff while offline."""
        if timer:
            GLib.source_remove(timer.pop("id"))
        timer["id"] = GLib.timeout_add_seconds(daemon.next_poll_in(), poll_now)

    def poll_now(backoff: bool = True) -> bool:
        timer.pop("id", None)  # this source ends here (returns False), so schedule() must not remove it
        try:
            daemon.tick(backoff=backoff)
        except Exception:  # a bad reply must not end polling for the rest of the session: retry it like offline
            traceback.print_exc()
            daemon.offline_tries += 1
        finally:
            schedule()
        return False

    def network_changed(_monitor, available: bool) -> None:
        if available and daemon.problem == "offline":  # the network came up: don't sit out the backoff
            if timer:
                GLib.source_remove(timer.pop("id"))
            GLib.idle_add(poll_now, False)  # not inside the signal: a poll can block for up to 20 s

    def settings_changed() -> None:
        daemon.render()
        schedule()

    monitor = daemon.settings.watch(settings_changed)  # noqa: F841
    network = Gio.NetworkMonitor.get_default()
    network.connect("network-changed", network_changed)
    daemon.boot()
    poll_now()  # the first poll, guarded like every later one
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: loop.quit() or False)
    loop.run()
    return 0
