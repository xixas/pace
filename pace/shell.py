"""The mini widget on GNOME is drawn by the Pace shell extension (always on top, on every workspace), which owns this bus name.

No GTK here. Every call returns None when the extension is not running, so the caller falls back to the GTK card."""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

NAME = "io.github.xixas.Pace.Shell"
PATH = "/io/github/xixas/Pace/Shell"
TIMEOUT_MS = 500


def call(method: str):
    """The reply's unpacked values, or None when the extension isn't there (no bus, name not owned, shell busy)."""
    try:  # a fresh connection each time: these calls are rare, and a cached process-wide bus can go stale
        address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
        flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        bus = Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
    except GLib.Error:
        return None
    try:
        # NO_AUTO_START: nothing activates this name, so a missing extension must fail fast instead of waiting
        reply = bus.call_sync(NAME, PATH, NAME, method, None, None, Gio.DBusCallFlags.NO_AUTO_START, TIMEOUT_MS, None)
    except GLib.Error:
        return None
    finally:
        bus.close_sync(None)
    return reply.unpack()


def show_widget() -> bool:
    return call("ShowWidget") is not None


def hide_widget() -> bool:
    return call("HideWidget") is not None


def widget_visible() -> bool | None:
    reply = call("WidgetVisible")
    return None if reply is None else bool(reply[0])
