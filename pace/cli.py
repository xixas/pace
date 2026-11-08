"""Entry points: `pace` (sign-in, status; the rest is the GTK app) and `paced` (the daemon). Config: $XDG_CONFIG_HOME/pace/config.json."""

from __future__ import annotations

import json
import os
import signal
import sys

from pace.files import config_dir, read_json, state_dir

# Osmosys Entra tenant, hrms-api's registration (MS_SSO_CLIENT_ID; dev and prod share them, hrms-portal 2026-10-30)
# and Pace's own public-client registration (created 2026-11-08). Public ids, not secrets.
DEFAULTS = {
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
    """The keyring when there is one; otherwise the mode 600 file (decision 8)."""
    from pace.tokens import FileStore, KeyringStore

    keyring = KeyringStore()
    return keyring if keyring.available() else FileStore()


def client(cfg):
    from pace.client import Client, urllib_transport

    return Client(cfg.base_url, session_store(), urllib_transport)


def sign_in() -> None:
    """The browser sign-in. Raises on failure."""
    import webbrowser

    from pace.signin import sign_in_flow

    cfg = load_config()
    sign_in_flow(cfg, client(cfg), open_uri=webbrowser.open)


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
        daemon = Daemon(client(load_config()), sign_in=sign_in)
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
        if timer:
            GLib.source_remove(timer["id"])
        timer["id"] = GLib.timeout_add_seconds(daemon.settings.data["refresh_minutes"] * 60, lambda: daemon.tick() or True)

    def settings_changed() -> None:
        daemon.render()
        schedule()

    monitor = daemon.settings.watch(settings_changed)  # noqa: F841
    daemon.boot()
    daemon.tick()
    schedule()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: loop.quit() or False)
    loop.run()
    return 0
