"""C7 Preferences (AdwPreferencesDialog) and C11 Remove my Pace data. Every change is written to settings.json at once."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from pace.ui import config  # noqa: E402
from pace.ui.services import RELEASES_URL, version  # noqa: E402
from pace.ui.widgets import box, label, open_uri  # noqa: E402

NUDGES = (
    ("friday", "Friday check", "Hours left to reach the target"),
    ("daily", "Daily summary", "Skipped on leave days and holidays"),
    ("pay_risk", "Pay risk", "When the loss-of-pay line gets out of reach"),
    ("project_behind", "Project behind", "Monthly project targets, once a day"),
    ("zero_hour", "Zero-hour day", "A working day with nothing billed"),
    ("monday", "Monday summary", "How last week ended, after Friday closes at 12:00"),
)
PANEL_TEXT = (
    ("hours", "30.1 / 42.5 h"),
    ("percent", "71%"),
    ("gap", "−6.5 h TWE"),
    ("left_today", "4.5 h left today"),
    ("icon", "Icon only"),
)
REFRESH = (5, 10, 15, 30, 60)


def _time_button(settings: dict, key: str, save) -> Gtk.MenuButton:
    """The time button opens a small picker (hours, minutes)."""
    hh, mm = config.split_time(settings["notify"][key]["at"])
    h = Gtk.SpinButton(
        adjustment=Gtk.Adjustment(value=hh, lower=0, upper=23, step_increment=1),
        width_chars=2,
        orientation=Gtk.Orientation.VERTICAL,
        wrap=True,
    )
    m = Gtk.SpinButton(
        adjustment=Gtk.Adjustment(value=mm, lower=0, upper=59, step_increment=5),
        width_chars=2,
        orientation=Gtk.Orientation.VERTICAL,
        wrap=True,
    )
    for spin in (h, m):
        spin.connect("output", lambda s: s.set_text(f"{int(s.get_value()):02d}") or True)
    btn = Gtk.MenuButton(label=settings["notify"][key]["at"], valign=Gtk.Align.CENTER, css_classes=["flat"])
    btn.set_popover(
        Gtk.Popover(
            child=box(
                h,
                label(":", "title-3"),
                m,
                vertical=False,
                spacing=6,
                margin_top=8,
                margin_bottom=8,
                margin_start=8,
                margin_end=8,
            )
        )
    )

    def changed(*_):
        text = config.format_time(int(h.get_value()), int(m.get_value()))
        btn.set_label(text)
        save(key, text)

    h.connect("value-changed", changed)
    m.connect("value-changed", changed)
    return btn


class Preferences(Adw.PreferencesDialog):
    def __init__(self, window, services):
        super().__init__(title="Preferences", search_enabled=True)
        self.window, self.services = window, services
        self.settings = config.load_settings()
        self.add(self._page())

    def _save(self) -> None:
        config.save_settings(self.settings)
        config.apply_autostart(self.settings)

    def _page(self) -> Adw.PreferencesPage:
        page, s = Adw.PreferencesPage(), self.settings
        notify = Adw.PreferencesGroup(title="Notify me when")
        for key, title, sub in NUDGES:
            row = Adw.SwitchRow(title=title, subtitle=sub, active=s["notify"][key]["on"])
            row.connect("notify::active", lambda r, k=key: self._set_nudge(k, r.get_active()))
            row.add_suffix(_time_button(s, key, self._set_time))
            notify.add(row)
        expired = Adw.ActionRow(title="Session expired", subtitle="Cannot be turned off")
        expired.add_suffix(Gtk.Image(icon_name="changes-prevent-symbolic"))
        notify.add(expired)
        page.add(notify)

        display = Adw.PreferencesGroup(title="Display")
        labels = self.window.status().get("labels") or {}
        texts = [(key, labels.get(key) or example) for key, example in PANEL_TEXT]
        panel = Adw.ComboRow(
            title="Panel text",
            model=Gtk.StringList.new([t for _, t in texts]),
            selected=[k for k, _ in texts].index(s["panel_text"]),
        )
        panel.connect("notify::selected", lambda r, *_: self._set("panel_text", texts[r.get_selected()][0]))
        widget = Adw.SwitchRow(title="Show mini widget at login", active=s["widget_at_login"])
        widget.connect("notify::active", lambda r, *_: self._set("widget_at_login", r.get_active()))
        refresh = Adw.ComboRow(
            title="Refresh every",
            model=Gtk.StringList.new([f"{m} min" for m in REFRESH]),
            selected=REFRESH.index(s["refresh_minutes"]) if s["refresh_minutes"] in REFRESH else 2,
        )
        refresh.connect("notify::selected", lambda r, *_: self._set("refresh_minutes", REFRESH[r.get_selected()]))
        for r in (panel, widget, refresh):
            display.add(r)
        page.add(display)

        startup = Adw.PreferencesGroup(title="Startup")
        login = Adw.SwitchRow(title="Start Pace at login", subtitle="Adds an autostart entry", active=s["start_at_login"])
        login.connect("notify::active", lambda r, *_: self._set("start_at_login", r.get_active()))
        startup.add(login)
        page.add(startup)

        account = Adw.PreferencesGroup(title="Account")
        profile = self.services.profile() or {}
        who = Adw.ActionRow(title=f"Signed in as {profile.get('name') or 'you'}", subtitle=profile.get("email") or "")
        out = Gtk.Button(label="Sign out", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
        out.connect("clicked", lambda *_: (self.close(), self.window.confirm_sign_out()))
        who.add_suffix(out)
        account.add(who)
        page.add(account)

        about = Adw.PreferencesGroup(title="About")
        about.add(Adw.ActionRow(title="Version", subtitle=version()))
        upd = Adw.ActionRow(title="Updates", subtitle="Updates: install the newer package file you were sent")
        dl = Gtk.Button(label="Download", valign=Gtk.Align.CENTER)
        dl.connect("clicked", lambda *_: open_uri(self.window, RELEASES_URL))
        upd.add_suffix(dl)
        about.add(upd)
        page.add(about)

        data = Adw.PreferencesGroup(title="Data")
        rm = Adw.ActionRow(
            title="Remove my Pace data",
            subtitle="Deletes the keyring entry, status.json, ~/.config/pace and the autostart entry. Cannot be undone.",
        )
        btn = Gtk.Button(label="Remove…", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
        btn.connect("clicked", lambda *_: self._confirm_remove())
        rm.add_suffix(btn)
        data.add(rm)
        page.add(data)
        return page

    def _set(self, key: str, value) -> None:
        self.settings[key] = value
        self._save()

    def _set_nudge(self, key: str, on: bool) -> None:
        self.settings["notify"][key]["on"] = on
        self._save()

    def _set_time(self, key: str, text: str) -> None:
        self.settings["notify"][key]["at"] = text
        self._save()

    def _confirm_remove(self) -> None:
        d = Adw.AlertDialog(
            heading="Remove my Pace data?",
            body="This signs you out and deletes the keyring entry, status.json, ~/.config/pace and the autostart entries. Targets and settings go too. It cannot be undone.",
        )
        d.add_response("cancel", "Cancel")
        d.add_response("remove", "Remove")
        d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel")
        d.connect("response", lambda _d, r: self._remove() if r == "remove" else None)
        d.present(self)

    def _remove(self) -> None:
        config.remove_my_data(self.services.sign_out)
        self.close()
        self.window.after_data_removed()
