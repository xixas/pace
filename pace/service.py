"""paced's D-Bus face (contract section 4): io.github.xixas.Pace1 on the session bus. Gio only, no GTK."""

from __future__ import annotations

import json

from gi.repository import Gio, GLib

NAME = "io.github.xixas.Pace"
PATH = "/io/github/xixas/Pace"
IFACE = "io.github.xixas.Pace1"
METHODS = {
    "Refresh": "refresh",
    "Snooze": "snooze",
    "Unsnooze": "unsnooze",
    "SignIn": "sign_in",
    "ShowWidget": "show_widget",
    "Quit": "quit",
}
XML = (
    f'<node><interface name="{IFACE}">'
    + "".join(f'<method name="{m}"/>' for m in METHODS)
    + '<signal name="StatusChanged"><arg type="s" name="json"/></signal></interface></node>'
)


class Service:
    """Exports the interface on bus. daemon needs refresh, snooze, unsnooze, sign_in, show_widget and quit (no arguments)."""

    def __init__(self, bus: Gio.DBusConnection, daemon):
        self.bus, self.daemon, self.owned = bus, daemon, False
        bus.register_object(PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], self.handle, None, None)
        Gio.bus_own_name_on_connection(
            bus, NAME, Gio.BusNameOwnerFlags.DO_NOT_QUEUE, self.acquired, lambda *_: daemon.quit()
        )  # a second paced has nothing to do

    def acquired(self, *_) -> None:
        self.owned = True

    def handle(self, _conn, _sender, _path, _iface, method, _params, invocation) -> None:
        getattr(self.daemon, METHODS[method])()
        invocation.return_value(None)

    def status_changed(self, status: dict) -> None:
        self.bus.emit_signal(None, PATH, IFACE, "StatusChanged", GLib.Variant("(s)", (json.dumps(status, ensure_ascii=False),)))
