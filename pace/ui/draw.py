"""Cairo drawing for the week bar (C1 ticks), the day split strip and the month sparkline (C3). Thin: numbers arrive pre-computed.

Colours come from the stylesheet: each area carries `.pace-ink.<colour>` so `get_color()` is the themed verdict colour, and the
parent's colour is the neutral foreground for tracks, grids and labels. Text goes through Pango so it uses the UI font.
"""

from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gtk, Pango, PangoCairo  # noqa: E402

# Adwaita palette for the per-project split (blue, purple, teal, orange): light shade, dark shade.
SERIES = (
    ((0.21, 0.52, 0.89), (0.47, 0.68, 0.95)),
    ((0.57, 0.25, 0.67), (0.75, 0.55, 0.85)),
    ((0.13, 0.55, 0.52), (0.36, 0.78, 0.74)),
    ((0.90, 0.38, 0.0), (1.0, 0.64, 0.30)),
)
INK = ("green", "amber", "red", "blue", "grey")


def series_rgb(index: int) -> tuple[float, float, float]:
    return SERIES[index % len(SERIES)][1 if Adw.StyleManager.get_default().get_dark() else 0]


def _rgba(widget: Gtk.Widget, alpha: float = 1.0):
    c = widget.get_color()
    return c.red, c.green, c.blue, alpha


def _neutral(widget: Gtk.Widget, alpha: float):
    return _rgba(widget.get_parent() or widget, alpha)


def _layout(area: Gtk.Widget, text: str, size_pt: float = 8.5) -> Pango.Layout:
    layout = area.create_pango_layout(text)
    font = area.get_pango_context().get_font_description().copy()
    font.set_size(int(size_pt * Pango.SCALE))
    layout.set_font_description(font)
    layout.set_attributes(Pango.AttrList.from_string("0 -1 font-features 'tnum'"))
    return layout


def _text_width(area: Gtk.Widget, text: str, size_pt: float = 8.5) -> int:
    return _layout(area, text, size_pt).get_pixel_size()[0]


def _text(area: Gtk.Widget, cr, text: str, x: float, y: float, size_pt: float = 8.5, align=0.0) -> int:
    """Draw text with its left (align 0) or right (align 1) edge at x and its top at y. Returns its width."""
    layout = _layout(area, text, size_pt)
    w, _h = layout.get_pixel_size()
    cr.move_to(x - w * align, y)
    PangoCairo.show_layout(cr, layout)
    return w


def _set_ink(widget: Gtk.Widget, colour: str) -> None:
    widget.add_css_class("pace-ink")
    for c in INK:
        widget.remove_css_class(c)
    widget.add_css_class(colour if colour in INK else "grey")


def _round_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class WeekBar(Gtk.DrawingArea):
    """Progress bar with ticks for the pay line, the target and the expected total, each labelled under its own tick."""

    BAR, TOP = 12, 6

    def __init__(self):
        super().__init__(content_height=42, hexpand=True)
        self.bar = None
        self.set_draw_func(self._draw)

    def set_data(self, bar: dict, colour: str):
        self.bar = bar
        _set_ink(self, colour)
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        if not self.bar:
            return
        b, top, bar_h = self.bar, self.TOP, self.BAR
        scale = w / b["max"]
        _round_rect(cr, 0, top, w, bar_h, bar_h / 2)
        cr.set_source_rgba(*_neutral(area, 0.10))
        cr.fill()
        fill = min(max(bar_h, b["logged"] * scale), w)
        _round_rect(cr, 0, top, fill, bar_h, bar_h / 2)
        cr.set_source_rgba(*_rgba(area))
        cr.fill()
        ticks = [(b[k], n) for k, n in (("lop", "pay line"), ("target", "target"), ("expected", "expected")) if b[k]]
        ticks.sort()
        cr.set_line_width(2)
        for minutes, _ in ticks:
            x = round(min(minutes * scale, w - 1))
            cr.set_source_rgba(*_neutral(area, 0.7))
            cr.move_to(x, top - 3)
            cr.line_to(x, top + bar_h + 3)
            cr.stroke()
        # labels are centred under their tick, then pushed apart (and inside the bar) so none overlap; order stays tick order
        cr.set_source_rgba(*_neutral(area, 0.6))
        gap = 10
        labels = [(f"{name} {minutes / 60:g}", min(minutes * scale, w - 1)) for minutes, name in ticks]
        widths = [_text_width(area, t) for t, _ in labels]
        lefts = [x - tw / 2 for (_, x), tw in zip(labels, widths, strict=True)]
        for i in range(len(lefts)):
            lefts[i] = max(lefts[i], 0 if i == 0 else lefts[i - 1] + widths[i - 1] + gap)
        for i in reversed(range(len(lefts))):
            limit = w if i == len(lefts) - 1 else lefts[i + 1] - gap
            lefts[i] = max(0, min(lefts[i], limit - widths[i]))
        for (text, _), left in zip(labels, lefts, strict=True):
            _text(area, cr, text, left, top + bar_h + 7)


class SplitBar(Gtk.DrawingArea):
    """A 4 px strip split by project share, under a day's hours."""

    def __init__(self):
        super().__init__(content_height=4, hexpand=True)
        self.parts: list[tuple[float, int]] = []
        self.set_draw_func(self._draw)

    def set_data(self, parts: list[tuple[float, int]]):
        """parts: (fraction, series index) in display order."""
        self.parts = parts
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        _round_rect(cr, 0, 0, w, h, h / 2)
        cr.clip()
        cr.set_source_rgba(*_neutral(area, 0.08))
        cr.paint()
        x = 0.0
        for frac, index in self.parts:
            cr.rectangle(x, 0, w * frac, h)
            cr.set_source_rgb(*series_rgb(index))
            cr.fill()
            x += w * frac


class Sparkline(Gtk.DrawingArea):
    """Actual cumulative hours (solid) against the expected line (dashed), with hour labels on the left and dates below."""

    LEFT, BOTTOM, TOP_PAD = 36, 18, 6

    def __init__(self):
        super().__init__(content_height=120, hexpand=True)
        self.actual, self.expected, self.top = [], [], 1
        self.ylabels, self.first, self.last = [], "", ""
        self.set_draw_func(self._draw)

    def set_data(self, actual, expected, top, colour, ylabels=(), first="", last=""):
        self.actual, self.expected, self.top = actual, expected, max(top, 1)
        self.ylabels, self.first, self.last = list(ylabels), first, last
        _set_ink(self, colour)
        self.queue_draw()

    def _line(self, cr, values, w, h, n):
        plot_w, plot_h = w - self.LEFT - 2, h - self.BOTTOM - self.TOP_PAD
        for i, v in enumerate(values):
            x = self.LEFT + (0 if n < 2 else i * plot_w / (n - 1))
            y = self.TOP_PAD + plot_h * (1 - v / self.top)
            (cr.line_to if i else cr.move_to)(x, y)

    def _draw(self, area, cr, w, h):
        n = len(self.expected)
        if not n:
            return
        plot_h = h - self.BOTTOM - self.TOP_PAD
        for i, text in enumerate(self.ylabels):
            y = self.TOP_PAD + plot_h * i / max(len(self.ylabels) - 1, 1)
            cr.set_source_rgba(*_neutral(area, 0.10))
            cr.rectangle(self.LEFT, round(y), w - self.LEFT, 1)
            cr.fill()
            cr.set_source_rgba(*_neutral(area, 0.55))
            _text(area, cr, text, self.LEFT - 8, min(max(y - 7, 0), h - self.BOTTOM - 14), align=1.0)
        cr.set_source_rgba(*_neutral(area, 0.55))
        _text(area, cr, self.first, self.LEFT, h - 14)
        _text(area, cr, self.last, w, h - 14, align=1.0)
        cr.set_line_width(1.5)
        cr.set_dash([4, 3])
        cr.set_source_rgba(*_neutral(area, 0.45))
        self._line(cr, self.expected, w, h, n)
        cr.stroke()
        cr.set_dash([])
        cr.set_line_width(2.5)
        cr.set_line_join(1)  # round
        cr.set_source_rgba(*_rgba(area))
        self._line(cr, self.actual, w, h, n)
        cr.stroke()
