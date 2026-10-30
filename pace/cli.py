"""Entry points: `pace sign-in | status` and `paced` (the daemon). Config: $XDG_CONFIG_HOME/pace/config.json."""

from __future__ import annotations

import json
import signal
import sys

from pace.files import config_dir, read_json, state_dir

# Osmosys Entra tenant and hrms-api's registration (MS_SSO_CLIENT_ID); dev and prod share them (hrms-portal, 2026-10-30).
DEFAULTS = {"tenant": "95ca85cb-20c9-45c5-bbfc-be2d0ac2e657", "api_client_id": "97152fbf-dde7-4077-a876-ea74e8b40b0f"}
REQUIRED = ("base_url", "client_id")
POLL_SECONDS = 300


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


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["status"]:
        print(json.dumps(read_json(state_dir() / "status.json"), indent=1))
        return 0
    if args == ["sign-in"]:
        import webbrowser

        from pace.signin import sign_in_flow

        try:
            cfg = load_config()
            sign_in_flow(cfg, client(cfg), open_uri=webbrowser.open)
        except Exception as e:
            print(f"pace: sign-in failed: {e}", file=sys.stderr)
            return 1
        print("Signed in.")
        return 0
    print("usage: pace sign-in | status", file=sys.stderr)
    return 2


def paced(argv=None) -> int:
    """Paint the saved week, poll now, then every POLL_SECONDS on a GLib main loop. --once polls once and exits."""
    from pace.daemon import Daemon

    try:
        daemon = Daemon(client(load_config()))
    except ConfigError as e:
        print(f"paced: {e}", file=sys.stderr)
        return 1
    daemon.boot()
    daemon.tick()
    if "--once" in (sys.argv[1:] if argv is None else argv):
        return 0
    from gi.repository import GLib

    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(POLL_SECONDS, lambda: daemon.tick() or True)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: loop.quit() or False)
    loop.run()
    return 0
