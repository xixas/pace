"""Tray on a private bus with a fake StatusNotifierWatcher. Never touches the real session bus."""

import os
import shutil
import subprocess

import pytest

gi = pytest.importorskip("gi")
from gi.repository import Gio, GLib  # noqa: E402

from pace import tray  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("dbus-daemon") is None, reason="dbus-daemon not installed")

STATUS = {
    "colour": "green",
    "snoozed_until": None,
    "tray": {
        "number": "30",
        "tooltip_title": "Pace — Week · On track",
        "tooltip_lines": ["30.1 / 42.5 h · needs 8.0 h/day", "Tweelin Oct 112.5 / 133 h (−6.5)"],
        "info_rows": ["Week · On track — 30.1 / 42.5 h", "Needs 8.0 h/day · 4.5 h left today", "Tweelin −6.5 h (Oct)"],
        "fill": 0.71,
    },
}

NAME = f"org.kde.StatusNotifierItem-{os.getpid()}-1"

WATCHER_XML = """<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" name="service" direction="in"/></method>
</interface></node>"""


def pump(cond, timeout=5.0):
    ctx = GLib.MainContext.default()
    end = GLib.get_monotonic_time() + timeout * 1_000_000
    while not cond():
        if GLib.get_monotonic_time() > end:
            raise AssertionError("timed out")
        ctx.iteration(False)
        GLib.usleep(1000)


def call(conn, dest, path, iface, method, params=None, reply=None):
    box = {}
    conn.call(
        dest, path, iface, method, params, reply, Gio.DBusCallFlags.NONE, 5000, None, lambda c, r, _d: box.update(r=r), None
    )
    pump(lambda: "r" in box)
    return conn.call_finish(box["r"]).unpack()


@pytest.fixture(scope="module")
def bus_address():
    p = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address"], stdout=subprocess.PIPE, text=True)
    addr = p.stdout.readline().strip()
    yield addr
    p.terminate()
    p.wait()


@pytest.fixture
def conn_factory(bus_address):
    conns = []

    def make():
        c = Gio.DBusConnection.new_for_address_sync(
            bus_address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None,
            None,
        )
        conns.append(c)
        return c

    yield make
    for c in conns:
        c.close_sync(None)


class FakeWatcher:
    def __init__(self, conn):
        self.conn = conn
        self.registered: list[str] = []
        self.owner = 0
        self.reg = 0

    def start(self):
        node = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML)

        def handler(conn, sender, path, iface, method, params, inv):
            self.registered.append(params.unpack()[0])
            inv.return_value(None)

        self.reg = self.conn.register_object(tray.WATCHER_PATH, node.interfaces[0], handler, None, None)
        self.own()

    def own(self):
        self.conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
            GLib.Variant("(su)", (tray.WATCHER, 0)), None, Gio.DBusCallFlags.NONE, -1, None,
        )  # fmt: skip

    def stop(self):
        self.conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ReleaseName",
            GLib.Variant("(s)", (tray.WATCHER,)), None, Gio.DBusCallFlags.NONE, -1, None,
        )  # fmt: skip


@pytest.fixture
def env(conn_factory):
    watcher = FakeWatcher(conn_factory())
    watcher.start()
    actions: list[str] = []
    t = tray.Tray(conn_factory(), actions.append)
    pump(lambda: watcher.registered)
    client = conn_factory()
    yield t, watcher, actions, client
    t.close()


def prop(client, name, path=tray.ITEM_PATH, iface="org.kde.StatusNotifierItem", dest=None):
    dest = dest or NAME
    return call(client, dest, path, "org.freedesktop.DBus.Properties", "Get", GLib.Variant("(ss)", (iface, name)))[0]


def test_registers_with_watcher_under_its_service_name(env):
    _t, watcher, _a, _c = env
    assert watcher.registered[0].startswith("org.kde.StatusNotifierItem-")


def test_reregisters_when_watcher_restarts(env):
    _t, watcher, _a, _c = env
    watcher.stop()
    watcher.registered.clear()
    watcher.own()
    pump(lambda: watcher.registered)
    assert len(watcher.registered) == 1


def test_sni_properties_before_first_update(env):
    _t, _w, _a, client = env
    assert prop(client, "Id") == "pace"
    assert prop(client, "Category") == "ApplicationStatus"
    assert prop(client, "Status") == "Active"
    assert prop(client, "ItemIsMenu") is False
    assert prop(client, "Menu") == tray.MENU_PATH
    assert [(w, h) for w, h, _ in prop(client, "IconPixmap")] == [(22, 22), (32, 32), (48, 48), (64, 64)]


def test_update_sets_tooltip_and_icon_and_emits_signals(env):
    t, _w, _a, client = env
    seen = []
    client.signal_subscribe(None, "org.kde.StatusNotifierItem", None, tray.ITEM_PATH, None, Gio.DBusSignalFlags.NONE,
                            lambda *a: seen.append(a[4]), None)  # fmt: skip
    layouts = []
    client.signal_subscribe(None, "com.canonical.dbusmenu", "LayoutUpdated", tray.MENU_PATH, None, Gio.DBusSignalFlags.NONE,
                            lambda *a: layouts.append(a[5].unpack()), None)  # fmt: skip
    before = prop(client, "IconPixmap")[3][2]
    t.update(STATUS)
    pump(lambda: {"NewIcon", "NewToolTip"} <= set(seen) and layouts)
    _icon, _pm, title, desc = prop(client, "ToolTip")
    assert title == "Pace — Week · On track"
    assert desc == "30.1 / 42.5 h · needs 8.0 h/day\nTweelin Oct 112.5 / 133 h (−6.5)"
    assert prop(client, "IconPixmap")[3][2] != before


def test_activate_dispatches_widget(env):
    _t, _w, actions, client = env
    call(client, NAME, tray.ITEM_PATH, "org.kde.StatusNotifierItem", "Activate", GLib.Variant("(ii)", (0, 0)))
    assert actions == ["widget"]


def test_menu_layout_over_the_bus(env):
    t, _w, _a, client = env
    t.update(STATUS)
    _rev, (root, _props, children) = call(
        client, NAME, tray.MENU_PATH, "com.canonical.dbusmenu", "GetLayout", GLib.Variant("(iias)", (0, -1, []))
    )
    assert root == 0
    labels = [c[1].get("label") for c in children]
    assert labels[:3] == STATUS["tray"]["info_rows"]
    assert labels[4:] == ["Open dashboard", "Open PineStem", "Show mini widget", "Snooze nudges today", "Refresh", "Quit"]


def test_menu_click_dispatches_action(env):
    t, _w, actions, client = env
    t.update(STATUS)
    for label, action in [("Open dashboard", "dashboard"), ("Quit", "quit")]:
        item_id = next(i["id"] for i in tray.menu_items(STATUS) if i["props"].get("label") == label)
        call(client, NAME, tray.MENU_PATH, "com.canonical.dbusmenu", "Event",
             GLib.Variant("(isvu)", (item_id, "clicked", GLib.Variant("i", 0), 0)))  # fmt: skip
        assert actions[-1] == action


def test_info_row_and_hover_events_do_not_dispatch(env):
    t, _w, actions, client = env
    t.update(STATUS)
    call(client, NAME, tray.MENU_PATH, "com.canonical.dbusmenu", "Event",
         GLib.Variant("(isvu)", (51, "hovered", GLib.Variant("i", 0), 0)))  # fmt: skip
    assert actions == []


def test_group_properties_and_about_to_show(env):
    t, _w, _a, client = env
    t.update(STATUS)
    (props,) = call(client, NAME, tray.MENU_PATH, "com.canonical.dbusmenu", "GetGroupProperties",
                    GLib.Variant("(aias)", ([tray.ACTION_IDS["quit"]], ["label"])))  # fmt: skip
    assert props == [(tray.ACTION_IDS["quit"], {"label": "Quit"})]
    assert call(client, NAME, tray.MENU_PATH, "com.canonical.dbusmenu", "AboutToShow", GLib.Variant("(i)", (0,))) == (False,)
