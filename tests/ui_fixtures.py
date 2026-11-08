"""Hand-made status.json and history rows for the UI tests and screenshots. Mirrors docs/contract.md section 1 and 3a."""

from __future__ import annotations

from datetime import date, timedelta


def day(d, dow, minutes, kind, text):
    return {"date": d, "dow": dow, "min": minutes, "kind": kind, "text": text}


def status_on_track() -> dict:
    return {
        "version": 1,
        "as_of": "2026-10-29T14:10:00",
        "stale_after": "2026-10-29T14:55:00",
        "state": "on_track",
        "colour": "green",
        "icon": "dot",
        "text": "30.1 / 42.5 h",
        "verdict": "ON TRACK",
        "logged_min": 1806,
        "target_min": 2550,
        "title": "On track",
        "subtitle": "needs 8.0 h/day",
        "note": "4.5 h left today",
        "lines": {"lop_min": 2460, "target_min": 2550, "expected_min": 2700},
        "days": [
            day("2026-10-26", "Mon", 552, "billed", "9.2"),
            day("2026-10-27", "Tue", 504, "billed", "8.4"),
            day("2026-10-28", "Wed", 540, "billed", "9.0"),
            day("2026-10-29", "Thu", 210, "today", "3.5"),
            day("2026-10-30", "Fri", None, "future", "–"),
        ],
        "warning": None,
        "warning_detail": None,
        "action": {"label": "Open PineStem to bill Fri", "url": "https://pinestem.com/dashboard.html#/tasks"},
        "month": {
            "name": "October",
            "working_days_left": 2,
            "projects": [
                {
                    "code": "TWE",
                    "name": "Tweelin",
                    "billed_min": 6750,
                    "target_min": 7980,
                    "gap_min": -390,
                    "need_per_day_min": 618,
                    "text": "112.5 / 133 h · behind 6.5",
                    "need_text": "needs 10.3 h/day on Tweelin",
                    "short": "Tweelin −6.5 h",
                },
                {
                    "code": "RES",
                    "name": "R&D",
                    "billed_min": 1104,
                    "target_min": None,
                    "gap_min": None,
                    "need_per_day_min": None,
                    "text": "18.4 h · no target",
                    "need_text": None,
                    "short": None,
                },
            ],
        },
        "labels": {"hours": "30.1 / 42.5 h", "percent": "71%", "gap": "−6.5 h TWE", "left_today": "4.5 h left today"},
        "problem": None,
        "snoozed_until": None,
        "pinestem_url": "https://pinestem.com/dashboard.html#/tasks",
        "last_week": None,
        "widget": {
            "title": "Week on track",
            "big": "30.1 / 42.5",
            "side": "8.0/day",
            "lines": [],
            "project": {"title": "Tweelin −6.5 h", "big": "112.5 / 133", "side": "10.3/day"},
        },
    }


def status_pay_risk_half_leave() -> dict:
    s = status_on_track()
    s.update(
        state="pay_risk",
        verdict="PAY RISK",
        colour="red",
        title="Pay at risk",
        subtitle="pay needs 13.9 h",
        note=None,
        logged_min=1626,
        target_min=2460,
        lines={"lop_min": 2460, "target_min": 2460, "expected_min": 2700},
        warning="Short days (under 8.25 h): Mon 8.2 h · Tue 7.4 h · Wed 8.0 h",
        warning_detail="HR still needs 41 h for zero loss of pay with a half-day leave, so the target is 41 h, not 38.25.",
        days=[
            day("2026-10-26", "Mon", 492, "short", "8.2"),
            day("2026-10-27", "Tue", 444, "short", "7.4"),
            day("2026-10-28", "Wed", 480, "short", "8.0"),
            day("2026-10-29", "Thu", 210, "half_leave", "½ leave"),
            day("2026-10-30", "Fri", None, "future", "–"),
        ],
    )
    s["widget"] = {
        "title": "Week pay risk",
        "big": "27.1 / 42.5",
        "side": "13.9 today",
        "lines": ["Wed 6.0 h · Thu 3.5 h"],
        "project": None,
    }
    return s


def history_rows(first: date, last: date, today: date) -> list[dict]:
    """Mon-Fri 8-9 h of TWE/RES, the 2nd a holiday, the 9th leave, nothing after today."""
    rows, d = [], first
    while d <= last:
        kind, working, bill, non = "working", 1.0, 0, 0
        if d.weekday() >= 5:
            kind, working = "weekend", 0
        elif d.day == 2:
            kind, working = "holiday", 0
        elif d.day == 9:
            kind, working = "leave", 0
        elif d <= today:
            bill, non = 450 + (d.day % 5) * 20, 20
        projects = (
            [
                {"code": "TWE", "name": "Tweelin", "billable_min": bill - 80, "non_billable_min": 0},
                {"code": "RES", "name": "R&D", "billable_min": 80, "non_billable_min": non},
            ]
            if bill
            else []
        )
        rows.append(
            {
                "date": d.isoformat(),
                "type": kind,
                "working": working,
                "billable_min": bill,
                "non_billable_min": non,
                "projects": projects,
            }
        )
        d += timedelta(days=1)
    return rows
