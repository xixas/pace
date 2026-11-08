"""Day-by-day hours and calendar for any range (contract section 3a), for the app's dashboard. No GTK."""

from __future__ import annotations

from datetime import date, timedelta

from pace import targets

MAX_DAYS = 92  # hrms-api's longest range per call


def load(start: date, end: date, api=None) -> list[dict]:
    """One dict per date from start to end. Raises pace.client.Offline / SignedOut."""
    if api is None:
        from pace.cli import client, load_config

        api = client(load_config())
    codes = {p["name"]: p["code"] for p in targets.load()["projects"]}
    days, rows = [], []
    for a, b in chunks(start, end):
        days += api.my_days(a, b)
        rows += api.my_hours(a, b)
    return [day(d, [r for r in rows if r["date"] == d["date"]], codes) for d in days]


def chunks(start: date, end: date):
    while start <= end:
        stop = min(end, start + timedelta(MAX_DAYS - 1))
        yield start, stop
        start = stop + timedelta(1)


def day(d: dict, rows: list[dict], codes: dict) -> dict:
    return {
        "date": d["date"],
        "type": d.get("type", "working"),
        "working": float(d["working"]) if d["working"] else 0,
        "billable_min": sum(r["billable_min"] for r in rows),
        "non_billable_min": sum(r["non_billable_min"] for r in rows),
        "projects": [
            {
                "code": codes.get(r["project_name"], r["project_name"][:3].upper()),
                "name": r["project_name"],
                "billable_min": r["billable_min"],
                "non_billable_min": r["non_billable_min"],
            }
            for r in rows
        ],
    }
