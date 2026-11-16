"""B10 mini widget: 240 px, undecorated, draggable by its body, fed by status.json's `widget` key."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Pango  # noqa: E402

from pace import settings  # noqa: E402
from pace.ui import config  # noqa: E402
from pace.ui.model import widget_view  # noqa: E402
from pace.ui.widgets import box, clear, label  # noqa: E402

WIDTH = 240
TITLE = "Pace mini widget"


class MiniWidget(Gtk.ApplicationWindow):
    def __init__(self, app, host):
        super().__init__(application=app, decorated=False, resizable=False, default_width=WIDTH + 20, title=TITLE)
        self.host = host
        self.add_css_class("pace-widget")
        self.content = box()
        self.body = box(
            self.content,
            classes=("pace-widget-card",),
            width_request=WIDTH,
            margin_top=14,
            margin_bottom=14,
            margin_start=14,
            margin_end=14,
        )
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
        v = widget_view(status, settings.rules_from(config.load_settings()))
        clear(self.content)
        self.content.append(self._section(v["week"]))
        if v["project"]:
            self.content.append(Gtk.Box(css_classes=["pace-widget-sep"]))
            self.content.append(self._section(v["project"]))

    @staticmethod
    def _section(s: dict) -> Gtk.Box:
        """Label and state word, the big numbers, a thin bar, then the dim caption lines. s is one section of widget_view."""
        parts = [
            box(
                label(s["label"], "pace-w-label", hexpand=True, ellipsize=Pango.EllipsizeMode.END),
                label(s["word"], "pace-w-word", s["colour"], margin_start=8),
                vertical=False,
            )
        ]
        if s["big"]:
            parts.append(
                box(
                    label(s["big"], "big"),
                    label(s["unit"], "pace-w-unit", valign=Gtk.Align.BASELINE_FILL),
                    vertical=False,
                    spacing=4,
                    margin_top=6,
                    baseline_position=Gtk.BaselinePosition.BOTTOM,
                )
            )
        if s["fill"] is not None:
            bar = Gtk.ProgressBar(fraction=s["fill"], css_classes=["pace-w-bar", s["colour"]], margin_top=8)
            parts.append(bar)
        parts += [
            label(line, "caption", "dim-label", wrap=True, margin_top=6 if i == 0 else 0) for i, line in enumerate(s["lines"])
        ]
        return box(*parts)
