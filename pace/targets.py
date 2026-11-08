"""targets.json (contract section 3) and the month-per-project maths (design "Month, per project"). Billable minutes only."""

from __future__ import annotations

import calendar
from datetime import date

from pace.engine import hours
from pace.files import config_dir, read_json

MINUS = "−"


def load() -> dict:
    raw = read_json(config_dir() / "targets.json")
    raw = raw if isinstance(raw, dict) else {}
    return {"dailyMinimum": raw.get("dailyMinimum", 8.5), "projects": raw.get("projects") or []}


def month(rows: list[dict], days: list[dict], targets: dict, at: date, today: date | None = None) -> list[dict]:
    """The month.projects[] of status.json for the month containing `at`.

    rows: my-hours rows, days: my-days rows (the whole month). eff_target = monthly × avail ÷ month working days when the
    project is prorated; need/day = (eff_target − billed) ÷ the avail days still to come (today included).
    """
    today = today or date.today()
    mine = [d for d in days if d["date"][:7] == f"{at:%Y-%m}"]
    avail = sum(d["working"] for d in mine)
    left = sum(d["working"] for d in mine if date.fromisoformat(d["date"]) >= today)
    weekdays = sum(1 for n in range(1, calendar.monthrange(at.year, at.month)[1] + 1) if date(at.year, at.month, n).weekday() < 5)
    billed: dict[str, int] = {}
    for r in rows:
        if r["date"][:7] == f"{at:%Y-%m}":
            billed[r["project_name"]] = billed.get(r["project_name"], 0) + r["billable_min"]
    out = [project(t["code"], t["name"], billed.get(t["name"], 0), t, avail, left, weekdays) for t in targets["projects"]]
    named = {t["name"] for t in targets["projects"]}
    out += [project(n[:3].upper(), n, m, None, avail, left, weekdays) for n, m in billed.items() if n not in named]
    return sorted(out, key=lambda p: (p["target_min"] is None, -p["billed_min"]))


def project(code: str, name: str, billed: int, target: dict | None, avail: float, left: float, weekdays: int) -> dict:
    out = {"code": code, "name": name, "billed_min": billed, "target_min": None, "gap_min": None}
    out |= {"need_per_day_min": None, "text": f"{hours(billed)} h · no target", "need_text": None, "short": None}
    if not target or target.get("monthly_h") is None:
        return out
    eff = target["monthly_h"] * 60 * (avail / weekdays if target.get("prorate") else 1)
    eff_min = round(eff)
    expected = round(eff * (avail - left) / avail) if avail else eff_min
    gap = billed - expected
    need = round((eff - billed) / left) if left and billed < eff else None
    out |= {"target_min": eff_min, "gap_min": gap, "need_per_day_min": need}
    word = f"behind {hours(-gap)}" if gap < 0 else f"ahead {hours(gap)}" if gap > 0 else "on track"
    out["text"] = f"{hours(billed)} / {hours(eff_min, trim=True)} h · {word}"
    if need is not None:
        out["need_text"] = f"needs {hours(need)} h/day on {name}"
    if gap < 0:
        out["short"] = f"{name} {MINUS}{hours(-gap)} h"
    return out
