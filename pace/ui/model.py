"""Pure view models for the dashboard and mini widget: status.json in, plain dicts out. No GTK, so pytest runs them.

Frontends never recompute verdict maths (contract section 1); what is derived here is display only (averages, bar scale).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

KNOWN_VERSION = 1
FALLBACK_STALE = timedelta(minutes=15)
FINISHED = ("billed", "short", "half_leave")
OPEN_DAYS = ("today", "future", "pending")


def hours(minutes: int | float | None, places: int = 1) -> str:
    return "–" if minutes is None else f"{minutes / 60:.{places}f}"


def h_short(minutes: int | float) -> str:
    """41 h, 42.5 h: no trailing zero."""
    return f"{minutes / 60:g}"


def parse_dt(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def as_of_text(status: dict, now: datetime) -> str:
    as_of = parse_dt(status.get("as_of"))
    if not as_of:
        return "never"
    minutes = int((now - as_of).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    return f"{minutes // 60} h ago"


def is_stale(status: dict, now: datetime) -> bool:
    as_of = parse_dt(status.get("as_of"))
    limit = parse_dt(status.get("stale_after")) or (as_of + FALLBACK_STALE if as_of else None)
    return bool(limit and now > limit)


def skew(status: dict) -> str | None:
    """C10. "app_old": status.json is newer than this app. "service_old": paced is older than this app."""
    v = status.get("version")
    if v is None or v == KNOWN_VERSION:
        return None
    return "app_old" if v > KNOWN_VERSION else "service_old"


def _stat(label, value, sub="", badge=None):
    return {"label": label, "value": value, "sub": sub, "badge": badge}


def _left_text(note: str | None) -> str:
    m = re.match(r"([\d.]+) h left today", note or "")
    return f"{m.group(1)} left" if m else (note or "")


def _need_text(status: dict) -> str:
    m = re.search(r"needs ([\d.]+)", status.get("subtitle") or "")
    return f"needs {m.group(1)}" if m else ""


def _projected(status: dict, expected_daily_h: float):
    """Finished days as billed, today and later at the expected daily hours (today never below what is already in)."""
    days = status.get("days") or []
    if not any(d["kind"] in OPEN_DAYS for d in days):
        return None
    total = 0.0
    for d in days:
        if d["kind"] in FINISHED:
            total += d["min"] or 0
        elif d["kind"] in OPEN_DAYS:
            total += max(d["min"] or 0, expected_daily_h * 60)
    last = [d["dow"] for d in days if d["kind"] in FINISHED + OPEN_DAYS][-1]
    return last, total


def week_view(status: dict, expected_daily_h: float, split: dict | None = None) -> dict | None:
    """C1/C2. split: {iso date: [(code, "7.7"), ...]} from pace.history, optional."""
    if status.get("logged_min") is None:
        return None
    logged, lines, days = status["logged_min"], status.get("lines") or {}, status.get("days") or []
    lop, target, expected = (
        lines.get("lop_min") or 0,
        lines.get("target_min") or status.get("target_min") or 0,
        lines.get("expected_min") or 0,
    )
    done = [d for d in days if d["kind"] in ("billed", "short")]
    done_min = sum(d["min"] or 0 for d in done)
    pay_sub = "reached" if logged >= lop else f"{hours(lop - logged)} h to go"
    suffix = {"pay_risk": "LOP risk", "lop": "LOP"}.get(status.get("state"))
    if suffix and logged < lop:
        pay_sub += f" · {suffix}"
    stats = [
        _stat(
            "This week",
            f"{hours(logged)} h",
            status.get("subtitle") or "",
            (status.get("verdict") or status.get("title") or "").upper(),
        ),
        _stat(
            "Average / working day",
            f"{done_min / len(done) / 60:.2f} h" if done else "–",
            f"{len(done)} finished days · {hours(done_min)} h" if done else "no finished day yet",
        ),
        _stat("Pay line", f"{h_short(lop)} h", pay_sub),
    ]
    half = [d for d in days if d["kind"] == "half_leave"]
    if half:
        stats.insert(1, _stat("Target", f"{h_short(target)} h", f"half-day leave {half[0]['dow']}"))
    elif (p := _projected(status, expected_daily_h)) is not None:
        stats.append(_stat(f"Projected {p[0]}", f"{p[1] / 60:.1f} h", f"at the {expected_daily_h:.1f} h/day expected pace"))
    need = _need_text(status)
    cards = []
    for d in days:
        foot = {
            "today": _left_text(status.get("note")),
            "future": need,
            "half_leave": "½ leave",
            "holiday": "Holiday",
            "leave": "Leave",
        }.get(d["kind"], "")
        text = hours(d["min"]) if d["kind"] == "half_leave" and d["min"] else d["text"]  # the tag says "½ leave"
        cards.append(
            {
                "date": d["date"],
                "dow": d["dow"],
                "text": text,
                "kind": d["kind"],
                "foot": foot,
                "today": d["kind"] == "today",
                "split": (split or {}).get(d["date"], []),
            }
        )
    first = parse_dt(days[0]["date"]) if days else None
    return {
        "stats": stats,
        "bar": {"logged": logged, "lop": lop, "target": target, "expected": expected, "max": max(logged, target, expected, 1)},
        "bar_text": f"{hours(logged)} / {h_short(target)} h",
        "week_label": f"Week of {first.day} {first:%b}" if first else "This week",
        "cards": cards,
        "warning": status.get("warning"),
        "warning_detail": status.get("warning_detail"),
        "colour": status.get("colour") or "grey",
    }


def banner(status: dict) -> dict | None:
    """The one strip above the dashboard. Session problems beat the last-week reminder."""
    problem = (status.get("problem") or {}).get("kind")
    if status.get("state") == "signed_out" or problem == "signed_out":
        return {"kind": "signed_out", "text": "Your sign-in expired", "button": "Sign in again"}
    if problem == "no_mapping" or status.get("state") == "no_mapping":
        return {"kind": "no_mapping", "text": "Your DhiHRMS profile isn't linked to PineStem. Ask HR.", "button": "Dismiss"}
    if problem == "offline":
        return {"kind": "offline", "text": status["problem"].get("message") or "Can't reach DhiHRMS", "button": None}
    if last := status.get("last_week"):
        return {
            "kind": "last_week",
            "text": last["text"] + (f". {last['detail']}" if last.get("detail") else ""),
            "button": "Open PineStem",
            "url": last.get("url"),
        }
    return None


def _range_label(days: list[dict]) -> str:
    first, last = parse_dt(days[0]["date"]), parse_dt(days[-1]["date"])
    return f"{first.day}–{last.day} {last:%b}"


def empty_state(status: dict) -> dict | None:
    """C5 (AdwStatusPage). None means there are numbers to show."""
    days = status.get("days") or []
    if status.get("state") == "on_leave" and days:
        return {
            "icon": "weather-clear-symbolic",
            "title": "Enjoy your leave",
            "body": "The whole week is leave or holiday, so there is no target and nothing to bill. Nudges are paused.",
            "pill": f"ON LEAVE · {_range_label(days)}",
        }
    if joined := status.get("joined"):  # optional key, see report: not in contract v1
        return {
            "icon": "avatar-default-symbolic",
            "title": "Targets start from your joining date",
            "body": joined.get("text", ""),
            "pill": joined.get("pill"),
        }
    if status.get("logged_min") == 0 and not any(d["kind"] in FINISHED for d in days):
        target = status.get("target_min")
        today = next((d for d in days if d["kind"] == "today"), None)
        lead = "It is Monday morning. " if today and today["dow"] == "Mon" else ""
        return {
            "icon": "document-open-recent-symbolic",
            "title": "Nothing billed yet this week",
            "body": f"{lead}Hours appear here as soon as you bill them in PineStem."
            + (f" Target for the week is {h_short(target)} h." if target else ""),
            "pill": None,
            "button": "Open PineStem",
        }
    return None


def week_split(rows: list[dict]) -> dict:
    """history rows → {iso date: [(code, "7.7")]} billable hours per project, for the day cards."""
    out = {}
    for r in rows:
        out[r["date"]] = [(p["code"], hours(p["billable_min"])) for p in r.get("projects", []) if p.get("billable_min")]
    return out


def week_bounds(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def widget_view(status: dict) -> dict:
    """What the card shows. Signed out or before the first poll there is no `widget` key."""
    w = status.get("widget")
    if not w:
        return {
            "title": "Pace",
            "big": "–",
            "side": "",
            "lines": [status.get("text") or "Sign in to see your week"],
            "project": None,
            "colour": "grey",
        }
    return {**w, "colour": status.get("colour") or "grey"}
