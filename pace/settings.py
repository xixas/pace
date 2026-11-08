"""settings.json (contract section 2): the GTK app writes it, paced reads it. Missing file or key → the defaults."""

from __future__ import annotations

import copy
import re

from pace.engine import Rules
from pace.files import config_dir, read_json

NUDGES = ("pay_risk", "friday", "daily", "monday", "zero_hour", "project_behind")
DEFAULTS = {
    "panel_text": "hours",
    "refresh_minutes": 15,
    "start_at_login": True,
    "expected_daily_h": 9.0,
    "notify": {
        "pay_risk": {"on": True, "at": "11:00"},
        "friday": {"on": True, "at": "16:00"},
        "daily": {"on": True, "at": "20:00"},
        "monday": {"on": True, "at": "12:30"},
        "zero_hour": {"on": True, "at": "12:00"},
        "project_behind": {"on": True, "at": "10:30"},
        "signed_out": {"on": True},
    },
    "rules": {"daily_target_h": 8.5, "full_day_h": 9.0, "part_day_h": 5.0},
    "widget_at_login": False,
    "token_store": "keyring",
}
CHOICES = {"panel_text": ("hours", "percent", "gap", "left_today", "icon"), "token_store": ("keyring", "file", "none")}
RULE_KEYS = ("daily_target_h", "full_day_h", "part_day_h")
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def merge(base: dict, over: dict) -> dict:
    """over's values laid on base, keeping base's value wherever over's is missing or the wrong kind."""
    out = copy.deepcopy(base)
    for key, default in base.items():
        value = over.get(key)
        if isinstance(default, dict):
            out[key] = merge(default, value if isinstance(value, dict) else {})
        elif key in CHOICES and value in CHOICES[key]:
            out[key] = value
        elif key == "at" and isinstance(value, str) and TIME.fullmatch(value):
            out[key] = value
        elif key not in CHOICES and key != "at" and type(value) is type(default):
            out[key] = value
        elif key in RULE_KEYS and isinstance(value, int | float) and not isinstance(value, bool):
            out[key] = float(value)
        elif key == "expected_daily_h" and isinstance(value, int | float) and not isinstance(value, bool):
            out[key] = float(value)
    return out


def valid_rules(r: dict) -> bool:
    return 0 < r["part_day_h"] < r["full_day_h"] <= 24 and 0 < r["daily_target_h"] <= 24


def rules_from(data: dict) -> Rules:
    r = data["rules"]
    return Rules(round(r["daily_target_h"] * 60), round(r["full_day_h"] * 60), round(r["part_day_h"] * 60))


class Settings:
    def __init__(self):
        self.path = config_dir() / "settings.json"
        self.data: dict = {}
        self.reload()

    def reload(self) -> None:
        raw = read_json(self.path)
        self.data = merge(DEFAULTS, raw if isinstance(raw, dict) else {})
        if not valid_rules(self.data["rules"]):
            self.data["rules"] = dict(DEFAULTS["rules"])

    def rules(self) -> Rules:
        return rules_from(self.data)

    def watch(self, on_change):
        """Re-read the file whenever the app saves it, then call on_change(). Returns the monitor; keep it alive."""
        from gi.repository import Gio

        self.path.parent.mkdir(parents=True, exist_ok=True)
        monitor = Gio.File.new_for_path(str(self.path.parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)

        def changed(_monitor, file, _other, event):
            if file.get_basename() == self.path.name and event in (
                Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                Gio.FileMonitorEvent.CREATED,
                Gio.FileMonitorEvent.RENAMED,
                Gio.FileMonitorEvent.MOVED_IN,
            ):
                self.reload()
                on_change()

        monitor.connect("changed", changed)
        return monitor
