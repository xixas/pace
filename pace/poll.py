"""One poll cycle: hrms-api → ledger → engine → status dict. No GTK; the API object comes from pace.client.

state is what paced keeps between polls: {"ledger": ..., "days": [...], "as_of": iso}.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pace.client import Offline, SignedOut
from pace.engine import hours, lop_count, week_verdict
from pace.hrms import entries, record, work_days
from pace.status import lop_text, status


def poll(api, state: dict, now: datetime) -> tuple[dict, dict]:
    monday = now.date() - timedelta(now.weekday())
    start, end = monday - timedelta(7), monday + timedelta(6)  # last week too: its Friday stays open until Monday 12:00
    try:
        days = api.my_days(start, end)
        rows = api.my_hours(start, end)
    except SignedOut:
        return status(None, None, problem="signed_out"), state
    except Offline:
        if not state:
            return status(None, None, problem="offline"), state
        as_of = datetime.fromisoformat(state["as_of"])
        return verdict_status(state, as_of, problem="offline"), state
    ledger = record(state.get("ledger", {}), rows, now, polled=(start, end))
    state = {"ledger": ledger, "days": days, "as_of": now.isoformat()}
    return verdict_status(state, now), state


def verdict_status(state: dict, at: datetime, problem: str | None = None) -> dict:
    monday = at.date() - timedelta(at.weekday())
    hour = at.hour + at.minute / 60
    s = status(week_verdict(work_days(state["days"], monday), entries(state["ledger"], monday), at.weekday(), hour), at, problem)
    s["last_week"] = last_week_banner(state, monday - timedelta(7), 7 + at.weekday(), hour)
    return s


def last_week_banner(state: dict, monday: date, day: int, hour: float) -> dict | None:
    """B12: last week's days still inside their grace, and what the week comes to if they stay unbilled."""
    work = work_days(state["days"], monday)
    v = week_verdict(work, entries(state["ledger"], monday), day, hour)
    if not v.pending:
        return None
    n = lop_count(v.logged, sum(work))
    cost = lop_text(n) if n > 0 else "pay safe"
    return {
        "text": ", ".join(f"{monday + timedelta(i):%a %-d %b}" for i in v.pending) + " not billed yet",
        "if_unbilled": f"{hours(v.logged)} h → {cost}",
    }
