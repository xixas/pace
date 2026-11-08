"""Small GTK helpers shared by the screens. Anything with a decision in it lives in model/period/onboarding/config instead."""

from __future__ import annotations

import threading
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402


def label(text: str = "", *classes: str, xalign: float = 0, wrap: bool = False, **props) -> Gtk.Label:
    lab = Gtk.Label(label=text, xalign=xalign, wrap=wrap, **props)
    for c in classes:
        lab.add_css_class(c)
    return lab


def box(*children, vertical: bool = True, spacing: int = 0, classes: tuple[str, ...] = (), **props) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing, **props)
    for c in classes:
        b.add_css_class(c)
    for child in children:
        b.append(child)
    return b


def pill(text: str, colour: str = "grey") -> Gtk.Label:
    return label(text, "pace-pill", colour, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)


def clear(container: Gtk.Box) -> None:
    while child := container.get_first_child():
        container.remove(child)


def run_async(work: Callable, done: Callable[[object, BaseException | None], None]) -> None:
    """work() on a thread, done(result, error) back on the main loop."""

    def target():
        try:
            result, error = work(), None
        except Exception as e:  # reported to done, never lost
            result, error = None, e
        GLib.idle_add(lambda: done(result, error) and False)

    threading.Thread(target=target, daemon=True).start()


def open_uri(parent: Gtk.Widget | None, uri: str) -> None:
    Gtk.UriLauncher.new(uri).launch(parent.get_root() if parent else None, None, None)
