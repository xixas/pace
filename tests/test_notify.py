"""Which nudges are due (design C6) and what they say. Statuses come from real weeks via test_status_details.build."""

from datetime import datetime, timedelta

from test_status_details import MON, TWE, build

from pace.notify import due
from pace.settings import DEFAULTS

OPEN = [("pinestem", "Open PineStem"), ("snooze", "Snooze today")]


def at(day, hour, minute=0):
    return datetime(2026, 10, 26, hour, minute) + timedelta(day)


def nudges(minutes, now, sent=None, settings=DEFAULTS, summary=None, **kw):
    s = build(minutes, now, **kw)
    return {n.key: n for n in due(s, settings, now, sent or {}, summary)}


def test_friday_check_says_how_many_hours_are_left_from_16_00():
    n = nudges([552, 504, 540, 540, 120], at(4, 16, 5), now_day=4)["friday"]
    assert (n.title, n.body, n.actions) == ("Friday check: 4.9 h left to reach 42.5", "Bill your work before you log off.", OPEN)
    assert "friday" not in nudges([552, 504, 540, 540, 120], at(4, 15, 59), now_day=4)
    assert "friday" not in nudges([552, 504, 540, 540], at(3, 16, 5), now_day=3)  # not the last working day


def test_pay_risk_names_the_numbers_and_the_short_days():
    n = nudges([552, 504, 360, 210, 0], at(4, 11, 0))["pay_risk"]
    assert n.title == "Pay at risk: 41 h is out of reach"
    assert (
        n.body
        == "27.1 h by Fri 11:00 needs 13.9 h today, more than 10.5. Short days: Wed 6.0 h · Thu 3.5 h. Bill missing hours now."
    )
    assert n.actions == OPEN


def test_daily_at_20_00_on_a_pay_risk_week_names_the_short_day_and_what_friday_needs():
    n = nudges([552, 504, 540, 210], at(3, 20, 0))["daily"]
    assert n.title == "Pay at risk this week"
    assert (
        n.body
        == "Thursday has 3.5 h. Reaching the 41 h line needs 10.9 h on Friday, more than 10.5. Bill the rest of Thursday now."
    )


def test_daily_summary_on_a_normal_day():
    n = nudges([552, 504, 540, 540], at(3, 20, 0))["daily"]
    assert n.title == "Thu: 9.0 h billed"
    assert n.body == "Week 35.6 / 42.5 h."


def test_zero_hour_day_fires_after_the_grace_with_the_days_name():
    got = nudges([552, 504, 0, 540], at(3, 12, 0))
    assert got["zero_hour:2026-10-28"].title == "Wednesday has 0 h billed"
    assert got["zero_hour:2026-10-28"].body == "Forgot to bill? Add it before the week closes."
    assert "zero_hour:2026-10-28" not in nudges([552, 504, 0, 540], at(3, 11, 59))


def test_project_behind_once_a_day_with_the_days_it_must_be_caught_up_over():
    rows = [{"date": "2026-10-05", "project_id": 1, "project_name": "Tweelin", "billable_min": 6750, "non_billable_min": 0}]
    n = nudges([552, 504, 540, 210], at(3, 10, 30), targets={"projects": [TWE]}, rows=rows)["project_behind:TWE"]
    assert n.title.startswith("Tweelin is ") and n.title.endswith(" h behind for October")
    assert n.body.startswith("112.5 of 140 h. ") and n.body.endswith(" h/day needed on Thu–Fri.")


def test_monday_summary_of_last_week_at_12_30():
    summary = {"logged_min": 2586, "target_min": 2550, "lop_days": 0}
    n = nudges([0], at(7, 12, 30), summary=summary)["monday"]
    assert (n.title, n.body) == ("Last week 43.1 h ✓", "Above the 42.5 h target.")
    assert n.actions == [("dashboard", "Open dashboard"), ("dismiss", "Dismiss")]
    assert "monday" not in nudges([0], at(7, 12, 29), summary=summary)


def test_monday_summary_for_a_week_that_lost_pay():
    summary = {"logged_min": 2370, "target_min": 2550, "lop_days": 1}
    assert nudges([0], at(7, 12, 30), summary=summary)["monday"].title == "Last week 39.5 h · LOP 1 day"


def test_each_nudge_goes_out_once_a_day():
    sent = {"2026-10-29": ["daily"]}
    assert "daily" not in nudges([552, 504, 540, 540], at(3, 20, 0), sent=sent)


def test_a_switched_off_nudge_stays_quiet():
    off = {**DEFAULTS, "notify": {**DEFAULTS["notify"], "daily": {"on": False, "at": "20:00"}}}
    assert "daily" not in nudges([552, 504, 540, 540], at(3, 20, 0), settings=off)


def test_snoozed_offline_and_leave_days_send_nothing():
    s = build([552, 504, 540, 540], at(3, 20, 0), snoozed="2026-10-30T00:00:00")
    assert due(s, DEFAULTS, at(3, 20, 0), {}) == []
    off = build([552, 504, 540, 540], at(3, 20, 0), problem="offline")
    assert due(off, DEFAULTS, at(3, 20, 0), {}) == []
    leave = build([552, 504, 540], at(3, 20, 0), off=[(MON.replace(day=29), "leave")])
    assert due(leave, DEFAULTS, at(3, 20, 0), {}) == []
    holiday = build([552, 504, 540], at(3, 20, 0), off=[(MON.replace(day=29), "holiday")])
    assert due(holiday, DEFAULTS, at(3, 20, 0), {}) == []


def test_signed_out_asks_once_with_the_time_numbers_stopped():
    from pace.notify import signed_out
    from pace.status import status

    s = status(None, None, problem="signed_out")
    n = signed_out(s, DEFAULTS, False, paused_at=datetime(2026, 10, 29, 9, 40))
    assert (n.title, n.body, n.actions) == (
        "Sign in again",
        "Your Microsoft session has expired. Numbers are paused at 09:40.",
        [("signin", "Sign in"), ("dismiss", "Later")],
    )
    assert signed_out(s, DEFAULTS, True, paused_at=None) is None


# --- the D-Bus side, against a private session bus and a fake notification daemon ---

import subprocess  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def bus_address():
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address"], stdout=subprocess.PIPE, text=True)
    yield daemon.stdout.readline().strip()
    daemon.terminate()
    daemon.wait()


def connect(address):
    from gi.repository import Gio

    flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
    return Gio.DBusConnection.new_for_address_sync(address, flags, None, None)


def pump(until, seconds=3):
    import time

    from gi.repository import GLib

    end = time.time() + seconds
    while not until() and time.time() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(0.005)
    return until()


NOTIFICATIONS_XML = """<node><interface name="org.freedesktop.Notifications">
<method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/>
<arg type="s" direction="in"/><arg type="as" direction="in"/><arg type="a{sv}" direction="in"/><arg type="i" direction="in"/>
<arg type="u" direction="out"/></method>
<signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal></interface></node>"""


def test_nudge_goes_over_dbus_and_a_button_click_comes_back(bus_address):
    from gi.repository import Gio, GLib

    from pace.notify import Notifier, Nudge

    server, calls = connect(bus_address), []

    def handle(conn, sender, path, iface, method, params, invocation):
        calls.append(params.unpack())
        invocation.return_value(GLib.Variant("(u)", (7,)))

    info = Gio.DBusNodeInfo.new_for_xml(NOTIFICATIONS_XML).interfaces[0]
    server.register_object("/org/freedesktop/Notifications", info, handle, None, None)
    Gio.bus_own_name_on_connection(server, "org.freedesktop.Notifications", Gio.BusNameOwnerFlags.NONE, None, None)

    clicked = []
    notifier = Notifier(connect(bus_address), clicked.append)
    notifier.send(Nudge("friday", "Friday check", "Bill your work.", OPEN))
    assert pump(lambda: calls)
    app, replaces, icon, title, body, actions, hints, timeout = calls[0]
    assert (app, title, body, actions) == (
        "Pace",
        "Friday check",
        "Bill your work.",
        ["pinestem", "Open PineStem", "snooze", "Snooze today"],
    )
    assert pump(lambda: 7 in notifier.ours)
    server.emit_signal(
        None,
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "ActionInvoked",
        GLib.Variant("(us)", (7, "snooze")),
    )
    assert pump(lambda: clicked) and clicked == ["snooze"]
    server.emit_signal(
        None,
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "ActionInvoked",
        GLib.Variant("(us)", (99, "snooze")),
    )
    pump(lambda: False, 0.2)
    assert clicked == ["snooze"]  # someone else's notification
