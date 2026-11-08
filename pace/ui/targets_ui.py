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
from pace.ui.widgets import action_row, box, label  # noqa: E402


def _tag(text: str) -> Gtk.Label:
    return label(text, "caption-heading", "dim-label", valign=Gtk.Align.CENTER)


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
        minimum = action_row(title="Minimum average", subtitle="Weekly average must stay above this")
        minimum.add_suffix(Gtk.Image(icon_name="changes-prevent-symbolic", valign=Gtk.Align.CENTER))
        minimum.add_suffix(_tag("set by org"))
        minimum.add_suffix(label(f"{targets['dailyMinimum']:g} h", "heading", valign=Gtk.Align.CENTER))
        expected = action_row(title="Expected", subtitle="What a good day looks like")
        expected.add_suffix(_spin(settings["expected_daily_h"], 5, 14, 0.5, self._set_expected))
        expected.add_suffix(label("h", "dim-label", valign=Gtk.Align.CENTER))
        how, week = config.lop_line(settings["rules"])
        lop = action_row(title="Loss-of-pay line", subtitle=how)
        lop.add_suffix(_tag("read-only"))
        lop.add_suffix(label(week, "heading", valign=Gtk.Align.CENTER))
        for r in (minimum, expected, lop):
            daily.add(r)
        page.add(daily)

        monthly = Adw.PreferencesGroup(title="Monthly by project (billable)", description="Tap a project to set its target.")
        for row in project_rows(self.window.status(), targets):
            monthly.add(self._project_row(row))
            if row.get("monthly_h") is not None:
                monthly.add(self._prorate_row(row))
        add = action_row(title="Add personal target", activatable=True)
        add.add_prefix(Gtk.Image(icon_name="list-add-symbolic"))
        add.connect("activated", lambda *_: self._add_dialog())
        monthly.add(add)
        page.add(monthly)
        note = Adw.PreferencesGroup()
        why = action_row(
            title="Pay (LOP) always counts billable + non-billable.", subtitle="Project targets above count billable only."
        )
        why.add_prefix(Gtk.Image(icon_name="dialog-information-symbolic", css_classes=["accent"], pixel_size=20))
        note.add(why)
        page.add(note)
        self.holder.set_child(page)

    def _project_row(self, row: dict) -> Adw.ActionRow:
        """Every project row opens the edit dialog; the suffix says who set what."""
        ar = action_row(title=row["name"], subtitle=row["code"], activatable=True)
        h, lead = row.get("monthly_h"), config.lead_hours(row)
        if h is None:
            ar.add_suffix(_tag("no target · tracked"))
        elif row["source"] == "lead":
            ar.add_suffix(_tag("set by lead" if h == lead else f"set by lead {lead:g} h · raised"))
            ar.add_suffix(label(f"{h:g} h", "heading", valign=Gtk.Align.CENTER))
        else:
            ar.add_suffix(label(f"{h:g} h", "heading", valign=Gtk.Align.CENTER))
        ar.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        ar.connect("activated", lambda *_: self._edit_dialog(row))
        return ar

    def _prorate_row(self, row: dict) -> Adw.ActionRow:
        pr = action_row(title="Prorate for leave & holidays")
        if row["source"] == "lead":
            pr.set_subtitle(f"Lead's choice for {row['name']}")
            pr.add_suffix(_tag("set by lead"))
            pr.add_suffix(Gtk.Switch(active=bool(row.get("prorate")), sensitive=False, valign=Gtk.Align.CENTER))
        else:
            pr.set_subtitle(f"Your choice for {row['name']}")
            sw = Gtk.Switch(active=bool(row.get("prorate")), valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, *_: self._save(row["code"], row["name"], row["monthly_h"], s.get_active()))
            pr.add_suffix(sw)
            pr.set_activatable_widget(sw)
        return pr

    def _set_expected(self, value: float) -> None:
        s = config.load_settings()
        s["expected_daily_h"] = value
        config.save_settings(s)

    def _save(self, code: str, name: str, monthly_h: float | None, prorate: bool) -> None:
        config.save_targets(config.set_target(config.load_targets(), code, name, monthly_h, prorate))
        self.rebuild()

    @staticmethod
    def _target_fields(row: dict | None) -> tuple[Adw.PreferencesGroup, Adw.EntryRow, Adw.SwitchRow]:
        """The two inputs every target dialog has: hours (empty = no target) and the prorate switch."""
        lead = row is not None and row.get("source") == "lead"
        raised = lead and "lead_h" in row
        hours = Adw.EntryRow(title="Monthly billable hours", input_purpose=Gtk.InputPurpose.NUMBER)
        if row and row.get("monthly_h") is not None and (not lead or raised):
            hours.set_text(f"{row['monthly_h']:g}")
        prorate = Adw.SwitchRow(use_markup=False, active=bool(row and row.get("prorate")))
        prorate.set_title("Prorate for leave & holidays")
        prorate.set_subtitle("Lead's choice, kept" if lead else "The target shrinks for each leave day or holiday")
        prorate.set_sensitive(not lead)
        group = Adw.PreferencesGroup()
        group.add(hours)
        group.add(prorate)
        return group, hours, prorate

    def _edit_dialog(self, row: dict) -> None:
        lead = row.get("source") == "lead"
        if lead:
            body = (
                f"{row.get('lead') or 'Your lead'} set {config.lead_hours(row):g} h. A personal target can only raise it; "
                "leave the hours empty to use the lead's value."
            )
        else:
            body = "Billable hours per month. Leave the hours empty to track the project without a target."
        group, hours, prorate = self._target_fields(row)
        d = Adw.AlertDialog(heading=f"{row['name']} · {row['code']}", body=body)
        d.set_extra_child(group)
        d.add_response("cancel", "Cancel")
        if row.get("monthly_h") is not None and (not lead or "lead_h" in row):
            d.add_response("remove", "Use lead's value" if lead else "Remove target")
            d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.add_response("save", "Save")
        d.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("save")

        def answered(_d, response):
            if response == "remove":
                config.save_targets(config.remove_target(config.load_targets(), row["code"]))
                return self.rebuild()
            if response != "save":
                return
            try:
                h = config.parse_hours(hours.get_text())
            except ValueError:
                return self.window.toast("Monthly hours must be a number")
            self._save(row["code"], row["name"], h, prorate.get_active())

        d.connect("response", answered)
        d.present(self.window)

    def _add_dialog(self) -> None:
        """Pick a project Pace has seen this month, or type a code and a name."""
        known = {r["code"] for r in config.load_targets()["projects"]}
        seen = [p for p in (self.window.status().get("month") or {}).get("projects", []) if p["code"] not in known]
        names = [f"{p['name']} · {p['code']}" for p in seen] + ["Other project…"]
        project = Adw.ComboRow(use_markup=False, title="Project", model=Gtk.StringList.new(names), visible=bool(seen))
        code = Adw.EntryRow(title="Project code (e.g. TWE)", visible=not seen)
        name = Adw.EntryRow(title="Project name", visible=not seen)
        group, hours, prorate = self._target_fields(None)
        for r in (prorate, hours):
            group.remove(r)
        for r in (project, code, name, hours, prorate):
            group.add(r)

        def other(*_):
            manual = project.get_selected() >= len(seen)
            code.set_visible(manual)
            name.set_visible(manual)

        project.connect("notify::selected", other)
        d = Adw.AlertDialog(
            heading="Add personal target", body="Billable hours only. Lead-set targets can only be raised by a personal one."
        )
        d.set_extra_child(group)
        d.add_response("cancel", "Cancel")
        d.add_response("add", "Add")
        d.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("add")

        def answered(_d, response):
            if response != "add":
                return
            try:
                h = config.parse_hours(hours.get_text())
            except ValueError:
                return self.window.toast("Monthly hours must be a number")
            if seen and project.get_selected() < len(seen):
                picked = seen[project.get_selected()]
                c, n = picked["code"], picked["name"]
            else:
                c, n = code.get_text().strip().upper(), name.get_text().strip()
            if not c or not n:
                return self.window.toast("A target needs a code and a name")
            self._save(c, n, h, prorate.get_active())

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
