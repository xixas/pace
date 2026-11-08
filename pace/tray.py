"""StatusNotifierItem tray icon with a hand-written com.canonical.dbusmenu (no GTK).

Used by paced on desktops without the GNOME panel extension (KDE, COSMIC, XFCE, Cinnamon).
"""

import os
from collections.abc import Callable

from gi.repository import Gio, GLib

from pace import trayicon

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="Activate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="Scroll"><arg type="i" name="delta" direction="in"/><arg type="s" name="orientation" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg type="s" name="status"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated"><arg type="u" name="revision"/><arg type="i" name="parent"/></signal>
    <signal name="ItemActivationRequested"><arg type="i" name="id"/><arg type="u" name="timestamp"/></signal>
  </interface>
</node>
"""

# Fixed ids so a menu rebuild never renumbers the actions; info rows take 1..INFO_MAX.
INFO_MAX = 9
SEPARATOR_ID = 50
ACTION_IDS = {"dashboard": 51, "pinestem": 52, "widget": 53, "snooze": 54, "refresh": 55, "quit": 56}
SNOOZE_LABEL = "Snooze nudges today"
UNSNOOZE_LABEL = "Nudges snoozed until midnight · Undo"


def _props(label: str, enabled: bool = True) -> dict:
    return {"label": label, "enabled": enabled, "visible": True}


def menu_items(status: dict | None) -> list[dict]:
    """Flat menu: [{"id", "props", "action"?}], info rows first, then the actions."""
    status = status or {}
    tray = status.get("tray") or {}
    items = [{"id": n, "props": _props(row, False)} for n, row in enumerate(tray.get("info_rows") or [], 1) if n <= INFO_MAX]
    if items:
        items.append({"id": SEPARATOR_ID, "props": {"type": "separator", "enabled": True, "visible": True}})
    snoozed = bool(status.get("snoozed_until"))
    rows = [
        ("dashboard", "Open dashboard"),
        ("pinestem", "Open PineStem"),
        ("widget", "Show mini widget"),
        ("unsnooze" if snoozed else "snooze", UNSNOOZE_LABEL if snoozed else SNOOZE_LABEL),
        ("refresh", "Refresh"),
        ("quit", "Quit"),
    ]
    for action, label in rows:
        items.append({"id": ACTION_IDS["snooze" if action == "unsnooze" else action], "props": _props(label), "action": action})
    return items


def _variants(props: dict, names=None) -> dict:
    sig = {bool: "b", str: "s"}
    out = {k: GLib.Variant(sig[type(v)], v) for k, v in props.items()}
    return {k: v for k, v in out.items() if not names or k in names}


def layout(status: dict | None, revision: int):
    """GetLayout result: (revision, (0, root props, [child variants]))."""
    children = [GLib.Variant("(ia{sv}av)", (i["id"], _variants(i["props"]), [])) for i in menu_items(status)]
    return revision, (0, {"children-display": GLib.Variant("s", "submenu")}, children)


class Tray:
    def __init__(self, bus: Gio.DBusConnection, on_action: Callable[[str], None]):
        self._bus = bus
        self._on_action = on_action
        self._status: dict = {}
        self._revision = 1
        self._regs: list[int] = []
        self._pixmaps = trayicon.pixmaps("grey", None)
        self._name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._watch_id = 0
        self._sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        self._menu_node = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
        self._regs.append(bus.register_object(ITEM_PATH, self._sni_node.interfaces[0], self._sni_call, self._sni_get, None))
        self._regs.append(bus.register_object(MENU_PATH, self._menu_node.interfaces[0], self._menu_call, self._menu_get, None))
        bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
            GLib.Variant("(su)", (self._name, 4)), None, Gio.DBusCallFlags.NONE, -1, None,
        )  # fmt: skip
        self._watch_id = Gio.bus_watch_name_on_connection(
            bus, WATCHER, Gio.BusNameWatcherFlags.NONE, self._watcher_appeared, None
        )

    # registration -------------------------------------------------------
    def _watcher_appeared(self, conn, name, owner):
        # Fires at start and again whenever the watcher restarts.
        conn.call(
            WATCHER, WATCHER_PATH, WATCHER, "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self._name,)), None, Gio.DBusCallFlags.NONE, -1, None, self._registered, None,
        )  # fmt: skip

    @staticmethod
    def _registered(conn, result, _data):
        try:
            conn.call_finish(result)
        except GLib.Error:
            pass  # watcher went away mid-call; the watch re-registers when it returns

    # SNI ------------------------------------------------------------------
    def _tray(self) -> dict:
        return self._status.get("tray") or {}

    def _tooltip(self):
        t = self._tray()
        return ("", [], t.get("tooltip_title") or "Pace", "\n".join(t.get("tooltip_lines") or []))

    def _sni_get(self, conn, sender, path, iface, name):
        values = {
            "Category": ("s", "ApplicationStatus"),
            "Id": ("s", "pace"),
            "Title": ("s", "Pace"),
            "Status": ("s", "Active"),
            "WindowId": ("u", 0),
            "IconName": ("s", ""),
            "IconPixmap": ("a(iiay)", self._pixmaps),
            "OverlayIconName": ("s", ""),
            "OverlayIconPixmap": ("a(iiay)", []),
            "AttentionIconName": ("s", ""),
            "AttentionIconPixmap": ("a(iiay)", []),
            "AttentionMovieName": ("s", ""),
            "ToolTip": ("(sa(iiay)ss)", self._tooltip()),
            "ItemIsMenu": ("b", False),
            "Menu": ("o", MENU_PATH),
        }
        sig, value = values[name]
        return GLib.Variant(sig, value)

    def _sni_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "Activate":
            self._on_action("widget")
        invocation.return_value(None)  # ContextMenu/SecondaryActivate/Scroll: the host shows the dbusmenu itself

    # dbusmenu ---------------------------------------------------------------
    def _menu_get(self, conn, sender, path, iface, name):
        return {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }[name]

    def _item(self, item_id: int):
        return next((i for i in menu_items(self._status) if i["id"] == item_id), None)

    def _event(self, item_id: int, event: str) -> bool:
        item = self._item(item_id)
        if item is None:
            return False
        if event == "clicked" and item.get("action"):
            self._on_action(item["action"])
        return True

    def _menu_call(self, conn, sender, path, iface, method, params, invocation):
        args = params.unpack()
        if method == "GetLayout":
            rev, lay = layout(self._status, self._revision)
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (rev, lay)))
        elif method == "GetGroupProperties":
            ids, names = args
            items = [i for i in menu_items(self._status) if not ids or i["id"] in ids]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", ([(i["id"], _variants(i["props"], names)) for i in items],)))
        elif method == "GetProperty":
            item = self._item(args[0])
            props = _variants(item["props"]) if item else {}
            if args[1] not in props:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", "no such property")
            else:
                invocation.return_value(GLib.Variant("(v)", (props[args[1]],)))
        elif method == "Event":
            self._event(args[0], args[1])
            invocation.return_value(None)
        elif method == "EventGroup":
            errors = [i for i, ev, _d, _t in args[0] if not self._event(i, ev)]
            invocation.return_value(GLib.Variant("(ai)", (errors,)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

    # public ----------------------------------------------------------------
    def _emit(self, path: str, iface: str, signal: str, params):
        self._bus.emit_signal(None, path, iface, signal, params)

    def update(self, status: dict) -> None:
        self._status = status or {}
        self._pixmaps = trayicon.pixmaps(self._status.get("colour") or "grey", self._tray())
        self._revision += 1
        sni = "org.kde.StatusNotifierItem"
        self._emit(ITEM_PATH, sni, "NewIcon", None)
        self._emit(ITEM_PATH, sni, "NewToolTip", None)
        self._emit(MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self._revision, 0)))

    def close(self) -> None:
        if self._watch_id:
            Gio.bus_unwatch_name(self._watch_id)
            self._watch_id = 0
        for reg in self._regs:
            self._bus.unregister_object(reg)
        self._regs = []
        try:
            self._bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ReleaseName",
                GLib.Variant("(s)", (self._name,)), None, Gio.DBusCallFlags.NONE, -1, None,
            )  # fmt: skip
        except GLib.Error:
            pass
