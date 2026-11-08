"""Files the GTK app owns: settings.json, targets.json (contract sections 2-3), autostart entries, widget position. No GTK."""

from __future__ import annotations

import copy
import json
import re
import shutil
from collections.abc import Callable
from datetime import date
from pathlib import Path

from pace.files import config_dir, data_dir, read_json, state_dir, write_json

DEFAULT_SETTINGS = {
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
    "widget_at_login": False,
    "token_store": "keyring",
}
DEFAULT_TARGETS = {"dailyMinimum": 8.5, "projects": []}
DAEMON_DESKTOP = "io.github.xixas.Pace.daemon.desktop"
WIDGET_DESKTOP = "io.github.xixas.Pace.widget.desktop"
HIDDEN_ENTRY = "[Desktop Entry]\nType=Application\nName=Pace\nHidden=true\n"
WIDGET_ENTRY = "[Desktop Entry]\nType=Application\nName=Pace mini widget\nExec=pace widget\nX-GNOME-Autostart-enabled=true\n"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def targets_path() -> Path:
    return config_dir() / "targets.json"


def autostart_dir() -> Path:
    return config_dir().parent / "autostart"


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> dict:
    saved = read_json(settings_path())
    return _merge(DEFAULT_SETTINGS, saved if isinstance(saved, dict) else {})


def save_settings(settings: dict) -> None:
    write_json(settings_path(), settings)


def apply_autostart(settings: dict) -> None:
    """start_at_login: Hidden=true override in ~/.config/autostart when off, no file when on (the system entry applies).
    widget_at_login: a real entry when on, so it works whether or not packaging ships a system one; Hidden=true when off."""
    d = autostart_dir()
    d.mkdir(parents=True, exist_ok=True)
    daemon = d / DAEMON_DESKTOP
    if settings["start_at_login"]:
        daemon.unlink(missing_ok=True)
    else:
        daemon.write_text(HIDDEN_ENTRY)
    (d / WIDGET_DESKTOP).write_text(WIDGET_ENTRY if settings["widget_at_login"] else HIDDEN_ENTRY)


TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def valid_time(text: str) -> bool:
    return bool(TIME.match(text))


def format_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def split_time(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


def load_targets() -> dict:
    saved = read_json(targets_path())
    return saved if isinstance(saved, dict) and "projects" in saved else copy.deepcopy(DEFAULT_TARGETS)


def save_targets(targets: dict) -> None:
    write_json(targets_path(), targets)


def lead_hours(row: dict) -> float | None:
    """What the lead set on a lead row, under any personal raise."""
    return row.get("lead_h", row.get("monthly_h"))


def set_target(targets: dict, code: str, name: str, monthly_h: float | None, prorate: bool) -> dict:
    """A11: save one project's personal target. monthly_h None = tracked only. A lead row keeps the lead's prorate choice and can
    only be raised: a personal value at or below the lead's (or none) puts the lead's own value back."""
    code = code.strip().upper()
    rows = [dict(p) for p in targets["projects"]]
    row = next((p for p in rows if p["code"] == code), None)
    if row is None:
        row = {"code": code, "name": name.strip(), "monthly_h": None, "prorate": False, "source": "personal"}
        rows.append(row)
    if row.get("source") == "lead":
        lead = lead_hours(row)
        if monthly_h is not None and monthly_h > lead:
            row["lead_h"], row["monthly_h"] = lead, monthly_h
        else:
            row.pop("lead_h", None)
            row["monthly_h"] = lead
    else:
        row["monthly_h"] = monthly_h
        row["prorate"] = bool(prorate) if monthly_h is not None else False
    return {**targets, "projects": rows}


def parse_hours(text: str) -> float | None:
    """The hours field of the target dialogs: empty = no target; "12,5 h" is fine; 0-744 h a month."""
    text = text.strip().rstrip("hH").strip().replace(",", ".")
    if not text:
        return None
    value = float(text)
    if not 0 <= value <= 744:
        raise ValueError(text)
    return value


def remove_target(targets: dict, code: str) -> dict:
    """Drop a personal row; a lead row only loses its personal raise."""
    code = code.strip().upper()
    if any(p["code"] == code and p.get("source") == "lead" for p in targets["projects"]):
        return set_target(targets, code, "", None, False)
    return {**targets, "projects": [p for p in targets["projects"] if p["code"] != code]}


class PresetError(ValueError):
    """The file isn't a Pace targets preset."""


def parse_preset(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as e:
        raise PresetError("That file isn't JSON.") from e
    projects = data.get("projects") if isinstance(data, dict) else None
    if not data or not isinstance(projects, list) or not projects:
        raise PresetError("That file has no projects in it.")
    for p in projects:
        if not isinstance(p, dict) or not p.get("code") or not p.get("name") or "monthly_h" not in p:
            raise PresetError("A project in that file is missing its code, name or monthly_h.")
    return {"from": str(data.get("from") or "your lead"), "projects": projects}


def preset_summary(projects: list[dict]) -> list[str]:
    return [
        f"{p['name']} {p['monthly_h']:g} h / month, " + ("prorated for leave & holidays" if p.get("prorate") else "fixed")
        for p in projects
        if p.get("monthly_h") is not None
    ]


def merge_preset(targets: dict, preset: dict) -> dict:
    """Imported rows are source "lead" (locked); personal rows for other projects stay."""
    codes = {p["code"] for p in preset["projects"]}
    old = {p["code"]: p for p in targets["projects"]}
    rows = [p for p in targets["projects"] if p["code"] not in codes]
    for p in preset["projects"]:
        row = {
            "code": p["code"],
            "name": p["name"],
            "monthly_h": p["monthly_h"],
            "prorate": bool(p.get("prorate")),
            "source": "lead",
            "lead": preset["from"],
        }
        raised = (old.get(p["code"]) or {}).get("monthly_h")
        if "lead_h" in (old.get(p["code"]) or {}) and raised is not None and raised > p["monthly_h"]:
            row |= {"monthly_h": raised, "lead_h": p["monthly_h"]}
        rows.append(row)
    rows.sort(key=lambda p: (p["source"] != "lead", p["name"]))
    return {**targets, "projects": rows}


def build_preset(sender: str, row: dict) -> dict:
    keep = {k: row[k] for k in ("code", "name", "monthly_h", "prorate")}
    return {"from": sender, "projects": [keep]}


def preset_filename(project_name: str, today: date) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
    return f"{slug}-{today.strftime('%b').lower()}.pace-targets.json"


def remove_my_data(clear_session: Callable[[], None]) -> None:
    """C11: the keyring/file session, status and profile, ~/.config/pace, the widget position and both autostart overrides."""
    try:
        clear_session()
    except Exception:
        pass  # no keyring entry to delete is fine
    for d in (state_dir(), config_dir(), data_dir()):
        shutil.rmtree(d, ignore_errors=True)
    for name in (DAEMON_DESKTOP, WIDGET_DESKTOP):
        (autostart_dir() / name).unlink(missing_ok=True)


def ui_state_path() -> Path:
    return state_dir() / "ui.json"


def load_ui_state() -> dict:
    s = read_json(ui_state_path())
    return s if isinstance(s, dict) else {}


def save_ui_state(**patch) -> None:
    write_json(ui_state_path(), {**load_ui_state(), **patch})


def load_widget_pos() -> tuple[int, int] | None:
    try:
        w = load_ui_state()["widget"]
        return int(w["x"]), int(w["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_widget_pos(x: int, y: int) -> None:
    save_ui_state(widget={"x": x, "y": y})
