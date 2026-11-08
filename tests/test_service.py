"""io.github.xixas.Pace1 on the session bus (contract section 4), against a private bus."""

import json

from gi.repository import Gio
from test_notify import bus_address, connect, pump  # noqa: F401

from pace.service import IFACE, NAME, PATH, Service


class Daemon:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda: self.calls.append(name)


def call(conn, method):
    return conn.call_sync(NAME, PATH, IFACE, method, None, None, Gio.DBusCallFlags.NONE, 2000, None)


def test_every_method_reaches_the_daemon(bus_address):  # noqa: F811
    daemon = Daemon()
    svc = Service(connect(bus_address), daemon)
    client = connect(bus_address)
    assert pump(lambda: svc.owned)
    done = []
    for method, expected in [
        ("Refresh", "refresh"),
        ("Snooze", "snooze"),
        ("Unsnooze", "unsnooze"),
        ("SignIn", "sign_in"),
        ("ShowWidget", "show_widget"),
        ("Quit", "quit"),
    ]:
        client.call(NAME, PATH, IFACE, method, None, None, Gio.DBusCallFlags.NONE, 2000, None, lambda c, r: done.append(c.call_finish(r)))
        assert pump(lambda: len(done) > 0 and expected in daemon.calls), method
        done.clear()
    assert daemon.calls == ["refresh", "snooze", "unsnooze", "sign_in", "show_widget", "quit"]


def test_status_changed_signal_carries_the_status_json(bus_address):  # noqa: F811
    svc = Service(connect(bus_address), Daemon())
    client = connect(bus_address)
    got = []
    client.signal_subscribe(NAME, IFACE, "StatusChanged", PATH, None, Gio.DBusSignalFlags.NONE, lambda *a: got.append(a[-1].unpack()[0]))
    assert pump(lambda: svc.owned)
    svc.status_changed({"state": "on_track", "text": "30.1 / 42.5 h"})
    assert pump(lambda: got)
    assert json.loads(got[0]) == {"state": "on_track", "text": "30.1 / 42.5 h"}
