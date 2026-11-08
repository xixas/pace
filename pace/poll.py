"""One poll cycle: hrms-api → ledger → engine → status dict. No GTK; the API object comes from pace.client.

state is what paced keeps between polls: {"ledger": ..., "days": [...], "rows": [...], "as_of": iso, "snoozed_until": iso?, ...}.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from pace.client import Offline, SignedOut
from pace.engine import DAYS, hours, lop_count, week_verdict
from pace.hrms import day_minutes, day_types, entries, record, work_days
from pace.settings import DEFAULTS
from pace.status import PINESTEM_URL, Ctx, Week, lop_text, status
from pace.targets import month_block


def poll(
    api, state: dict, now: datetime, settings: dict | None = None, targets: dict | None = None, fresh: bool = False
) -> tuple[dict, dict]:
    settings = settings or DEFAULTS
    monday = now.date() - timedelta(now.weekday())
    # last week too (its Friday stays open until Monday 12:00), and back to the 1st for the month's projects
    start, end = min(monday - timedelta(7), now.date().replace(day=1)), monday + timedelta(6)
    month_end = now.date().replace(day=calendar.monthrange(now.year, now.month)[1])  # the calendar runs on, for prorating
    retry = now + timedelta(minutes=settings["refresh_minutes"])
    try:
        days = api.my_days(start, max(end, month_end))
        rows = api.my_hours(start, end, fresh=True) if fresh else api.my_hours(start, end)
    except SignedOut:
        return status(None, None, problem="signed_out", ctx=Ctx(refresh_minutes=settings["refresh_minutes"])), state
    except Offline:
        if not state.get("as_of"):
            return status(None, None, problem="offline", ctx=Ctx(retry_at=retry)), state
        as_of = datetime.fromisoformat(state["as_of"])
        return verdict_status(state, as_of, "offline", settings, targets, retry), state
    ledger = record(state.get("ledger", {}), rows, now, polled=(start, end))
    state = {**state, "ledger": ledger, "days": days, "rows": rows, "as_of": now.isoformat()}
    return verdict_status(state, now, settings=settings, targets=targets), state


def verdict_status(
    state: dict,
    at: datetime,
    problem: str | None = None,
    settings: dict | None = None,
    targets: dict | None = None,
    retry_at: datetime | None = None,
) -> dict:
    settings = settings or DEFAULTS
    monday = at.date() - timedelta(at.weekday())
    hour = at.hour + at.minute / 60
    work = work_days(state["days"], monday)
    v = week_verdict(work, entries(state["ledger"], monday), at.weekday(), hour)
    snoozed = datetime.fromisoformat(state["snoozed_until"]) if state.get("snoozed_until") else None
    ctx = Ctx(
        week=Week(monday, at, work, day_types(state["days"], monday), day_minutes(state["ledger"], monday)),
        month=month_block(state.get("rows", []), state["days"], targets or {"projects": []}, at.date()),
        panel_text=settings["panel_text"],
        refresh_minutes=settings["refresh_minutes"],
        expected_daily_h=settings["expected_daily_h"],
        snoozed_until=snoozed if snoozed and snoozed > at else None,
        retry_at=retry_at,
        last_week=last_week_banner(state, monday - timedelta(7), 7 + at.weekday(), hour),
    )
    return status(v, at, problem, ctx)


def last_week_summary(state: dict, at: datetime) -> dict | None:
    """How last week ended, for the Monday nudge; None when it had no working days."""
    monday = at.date() - timedelta(at.weekday() + 7)
    work = work_days(state["days"], monday)
    if not sum(work):
        return None
    v = week_verdict(work, entries(state["ledger"], monday), 7 + at.weekday(), at.hour + at.minute / 60)
    return {"logged_min": v.logged, "target_min": v.target, "lop_days": lop_count(v.logged, sum(work))}


def last_week_banner(state: dict, monday: date, day: int, hour: float) -> dict | None:
    """B12: last week's days still inside their grace, and what the week comes to if they stay unbilled."""
    work = work_days(state["days"], monday)
    v = week_verdict(work, entries(state["ledger"], monday), day, hour)
    if not v.pending:
        return None
    n = lop_count(v.logged, sum(work))
    cost = lop_text(n) if n > 0 else "pay safe"
    first = next((i for i, w in enumerate(work_days(state["days"], monday + timedelta(7))) if w), 0)
    deadline = "today" if first == day - 7 else DAYS[first]
    unbilled = ", ".join(f"{monday + timedelta(i):%a %-d %b}" for i in v.pending)
    return {
        "text": f"Last week: {unbilled} not billed yet",
        "detail": f"Bill by 12:00 {deadline} or it counts as {hours(v.logged)} h → {cost}.",
        "url": PINESTEM_URL,
    }
