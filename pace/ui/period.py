"""Pure view models for the Month (C3) and Calendar (C4) tabs, built from pace.history rows (contract section 3a)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from pace.ui.model import hours, parse_dt


def month_bounds(d: date) -> tuple[date, date]:
    return d.replace(day=1), d.replace(day=calendar.monthrange(d.year, d.month)[1])


def shift_month(first: date, delta: int) -> date:
    index = first.year * 12 + first.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def total_min(row: dict) -> int:
    """Pay counts billable + non-billable, so the heat map does too."""
    return (row.get("billable_min") or 0) + (row.get("non_billable_min") or 0)


def heat_class(row: dict, today: date, daily_min_h: float) -> str:
    kind = row["type"]
    if kind == "weekend":
        return "heat-off"
    if kind == "holiday":
        return "heat-holiday"
    if kind == "leave":
        return "heat-leave"
    d, minutes, floor = parse_dt(row["date"]).date(), total_min(row), daily_min_h * 60
    if d > today or (d == today and minutes < floor):
        return "heat-pending"
    if minutes >= floor:
        return "heat-ok"
    return "heat-mid" if minutes >= floor - 90 else "heat-low"


def _label(row: dict, cls: str) -> str:
    if cls == "heat-off":
        return ""
    if cls == "heat-holiday":
        return "Holiday"
    if cls == "heat-leave":
        return "Leave"
    if cls == "heat-pending" and not total_min(row):
        return "–"
    return hours(total_min(row))


def _tip(row: dict) -> str:
    lines = [f"{p['code']} {hours(p['billable_min'])} h" for p in row.get("projects", []) if p.get("billable_min")]
    non = row.get("non_billable_min") or 0
    if non:
        lines.append(f"non-billable {hours(non)} h")
    return "\n".join(lines)


def calendar_grid(rows: list[dict], first: date, today: date, daily_min_h: float) -> list[list[dict]]:
    """Mon-first weeks of cells {day, date, label, cls, tip, today}; None day pads the edges."""
    by_date = {r["date"]: r for r in rows}
    start = first - timedelta(days=first.weekday())
    last = month_bounds(first)[1]
    weeks, d = [], start
    while d <= last:
        week = []
        for _ in range(7):
            row = by_date.get(d.isoformat())
            if d.month != first.month or row is None:
                week.append({"day": None, "date": None, "label": "", "cls": "heat-none", "tip": "", "today": False})
            else:
                cls = heat_class(row, today, daily_min_h)
                week.append(
                    {
                        "day": d.day,
                        "date": d.isoformat(),
                        "label": _label(row, cls),
                        "cls": cls,
                        "tip": _tip(row),
                        "today": d == today,
                    }
                )
            d += timedelta(days=1)
        weeks.append(week)
    return weeks


def week_table(rows: list[dict], first: date) -> dict:
    """C3 table: per Mon-Fri week of the month, working days, billable hours per project, total incl. non-billable."""
    billed: dict[str, int] = {}
    groups: dict[date, list[dict]] = {}
    for r in rows:
        d = parse_dt(r["date"]).date()
        if d.weekday() >= 5:
            continue
        groups.setdefault(d - timedelta(days=d.weekday()), []).append(r)
        for p in r.get("projects", []):
            billed[p["code"]] = billed.get(p["code"], 0) + (p.get("billable_min") or 0)
    codes = sorted(billed, key=lambda c: -billed[c])
    weeks = []
    for monday in sorted(groups):
        rs = groups[monday]
        by_code: dict[str, int] = {}
        for r in rs:
            for p in r.get("projects", []):
                if p.get("billable_min"):
                    by_code[p["code"]] = by_code.get(p["code"], 0) + p["billable_min"]
        a, b = parse_dt(rs[0]["date"]), parse_dt(rs[-1]["date"])
        weeks.append(
            {
                "monday": monday.isoformat(),
                "label": f"{a.day}–{b.day} {b:%b}",
                "days": sum(r["working"] for r in rs),
                "by_code": by_code,
                "total_min": sum(total_min(r) for r in rs),
            }
        )
    total = {
        "days": sum(w["days"] for w in weeks),
        "total_min": sum(w["total_min"] for w in weeks),
        "by_code": {c: sum(w["by_code"].get(c, 0) for w in weeks) for c in codes},
    }
    return {"codes": codes, "weeks": weeks, "total": total}


def cumulative(rows: list[dict], code: str) -> list[tuple[date, int]]:
    run, out = 0, []
    for r in rows:
        run += sum(p.get("billable_min") or 0 for p in r.get("projects", []) if p["code"] == code)
        out.append((parse_dt(r["date"]).date(), run))
    return out


def expected_line(rows: list[dict], target_min: int) -> list[tuple[date, float]]:
    """Straight line from 0 to the (prorated) target across the month's working days."""
    total = sum(r["working"] for r in rows) or 1
    run, out = 0.0, []
    for r in rows:
        run += r["working"]
        out.append((parse_dt(r["date"]).date(), target_min * run / total))
    return out


def core_month():
    """pace.targets.month when core has landed, else None."""
    try:
        from pace.targets import month
    except ImportError:
        return None
    return month


def _sum_projects(rows: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for r in rows:
        for p in r.get("projects", []):
            t = totals.setdefault(p["code"], {"name": p["name"], "min": 0})
            t["min"] += p.get("billable_min") or 0
    out = [
        {
            "code": c,
            "name": t["name"],
            "billed_min": t["min"],
            "target_min": None,
            "gap_min": None,
            "need_per_day_min": None,
            "text": f"{hours(t['min'])} h · no target",
            "need_text": None,
            "short": None,
        }
        for c, t in totals.items()
    ]
    return sorted(out, key=lambda p: -p["billed_min"])


def month_projects(rows, targets, month: date, status: dict, today: date, core="auto") -> list[dict]:
    """month.projects[] for any month: core's maths if it exists, status.json for the month it describes, else plain sums."""
    core = core_month() if core == "auto" else core
    if core is not None:
        return core(rows, rows, targets, month)
    if month == today.replace(day=1) and (status.get("month") or {}).get("projects"):
        return status["month"]["projects"]
    return _sum_projects(rows)


def project_badge(p: dict) -> tuple[str, str]:
    if p.get("target_min") is None or p.get("gap_min") is None:
        return "no target", "grey"
    if p["gap_min"] < 0:
        return f"BEHIND {abs(p['gap_min']) / 60:.1f} h", "amber"
    return "ON TRACK", "green"


def target_note(targets: dict, code: str) -> str:
    row = next((p for p in targets.get("projects", []) if p.get("code") == code), None)
    if not row or row.get("monthly_h") is None:
        return "tracked only · billable"
    text = f"{row['monthly_h']:g} {'prorated' if row.get('prorate') else 'fixed'}"
    return text + (" · lead's choice" if row.get("source") == "lead" else "")


def no_mapping_cards(rows: list[dict], today: date) -> list[tuple[str, str, str]]:
    """A8: without a PineStem mapping only leave and holidays are known. rows cover this month and the weeks ahead."""
    leave = [r for r in rows if r["type"] in ("leave", "half_leave") and r["date"][:7] == today.isoformat()[:7]]
    days = sum(1.0 if r["type"] == "leave" else 0.5 for r in leave)
    leave_val = "none" if not days else f"{days:g} day" + ("s" if days > 1 else "")
    leave_sub = ", ".join(f"{parse_dt(r['date']).day} {parse_dt(r['date']):%b}" for r in leave)
    nxt = next((parse_dt(r["date"]).date() for r in rows if r["type"] == "holiday" and r["date"] >= today.isoformat()), None)
    return [
        ("This week", "—", "no billing data"),
        (f"Leave · {today:%b}", leave_val, leave_sub),
        ("Next holiday", f"{nxt:%a} {nxt.day} {nxt:%b}" if nxt else "none soon", ""),
    ]


def _day_list(rows: list[dict]) -> str:
    days = [parse_dt(r["date"]) for r in rows]
    nums = [str(d.day) for d in days]
    head = nums[0] if len(nums) == 1 else ", ".join(nums[:-1]) + " and " + nums[-1]
    return f"{head} {days[-1]:%b}"


def footnote(rows: list[dict]) -> str:
    """C3 footer: the days that are not working days, in words."""
    parts = []
    holidays = [r for r in rows if r["type"] == "holiday" and parse_dt(r["date"]).weekday() < 5]
    leave = [r for r in rows if r["type"] in ("leave", "half_leave")]
    if holidays:
        parts.append(f"Holidays {_day_list(holidays)}")
    if leave:
        parts.append(f"leave {_day_list(leave)}")
    text = ", ".join(parts)
    return (text[0].upper() + text[1:] + ".") if text else ""
