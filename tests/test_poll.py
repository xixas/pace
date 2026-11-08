"""One poll cycle: hrms-api → ledger → engine → status. The API is faked; auth lives in pace.client."""

from datetime import date, datetime, timedelta

from pace.client import Offline, SignedOut
from pace.poll import poll

LAST_MON, MON = date(2026, 10, 26), date(2026, 11, 2)


def calendar(start, end):
    out, d = [], start
    while d <= end:
        weekday = d.weekday() < 5
        out.append({"date": d.isoformat(), "type": "working" if weekday else "weekend", "working": 1 if weekday else 0})
        d += timedelta(1)
    return out


def billed(*days, minutes=510):
    return [
        {"date": d.isoformat(), "project_id": 1, "project_name": "P1", "billable_min": minutes, "non_billable_min": 0}
        for d in days
    ]


class FakeApi:
    def __init__(self, hours):
        self.hours, self.calls = hours, []

    def my_days(self, start, end):
        self.calls.append(("my_days", start, end))
        return calendar(start, end)

    def my_hours(self, start, end, fresh=False):
        self.calls.append(("my_hours", start, end, fresh) if fresh else ("my_hours", start, end))
        return [r for r in self.hours if start.isoformat() <= r["date"] <= end.isoformat()]


def test_poll_fetches_last_monday_to_this_sunday_and_reports_this_weeks_verdict():
    api = FakeApi(billed(MON, MON + timedelta(1), MON + timedelta(2)))
    s, state = poll(api, {}, datetime(2026, 11, 5, 9, 0))
    # the calendar runs to the month's end so a month can be prorated; the hours stop at this Sunday
    assert api.calls == [("my_days", LAST_MON, date(2026, 11, 30)), ("my_hours", LAST_MON, date(2026, 11, 8))]
    assert (s["state"], s["text"], s["as_of"]) == ("on_track", "25.5 / 42.5 h", "2026-11-05T09:00:00")
    assert state["as_of"] == "2026-11-05T09:00:00"


class DownApi:
    def __init__(self, error):
        self.error = error

    def my_days(self, start, end):
        raise self.error

    my_hours = my_days


def test_offline_keeps_the_last_good_verdict_as_of_its_fetch():
    _, state = poll(FakeApi(billed(MON, MON + timedelta(1), MON + timedelta(2))), {}, datetime(2026, 11, 5, 9, 40))
    s, kept = poll(DownApi(Offline("timed out")), state, datetime(2026, 11, 5, 14, 10))
    assert (s["state"], s["text"], s["as_of"]) == ("offline", "25.5 / 42.5 h · 09:40", "2026-11-05T09:40:00")
    assert kept == state


def test_expired_session_shows_sign_in_again():
    s, _ = poll(DownApi(SignedOut("refresh rejected")), {}, datetime(2026, 11, 5, 9, 40))
    assert s["state"] == "signed_out"


def test_offline_on_first_start_shows_offline_without_numbers():
    s, state = poll(DownApi(Offline("no route")), {}, datetime(2026, 11, 5, 9, 40))
    assert (s["state"], s["text"], s["logged_min"], state) == ("offline", "Offline", None, {})


def test_monday_morning_banner_for_last_fridays_unbilled_hours_until_noon():
    api = FakeApi(billed(*(LAST_MON + timedelta(i) for i in range(4))))  # last Mon-Thu billed, Fri not
    s, state = poll(api, {}, datetime(2026, 11, 2, 9, 20))
    assert (s["state"], s["text"]) == ("on_track", "0.0 / 42.5 h")  # the dot shows only this week
    assert s["last_week"] == {
        "text": "Last week: Fri 30 Oct not billed yet",
        "detail": "Bill by 12:00 today or it counts as 34.0 h → LOP 1 day.",
        "url": "https://pinestem.com/dashboard.html#/tasks",
    }
    s, _ = poll(api, state, datetime(2026, 11, 2, 12, 30))
    assert s["last_week"] is None


def test_the_month_is_fetched_from_its_first_day_when_that_is_before_last_monday():
    api = FakeApi([])
    poll(api, {}, datetime(2026, 11, 20, 9, 0))  # Fri 20 Nov: last Monday is 9 Nov, the month starts 1 Nov
    assert api.calls[1] == ("my_hours", date(2026, 11, 1), date(2026, 11, 22))


def test_fresh_is_passed_on_to_my_hours():
    api = FakeApi([])
    poll(api, {}, datetime(2026, 11, 5, 9, 0), fresh=True)
    assert api.calls[1][3] is True


def test_the_poll_keeps_what_else_the_daemon_stored_in_state():
    _, state = poll(FakeApi([]), {"snoozed_until": "2026-11-06T00:00:00", "sent": {}}, datetime(2026, 11, 5, 9, 0))
    assert state["snoozed_until"] == "2026-11-06T00:00:00" and state["sent"] == {}
