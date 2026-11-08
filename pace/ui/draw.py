"""Cairo drawing for the week bar (C1 ticks) and the month sparkline (C3). Thin: all numbers arrive pre-computed."""

from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

COLOURS = {  # Adwaita palette: light shade, dark shade
    "green": ((0.15, 0.64, 0.41), (0.34, 0.89, 0.54)),
    "amber": ((0.77, 0.50, 0.0), (0.97, 0.78, 0.17)),
    "red": ((0.75, 0.11, 0.16), (1.0, 0.48, 0.39)),
    "blue": ((0.21, 0.52, 0.89), (0.47, 0.68, 0.95)),
    "grey": ((0.60, 0.60, 0.58), (0.60, 0.60, 0.58)),
}


def rgb(name: str) -> tuple[float, float, float]:
    return COLOURS.get(name, COLOURS["grey"])[1 if Adw.StyleManager.get_default().get_dark() else 0]


def _fg(widget: Gtk.Widget, alpha: float):
    c = widget.get_color()
    return c.red, c.green, c.blue, alpha


def _round_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class WeekBar(Gtk.DrawingArea):
    """Progress bar with ticks for the pay line, the target and the expected total, labelled underneath."""

    def __init__(self):
        super().__init__(content_height=54, hexpand=True)
        self.bar, self.colour = None, "grey"
        self.set_draw_func(self._draw)

    def set_data(self, bar: dict, colour: str):
        self.bar, self.colour = bar, colour
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        if not self.bar:
            return
        b, top, bar_h = self.bar, 4, 14
        scale = (w - 2) / b["max"]
        _round_rect(cr, 0, top, w, bar_h, 7)
        cr.set_source_rgba(*_fg(area, 0.12))
        cr.fill()
        fill = max(bar_h, b["logged"] * scale)
        _round_rect(cr, 0, top, min(fill, w), bar_h, 7)
        cr.set_source_rgb(*rgb(self.colour))
        cr.fill()
        cr.select_font_face("sans-serif")
        cr.set_font_size(11)
        for key in ("lop", "target", "expected"):
            minutes = b[key]
            if not minutes:
                continue
            x = min(minutes * scale, w - 1)
            cr.set_source_rgba(*_fg(area, 0.75))
            cr.set_line_width(2)
            cr.move_to(x, top - 3)
            cr.line_to(x, top + bar_h + 3)
            cr.stroke()
        # labels: one line, right-aligned to each tick would collide, so list them in tick order under the bar
        label = " · ".join(
            f"{n} {b[k] / 60:g}" for k, n in (("lop", "pay line"), ("target", "target"), ("expected", "expected")) if b[k]
        )
        cr.set_source_rgba(*_fg(area, 0.6))
        cr.move_to(0, top + bar_h + 20)
        cr.show_text(f"Ticks: {label}")


class Sparkline(Gtk.DrawingArea):
    """Actual cumulative hours (solid) against the expected line (dashed), with hour labels on the left and dates below."""

    LEFT, BOTTOM = 34, 16

    def __init__(self):
        super().__init__(content_height=104, hexpand=True)
        self.actual, self.expected, self.top, self.colour = [], [], 1, "amber"
        self.ylabels, self.first, self.last = [], "", ""
        self.set_draw_func(self._draw)

    def set_data(self, actual, expected, top, colour, ylabels=(), first="", last=""):
        self.actual, self.expected, self.top, self.colour = actual, expected, max(top, 1), colour
        self.ylabels, self.first, self.last = list(ylabels), first, last
        self.queue_draw()

    def _line(self, cr, values, w, h, n):
        plot_w, plot_h = w - self.LEFT - 2, h - self.BOTTOM - 6
        for i, v in enumerate(values):
            x = self.LEFT + (0 if n < 2 else i * plot_w / (n - 1))
            y = 3 + plot_h * (1 - v / self.top)
            (cr.line_to if i else cr.move_to)(x, y)

    def _draw(self, area, cr, w, h):
        n = len(self.expected)
        if not n:
            return
        plot_h = h - self.BOTTOM - 6
        cr.select_font_face("sans-serif")
        cr.set_font_size(10)
        for i, text in enumerate(self.ylabels):
            y = 3 + plot_h * i / max(len(self.ylabels) - 1, 1)
            cr.set_source_rgba(*_fg(area, 0.10))
            cr.rectangle(self.LEFT, y, w - self.LEFT, 1)
            cr.fill()
            cr.set_source_rgba(*_fg(area, 0.6))
            cr.move_to(0, y + 3)
            cr.show_text(text)
        cr.set_source_rgba(*_fg(area, 0.6))
        cr.move_to(self.LEFT, h - 2)
        cr.show_text(self.first)
        cr.move_to(w - cr.text_extents(self.last).x_advance, h - 2)
        cr.show_text(self.last)
        cr.set_line_width(1.5)
        cr.set_dash([4, 3])
        cr.set_source_rgba(*_fg(area, 0.55))
        self._line(cr, self.expected, w, h, n)
        cr.stroke()
        cr.set_dash([])
        cr.set_line_width(2.5)
        cr.set_source_rgb(*rgb(self.colour))
        self._line(cr, self.actual, w, h, n)
        cr.stroke()
