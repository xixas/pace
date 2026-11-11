"""The pay-rule steppers (daily target, full day, part day) shared by Preferences and the targets page, so both edit the same
settings.json `rules` with the same limits: 0 < part < full <= 24 and 0 < target <= 24 (docs/contract.md section 2)."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from pace.ui import config  # noqa: E402

RULES = (
    ("daily_target_h", "Daily target", "Weekly average to aim for"),
    ("full_day_h", "Full day for pay", "Hours HR counts as one day · DhiHRMS default 9"),
    ("part_day_h", "Part day for pay", "Leftover that still counts as a day · DhiHRMS default 5"),
)


def hours_format(row: Adw.SpinRow) -> Adw.SpinRow:
    """Show the stepper's value as "8.5 h" and read it back without the unit: one style for every hour row."""

    def output(r):
        r.set_text(f"{r.get_value():.1f} h")
        return True

    def parse(r):
        try:
            return float(r.get_text().lower().replace("h", "").replace(",", ".").strip())
        except ValueError:
            return Gtk.INPUT_ERROR

    row.connect("output", output)
    row.connect("input", parse)
    return row


def rule_rows(
    rules: dict, save: Callable[[str, float], None], titles: dict[str, tuple[str, str]] | None = None
) -> dict[str, Adw.SpinRow]:
    """Three half-hour steppers keyed by rule; the part day always stays below the full day. save(key, value) on every change."""
    rows: dict[str, Adw.SpinRow] = {}
    for key, title, sub in RULES:
        title, sub = (titles or {}).get(key, (title, sub))
        rows[key] = hours_format(
            Adw.SpinRow(
                use_markup=False,
                title=title,
                subtitle=sub,
                digits=1,
                adjustment=Gtk.Adjustment(value=rules[key], lower=0.5, upper=24, step_increment=0.5, page_increment=1),
            )
        )
    full, part = rows["full_day_h"], rows["part_day_h"]
    full.get_adjustment().set_lower(part.get_value() + 0.5)
    part.get_adjustment().set_upper(full.get_value() - 0.5)

    def changed(row, key):
        if key == "full_day_h":
            part.get_adjustment().set_upper(row.get_value() - 0.5)
        elif key == "part_day_h":
            full.get_adjustment().set_lower(row.get_value() + 0.5)
        save(key, round(row.get_value(), 1))

    for key, row in rows.items():
        row.connect("notify::value", lambda r, _p, k=key: changed(r, k))
    return rows


def reset_rules(rows: dict[str, Adw.SpinRow]) -> None:
    for key in ("part_day_h", "full_day_h", "daily_target_h"):  # part first so the full day's floor allows the default
        rows[key].get_adjustment().set_lower(0.5)
        rows[key].get_adjustment().set_upper(24)
        rows[key].set_value(config.DEFAULT_RULES[key])


def reset_row(rows: dict[str, Adw.SpinRow]) -> Adw.ButtonRow:
    row = Adw.ButtonRow(title="Reset to DhiHRMS defaults")
    row.connect("activated", lambda *_: reset_rules(rows))
    return row


def save_rule(key: str, value: float) -> None:
    """Write one rule into settings.json, keeping everything else as it is on disk."""
    settings = config.load_settings()
    settings["rules"][key] = value
    config.save_settings(settings)
