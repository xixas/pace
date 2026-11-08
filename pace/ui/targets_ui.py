"""A11 targets editor, A12 import preset and C8 share targets (export). Rules and file formats live in pace.ui.config."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from pace.ui import config  # noqa: E402
from pace.ui.widgets import box, label  # noqa: E402


def _tag(text: str) -> Gtk.Label:
    return label(text, "pace-tag", valign=Gtk.Align.CENTER)


def _spin(value: float, low: float, high: float, step: float, on_change) -> Gtk.SpinButton:
    spin = Gtk.SpinButton(
        adjustment=Gtk.Adjustment(value=value, lower=low, upper=high, step_increment=step),
        digits=1,
        valign=Gtk.Align.CENTER,
        width_chars=5,
    )
    spin.connect("value-changed", lambda s: on_change(s.get_value()))
    return spin


def project_rows(window_status: dict, targets: dict) -> list[dict]:
    """Targets file rows first, then projects the month view already knows about (shown as "no target · tracked")."""
    rows = list(targets["projects"])
    known = {p["code"] for p in rows}
    for p in (window_status.get("month") or {}).get("projects", []):
        if p["code"] not in known:
            rows.append({"code": p["code"], "name": p["name"], "monthly_h": None, "prorate": False, "source": "personal"})
    return rows


class TargetsPage(Adw.NavigationPage):
    """A11. on_done runs when Done is pressed (the onboarding flow continues to A10, the menu entry just goes back)."""

    def __init__(self, window, on_done):
        super().__init__(title="Your targets", tag="targets")
        self.window, self.on_done = window, on_done
        self.holder = Adw.Bin()
        tv = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=self.holder, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        tv.add_top_bar(Adw.HeaderBar())
        imp = Gtk.Button(label="Import lead's preset…", css_classes=["pill"])
        done = Gtk.Button(label="Done", css_classes=["pill", "suggested-action"])
        imp.connect("clicked", lambda *_: import_preset(window, self.rebuild))
        done.connect("clicked", lambda *_: self.on_done())
        tv.add_bottom_bar(
            box(
                imp,
                Gtk.Box(hexpand=True),
                done,
                vertical=False,
                spacing=12,
                margin_top=10,
                margin_bottom=10,
                margin_start=16,
                margin_end=16,
            )
        )
        self.set_child(tv)
        self.rebuild()

    def rebuild(self) -> None:
        targets, settings = config.load_targets(), config.load_settings()
        page = Adw.PreferencesPage()
        daily = Adw.PreferencesGroup(title="Daily")
        minimum = Adw.ActionRow(use_markup=False, title="Minimum average", subtitle="Weekly average must stay above this")
        minimum.add_suffix(Gtk.Image(icon_name="changes-prevent-symbolic", valign=Gtk.Align.CENTER))
        minimum.add_suffix(_tag("set by org"))
        minimum.add_suffix(label(f"{targets['dailyMinimum']:g} h", "heading", valign=Gtk.Align.CENTER))
        expected = Adw.ActionRow(use_markup=False, title="Expected", subtitle="What a good day looks like")
        expected.add_suffix(_spin(settings["expected_daily_h"], 5, 14, 0.5, self._set_expected))
        expected.add_suffix(label("h", "dim-label", valign=Gtk.Align.CENTER))
        lop = Adw.ActionRow(use_markup=False, title="Loss-of-pay line", subtitle="9 h = a day, 5 h leftover = +1")
        lop.add_suffix(_tag("read-only"))
        lop.add_suffix(label("41 h / 5-day week", "heading", valign=Gtk.Align.CENTER))
        for r in (minimum, expected, lop):
            daily.add(r)
        page.add(daily)

        monthly = Adw.PreferencesGroup(title="Monthly by project (billable)")
        for row in project_rows(self.window.status(), targets):
            monthly.add(self._project_row(row, targets))
            if row["source"] == "lead" and row.get("monthly_h") is not None:
                pr = Adw.ActionRow(
                    use_markup=False, title="Prorate for leave & holidays", subtitle=f"Lead's choice for {row['name']}"
                )
                pr.add_suffix(_tag("set by lead"))
                pr.add_suffix(Gtk.Switch(active=bool(row.get("prorate")), sensitive=False, valign=Gtk.Align.CENTER))
                monthly.add(pr)
        add = Adw.ActionRow(use_markup=False, title="Add personal target", activatable=True)
        add.add_prefix(Gtk.Image(icon_name="list-add-symbolic"))
        add.connect("activated", lambda *_: self._add_dialog())
        monthly.add(add)
        page.add(monthly)
        note = Adw.PreferencesGroup()
        note.add(
            box(
                label("Pay (LOP) always counts billable + non-billable.", "heading", wrap=True),
                label("Project targets above count billable only.", "caption", wrap=True),
                classes=("pace-info",),
                spacing=2,
            )
        )
        page.add(note)
        self.holder.set_child(page)

    def _project_row(self, row: dict, targets: dict) -> Adw.ActionRow:
        ar = Adw.ActionRow(use_markup=False, title=row["name"], subtitle=row["code"])
        if row.get("monthly_h") is None:
            ar.add_suffix(_tag("no target · tracked"))
        elif row["source"] == "lead":
            ar.add_suffix(_tag("set by lead"))
            ar.add_suffix(label(f"{row['monthly_h']:g} h", "heading", valign=Gtk.Align.CENTER))
        else:
            ar.add_suffix(_spin(row["monthly_h"], 0, 400, 1, lambda v, r=row: self._set_hours(r["code"], v)))
            rm = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"], valign=Gtk.Align.CENTER, tooltip_text="Remove")
            rm.connect("clicked", lambda *_: self._remove(row["code"]))
            ar.add_suffix(rm)
        return ar

    def _set_expected(self, value: float) -> None:
        s = config.load_settings()
        s["expected_daily_h"] = value
        config.save_settings(s)

    def _set_hours(self, code: str, value: float) -> None:
        t = config.load_targets()
        for p in t["projects"]:
            if p["code"] == code and p["source"] != "lead":
                p["monthly_h"] = value
        config.save_targets(t)

    def _remove(self, code: str) -> None:
        t = config.load_targets()
        t["projects"] = [p for p in t["projects"] if p["code"] != code or p["source"] == "lead"]
        config.save_targets(t)
        self.rebuild()

    def _add_dialog(self) -> None:
        code, name, hours = (
            Adw.EntryRow(title="Project code (e.g. TWE)"),
            Adw.EntryRow(title="Project name"),
            Adw.EntryRow(title="Monthly billable hours"),
        )
        group = Adw.PreferencesGroup()
        for r in (code, name, hours):
            group.add(r)
        d = Adw.AlertDialog(
            heading="Add personal target", body="Billable hours only. Lead-set targets can only be raised by a personal one."
        )
        d.set_extra_child(group)
        d.add_response("cancel", "Cancel")
        d.add_response("add", "Add")
        d.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def answered(_d, response):
            if response != "add":
                return
            try:
                h = float(hours.get_text().replace(",", "."))
            except ValueError:
                return self.window.toast("Monthly hours must be a number")
            if not code.get_text().strip() or not name.get_text().strip():
                return self.window.toast("A target needs a code and a name")
            t = config.load_targets()
            t["projects"] = [p for p in t["projects"] if p["code"] != code.get_text().strip().upper()]
            t["projects"].append(
                {
                    "code": code.get_text().strip().upper(),
                    "name": name.get_text().strip(),
                    "monthly_h": h,
                    "prorate": False,
                    "source": "personal",
                }
            )
            config.save_targets(t)
            self.rebuild()

        d.connect("response", answered)
        d.present(self.window)


def import_preset(window, on_imported) -> None:
    """A12: pick a *.pace-targets.json, confirm, merge."""
    flt = Gtk.FileFilter(name="Pace targets")
    flt.add_pattern("*.pace-targets.json")
    filters = Gio.ListStore.new(Gtk.FileFilter)
    filters.append(flt)
    chooser = Gtk.FileDialog(title="Import targets", filters=filters, default_filter=flt)

    def picked(dlg, result):
        try:
            file = dlg.open_finish(result)
        except GLib.Error:
            return  # dismissed
        try:
            preset = config.parse_preset(Path(file.get_path()).read_text())
        except (OSError, config.PresetError) as e:
            return window.alert("Can't import that file", str(e))
        confirm_import(window, file.get_basename(), preset, on_imported)

    chooser.open(window, None, picked)


def confirm_import(window, filename: str, preset: dict, on_imported) -> None:
    lines = "\n".join(config.preset_summary(preset["projects"]))
    d = Adw.AlertDialog(
        heading="Import targets?", body=f"Import targets from {filename} (from {preset['from']}, lead)?\n\n{lines}"
    )
    d.add_response("cancel", "Cancel")
    d.add_response("import", "Import")
    d.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)

    def answered(_d, response):
        if response == "import":
            config.save_targets(config.merge_preset(config.load_targets(), preset))
            on_imported()

    d.connect("response", answered)
    d.present(window)


def share_dialog(window, sender: str) -> None:
    """C8: pick a project and a number, export the preset file the team imports."""
    rows = project_rows(window.status(), config.load_targets())
    if not rows:
        return window.alert("Nothing to share yet", "Pace doesn't know any project yet. Add a personal target first.")
    dialog = Adw.Dialog(title="Share targets", content_width=460)
    project = Adw.ComboRow(
        use_markup=False, title="Project", model=Gtk.StringList.new([f"{r['name']} · {r['code']}" for r in rows])
    )
    first = rows[0].get("monthly_h") or 0
    monthly = Adw.SpinRow(
        use_markup=False,
        title="Monthly target",
        subtitle="billable hours",
        adjustment=Gtk.Adjustment(value=first, lower=0, upper=400, step_increment=1),
    )
    prorate = Adw.SwitchRow(
        use_markup=False,
        title="Prorate for leave and holidays",
        subtitle="Yes: the target shrinks for each leave day or holiday",
        active=bool(rows[0].get("prorate")),
    )

    def project_changed(*_):
        r = rows[project.get_selected()]
        monthly.set_value(r.get("monthly_h") or 0)
        prorate.set_active(bool(r.get("prorate")))

    project.connect("notify::selected", project_changed)
    prorate.connect(
        "notify::active",
        lambda *_: prorate.set_subtitle(
            "Yes: the target shrinks for each leave day or holiday" if prorate.get_active() else "No: the target stays fixed"
        ),
    )
    group = Adw.PreferencesGroup()
    for r in (project, monthly, prorate):
        group.add(r)
    cancel = Gtk.Button(label="Cancel")
    export = Gtk.Button(label="Export…", css_classes=["suggested-action"])
    cancel.connect("clicked", lambda *_: dialog.close())
    header = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
    header.pack_start(cancel)
    header.pack_end(export)
    intro = label(
        "Make a preset file for your team. They import it in Preferences, and its values show as “set by lead”.",
        "dim-label",
        wrap=True,
    )
    tv = Adw.ToolbarView(content=box(intro, group, spacing=16, margin_top=12, margin_bottom=20, margin_start=16, margin_end=16))
    tv.add_top_bar(header)
    dialog.set_child(tv)

    def do_export(*_):
        row = {**rows[project.get_selected()], "monthly_h": monthly.get_value(), "prorate": prorate.get_active()}
        preset = config.build_preset(sender, row)
        name = config.preset_filename(row["name"], date.today())
        chooser = Gtk.FileDialog(title="Export preset", initial_name=name)

        def saved(dlg, result):
            try:
                file = dlg.save_finish(result)
            except GLib.Error:
                return
            file.replace_contents(json.dumps(preset, indent=2).encode(), None, False, Gio.FileCreateFlags.NONE, None)
            dialog.close()
            window.toast(
                f"Saved {file.get_basename()}",
                "Show in folder",
                lambda: Gtk.FileLauncher.new(file).open_containing_folder(window, None, None),
            )

        chooser.save(window, None, saved)

    export.connect("clicked", do_export)
    dialog.present(window)
