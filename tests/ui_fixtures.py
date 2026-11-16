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
            "week": section("THIS WEEK", "on track", "green", "30.1 / 42.5", 0.71, ["8.0 h/day to reach 42.5 h"]),
            "project": section("TWEELIN · OCTOBER", "behind 6.5 h", "amber", "112.5 / 133", 0.85, ["10.3 h/day · 2 days left"]),
        },
    }


def section(label, word, colour, big, fill, lines) -> dict:
    return {"label": label, "word": word, "colour": colour, "big": big, "unit": "h" if big else "", "fill": fill, "lines": lines}


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
        warning_detail="Thu +1.75 h and Fri 10.5 h at most make 12.25 h, short of the 13.9 h still needed.",
        days=[
            day("2026-10-26", "Mon", 492, "short", "8.2"),
            day("2026-10-27", "Tue", 444, "short", "7.4"),
            day("2026-10-28", "Wed", 480, "short", "8.0"),
            day("2026-10-29", "Thu", 210, "half_leave", "½ leave"),
            day("2026-10-30", "Fri", None, "future", "–"),
        ],
    )
    s["widget"] = {
        "week": section("THIS WEEK", "pay risk", "red", "27.1 / 42.5", 0.64, ["13.9 h needed today", "Wed 6.0 h · Thu 3.5 h"]),
        "project": None,
    }
    return s


# One dataset for every screen: October 2026 from the design (C1 week, C3 table and cards, C4 heat map).
# date -> (TWE, RES, non-billable) in tenths of an hour. 2 and 20 Oct are holidays, 9 Oct is leave.
WORK = {
    "2026-10-01": (76, 6, 7),
    "2026-10-05": (72, 10, 8), "2026-10-06": (70, 11, 7), "2026-10-07": (68, 10, 8), "2026-10-08": (70, 11, 7),
    "2026-10-12": (54, 10, 35), "2026-10-13": (36, 10, 20), "2026-10-14": (56, 10, 36), "2026-10-15": (56, 10, 28),
    "2026-10-16": (50, 10, 20),
    "2026-10-19": (72, 11, 12), "2026-10-21": (64, 11, 12), "2026-10-22": (66, 10, 12), "2026-10-23": (57, 11, 12),
    "2026-10-26": (77, 15, 0), "2026-10-27": (70, 14, 0), "2026-10-28": (76, 14, 0), "2026-10-29": (35, 0, 0),
}  # fmt: skip
# C2 (half-day leave Thursday) deliberately uses other hours, as in the design, so the PAY RISK rule can show.
WORK_C2 = {
    "2026-10-26": (69, 13, 0), "2026-10-27": (62, 12, 0), "2026-10-28": (67, 13, 0), "2026-10-29": (35, 0, 0),
}  # fmt: skip
HOLIDAYS, LEAVE = {"2026-10-02", "2026-10-20"}, {"2026-10-09"}


def history_rows(first: date, last: date, today: date, work: dict | None = None, half_leave: str | None = None) -> list[dict]:
    """pace.history.load() shape. Weekdays without an entry (and after today) are working days with nothing billed."""
    work = {**WORK, **(work or {})}
    rows, d = [], first
    while d <= last:
        iso = d.isoformat()
        kind, working, projects, non = "working", 1.0, [], 0
        if d.weekday() >= 5:
            kind, working = "weekend", 0
        elif iso in HOLIDAYS:
            kind, working = "holiday", 0
        elif iso in LEAVE:
            kind, working = "leave", 0
        elif iso == half_leave:
            kind, working = "half_leave", 0.5
        if iso in work and d <= today and kind in ("working", "half_leave"):
            twe, res, nb = work[iso]
            non = nb * 6
            projects = [{"code": "TWE", "name": "Tweelin", "billable_min": twe * 6, "non_billable_min": 0}]
            if res:
                projects.append({"code": "RES", "name": "R&D", "billable_min": res * 6, "non_billable_min": non})
            elif non:
                projects[0]["non_billable_min"] = non
        bill = sum(p["billable_min"] for p in projects)
        rows.append(
            {
                "date": iso, "type": kind, "working": working,
                "billable_min": bill, "non_billable_min": non, "projects": projects,
            }
        )  # fmt: skip
        d += timedelta(days=1)
    return rows


def status_on_leave() -> dict:
    """The live shape of a week that is all leave and holiday (9-13 Nov 2026: Diwali Mon, leave Tue-Fri)."""
    s = status_on_track()
    s.update(
        as_of="2026-11-11T10:00:00",
        stale_after="2026-11-11T10:45:00",
        state="on_leave",
        colour="grey",
        icon="circle",
        text="On leave",
        verdict="ON LEAVE",
        logged_min=0,
        target_min=None,
        title="On leave",
        subtitle=None,
        note="No target this week",
        lines=None,
        days=[day("2026-11-09", "Mon", 0, "holiday", "holiday")]
        + [day(f"2026-11-{n}", dow, 0, "leave", "leave") for n, dow in ((10, "Tue"), (11, "Wed"), (12, "Thu"), (13, "Fri"))],
        warning=None,
        warning_detail=None,
        action=None,
        month={
            "name": "November",
            "working_days_left": 11,
            "projects": [
                {"code": "TWE", "name": "Tweelin", "billed_min": 1980, "target_min": None, "gap_min": None,
                 "need_per_day_min": None, "text": "33.0 h · no target", "need_text": None, "short": None},
                {"code": "RES", "name": "Research and Development", "billed_min": 720, "target_min": None, "gap_min": None,
                 "need_per_day_min": None, "text": "12.0 h · no target", "need_text": None, "short": None},
            ],
        },
        labels={"hours": "On leave", "percent": "On leave", "gap": "On leave", "left_today": "On leave"},
        widget={"week": section("THIS WEEK", "on leave", "grey", "", None, []), "project": None},
    )  # fmt: skip
    return s


def leave_rows(last_week_min=(540, 540, 540, 540, 540)) -> list[dict]:
    """History rows 2 Nov - 22 Nov 2026 around status_on_leave(): last week billed, this week off, next week normal."""
    out, d = [], date(2026, 11, 2)
    while d <= date(2026, 11, 22):
        iso, kind, working, bill = d.isoformat(), "working", 1.0, 0
        if d.weekday() >= 5:
            kind, working = "weekend", 0
        elif iso == "2026-11-09":
            kind, working = "holiday", 0
        elif date(2026, 11, 10) <= d <= date(2026, 11, 13):
            kind, working = "leave", 0
        elif d < date(2026, 11, 9):
            bill = last_week_min[d.weekday()]
        proj = [{"code": "TWE", "name": "Tweelin", "billable_min": bill, "non_billable_min": 0}] if bill else []
        out.append({"date": iso, "type": kind, "working": working, "billable_min": bill, "non_billable_min": 0, "projects": proj})
        d += timedelta(days=1)
    return out
