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
    if d > today:
        return "heat-future"
    if d == today and minutes < floor:
        return "heat-pending"
    if minutes >= floor:
        return "heat-ok"
    return "heat-mid" if minutes >= floor - 90 else "heat-low"


def _label(row: dict, cls: str) -> str:
    if cls == "heat-holiday":
        return "Holiday"
    if cls == "heat-leave":
        return "Leave"
    if cls == "heat-future":
        return ""
    return hours(total_min(row)) if total_min(row) else ""  # a weekend or a day just begun shows hours only when it has some


def _tip(row: dict) -> str:
    lines = [f"{p['code']} {hours(p['billable_min'])} h" for p in row.get("projects", []) if p.get("billable_min")]
    non = row.get("non_billable_min") or 0
    if non:
        lines.append(f"non-billable {hours(non)} h")
    return "\n".join(lines)


def _split(row: dict) -> list[tuple[str, int]]:
    return [(p["code"], p["billable_min"]) for p in row.get("projects", []) if p.get("billable_min")]


def calendar_grid(rows: list[dict], first: date, today: date, daily_min_h: float) -> list[list[dict]]:
    """Mon-first weeks of cells {day, date, label, cls, tip, today, outside, split, total_min}. Days of the neighbouring
    months fill the first and last week as muted number-only cells (outside=True); they have no data."""
    by_date = {r["date"]: r for r in rows}
    last = month_bounds(first)[1]
    d = first - timedelta(days=first.weekday())
    end = last + timedelta(days=6 - last.weekday())
    weeks = []
    while d <= end:
        week = []
        for _ in range(7):
            row = by_date.get(d.isoformat())
            cell = {"day": d.day, "date": d.isoformat(), "label": "", "cls": "heat-none", "tip": "", "today": d == today}
            cell.update(outside=d.month != first.month, split=[], total_min=0, weekend=d.weekday() >= 5)
            if not cell["outside"] and row is not None:
                cls = heat_class(row, today, daily_min_h)
                cell.update(label=_label(row, cls), cls=cls, tip=_tip(row), split=_split(row), total_min=total_min(row))
            week.append(cell)
            d += timedelta(days=1)
        weeks.append(week)
    return weeks


TYPE_TEXT = {
    "working": "Working day",
    "weekend": "Weekend",
    "holiday": "Holiday",
    "leave": "Leave",
    "half_leave": "Half-day leave",
}
HEAT_COLOUR = {"heat-ok": "green", "heat-mid": "amber", "heat-low": "red", "heat-holiday": "blue", "heat-leave": "blue"}


def day_detail(row: dict, today: date, daily_min_h: float) -> dict:
    """What the day dialog shows: date, kind, billed against the daily target with the verdict colour, the split."""
    d = parse_dt(row["date"]).date()
    cls = heat_class(row, today, daily_min_h)
    kind, minutes, target = row["type"], total_min(row), round(daily_min_h * 60)
    counts = kind in ("working", "half_leave") and d <= today
    if kind in ("holiday", "leave"):
        verdict = (
            TYPE_TEXT[kind]
            + (" · hours still count toward the week" if minutes else "")
            + (f" · {row['name']}" if row.get("name") else "")
        )
    elif kind == "weekend":
        verdict = "Weekend hours count toward the week" if minutes else "Weekend"
    elif d > today:
        verdict = "Not yet"
    elif cls == "heat-pending":
        verdict = f"{hours(target - minutes)} h to go today"
    elif minutes >= target:
        verdict = "Target met"
    else:
        verdict = f"{hours(target - minutes)} h under the target"
    return {
        "title": f"{d:%A} {d.day} {d:%B %Y}",
        "kind": TYPE_TEXT.get(kind, kind),
        "colour": HEAT_COLOUR.get(cls, "grey"),
        "verdict": verdict,
        "has_hours": bool(minutes) or kind in ("working", "half_leave"),
        "total": f"{hours(minutes)} h",
        "target": f"of {hours(target)} h target" if counts and kind == "working" else "",
        "fill": min(minutes / target, 1.0) if counts and target else None,
        "billable": f"{hours(row.get('billable_min') or 0)} h",
        "non_billable": f"{hours(row.get('non_billable_min') or 0)} h",
        "projects": [
            {
                "code": p["code"],
                "name": p["name"],
                "text": f"{hours(p.get('billable_min') or 0)} h"
                + (f" + {hours(p['non_billable_min'])} h non-billable" if p.get("non_billable_min") else ""),
            }
            for p in row.get("projects", [])
            if p.get("billable_min") or p.get("non_billable_min")
        ],
    }


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
    if core is not None:  # core wants my-hours rows and my-days rows, not the merged history rows
        hours_rows = [
            {"date": r["date"], "project_name": p["name"], "billable_min": p.get("billable_min") or 0}
            for r in rows
            for p in r.get("projects", [])
        ]
        days = [{"date": r["date"], "working": r["working"]} for r in rows]
        return core(hours_rows, days, targets, month, today)
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
        return "No target set"
    text = f"{row['monthly_h']:g} {'prorated' if row.get('prorate') else 'fixed'}"
    return text + (" · lead's choice" if row.get("source") == "lead" else "")


def no_mapping_cards(rows: list[dict], today: date) -> list[tuple[str, str, str]]:
    """A8: without a PineStem mapping only leave and holidays are known. rows cover this month and the weeks ahead."""
    leave = [r for r in rows if r["type"] in ("leave", "half_leave") and r["date"][:7] == today.isoformat()[:7]]
    days = sum(1.0 if r["type"] == "leave" else 0.5 for r in leave)
    leave_val = "none" if not days else f"{days:g} day" + ("s" if days > 1 else "")
    leave_sub = ", ".join(f"{parse_dt(r['date']).day} {parse_dt(r['date']):%b}" for r in leave)
    hol = next((r for r in rows if r["type"] == "holiday" and r["date"] >= today.isoformat()), None)
    nxt = parse_dt(hol["date"]).date() if hol else None
    return [
        ("This week", "—", "no billing data"),
        (f"Leave · {today:%b}", leave_val, leave_sub),
        ("Next holiday", f"{nxt:%a} {nxt.day} {nxt:%b}" if nxt else "none soon", hol.get("name", "") if hol else ""),
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


def axis_labels(target_min: int, rows: list[dict]) -> tuple[list[str], str, str]:
    """C3 sparkline: y labels top to bottom (target, two thirds, one third, 0 in hours, nearest 5) and the first and last day."""
    top = target_min / 60
    ys = [f"{round(top, 1):g}", *(str(int(round(top * f / 5) * 5)) for f in (2 / 3, 1 / 3)), "0"]
    days = [parse_dt(r["date"]) for r in rows if r["working"]]
    return ys, f"{days[0].day} {days[0]:%b}", f"{days[-1].day} {days[-1]:%b}"


def project_sub(p: dict) -> str:
    """The project row's second line: what the pill (BEHIND 6.5 h, ON TRACK, no target) does not already say."""
    billed = hours(p.get("billed_min") or 0)
    head = f"{billed} / {round((p['target_min'] / 60), 1):g} h" if p.get("target_min") else f"{billed} h"
    return " · ".join(x for x in (head, p.get("need_text")) if x)
