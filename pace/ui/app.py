"""The one Adw.Application (io.github.xixas.Pace.App): `pace` opens the dashboard (or onboarding), `pace widget` the B10 mini
widget, `pace settings` the C7 preferences. A second `pace ...` forwards to the running instance."""

from __future__ import annotations

from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from pace import shell  # noqa: E402
from pace.files import state_dir  # noqa: E402
from pace.ui import onboarding  # noqa: E402
from pace.ui.dashboard import Dashboard  # noqa: E402
from pace.ui.miniwidget import MiniWidget  # noqa: E402
from pace.ui.prefs_ui import Preferences  # noqa: E402
from pace.ui.screens import Onboarding, ask_topbar, confirm_sign_out  # noqa: E402
from pace.ui.services import Services  # noqa: E402
from pace.ui.style import CSS  # noqa: E402
from pace.ui.targets_ui import TargetsPage, share_dialog  # noqa: E402

APP_ID = "io.github.xixas.Pace.App"
ABOUT_COMMENTS = (
    "Pace tells you early if your week or month is slipping: your billed hours against the weekly target, "
    "the loss-of-pay line and your project targets.\n\n"
    "Data: billed hours come from PineStem through hrms-api; leave and holidays from the DhiHRMS calendar. "
    "Nothing leaves your computer except those requests.\n\n"
    "Loss-of-pay rule: each 9 h of a day counts as a day, and a 5 h leftover counts as one more. "
    "You can change both numbers in Preferences."
)
# tall enough for the longest week view (a pay-risk week with its warning body is about 725 plus margins and header), so no card is cut at the bottom
SIZES = {"onboarding": (460, 640), "dashboard": (820, 840)}


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: PaceApp):
        super().__init__(application=app, title="Pace", default_width=460, default_height=640)
        self.app, self.services = app, app.services
        self._status: dict = {}
        self.toasts = Adw.ToastOverlay()
        self.nav = Adw.NavigationView()
        self.toasts.set_child(self.nav)
        self.set_content(self.toasts)
        self.stack = Gtk.Stack()
        self.onboarding = Onboarding(self.services, self, app.desktop)
        header = Adw.HeaderBar(show_title=False, css_classes=["flat"])
        tv = Adw.ToolbarView(content=self.onboarding)
        tv.add_top_bar(header)
        self.dashboard = Dashboard(self.services, self, app.now)
        self.stack.add_named(tv, "onboarding")
        self.stack.add_named(self.dashboard, "dashboard")
        self.nav.add(Adw.NavigationPage(title="Pace", tag="main", child=self.stack))
        for name, fn in (
            ("prefs", self.show_preferences),
            ("share", self.show_share),
            ("targets", self.show_targets),
            ("topbar", self.show_topbar),
            ("widget", app.toggle_widget),
            ("signout", self.confirm_sign_out),
            ("about", self.show_about),
        ):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_, f=fn: f())
            self.add_action(act)
        self.refresh()

    def _page(self, name: str) -> None:
        """Switch between onboarding and dashboard, with a window size that suits each."""
        self.stack.set_visible_child_name(name)
        self.set_default_size(*SIZES[name])

    # ---- state -----------------------------------------------------------------------------------------------------

    def status(self) -> dict:
        return self._status

    def refresh(self) -> None:
        self._status = self.services.status()
        if self.services.signed_in():
            self.dashboard.set_status(self._status)
            if self.stack.get_visible_child_name() != "dashboard":
                self.go_dashboard()
        elif self.stack.get_visible_child_name() != "onboarding":
            self.onboarding.show("welcome")
            self._page("onboarding")
        elif self.onboarding.stack.get_visible_child_name() is None:
            self.onboarding.show("welcome")

    def set_status(self, status: dict) -> None:
        self._status = status
        if self.stack.get_visible_child_name() == "dashboard":
            self.dashboard.set_status(status)

    def go_dashboard(self) -> None:
        self._status = self.services.status()
        self.dashboard.set_status(self._status)
        self.nav.pop_to_tag("main")
        self._page("dashboard")

    def show_dashboard(self) -> None:
        self.present()

    # ---- helpers the screens call ------------------------------------------------------------------------------------

    def toast(self, text: str, button: str | None = None, on_button=None) -> None:
        t = Adw.Toast(title=text, timeout=5)
        if button:
            t.set_button_label(button)
            t.connect("button-clicked", lambda *_: on_button())
        self.toasts.add_toast(t)

    def alert(self, heading: str, body: str) -> None:
        d = Adw.AlertDialog(heading=heading, body=body)
        d.add_response("ok", "OK")
        d.present(self)

    def build_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        top = Gio.Menu()
        top.append("Your targets", "win.targets")
        top.append("Share targets…", "win.share")
        top.append("Mini widget", "win.widget")
        if onboarding.topbar_kind(self.onboarding.desktop) == "gnome":  # elsewhere Pace is a tray icon
            top.append("Show Pace in the top bar", "win.topbar")
        menu.append_section(None, top)
        bottom = Gio.Menu()
        bottom.append("Preferences", "win.prefs")
        bottom.append("Sign out", "win.signout")
        bottom.append("About Pace", "win.about")
        menu.append_section(None, bottom)
        return menu

    def push_targets(self, on_done) -> None:
        self.nav.push(TargetsPage(self, on_done))

    def show_targets(self) -> None:
        self.push_targets(lambda: self.nav.pop())

    def show_share(self) -> None:
        share_dialog(self, (self.services.profile() or {}).get("name") or "Me")

    def show_preferences(self) -> None:
        self.prefs = Preferences(self, self.services)
        self.prefs.present(self)

    def show_topbar(self) -> None:
        ask_topbar(self, self.services)

    def show_about(self) -> None:
        from pace.ui.services import version

        about = Adw.AboutDialog(
            application_name="Pace",
            application_icon="preferences-system-time-symbolic",
            version=version(),
            developer_name="Vikas Kyatannawar",
            developers=["Vikas Kyatannawar"],
            website="https://github.com/xixas/pace",
            issue_url="https://github.com/xixas/pace/issues",
            comments=ABOUT_COMMENTS,
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self)

    def confirm_sign_out(self) -> None:
        confirm_sign_out(self, self._sign_out)

    def _sign_out(self) -> None:
        try:
            self.services.sign_out()
        except Exception as e:
            return self.toast(f"Couldn't sign out: {e}")
        self.onboarding.show("welcome")
        self._page("onboarding")

    def after_data_removed(self) -> None:
        self._status = {}
        self.onboarding.show("welcome")
        self._page("onboarding")
        self.toast("Your Pace data is gone")

    def sign_in_again(self) -> None:
        self.onboarding.begin("dashboard")
        self._page("onboarding")

    def skew_action(self) -> None:
        if self.dashboard.status.get("version", 0) > 1:
            self.app.quit()
        else:
            GLib.spawn_command_line_async("gnome-session-quit --logout")


class PaceApp(Adw.Application):
    def __init__(self, services=None, now=datetime.now, desktop: str | None = None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.services, self.now, self.desktop = services or Services(), now, desktop
        self.window: MainWindow | None = None
        self.mini: MiniWidget | None = None
        self._monitor = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        watched = Gio.File.new_for_path(str(state_dir()))
        try:
            state_dir().mkdir(parents=True, exist_ok=True)
            self._monitor = watched.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect("changed", self._on_state_changed)
        except GLib.Error:
            self._monitor = None

    def do_command_line(self, cmdline):
        self.open_view(cmdline.get_arguments()[1:])
        return 0

    def do_activate(self):
        self.open_view([])

    def open_view(self, args: list[str]) -> None:
        if args == ["widget"]:
            self.show_widget()
        else:
            self.main().present()
            if args == ["settings"]:
                self.window.show_preferences()

    def main(self) -> MainWindow:
        if self.window is None:
            self.window = MainWindow(self)
            self.window.connect("close-request", self._main_closed)
        return self.window

    def _main_closed(self, *_):
        self.window = None
        return False

    def show_widget(self) -> None:
        """On GNOME the shell extension draws the widget (above windows, on every workspace); else the GTK card."""
        if shell.show_widget():
            if self.mini:  # opened while the extension was not on the bus yet (login race, lock screen)
                self.mini.close()
            return
        if self.mini is None:
            self.mini = MiniWidget(self, self)
            self.mini.connect("close-request", self._mini_closed)
            self.mini.set_status(self.services.status())
        self.mini.present()

    def toggle_widget(self) -> None:
        visible = shell.widget_visible()
        if visible is None and self.mini:
            self.mini.close()
        elif visible is None:
            self.show_widget()
        elif visible:
            shell.hide_widget()
        else:
            shell.show_widget()

    def show_dashboard(self) -> None:
        self.main().present()

    def _mini_closed(self, *_):
        self.mini = None
        return False

    def _on_state_changed(self, _mon, file, _other, _event):
        if file.get_basename() != "status.json":
            return
        status = self.services.status()
        if self.window:
            self.window.set_status(status)
        if self.mini:
            self.mini.set_status(status)


def run(argv: list[str]) -> int:
    return PaceApp().run(["pace", *argv])
