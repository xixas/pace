"""hrms-api responses → engine inputs: no I/O. Shapes from GET /api/calendar/my-days/ and /api/billing-report/my-hours/."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pace.engine import Entry


def work_days(days: list[dict], monday: date) -> list[float]:
    """my-days rows → fraction of each day Mon..Sun that is a working day. Dates the server didn't send count as 0."""
    by_date = {row["date"]: row["working"] for row in days}
    return [by_date.get((monday + timedelta(i)).isoformat(), 0) for i in range(7)]


def record(ledger: dict, rows: list[dict], now: datetime, polled: tuple[date, date] | None = None) -> dict:
    """Fold one my-hours poll into the ledger {date: [[seen_iso, minutes], ...]}: what each day gained, and when Pace saw it.

    polled is the poll's from/to range: a ledger day inside it that the poll didn't return now totals 0.
    """
    totals: dict[str, int] = {}
    if polled:
        totals = {d: 0 for d in ledger if polled[0] <= date.fromisoformat(d) <= polled[1]}
    for row in rows:
        totals[row["date"]] = totals.get(row["date"], 0) + row["billable_min"] + row["non_billable_min"]
    out = {d: [list(part) for part in parts] for d, parts in ledger.items()}
    for d, total in totals.items():
        parts = out.setdefault(d, [])
        gained = total - sum(minutes for _, minutes in parts)
        if gained > 0:
            parts.append([now.isoformat(), gained])
        while gained < 0:  # billed down or deleted: take it back from the latest additions first
            take = min(-gained, parts[-1][1])
            parts[-1][1] -= take
            gained += take
            if not parts[-1][1]:
                parts.pop()
        if not parts:
            del out[d]
    return out


def entries(ledger: dict, monday: date) -> list[Entry]:
    out = []
    for d, parts in ledger.items():
        for_day = (date.fromisoformat(d) - monday).days
        for seen_iso, minutes in parts:
            seen = datetime.fromisoformat(seen_iso)
            out.append(Entry(for_day, (seen.date() - monday).days, seen.hour + seen.minute / 60, minutes))
    return out
