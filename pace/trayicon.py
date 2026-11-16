"""Tray ring icon drawn with pycairo (no GTK): verdict-colour ring, progress arc, hours in the middle."""

import math
import sys

import cairo

SIZES = (22, 32, 48, 64)

# Marker palette (contract section 1 colours)
COLOURS = {
    "green": (0x57, 0xE3, 0x89),
    "amber": (0xFF, 0xBE, 0x6F),
    "red": (0xFF, 0x7B, 0x63),
    "blue": (0x78, 0xAE, 0xED),
    "grey": (0x9A, 0x99, 0x96),
}
TRACK_ALPHA = 0.3
DISC = (0x1C / 255, 0x2A / 255, 0x3A / 255)  # the app icon's tile colour


def _rgb(colour: str) -> tuple[float, float, float]:
    r, g, b = COLOURS.get(colour, COLOURS["grey"])
    return r / 255, g / 255, b / 255


def _draw(colour: str, tray: dict, size: int) -> cairo.ImageSurface:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    r, g, b = _rgb(colour)
    thick = max(2.0, size * 0.14)
    radius = (size - thick) / 2 - size * 0.02
    c = size / 2
    # The pastel marker colours are made for a dark panel and wash out on Breeze Light, so the ring sits on a dark disc.
    ctx.set_source_rgb(*DISC)
    ctx.arc(c, c, c, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_line_width(thick)
    ctx.set_source_rgba(r, g, b, TRACK_ALPHA)
    ctx.arc(c, c, radius, 0, 2 * math.pi)
    ctx.stroke()
    fill = max(0.0, min(1.0, float(tray.get("fill") or 0)))
    if fill > 0:
        ctx.set_source_rgba(r, g, b, 1)
        ctx.arc(c, c, radius, -math.pi / 2, -math.pi / 2 + 2 * math.pi * fill)
        ctx.stroke()
    number = str(tray.get("number") or "")
    if number:
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        inner = (radius - thick / 2) * 2 * 0.92
        ctx.set_font_size(size * 0.5)
        ext = ctx.text_extents(number)
        if ext.width > inner:
            ctx.set_font_size(size * 0.5 * inner / ext.width)
            ext = ctx.text_extents(number)
        ctx.set_source_rgba(r, g, b, 1)
        ctx.move_to(c - ext.x_bearing - ext.width / 2, c - ext.y_bearing - ext.height / 2)
        ctx.show_text(number)
    surf.flush()
    return surf


def _to_argb_be(surf: cairo.ImageSurface) -> bytes:
    """cairo ARGB32 is premultiplied native-endian; SNI wants straight A,R,G,B bytes."""
    raw = bytes(surf.get_data())
    out = bytearray(len(raw))
    little = sys.byteorder == "little"
    for i in range(0, len(raw), 4):
        if little:
            bl, gr, re, a = raw[i : i + 4]
        else:
            a, re, gr, bl = raw[i : i + 4]
        if 0 < a < 255:
            re, gr, bl = (min(255, v * 255 // a) for v in (re, gr, bl))
        out[i : i + 4] = bytes((a, re, gr, bl))
    return bytes(out)


def pixmaps(colour: str, tray: dict | None) -> list[tuple[int, int, bytes]]:
    """IconPixmap value: [(w, h, ARGB32 big-endian bytes)] at 22, 32, 48 and 64 px."""
    tray = tray or {}
    return [(s, s, _to_argb_be(_draw(colour, tray, s))) for s in SIZES]


def save_png(path, colour: str, tray: dict | None, size: int = 64) -> None:
    _draw(colour, tray or {}, size).write_to_png(str(path))
