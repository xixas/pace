"""B10 mini widget: 230 px, undecorated, draggable by its body, fed by status.json's `widget` key."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from pace.ui.widgets import box, clear, label  # noqa: E402

WIDTH = 230


def widget_view(status: dict) -> dict:
    """What the card shows. Signed out or before the first poll there is no `widget` key."""
    w = status.get("widget")
    if not w:
        return {"title": "Pace", "big": "–", "side": "", "lines": [status.get("text") or "Sign in to see your week"], "project": None, "colour": "grey"}
    return {**w, "colour": status.get("colour") or "grey"}


class MiniWidget(Gtk.ApplicationWindow):
    def __init__(self, app, host):
        super().__init__(application=app, decorated=False, resizable=False, default_width=WIDTH, title="Pace")
        self.host = host
        self.add_css_class("pace-widget")
        self.content = box()
        self.body = box(self.content, classes=("pace-widget-card",), width_request=WIDTH)
        self.set_child(Gtk.WindowHandle(child=self.body))
        items = box()
        menu = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START, child=items)
        for text, fn in (("Open dashboard", host.show_dashboard), ("Close widget", self.close)):
            b = Gtk.Button(label=text, css_classes=["flat"])
            b.connect("clicked", lambda _b, f=fn: (menu.popdown(), f()))
            items.append(b)
        menu.set_parent(self.body)
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, n, x, y: menu.popup())
        self.body.add_controller(right)
        self._menu = menu

    def set_status(self, status: dict) -> None:
        v = widget_view(status)
        clear(self.content)
        dot = Gtk.Box(css_classes=["pace-dot", v["colour"]], valign=Gtk.Align.CENTER)
        self.content.append(box(dot, label(v["title"], "title"), vertical=False, spacing=8))
        self.content.append(self._numbers(v["big"], v["side"]))
        for line in v["lines"]:
            self.content.append(label(line, "caption", "dim-label", wrap=True))
        if p := v.get("project"):
            self.content.append(Gtk.Box(css_classes=["pace-widget-sep"]))
            self.content.append(label(p["title"], "title"))
            self.content.append(self._numbers(p["big"], p["side"]))

    @staticmethod
    def _numbers(big: str, side: str) -> Gtk.Box:
        return box(label(big, "big", hexpand=True), label(side, "caption", "dim-label", valign=Gtk.Align.END, margin_bottom=4), vertical=False, spacing=8)
