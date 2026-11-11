"""Onboarding screens A2-A10 and the sign-out confirm A14. Wording lives in pace.ui.onboarding; this file only lays it out."""

from __future__ import annotations

import os
from datetime import date

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from pace.ui import config, onboarding  # noqa: E402
from pace.ui.widgets import action_row, box, label, pill, run_async  # noqa: E402

APP_ICON = "preferences-system-time-symbolic"
EXTENSION = "pace@osmosys"


def pill_button(text: str, suggested: bool = True, destructive: bool = False) -> Gtk.Button:
    b = Gtk.Button(label=text, halign=Gtk.Align.CENTER)
    b.add_css_class("pill")
    if suggested:
        b.add_css_class("suggested-action")
    if destructive:
        b.add_css_class("destructive-action")
    return b


TOPBAR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
    '<rect x="14" y="22" width="100" height="84" rx="12" fill="none" stroke="#8a8a8a" stroke-width="8"/>'
    '<rect x="14" y="22" width="100" height="22" rx="10" fill="#8a8a8a"/>'
    '<rect x="26" y="29" width="30" height="8" rx="4" fill="#fafafa"/>'
    '<rect x="78" y="29" width="24" height="8" rx="4" fill="#fafafa"/>'
    "</svg>"
)


def topbar_art() -> Gdk.Texture | None:
    """The top-bar illustration as a real scalable SVG, so it stays sharp at status-page size on any theme."""
    try:
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(TOPBAR_SVG.encode()))
        return Gdk.Texture.new_for_pixbuf(GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, 128, 128, True, None))
    except GLib.Error:
        return None


def page(icon: str, title: str, body: str, *children: Gtk.Widget) -> Adw.StatusPage:
    sp = Adw.StatusPage(icon_name=icon, title=title, description=body, vexpand=True)
    if icon == "view-pin-symbolic" and (art := topbar_art()):
        sp.set_paintable(art)
    if children:
        sp.set_child(box(*children, spacing=12, halign=Gtk.Align.CENTER, margin_top=6))
    return sp


def confirm_sign_out(window, on_confirm) -> None:
    """A14."""
    d = Adw.AlertDialog(
        heading="Sign out of Pace?",
        body="Pace will forget your sign-in on this computer. Your targets stay saved. Numbers disappear until you sign in again.",
    )
    d.add_response("cancel", "Cancel")
    d.add_response("out", "Sign out")
    d.set_response_appearance("out", Adw.ResponseAppearance.DESTRUCTIVE)
    d.set_default_response("cancel")
    d.connect("response", lambda _d, r: on_confirm() if r == "out" else None)
    d.present(window)


class Onboarding(Adw.Bin):
    """One Gtk.Stack of pages. host is the main window: toast(), go_dashboard(), push_targets(on_done)."""

    def __init__(self, services, host, desktop: str | None = None):
        super().__init__()
        self.services, self.host = services, host
        self.desktop = os.environ.get("XDG_CURRENT_DESKTOP", "") if desktop is None else desktop
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hhomogeneous=False, vhomogeneous=False)
        self.set_child(Gtk.ScrolledWindow(child=self.stack, hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.attempt, self.redirect, self.url, self.after = 0, None, None, "summary"
        self.waiting = Adw.StatusPage(icon_name="web-browser-symbolic", title="Finish signing in in your browser…", vexpand=True)
        self.failure_holder = Adw.Bin()
        self.summary_holder = Adw.Bin()
        for name, widget in (
            ("welcome", self._welcome()),
            ("waiting", self._waiting()),
            ("failure", self.failure_holder),
            ("keyring", self._keyring()),
            ("summary", self.summary_holder),
        ):
            self.stack.add_named(widget, name)

    def show(self, name: str) -> None:
        self.stack.set_visible_child_name(name)

    # ---- A2 --------------------------------------------------------------------------------------------------------

    def _welcome(self) -> Adw.StatusPage:
        go = pill_button("Sign in with Microsoft")
        go.connect("clicked", lambda *_: self.begin())
        return page(
            APP_ICON,
            "Know your pace before Friday",
            "Pace reads your billed hours, leave and holidays, and tells you early if the week or month is slipping.",
            go,
            label("Opens your browser · no passwords stored", "caption", "dim-label"),
        )

    def begin(self, after: str = "summary") -> None:
        self.after = after
        if config.load_settings()["token_store"] == "keyring" and not self.services.keyring_available():
            return self.show("keyring")
        self._sign_in()

    # ---- A3 --------------------------------------------------------------------------------------------------------

    def _waiting(self) -> Adw.StatusPage:
        copy, cancel = Gtk.Button(label="Copy link", css_classes=["link"]), Gtk.Button(label="Cancel")
        copy.connect("clicked", self._copy_link)
        cancel.connect("clicked", lambda *_: self._cancel())
        self.waiting.set_child(
            box(
                Adw.Spinner(width_request=32, height_request=32),
                box(
                    label("Didn't open?", "dim-label"),
                    copy,
                    cancel,
                    vertical=False,
                    spacing=12,
                    halign=Gtk.Align.CENTER,
                    valign=Gtk.Align.CENTER,
                ),
                spacing=16,
                halign=Gtk.Align.CENTER,
            )
        )
        return self.waiting

    def _sign_in(self) -> None:
        self.attempt += 1
        n, self.redirect, self.url = self.attempt, None, None
        self.waiting.set_description("Starting the sign-in…")
        self.show("waiting")

        def open_uri(url):
            self.url = url
            GLib.idle_add(self._opened, url, n)

        run_async(lambda: self.services.sign_in(open_uri), lambda _r, error: self._finished(n, error))

    def _opened(self, url: str, n: int) -> None:
        if n != self.attempt:
            return
        port = onboarding.listening_port(url)
        self.redirect = f"http://127.0.0.1:{port}/" if port else None
        self.waiting.set_description(
            f"Pace is waiting on 127.0.0.1:{port}. It gives up after 5 minutes." if port else "It gives up after 5 minutes."
        )
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None)

    def _copy_link(self, *_):
        if self.url:
            self.get_clipboard().set(self.url)
            self.host.toast("Link copied")

    def _cancel(self) -> None:
        self.attempt += 1  # whatever the thread ends with is ignored
        if self.redirect:
            run_async(lambda: self.services.cancel_sign_in(self.redirect), lambda *_: None)
        self.show("welcome")

    def _finished(self, n: int, error) -> None:
        if n != self.attempt:
            return
        if error is None:
            self.services.refresh(lambda _ok: None)
            return self.host.go_dashboard() if self.after == "dashboard" else self.show_summary()
        self.show_failure(onboarding.classify_failure(error))

    # ---- A7 --------------------------------------------------------------------------------------------------------

    def show_failure(self, kind: str) -> None:
        f = onboarding.FAILURES[kind]
        retry = pill_button(f["button"])
        retry.connect("clicked", lambda *_: self.begin(self.after))
        kids = [retry]
        if f["extra"]:
            ask = pill_button(f["extra"], suggested=False)
            ask.connect("clicked", self._copy_it_request)
            kids.append(ask)
        self.failure_holder.set_child(page(f["icon"], f["title"], f["body"], *kids))
        self.show("failure")

    def _copy_it_request(self, *_):
        self.get_clipboard().set(onboarding.it_request())
        self.host.toast("Message copied")

    # ---- A9 --------------------------------------------------------------------------------------------------------

    def _keyring(self) -> Adw.StatusPage:
        file_row, none_row = (
            action_row(
                title="Store in a private file",
                subtitle="~/.local/share/pace, mode 600 — readable only by your user, not encrypted (like rclone.conf)",
            ),
            action_row(
                title="Sign in every login",
                subtitle="Nothing is stored; you sign in each time you log in to the desktop",
            ),
        )
        a, b = Gtk.CheckButton(active=True), Gtk.CheckButton(group=None)
        b.set_group(a)
        for row, check in ((file_row, a), (none_row, b)):
            row.add_prefix(check)
            row.set_activatable_widget(check)
        file_row.add_suffix(pill("recommended here", "green"))
        group = Adw.PreferencesGroup()
        group.add(file_row)
        group.add(none_row)
        later, go = pill_button("Not now", suggested=False), pill_button("Continue")
        later.connect("clicked", lambda *_: self.show("welcome"))

        def proceed(*_):
            s = config.load_settings()
            s["token_store"] = "file" if a.get_active() else "none"
            config.save_settings(s)
            self._sign_in()

        go.connect("clicked", proceed)
        sp = Adw.StatusPage(
            icon_name="system-lock-screen-symbolic",
            title="Pace can't reach a password keyring",
            vexpand=True,
            description="Your desktop has no Secret Service (common on minimal KDE or COSMIC). Pace needs somewhere to keep your sign-in. You choose once.",
        )
        sp.set_child(
            Adw.Clamp(
                maximum_size=520,
                child=box(group, box(later, go, vertical=False, spacing=12, halign=Gtk.Align.CENTER, margin_top=18)),
            )
        )
        return sp

    # ---- A6 --------------------------------------------------------------------------------------------------------

    def show_summary(self) -> None:
        profile = self.services.profile()
        self._draw_summary(onboarding.summary(profile, None, None, date.today().year))
        self.show("summary")
        today = date.today()

        def work():
            rows = self.services.history(date(today.year, 1, 1), date(today.year, 12, 31))
            month = [r for r in rows if r["date"][:7] == today.isoformat()[:7]]
            return (
                sum(1 for r in rows if r["type"] == "holiday"),
                sum({"leave": 1.0, "half_leave": 0.5}.get(r["type"], 0) for r in month),
            )

        def done(result, error):
            if not error and result:
                self._draw_summary(onboarding.summary(profile, result[0], result[1], today.year))

        run_async(work, done)

    def _draw_summary(self, s: dict) -> None:
        group = Adw.PreferencesGroup()
        for title, value in s["rows"]:
            row = action_row(title=title)
            row.add_prefix(
                Gtk.Image(icon_name="object-select-symbolic" if not value or value == "linked" else "x-office-calendar-symbolic")
            )
            if value:
                row.add_suffix(label(value, "dim-label"))
            group.add(row)
        nxt = pill_button("Next: targets →")
        nxt.connect("clicked", lambda *_: self.host.push_targets(self.show_topbar))
        name = s["headline"].removeprefix("Signed in as ") or "?"
        content = box(
            Adw.Avatar(size=96, text=name, show_initials=True, halign=Gtk.Align.CENTER),
            label(s["headline"], "title-1", xalign=0.5, margin_top=18, wrap=True, justify=Gtk.Justification.CENTER),
            label(s["email"], "dim-label", xalign=0.5, margin_bottom=24),
            group,
            box(nxt, margin_top=24, halign=Gtk.Align.CENTER),
        )
        wrap = Adw.Clamp(maximum_size=460, child=content, valign=Gtk.Align.CENTER, margin_start=16, margin_end=16)
        self.summary_holder.set_child(wrap)

    # ---- A10 -------------------------------------------------------------------------------------------------------

    def show_topbar(self) -> None:
        if config.load_ui_state().get("topbar_seen") and self.after != "topbar":
            return self.host.go_dashboard()
        if onboarding.topbar_kind(self.desktop) != "gnome":
            got = pill_button("Got it")
            got.connect("clicked", lambda *_: self._finish_topbar())
            return self._put(
                "topbar",
                page(
                    "object-select-symbolic",
                    "Pace is in your system tray",
                    "Left-click opens the mini widget, right-click the menu.",
                    got,
                ),
            )
        self._topbar_asked = n = getattr(self, "_topbar_asked", 0) + 1
        run_async(
            lambda: self.services.extension_info(EXTENSION),
            lambda info, _error: n == self._topbar_asked and self._topbar_checked(info),
        )

    def _topbar_checked(self, info: dict | None) -> None:
        """A10 on GNOME: ask the shell first. Already running means there is nothing to turn on."""
        if onboarding.extension_active(info):
            if self.after != "topbar":  # in the first-run flow there is no screen to show
                return self._finish_topbar()
            got = pill_button("Done")
            got.connect("clicked", lambda *_: self._finish_topbar())
            return self._put(
                "topbar",
                page("view-pin-symbolic", "Pace is in your top bar", "The panel extension is switched on and running.", got),
            )
        enable, skip = pill_button("Enable"), pill_button("Skip, use the window only", suggested=False)
        enable.connect("clicked", self._enable_extension)
        skip.connect("clicked", lambda *_: self._finish_topbar())
        self._put(
            "topbar",
            page(
                "view-pin-symbolic",
                "Turn on Pace in the top bar",
                "GNOME has no system tray, so Pace ships a small panel extension inside the package. It only needs switching on.",
                enable,
                skip,
            ),
        )

    def _put(self, name: str, widget: Gtk.Widget) -> None:
        old = self.stack.get_child_by_name(name)
        if old:
            self.stack.remove(old)
        self.stack.add_named(widget, name)
        self.show(name)

    def _enable_extension(self, *_):
        """Switch the extension on through the shell, then always go to the dashboard: the toast says how it went."""

        def done(ok, error):
            self._finish_topbar()
            if error or not ok:
                return self.host.toast("Couldn't enable the extension. Try: gnome-extensions enable pace@osmosys")
            self.host.toast(
                "Pace is switched on. If it isn't in the top bar yet, log out and back in.",
                "Log out",
                lambda: GLib.spawn_command_line_async("gnome-session-quit --logout"),
            )

        run_async(lambda: self.services.enable_extension(EXTENSION), done)

    def _finish_topbar(self) -> None:
        config.save_ui_state(topbar_seen=True)
        self.host.go_dashboard()
