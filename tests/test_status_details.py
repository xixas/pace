"""The added status.json keys (contract section 1), worded as the design mocks B2-B6, B10, B12 show them."""

from datetime import date, datetime, timedelta

from pace.poll import verdict_status
from pace.settings import DEFAULTS

MON = date(2026, 10, 26)
TWE = {"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True, "source": "lead"}


def calendar(start=date(2026, 10, 1), end=date(2026, 11, 30), off=()):
    out, d = [], start
    while d <= end:
        kind = dict(off).get(d) or ("weekend" if d.weekday() > 4 else "working")
        out.append({"date": d.isoformat(), "type": kind, "working": 1 if kind == "working" else 0})
        d += timedelta(1)
    return out


def week(minutes, seen_hour=18, now_day=None, now_seen=13):
    """ledger for Mon..: minutes per day; each seen at seen_hour that day (the current day at now_seen)."""
    ledger = {}
    for i, m in enumerate(minutes):
        if m:
            at = datetime.combine(MON + timedelta(i), datetime.min.time()).replace(hour=now_seen if i == now_day else seen_hour)
            ledger[(MON + timedelta(i)).isoformat()] = [[at.isoformat(), m]]
    return ledger


def build(minutes, at, now_day=None, problem=None, settings=None, targets=None, rows=(), off=(), snoozed=None, **kw):
    state = {
        "ledger": week(minutes, now_day=now_day),
        "days": calendar(off=off),
        "rows": list(rows),
        "as_of": at.isoformat(),
        "snoozed_until": snoozed,
    }
    return verdict_status(state, at, problem, settings=settings or DEFAULTS, targets=targets, **kw)


def test_b2_on_track_thursday():
    s = build([552, 504, 540, 210], datetime(2026, 10, 29, 14, 10), now_day=3)
    assert (s["state"], s["title"], s["subtitle"], s["note"]) == ("on_track", "On track", "needs 8.0 h/day", "4.5 h left today")
    assert s["lines"] == {"lop_min": 2460, "target_min": 2550, "expected_min": 2700, "emphasis": None}
    assert [(d["dow"], d["kind"], d["text"]) for d in s["days"]] == [
        ("Mon", "billed", "9.2"),
        ("Tue", "billed", "8.4"),
        ("Wed", "billed", "9.0"),
        ("Thu", "today", "3.5"),
        ("Fri", "future", "–"),
    ]
    assert s["days"][0]["date"] == "2026-10-26" and s["days"][0]["min"] == 552 and s["days"][4]["min"] is None
    assert (s["warning"], s["warning_detail"], s["action"], s["problem"], s["snoozed_until"]) == (None, None, None, None, None)
    assert s["stale_after"] == "2026-10-29T14:55:00"
    assert s["pinestem_url"] == "https://pinestem.com/dashboard.html#/tasks"
    assert s["labels"]["hours"] == "30.1 / 42.5 h" and s["labels"]["percent"] == "71%"
    assert s["labels"]["left_today"] == "4.5 h left today"
    assert s["last_week"] is None


def test_b3_last_working_day_under_the_pay_line_spells_out_the_gap():
    s = build([552, 504, 540, 540, 264], datetime(2026, 10, 30, 18, 30), now_day=4)
    assert (s["state"], s["text"]) == ("on_track", "40.0 / 42.5 h · pay needs 1.0 h")
    assert (s["subtitle"], s["note"]) == ("pay needs 1.0 h", "Last working day · 40.0 of the 41 h line")
    assert s["action"] == {"label": "Bill 1 h to stay clear of loss of pay", "url": s["pinestem_url"]}
    assert s["gap_text"] == "1.0 h to the loss-of-pay line · 2.5 h to target"
    assert s["lines"]["emphasis"] == "lop"


def test_b4_pay_risk_names_the_short_days_and_the_best_case():
    s = build([552, 504, 360, 210, 0], datetime(2026, 10, 30, 11, 0))
    assert (s["state"], s["title"], s["subtitle"]) == ("pay_risk", "Pay at risk", "27.1 / 42.5 h")
    assert s["note"] == "Needs 13.9 h today to reach 41 h. The limit is 10.5 h/day."
    assert s["warning"] == "Short days: Wed 6.0 h · Thu 3.5 h"
    assert s["warning_detail"] == "Even 10.5 h today ends 3.4 h under the line, about 1 day of loss of pay."
    assert s["action"] == {"label": "Open PineStem to bill Fri", "url": s["pinestem_url"]}
    assert [d["kind"] for d in s["days"]] == ["billed", "billed", "short", "short", "today"]
    assert s["days"][4]["text"] == "0.0"
    assert (s["lines"]["emphasis"], s["gap_text"]) == ("lop", None)


def test_b5_bill_is_a_calm_not_billed_yet():
    s = build([510, 510, 510, 510, 0], datetime(2026, 10, 30, 20, 30))
    assert (s["state"], s["title"], s["subtitle"], s["note"]) == (
        "bill",
        "Bill your hours",
        "34.0 / 42.5 h",
        "Fri not billed yet",
    )
    assert (s["days"][4]["kind"], s["days"][4]["text"]) == ("pending", "not yet")
    assert s["action"]["label"] == "Open PineStem to bill Fri"
    assert s["warning"] is None


def test_b6_offline_keeps_the_verdict_and_says_when_it_retries():
    at, retry = datetime(2026, 10, 29, 9, 40), datetime(2026, 10, 29, 14, 12)
    s = build([552, 504, 540, 0], at, problem="offline", retry_at=retry)
    assert (s["state"], s["title"], s["text"]) == ("offline", "On track", "26.6 / 42.5 h · 09:40")
    assert s["problem"] == {"kind": "offline", "message": "Can't reach DhiHRMS", "retry_at": "2026-10-29T14:12:00"}


def test_signed_out_has_a_problem_and_no_numbers():
    s = build([], datetime(2026, 10, 29, 9, 40), problem="signed_out")
    assert s["problem"]["kind"] == "signed_out" and s["days"] is None and s["labels"] is None and s["title"] is None


def test_panel_text_setting_picks_the_label_and_icon_means_empty():
    at = datetime(2026, 10, 29, 14, 10)
    for fmt, text in [("percent", "71%"), ("left_today", "4.5 h left today"), ("icon", ""), ("gap", "30.1 / 42.5 h")]:
        s = build([552, 504, 540, 210], at, now_day=3, settings={**DEFAULTS, "panel_text": fmt})
        assert s["text"] == text, fmt


def test_gap_label_names_the_project_that_is_behind():
    rows = [{"date": "2026-10-05", "project_id": 1, "project_name": "Tweelin", "billable_min": 3000, "non_billable_min": 0}]
    s = build(
        [552, 504, 540, 210],
        datetime(2026, 10, 29, 14, 10),
        now_day=3,
        targets={"projects": [TWE]},
        rows=rows,
        settings={**DEFAULTS, "panel_text": "gap"},
    )
    assert s["text"].endswith(" h TWE") and s["text"].startswith("−")
    assert s["month"]["name"] == "October" and s["month"]["working_days_left"] == 2
    assert s["month"]["projects"][0]["code"] == "TWE"


def test_tray_and_widget_are_ready_made_for_every_frontend():
    rows = [{"date": "2026-10-05", "project_id": 1, "project_name": "Tweelin", "billable_min": 6750, "non_billable_min": 0}]
    s = build([552, 504, 540, 210], datetime(2026, 10, 29, 14, 10), now_day=3, targets={"projects": [TWE]}, rows=rows)
    t = s["tray"]
    assert (t["number"], t["tooltip_title"], t["fill"]) == ("30", "Pace — Week · On track", 0.71)
    assert t["tooltip_lines"][0] == "30.1 / 42.5 h · needs 8.0 h/day"
    assert t["tooltip_lines"][1].startswith("Tweelin Oct 112.5 / ")
    assert t["info_rows"][:2] == ["Week · On track — 30.1 / 42.5 h", "Needs 8.0 h/day · 4.5 h left today"]
    w = s["widget"]["week"]
    assert (w["label"], w["word"], w["colour"]) == ("THIS WEEK", "on track", "green")
    assert (w["big"], w["unit"], w["fill"], w["lines"]) == ("30.1 / 42.5", "h", 0.71, ["8.0 h/day to reach 42.5 h"])
    p = s["widget"]["project"]
    assert p["label"] == "TWEELIN · OCT" and p["big"].startswith("112.5 / ") and p["unit"] == "h"
    assert p["lines"] == ["13.8 h/day · 2 days left"]
    assert p["word"] == "behind 14.8 h" and p["colour"] == "amber" and p["fill"] == 0.8


def test_pay_risk_widget_shows_the_hours_needed_today_and_the_short_days():
    s = build([552, 504, 360, 210, 0], datetime(2026, 10, 30, 11, 0))
    w = s["widget"]["week"]
    assert (w["word"], w["colour"], w["lines"]) == ("pay risk", "red", ["13.9 h needed today", "Wed 6.0 h · Thu 3.5 h"])


def test_widget_trims_whole_hours_and_gives_the_other_states_their_words():
    s = build([600, 600, 600, 750], datetime(2026, 10, 29, 18, 30))
    w = s["widget"]["week"]
    assert (w["word"], w["big"], w["fill"]) == ("done", "42.5", 1)
    assert s["widget"]["project"] is None
    s = build([552, 504, 540, 0], datetime(2026, 10, 29, 9, 40), problem="offline", retry_at=datetime(2026, 10, 29, 14, 12))
    w = s["widget"]["week"]
    assert (w["word"], w["colour"], w["lines"]) == ("offline", "grey", ["as of 09:40 · Can't reach DhiHRMS, retrying"])
    s = build([510, 510, 510, 510, 0], datetime(2026, 10, 30, 20, 30))
    assert (s["widget"]["week"]["word"], s["widget"]["week"]["lines"]) == ("bill", ["Fri not billed yet"])


def test_widget_project_under_pace_is_neutral_and_met_is_green():
    t = {**TWE, "monthly_h": 120, "prorate": False}
    rows = [{"date": "2026-10-05", "project_id": 1, "project_name": "Tweelin", "billable_min": 6300, "non_billable_min": 0}]
    s = build([552, 504, 540, 210], datetime(2026, 10, 29, 14, 10), now_day=3, targets={"projects": [t]}, rows=rows)
    p = s["widget"]["project"]
    assert p["word"].endswith("h under pace") and p["colour"] == "grey" and p["big"] == "105 / 120"


def test_snoozed_until_shows_while_it_lasts():
    state = {"ledger": week([552]), "days": calendar(), "as_of": "2026-10-26T18:00:00", "snoozed_until": "2026-10-27T00:00:00"}
    s = verdict_status(state, datetime(2026, 10, 26, 18, 0), settings=DEFAULTS)
    assert s["snoozed_until"] == "2026-10-27T00:00:00"


def test_leave_and_holiday_days_are_named():
    off = [(MON + timedelta(1), "leave"), (MON + timedelta(2), "holiday")]
    s = build([552, 0, 0, 0, 0], datetime(2026, 10, 27, 10, 0), off=off)
    assert [(d["kind"], d["text"]) for d in s["days"][:3]] == [("billed", "9.2"), ("leave", "leave"), ("holiday", "holiday")]
