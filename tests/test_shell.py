"""pace.shell: the app asks the shell extension to draw the widget. A private bus with a fake extension; never the real session."""

import os
import shutil
import subprocess

import pytest

gi = pytest.importorskip("gi")
from gi.repository import Gio, GLib  # noqa: E402

from pace import shell  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("dbus-daemon") is None, reason="dbus-daemon not installed")

XML = f"""<node><interface name="{shell.NAME}">
<method name="ShowWidget"/><method name="HideWidget"/>
<method name="WidgetVisible"><arg type="b" name="visible" direction="out"/></method>
</interface></node>"""


@pytest.fixture
def bus(monkeypatch):
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--print-address", "--nofork"], stdout=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", address)
    yield address
    daemon.terminate()
    daemon.wait(5)


def test_without_the_extension_every_call_says_so(bus):
    assert shell.show_widget() is False
    assert shell.hide_widget() is False
    assert shell.widget_visible() is None


def test_no_session_bus_at_all_is_the_same_as_no_extension(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/nonexistent/pace-test-bus")
    assert shell.show_widget() is False


def test_a_running_extension_is_asked_to_show_hide_and_report(bus):
    import threading

    shown = {"on": False}
    ready, stop = threading.Event(), threading.Event()

    def serve():  # the fake extension, in its own thread and main context so the blocking calls below can be answered
        ctx = GLib.MainContext.new()
        ctx.push_thread_default()
        conn = Gio.DBusConnection.new_for_address_sync(
            bus, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None
        )

        def handle(_c, _s, _p, _i, method, _args, inv):
            if method in ("ShowWidget", "HideWidget"):
                shown["on"] = method == "ShowWidget"
                inv.return_value(None)
            else:
                inv.return_value(GLib.Variant("(b)", (shown["on"],)))

        conn.register_object(PATH := shell.PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], handle, None, None)
        assert PATH
        Gio.bus_own_name_on_connection(conn, shell.NAME, Gio.BusNameOwnerFlags.NONE, lambda *_: ready.set(), None)
        while not stop.is_set():
            ctx.iteration(False)
            stop.wait(0.01)

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    assert ready.wait(5), os.environ["DBUS_SESSION_BUS_ADDRESS"]
    try:
        assert shell.widget_visible() is False
        assert shell.show_widget() is True and shell.widget_visible() is True
        assert shell.hide_widget() is True and shell.widget_visible() is False
    finally:
        stop.set()
        t.join(5)
