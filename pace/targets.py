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
    left = days_left(mine, today)
    # The month's working days: weekdays less company holidays. Personal leave only lowers avail.
    holidays = {d["date"] for d in mine if d.get("type") == "holiday"}
    weekdays = sum(
        1
        for n in range(1, calendar.monthrange(at.year, at.month)[1] + 1)
        if date(at.year, at.month, n).weekday() < 5 and date(at.year, at.month, n).isoformat() not in holidays
    )
    billed: dict[str, int] = {}
    for r in rows:
        if r["date"][:7] == f"{at:%Y-%m}":
            billed[r["project_name"]] = billed.get(r["project_name"], 0) + r["billable_min"]
    daily = targets.get("dailyMinimum", 8.5) * 60
    named = {t["name"] for t in targets["projects"]}

    def build(total_need):
        got = [
            project(t["code"], t["name"], billed.get(t["name"], 0), t, avail, left, weekdays, daily, total_need)
            for t in targets["projects"]
        ]
        return got + [project(n[:3].upper(), n, m, None, avail, left, weekdays) for n, m in billed.items() if n not in named]

    # What every targeted project still needs per day, together, against one day's target: the month is at risk as a whole.
    total_need = sum(p["need_per_day_min"] or 0 for p in build(None))
    out = build(total_need)
    return sorted(out, key=lambda p: (p["target_min"] is None, -p["billed_min"]))


def days_left(days: list[dict], today: date) -> float:
    return sum(d["working"] for d in days if date.fromisoformat(d["date"]) >= today)


def month_block(rows: list[dict], days: list[dict], targets: dict, today: date) -> dict:
    """status.json's `month` for the month containing today."""
    left = days_left([d for d in days if d["date"][:7] == f"{today:%Y-%m}"], today)
    return {
        "name": f"{today:%B}",
        "working_days_left": int(left) if left == int(left) else left,
        "projects": month(rows, days, targets, today, today),
    }


def project(
    code: str,
    name: str,
    billed: int,
    target: dict | None,
    avail: float,
    left: float,
    weekdays: int,
    daily_min: float = 510,
    total_need: float | None = None,
) -> dict:
    """One project's month. Below the even pace is only "behind" (at_risk, amber, nudged) when the days left at the daily
    target (daily_min, minutes) cannot close the gap, counting every project's need together (total_need, default this
    project's own) or when no days are left; otherwise it is "under pace" and quiet."""
    out = {"code": code, "name": name, "billed_min": billed, "target_min": None, "gap_min": None, "at_risk": False}
    out |= {"need_per_day_min": None, "text": f"{hours(billed)} h · no target", "need_text": None, "short": None}
    if not target or target.get("monthly_h") is None:
        return out
    eff = target["monthly_h"] * 60 * (avail / weekdays if target.get("prorate") else 1)
    eff_min = round(eff)
    expected = round(eff * (avail - left) / avail) if avail else eff_min
    gap = billed - expected
    need = round((eff - billed) / left) if left and billed < eff else None
    out |= {"target_min": eff_min, "gap_min": gap, "need_per_day_min": need}
    risk = gap < 0 and (need is None or (need if total_need is None else total_need) > daily_min)
    word = (
        "on pace"
        if gap == 0
        else f"ahead {hours(gap)} h"
        if gap > 0
        else f"behind {hours(-gap)} h"
        if risk
        else f"{hours(-gap)} h under pace"
    )
    out["text"] = f"{hours(billed)} / {hours(eff_min, trim=True)} h · {word}"
    if need is not None:
        out["need_text"] = f"needs {hours(need)} h/day on {name}"
    if risk:
        out["at_risk"] = True
        out["short"] = f"{name} {MINUS}{hours(-gap)} h"
    return out
