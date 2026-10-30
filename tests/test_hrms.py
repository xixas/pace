"""hrms-api responses → engine inputs. Shapes from hrms-api feat/pace-my-hours-my-days (2026-10-30)."""

from datetime import date, datetime, timedelta

from pace.engine import Entry
from pace.hrms import entries, record, work_days

MON = date(2026, 10, 26)


def day(d, type_, working):
    return {"date": d, "type": type_, "working": working}


def test_work_days_maps_my_days_onto_mon_to_sun():
    days = [
        day("2026-10-26", "working", 1),
        day("2026-10-27", "working", 1),
        day("2026-10-28", "holiday", 0),
        day("2026-10-29", "half_leave", 0.5),
        day("2026-10-30", "working", 1),
        day("2026-10-31", "comp_off_worked", 1),
        day("2026-11-01", "weekend", 0),
    ]
    assert work_days(days, MON) == [1, 1, 0, 0.5, 1, 1, 0]


def test_work_days_treats_missing_dates_as_not_working():
    assert work_days([day("2026-10-27", "working", 1)], MON) == [0, 1, 0, 0, 0, 0, 0]


def hours(d, project_id, billable, non_billable=0):
    return {
        "date": d,
        "project_id": project_id,
        "project_name": f"P{project_id}",
        "billable_min": billable,
        "non_billable_min": non_billable,
    }


def test_first_poll_records_each_days_total_across_projects_as_seen_now():
    ledger = record({}, [hours("2026-10-26", 1, 300, 30), hours("2026-10-26", 2, 180)], datetime(2026, 10, 26, 18, 30))
    assert entries(ledger, MON) == [Entry(for_day=0, seen_day=0, seen_hour=18.5, minutes=510)]


def test_later_poll_adds_only_what_each_day_gained():
    first = record({}, [hours("2026-10-26", 1, 300)], datetime(2026, 10, 26, 13, 0))
    later = record(first, [hours("2026-10-26", 1, 510), hours("2026-10-26", 2, 0)], datetime(2026, 10, 27, 10, 0))
    unchanged = record(later, [hours("2026-10-26", 1, 510)], datetime(2026, 10, 27, 11, 0))
    assert entries(unchanged, MON) == [Entry(0, 0, 13.0, 300), Entry(0, 1, 10.0, 210)]


def test_poll_shrinks_a_day_billed_down_or_deleted_but_keeps_days_outside_the_range():
    ledger = record({}, [hours("2026-10-23", 1, 510), hours("2026-10-26", 1, 300)], datetime(2026, 10, 26, 13, 0))
    ledger = record(ledger, [hours("2026-10-26", 1, 510), hours("2026-10-27", 1, 120)], datetime(2026, 10, 27, 10, 0))
    ledger = record(ledger, [hours("2026-10-26", 1, 400)], datetime(2026, 10, 27, 11, 0), polled=(MON, date(2026, 10, 27)))
    # Mon edited 510 → 400: the latest 210 shrinks to 100. Tue deleted: gone. Last Friday was not polled: kept.
    assert entries(ledger, MON) == [Entry(0, 0, 13.0, 300), Entry(0, 1, 10.0, 100)]
    assert entries(ledger, MON - timedelta(7)) == [Entry(4, 7, 13.0, 510)]


def test_entries_returns_only_the_asked_for_week():
    ledger = record(
        {}, [hours("2026-10-25", 1, 60), hours("2026-10-26", 1, 510), hours("2026-11-02", 1, 120)], datetime(2026, 11, 2, 9, 0)
    )
    assert entries(ledger, MON) == [Entry(0, 7, 9.0, 510)]


def test_half_hourly_polls_reproduce_sim_scenario_2_billed_next_morning():
    """Each weekday's 8.5 h is billed at 10:00 the next morning (Fri's on Sat). Verdicts match sim/week-rules-v4-out.txt."""
    from datetime import timedelta

    from pace.engine import week_verdict

    week = [day((MON + timedelta(i)).isoformat(), "working" if i < 5 else "weekend", 1 if i < 5 else 0) for i in range(7)]
    work = work_days(week, MON)
    ledger, verdicts = {}, {}
    for step in range(7 * 48):
        now = datetime(2026, 10, 26) + timedelta(minutes=30 * step)
        billed = [hours((MON + timedelta(i)).isoformat(), 1, 510) for i in range(5) if now >= datetime(2026, 10, 27 + i, 10)]
        ledger = record(ledger, billed, now, polled=(MON, now.date()))
        verdicts[now.strftime("%a %H:%M")] = week_verdict(
            work, entries(ledger, MON), (now.date() - MON).days, now.hour + now.minute / 60
        ).label
    assert verdicts["Mon 20:30"] == "ON TRACK · Mon not billed yet"
    assert verdicts["Tue 12:30"] == "ON TRACK"
    assert verdicts["Fri 09:00"] == "ON TRACK · pay needs 7.0 h · Thu not billed yet"
    assert verdicts["Fri 20:30"] == "BILL · Fri not billed yet"
    assert verdicts["Sat 12:30"] == "DONE"
