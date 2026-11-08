"""B10 mini widget: 240 px, undecorated, draggable by its body, fed by status.json's `widget` key."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from pace.ui.model import widget_view  # noqa: E402
from pace.ui.widgets import box, clear, label  # noqa: E402

WIDTH = 240


class MiniWidget(Gtk.ApplicationWindow):
    def __init__(self, app, host):
        super().__init__(application=app, decorated=False, resizable=False, default_width=WIDTH, title="Pace")
        self.host = host
        self.add_css_class("pace-widget")
        self.content = box(spacing=4)
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
            self.content.append(label(line, "caption", "dim-label", wrap=True, margin_top=2))
        if p := v.get("project"):
            self.content.append(Gtk.Box(css_classes=["pace-widget-sep"]))
            self.content.append(label(p["title"], "title"))
            self.content.append(self._numbers(p["big"], p["side"]))

    @staticmethod
    def _numbers(big: str, side: str) -> Gtk.Box:
        return box(
            label(big, "big", hexpand=True),
            label(side, "caption", "dim-label", valign=Gtk.Align.BASELINE_FILL),
            vertical=False,
            spacing=10,
            margin_top=4,
            baseline_position=Gtk.BaselinePosition.BOTTOM,
        )
