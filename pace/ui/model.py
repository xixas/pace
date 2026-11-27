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
    return f"{round(minutes / 60, 1):g}"


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


COLOURS = ("green", "amber", "red", "blue", "grey")


def colour_class(colour: str | None) -> str:
    """status.json colour → the CSS class of pills, bars and dots; anything unknown reads as grey."""
    return colour if colour in COLOURS else "grey"


def badge_text(status: dict) -> str:
    """The verdict word: "PAY RISK" from "PAY RISK · pay needs 13.9 h · Mon 0 h"."""
    return (status.get("verdict") or status.get("title") or "").split(" · ")[0].upper()


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


DAY_SHARE_MIN = 510  # 8.5 h: what an unbilled day is expected to add (the daily minimum)


def _h1(minutes: float) -> str:
    return f"{minutes / 60:.1f} h"


def runway_caption(status: dict) -> str:
    """The one line under the runway: what is left to the pay line and the target, in words. Same strings as the GNOME menu."""
    logged, lines, days = status.get("logged_min") or 0, status.get("lines") or {}, status.get("days") or []
    lop, target = lines.get("lop_min") or 0, lines.get("target_min") or 0
    pending = [d["dow"] for d in days if d["kind"] == "pending"]
    week_open = any(d["kind"] in OPEN_DAYS for d in days)
    if logged >= target:
        over = logged - target
        return "target met" + (f" · +{_h1(over)}" if over >= 6 else "")
    if logged >= lop:
        return f"pay safe · {_h1(target - logged)} {'to' if week_open else 'under'} target"
    if not week_open:
        return f"{_h1(lop - logged)} under the pay line"
    if (status.get("note") or "").startswith("Last working day"):
        return f"pay needs {_h1(lop - logged)} · {_h1(target - logged)} to target"
    if pending:
        end = f"bill {pending[0]} to finish" if status.get("state") == "bill" else f"{pending[0]} not billed yet"
        return f"{_h1(lop - logged)} to pay line · {end}"
    return f"{_h1(lop - logged)} to pay line · {_h1(target - logged)} to target"


def runway(status: dict, stale: bool = False) -> dict:
    """Direction D. Everything as fractions of the target (the track): fill, the pay-safe band, the pending ghost.

    ink: neutral by default, red only for pay_risk and lop, green when done, grey when stale or offline. Overtime is capped
    at the track end and printed in the caption, never drawn.
    """
    logged, lines, days = status.get("logged_min") or 0, status.get("lines") or {}, status.get("days") or []
    lop, target = lines.get("lop_min") or 0, lines.get("target_min") or 0
    track = max(target, lop, 1)
    fill = min(logged / track, 1.0)
    state = status.get("state")
    ink = (
        "grey"
        if stale or state in ("offline", "on_leave")
        else "red"
        if state in ("pay_risk", "lop")
        else "green"
        if state == "done"
        else "neutral"
    )
    pending = sum(1 for d in days if d["kind"] == "pending")
    ghost = (fill, min(1.0, fill + pending * DAY_SHARE_MIN / track)) if pending and fill < 1 else None
    emphasis = logged < lop and (status.get("note") or "").startswith("Last working day")
    return {
        "fill": fill,
        "band": lop / track,  # where the pay-safe band starts; it runs to the track end
        "ghost": ghost,
        "ink": ink,
        "emphasis": emphasis or (ink == "red" and logged < lop),
        "caption": runway_caption(status),
    }


def day_cards(status: dict, split: dict | None = None) -> list[dict]:
    """The Mon-Fri chips of the week: hours, kind, the small foot line and the project split."""
    need = _need_text(status)
    cards = []
    for d in status.get("days") or []:
        foot = {
            "today": _left_text(status.get("note")),
            "future": need,
            "half_leave": "½ leave",
        }.get(d["kind"], "")
        text = hours(d["min"]) if d["kind"] == "half_leave" and d["min"] else d["text"]  # the tag says "½ leave"
        if d["kind"] in ("holiday", "leave"):
            text = text.capitalize()  # the chip says it once, in its big text
        if d.get("tag"):
            foot = d["tag"].capitalize()  # a day off you billed on: hours in the big text, the day off underneath
        cards.append(
            {
                "date": d["date"],
                "dow": d["dow"],
                "text": text,
                "kind": d["kind"],
                "foot": foot,
                "today": d["kind"] == "today",
                "worked": bool(d.get("tag")),
                "split": (split or {}).get(d["date"], []),
            }
        )
    return cards


def week_view(status: dict, expected_daily_h: float, split: dict | None = None, stale: bool = False) -> dict | None:
    """C1/C2. split: {iso date: [(code, "7.7"), ...]} from pace.history, optional."""
    if status.get("logged_min") is None:
        return None
    logged, lines, days = status["logged_min"], status.get("lines") or {}, status.get("days") or []
    lop, target = lines.get("lop_min") or 0, lines.get("target_min") or status.get("target_min") or 0
    done = [d for d in days if d["kind"] in ("billed", "short")]
    done_min = sum(d["min"] or 0 for d in done)
    pay_sub = "reached" if logged >= lop else f"{hours(lop - logged)} h to go"
    suffix = {"pay_risk": "loss-of-pay risk", "lop": "loss of pay"}.get(status.get("state"))
    if suffix and logged < lop:
        pay_sub += f" · {suffix}"
    stats = [
        _stat(
            "This week",
            f"{hours(logged)} h",
            status.get("subtitle") or "",
            badge_text(status),
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
    cards = day_cards(status, split)
    first = parse_dt(days[0]["date"]) if days else None
    return {
        "stats": stats,
        "bar": runway(status, stale),
        "bar_text": f"{hours(logged)} / {h_short(target)} h",
        "week_label": f"Week of {first.day} {first:%b}" if first else "This week",
        "cards": cards,
        "warning": status.get("warning"),
        "warning_detail": status.get("warning_detail"),
        "colour": "grey" if stale else colour_class(status.get("colour")),
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


def range_label(days: list[dict]) -> str:
    first, last = parse_dt(days[0]["date"]), parse_dt(days[-1]["date"])
    return f"{first.day}–{last.day} {last:%b}"


def empty_state(status: dict) -> dict | None:
    """C5 (AdwStatusPage). None means there are numbers to show."""
    days = status.get("days") or []
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


def leave_widget(status: dict, rules=None) -> dict:
    """The card for a week of leave: when you are back, the month so far, what next week needs. Same data as leave_view."""
    from pace.status import widget_section

    days = status["days"]
    back = back_date(status)
    lines = [f"Away {range_label(days)}"]
    if projects := (status.get("month") or {}).get("projects"):
        lines.append(
            f"{(status.get('month') or {}).get('name') or 'Month'}: "
            + " · ".join(f"{p['code']} {hours(p['billed_min'])} h" for p in projects[:3])
        )
    if rules is not None:
        from pace.engine import lop_line

        lines.append(
            f"Next week needs {h_short(max(rules.target * 5, lop_line(5, rules)))} h, pay line {h_short(lop_line(5, rules))} h"
        )
    return {
        "week": widget_section("ON LEAVE", f"back {back:%a} {back.day} {back:%b}", "grey", "", None, lines),
        "project": None,
    }


def widget_view(status: dict, rules=None) -> dict:
    """What the card shows. Signed out or before the first poll there is no `widget` key."""
    if status.get("state") == "on_leave" and status.get("days"):
        return leave_widget(status, rules)
    w = status.get("widget")
    if not w or "week" not in w:  # also a paced from before 0.1.4 still running after an upgrade
        from pace.status import widget_section

        return {
            "week": widget_section("PACE", "", "grey", "–", None, [status.get("text") or "Sign in to see your week"]),
            "project": None,
        }
    return {k: v and {**v, "colour": colour_class(v["colour"])} for k, v in w.items()}


def _is_working(row: dict) -> bool:
    return bool(row.get("working"))


def back_date(status: dict, rows: list[dict] | None = None) -> date:
    """The first working day after this week's leave: from the history rows when there are any, else next Monday."""
    days = status.get("days") or []
    last = parse_dt(days[-1]["date"]).date() if days else date.today()
    monday = last - timedelta(days=last.weekday())
    nxt = monday + timedelta(days=7)
    if rows:
        later = sorted(r["date"] for r in rows if r["date"] > last.isoformat() and _is_working(r))
        if later:
            return date.fromisoformat(later[0])
    return nxt


def _week_total(rows: list[dict]) -> int:
    return sum((r.get("billable_min") or 0) + (r.get("non_billable_min") or 0) for r in rows)


def leave_view(status: dict, rows: list[dict] | None, rules, split: dict | None = None) -> dict | None:
    """C5 for a week that is all leave or holiday: a calm banner, the day chips, and what still matters around it.

    rows: pace.history rows covering last week and next week (optional). rules: pace.engine.Rules. Everything here is
    derived from status.json, history and settings; nothing new from core.
    """
    from pace.engine import lop_count, lop_line

    days = status.get("days") or []
    if status.get("state") != "on_leave" or not days:
        return None
    first = parse_dt(days[0]["date"]).date()
    back = back_date(status, rows)
    banner = {
        "title": f"On leave · {range_label(days)}, back {back:%a} {back.day} {back:%b}",
        "detail": "No target this week and nothing to bill. Nudges are paused.",
    }
    view = {
        "banner": banner,
        "cards": day_cards(status, split),
        "last_week": None,
        "next_week": None,
        "month": status.get("month"),
    }
    if not rows:
        return view
    prev_monday = first - timedelta(days=7)
    prev = [r for r in rows if prev_monday.isoformat() <= r["date"] < first.isoformat()]
    if any(_is_working(r) for r in prev):
        d = sum(r.get("working") or 0 for r in prev)
        total = _week_total(prev)
        target, lop = max(rules.target * d, lop_line(d, rules)), lop_line(d, rules)
        lost = lop_count(total, d, rules)
        if total >= target:
            verdict, colour = "TARGET MET", "green"
        elif lost == 0:
            verdict, colour = f"PAY SAFE · {_h1(target - total)} under target", "amber"
        else:
            verdict, colour = f"LOSS OF PAY · {lost:g} day{'s' if lost != 1 else ''}", "red"
        view["last_week"] = {
            "label": f"Last week · {prev_monday.day}–{(first - timedelta(days=1)).day} {first - timedelta(days=1):%b}",
            "total": f"{hours(total)} h",
            "caption": f"of {h_short(target)} h target · pay line {h_short(lop)} h",
            "verdict": verdict,
            "colour": colour,
            "days": [
                {
                    "dow": f"{parse_dt(r['date']):%a}",
                    "text": hours((r.get("billable_min") or 0) + (r.get("non_billable_min") or 0)),
                    "kind": r["type"],
                }
                for r in prev
                if r["type"] != "weekend" or _week_total([r])
            ],
        }
    nxt_monday = first + timedelta(days=7)
    nxt = [r for r in rows if nxt_monday.isoformat() <= r["date"] < (nxt_monday + timedelta(days=7)).isoformat()]
    d = sum(r.get("working") or 0 for r in nxt) if nxt else 5.0
    lop = lop_line(d, rules)
    target = max(rules.target * d, lop)
    view["next_week"] = {
        "label": f"Next week · {nxt_monday.day}–{(nxt_monday + timedelta(days=4)).day} {nxt_monday + timedelta(days=4):%b}",
        "days": f"{d:g} working day{'s' if d != 1 else ''}",
        "target": f"{h_short(target)} h",
        "per_day": f"{h_short(target / d)} h/day" if d else "",
        "lop": f"Pay line {h_short(lop)} h. Each {h_short(rules.full)} h counts as a day, a {h_short(rules.part)} h leftover counts as one more; below the line is loss of pay.",
        "estimated": not nxt,
    }
    return view
