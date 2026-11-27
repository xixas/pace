"""status.json: the one file the panel extension, tray and mini widget read. No GTK. Keys and wording: docs/contract.md section 1.

Panel text follows the B1 mockup in docs/design.html. Bump VERSION on any breaking change to the keys.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from pace.engine import DAYS, DEFAULT, EOD, MAXDAY, Rules, Verdict, hours, lop_count, lop_line
from pace.files import state_dir, write_json
from pace.targets import MINUS

VERSION = 1
PINESTEM_URL = "https://pinestem.com/dashboard.html#/tasks"
OFFLINE_MESSAGE = "Can't reach DhiHRMS"
STALE_POLLS = 3  # stale_after = as_of + this many refresh intervals


# engine verdict → (state, colour, icon). Colours are the claude-usage palette names the extension maps to hex.
LOOK = {
    "ON TRACK": ("on_track", "green", "dot"),
    "AHEAD": ("ahead", "green", "triangle"),
    "TIGHT": ("tight", "amber", "dot"),
    "BEHIND": ("behind", "amber", "dot"),
    "PAY RISK": ("pay_risk", "red", "dot"),
    "BILL": ("bill", "blue", "ring"),
    "DONE": ("done", "green", "check"),
    "SHORT (pay safe)": ("short", "amber", "dot"),
    "LOP": ("lop", "red", "dot"),
    "ON LEAVE": ("on_leave", "grey", "circle"),
}
TITLES = {
    "on_track": "On track",
    "ahead": "Ahead",
    "tight": "Tight",
    "behind": "Behind",
    "pay_risk": "Pay at risk",
    "bill": "Bill your hours",
    "done": "Done",
    "short": "Short, pay safe",
    "lop": "Loss of pay",
    "on_leave": "On leave",
}
WIDGET_WORD = {"pay_risk": "pay risk", "bill": "bill", "short": "short", "lop": "loss of pay", "offline": "offline"}
NEEDY = ("on_track", "ahead", "tight")  # states whose subtitle is "needs N h/day"
PAY_NEEDS = re.compile(r" · (pay needs [\d.]+ h)")
ADDED = (
    "stale_after title subtitle note lines days warning warning_detail action gap_text month labels problem snoozed_until "
    "pinestem_url last_week tray widget"
).split()


@dataclass
class Week:
    """The calendar side of this week: what the verdict was computed from, so the days can be shown."""

    monday: date
    at: datetime
    work: list[float]  # Mon..Sun: 1, 0.5, 0
    types: list[str]  # Mon..Sun: working, weekend, holiday, leave, half_leave
    minutes: list[int]  # Mon..Sun: billable + non-billable


@dataclass
class Ctx:
    week: Week | None = None
    month: dict | None = None  # targets.month_block()
    panel_text: str = "hours"
    refresh_minutes: int = 15
    expected_daily_h: float = 9.0
    snoozed_until: datetime | None = None
    retry_at: datetime | None = None
    last_week: dict | None = None
    rules: Rules = DEFAULT


def look(v: Verdict) -> tuple[str, str, str]:
    head = v.label.split(" · ")[0]
    return LOOK["LOP" if head.startswith("LOP ") else head]


def status(v: Verdict | None, as_of: datetime | None, problem: str | None = None, ctx: Ctx | None = None) -> dict:
    """v and as_of are the last good fetch. problem: "offline" (keep the numbers, greyed), "signed_out" or "no_mapping"."""
    ctx = ctx or Ctx()
    s = dict.fromkeys(("state", "colour", "icon", "text", "verdict", "logged_min", "target_min"))
    s = {"version": VERSION, "as_of": as_of.isoformat() if as_of else None, **s, **dict.fromkeys(ADDED)}
    s["pinestem_url"] = PINESTEM_URL
    if as_of:
        s["stale_after"] = (as_of + timedelta(minutes=ctx.refresh_minutes * STALE_POLLS)).isoformat()
    if ctx.snoozed_until:
        s["snoozed_until"] = ctx.snoozed_until.isoformat()
    if problem in ("signed_out", "no_mapping") or v is None:
        state, colour, icon, text = bare_look(problem)
        s.update(state=state, colour=colour, icon=icon, text=text, problem=problem_info(problem or "offline", ctx))
        s["tray"], s["widget"] = bare_tray(text), bare_widget(text)
        return s
    state, colour, icon = base_look = look(v)
    base = base_look[0]
    labels = make_labels(v, base, ctx)
    text = "" if ctx.panel_text == "icon" else labels[ctx.panel_text]
    if problem == "offline":
        state, colour, icon = "offline", "grey", "circle"
        text = f"{text} · {as_of:%H:%M}" if text else ""
        s["problem"] = problem_info("offline", ctx)
    s.update(state=state, colour=colour, icon=icon, text=text, verdict=v.label, logged_min=v.logged, target_min=v.target)
    s.update(week_fields(v, base, ctx), labels=labels, last_week=ctx.last_week)
    s["tray"], s["widget"] = tray(s, v, base, labels, as_of), widget(s, v, base, ctx, as_of)
    return s


def bare_look(problem: str | None) -> tuple[str, str, str, str]:
    if problem == "signed_out":
        return "signed_out", "amber", "dot", "Sign in again"
    if problem == "no_mapping":
        return "no_mapping", "grey", "circle", "No billing data"
    return "offline", "grey", "circle", "Offline"


def problem_info(kind: str, ctx: Ctx) -> dict:
    message = {
        "offline": OFFLINE_MESSAGE,
        "signed_out": "Your sign-in expired. Sign in again.",
        "no_mapping": "Your DhiHRMS profile isn't linked to PineStem. Ask HR.",
    }[kind]
    retry = ctx.retry_at.isoformat() if kind == "offline" and ctx.retry_at else None
    return {"kind": kind, "message": message, "retry_at": retry}


def week_fields(v: Verdict, base: str, ctx: Ctx) -> dict:
    days = day_rows(v, ctx.week, ctx.rules) if ctx.week else None
    short = [d for d in days or [] if d["kind"] == "short"]
    show_warning = short and base not in ("done", "on_leave")
    return {
        "title": TITLES[base],
        "subtitle": subtitle(v, base),
        "note": note(v, base, ctx),
        "lines": lines(v, base, ctx),
        "days": days,
        "warning": "Short days: " + " · ".join(f"{d['dow']} {d['text']} h" for d in short) if show_warning else None,
        "warning_detail": warning_detail(v, ctx) if base == "pay_risk" else None,
        "action": action(v, base, ctx),
        "gap_text": gap_text(v, base),
        "month": ctx.month,
    }


def last_day_gap(v: Verdict, base: str) -> bool:
    """Last working day, under the pay line, and not a pay-risk week (that one has its own red warning)."""
    return base in NEEDY + ("behind",) and bool(PAY_NEEDS.search(v.label))


def day_rows(v: Verdict, wk: Week, rules: Rules = DEFAULT) -> list[dict]:
    today = wk.at.weekday()
    past_today = wk.at.hour + wk.at.minute / 60 >= EOD
    out = []
    for i in range(7):
        m = wk.minutes[i]
        if i > 4 and not m:
            continue
        kind, text = day_kind(i, m, wk, v, today, past_today, rules)
        row = {
            "date": (wk.monday + timedelta(i)).isoformat(),
            "dow": DAYS[i],
            "min": None if kind in ("future", "pending") else m,
            "kind": kind,
            "text": text,
        }
        if m and kind in ("holiday", "leave", "half_leave"):
            row["tag"] = "½ leave" if kind == "half_leave" else kind  # billed on a day off: hours shown, tag says why
        out.append(row)
    return out


def day_kind(i: int, m: int, wk: Week, v: Verdict, today: int, past_today: bool, rules: Rules = DEFAULT) -> tuple[str, str]:
    w = wk.work[i]
    if not w:
        kind = wk.types[i] if wk.types[i] in ("holiday", "leave") else "weekend" if i > 4 else "holiday"
        return kind, hours(m) if kind == "weekend" or m else kind  # a billed holiday shows its hours
    if i == today and not past_today:
        return "today", hours(m)
    if i > today:
        return ("half_leave", "½ leave") if w < 1 else ("future", "–")
    if i in v.pending:
        return "pending", "not yet"
    if m < rules.target * w - 15:
        return "short", hours(m)
    return ("half_leave", hours(m)) if w < 1 else ("billed", hours(m))


def subtitle(v: Verdict, base: str) -> str | None:
    if base in ("pay_risk", "bill"):
        return f"{hours(v.logged)} / {hours(v.target)} h"
    if base in NEEDY:
        m = PAY_NEEDS.search(v.label)
        return m.group(1) if m else f"needs {hours(v.need)} h/day" if v.need is not None else None
    return {
        "behind": lambda: f"pay needs {hours(v.lop_need)} h/day",
        "done": lambda: f"{hours(v.logged)} h",
        "short": lambda: "pay safe",
        "lop": lambda: lop_text(float(v.label.split(" · ")[0].removeprefix("LOP ").removesuffix("d"))),
    }.get(base, lambda: None)()


def note(v: Verdict, base: str, ctx: Ctx) -> str | None:
    if base == "on_leave":
        return "No target this week"
    if base == "bill":
        return f"{', '.join(DAYS[i] for i in v.pending)} not billed yet"
    if base == "pay_risk":
        return pay_risk_note(v, ctx)
    if base in NEEDY + ("behind",):
        if last_day_gap(v, base):
            return f"Last working day · {hours(v.logged)} of the {hours(v.lop, trim=True)} h line"
        if v.today_left is not None:
            return f"{hours(v.today_left)} h left today"
    return None


def pay_today(v: Verdict, ctx: Ctx) -> float:
    """Minutes still to bill today to stay within reach of the pay line."""
    w = ctx.week.work[ctx.week.at.weekday()] if ctx.week else 1
    return max(0, v.lop_need * w - v.today)


def pay_risk_note(v: Verdict, ctx: Ctx) -> str:
    line, limit = hours(v.lop, trim=True), hours(MAXDAY)
    if v.lop_need is None:
        return f"{hours(v.lop - v.base)} h short of the {line} h line."
    if v.today_left is not None:
        return f"Needs {hours(pay_today(v, ctx))} h today to reach {line} h. The limit is {limit} h/day."
    return f"Needs {hours(v.lop_need)} h/day to reach {line} h. The limit is {limit} h/day."


def warning_detail(v: Verdict, ctx: Ctx) -> str | None:
    if not ctx.week:
        return None
    best = v.base + MAXDAY * v.rem
    gap = v.lop - best
    if gap <= 0:
        return None
    n = lop_count(best, sum(ctx.week.work), ctx.rules)
    cost = f"about {n:g} {'day' if n <= 1 else 'days'} of loss of pay"
    if v.rem == 0:
        return f"The week ends {hours(gap)} h under the line, {cost}."
    when = f"Even {hours(MAXDAY)} h today" if v.rem <= 1 else f"Even {hours(MAXDAY)} h a day from now"
    return f"{when} ends {hours(gap)} h under the line, {cost}."


def lines(v: Verdict, base: str, ctx: Ctx) -> dict | None:
    d = sum(ctx.week.work) if ctx.week else 0
    if not d:
        return None
    emphasis = "lop" if base == "pay_risk" or last_day_gap(v, base) else None
    return {
        "lop_min": lop_line(d, ctx.rules),
        "target_min": v.target,
        "expected_min": round(ctx.expected_daily_h * 60 * d),
        "emphasis": emphasis,
    }


def gap_text(v: Verdict, base: str) -> str | None:
    """B3: the last working day's two gaps."""
    if not last_day_gap(v, base):
        return None
    return f"{hours(max(0, v.lop - v.base - v.today))} h to the loss-of-pay line · {hours(max(0, v.target - v.base - v.today))} h to target"


def action(v: Verdict, base: str, ctx: Ctx) -> dict | None:
    if base == "pay_risk":
        label = "Open PineStem to bill" + (f" {DAYS[ctx.week.at.weekday()]}" if ctx.week else "")
    elif base == "bill":
        label = f"Open PineStem to bill {', '.join(DAYS[i] for i in v.pending)}"
    elif last_day_gap(v, base):
        label = f"Bill {hours(max(0, v.lop - v.base - v.today), trim=True)} h to stay clear of loss of pay"
    else:
        return None
    return {"label": label, "url": PINESTEM_URL}


def make_labels(v: Verdict, base: str, ctx: Ctx) -> dict:
    """Every panel text format (B11); `text` picks one by settings.panel_text."""
    hrs = panel_text(base, v)
    if base == "on_leave":
        return dict.fromkeys(("hours", "percent", "gap", "left_today"), hrs)
    return {
        "hours": hrs,
        "percent": f"{math.floor(v.logged * 100 / v.target + 0.5)}%" if v.target else hrs,
        "gap": gap_label(ctx) or hrs,
        "left_today": f"{hours(v.today_left)} h left today" if v.today_left is not None else hrs,
    }


def gap_label(ctx: Ctx) -> str | None:
    tracked = [p for p in (ctx.month or {}).get("projects", []) if p["gap_min"] is not None]
    if not tracked:
        return None
    p = min(tracked, key=lambda p: p["gap_min"])
    sign = MINUS if p["gap_min"] < 0 else "+"
    return f"{sign}{hours(abs(p['gap_min']))} h {p['code']}"


def first_project(month: dict | None) -> dict | None:
    """The project the tray and widget show: the first with a target (the month list has those first)."""
    return next((p for p in (month or {}).get("projects", []) if p["target_min"] is not None), None)


def project_short(p: dict) -> str:
    return p["short"] or f"{p['name']} {'under pace' if p['gap_min'] < 0 else 'on pace'}"


def short_days_line(s: dict) -> list[str]:
    short = [d for d in s["days"] or [] if d["kind"] == "short"]
    return [" · ".join(f"{d['dow']} {d['text']} h" for d in short)] if short else []


def tray(s: dict, v: Verdict, base: str, labels: dict, as_of: datetime) -> dict:
    first = labels["hours"]
    if base in NEEDY and s["subtitle"] and " · " not in first:
        first += f" · {s['subtitle']}"
    title = f"Pace — Week · {s['title']}" + (f" (offline, {as_of:%H:%M})" if s["state"] == "offline" else "")
    month, p = s["month"], first_project(s["month"])
    tip, rows = [first], [f"Week · {s['title']} — {labels['hours'].split(' · ')[0]}"]
    needs = s["subtitle"].capitalize() if base in NEEDY + ("behind",) and s["subtitle"] else None
    extra = " · ".join(x for x in (needs, s["note"]) if x)
    if extra:
        rows.append(extra[0].upper() + extra[1:])
    if p:
        sign = MINUS if p["gap_min"] < 0 else "+"
        mon = month["name"][:3]
        tip.append(
            f"{p['name']} {mon} {hours(p['billed_min'])} / {hours(p['target_min'], trim=True)} h ({sign}{hours(abs(p['gap_min']))})"
        )
        rows.append(f"{project_short(p)} ({mon})")
    fill = min(1, v.logged / v.target) if v.target else 0
    return {
        "number": str(math.floor(v.logged / 60 + 0.5)),
        "tooltip_title": title,
        "tooltip_lines": tip,
        "info_rows": rows,
        "fill": round(fill, 2),
    }


def widget_section(label: str, word: str, colour: str, big: str, fill: float | None, lines: list[str]) -> dict:
    """One block of the mini widget (the GTK card and the shell widget draw the same keys): header, big numbers, bar, captions."""
    return {
        "label": label,
        "word": word,
        "colour": colour,
        "big": big,
        "unit": "h" if big and big[0].isdigit() else "",
        "fill": fill,
        "lines": lines,
    }


def week_caption(s: dict, v: Verdict, base: str, ctx: Ctx, as_of: datetime) -> list[str]:
    if s["state"] == "offline":
        return [f"as of {as_of:%H:%M} · {OFFLINE_MESSAGE}, retrying"]
    if base in NEEDY and v.need is not None:
        return [f"{hours(v.need)} h/day to reach {hours(v.target, trim=True)} h"]
    if base == "behind":
        return [f"pay needs {hours(v.lop_need)} h/day"]
    if base == "pay_risk":
        needed = [f"{hours(pay_today(v, ctx))} h needed today"] if v.lop_need is not None and v.today_left is not None else []
        return needed + short_days_line(s)
    if base == "bill":
        return [s["note"]]
    return []


def project_section(month: dict, p: dict) -> dict:
    colour = "amber" if p["at_risk"] else "grey" if p["gap_min"] < 0 else "green"
    word = p["text"].rsplit(" · ", 1)[1]
    left = month["working_days_left"]
    caption = (
        [f"{hours(p['need_per_day_min'])} h/day"]
        if p["need_per_day_min"]
        else ["target met"]
        if p["billed_min"] >= p["target_min"]
        else []
    )
    if left and p["billed_min"] < p["target_min"]:
        caption.append(f"{left} {'day' if left == 1 else 'days'} left")
    big = f"{hours(p['billed_min'], trim=True)} / {hours(p['target_min'], trim=True)}"
    fill = min(1, p["billed_min"] / p["target_min"]) if p["target_min"] else 0
    return widget_section(
        f"{p['name']} · {month['name'][:3]}".upper(), word, colour, big, round(fill, 2), [" · ".join(caption)] if caption else []
    )


def widget(s: dict, v: Verdict, base: str, ctx: Ctx, as_of: datetime) -> dict:
    offline = s["state"] == "offline"
    word = "offline" if offline else WIDGET_WORD.get(base, s["title"].lower())
    big = (
        hours(v.logged, trim=True)
        if base == "done"
        else f"{hours(v.logged, trim=True)} / {hours(v.target, trim=True)}"
        if v.target
        else ""
    )
    fill = round(min(1, v.logged / v.target), 2) if v.target else None
    week = widget_section("THIS WEEK", word, s["colour"], big, fill, week_caption(s, v, base, ctx, as_of))
    p = first_project(s["month"])
    return {"week": week, "project": project_section(s["month"], p) if p else None}


def bare_tray(text: str) -> dict:
    return {"number": "–", "tooltip_title": f"Pace — {text}", "tooltip_lines": [], "info_rows": [text], "fill": 0.0}


def bare_widget(text: str) -> dict:
    return {"week": widget_section("PACE", "", "grey", "", None, [text]), "project": None}


def panel_text(state: str, v: Verdict) -> str:
    if state == "on_leave":
        return "On leave"
    if state == "done":
        return f"{hours(v.logged)} h"
    if state == "lop":
        return f"{hours(v.logged)} h · {lop_text(float(v.label.split(' · ')[0].removeprefix('LOP ').removesuffix('d')))}"
    text = f"{hours(v.logged)} / {hours(v.target)} h"
    if state == "behind":
        return f"{text} · pay {hours(v.lop_need)}/day"
    if state == "pay_risk":
        return f"{text} · pay risk"
    if state == "short":
        return f"{text} · pay safe"
    if m := PAY_NEEDS.search(v.label):  # last working day under the pay line: the gap is always in the label
        return f"{text} · {m.group(1)}"
    return text


def lop_text(n: float) -> str:
    return f"LOP {n:g} {'day' if n <= 1 else 'days'}"


def write_status(s: dict) -> Path:
    return write_json(state_dir() / "status.json", s)
