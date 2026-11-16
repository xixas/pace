"""Month per project (design rules v4, contract sections 1 and 3). Billable minutes only."""

from datetime import date, timedelta

from pace.targets import load, month

TWE = {"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True, "source": "lead", "lead": "Anand"}
RES = {"code": "RES", "name": "R&D", "monthly_h": None, "prorate": False, "source": "personal"}
FEB = date(2027, 2, 1)  # 20 working days


def feb_days(leave=date(2027, 2, 10)):
    out = []
    for i in range(28):
        d = FEB + timedelta(i)
        weekday = d.weekday() < 5
        kind = "weekend" if not weekday else "leave" if d == leave else "working"
        out.append({"date": d.isoformat(), "type": kind, "working": 0 if kind != "working" else 1})
    return out


def rows(name, minutes, non_billable=0, day="2027-02-02"):
    return [{"date": day, "project_id": 1, "project_name": name, "billable_min": minutes, "non_billable_min": non_billable}]


def test_prorated_target_gap_and_need_per_day_match_the_b2_mock():
    r = rows("Tweelin", 6750, non_billable=300) + rows("R&D", 1104)
    out = month(r, feb_days(), {"projects": [TWE, RES]}, FEB, today=date(2027, 2, 25))
    assert out[0] == {
        "code": "TWE",
        "name": "Tweelin",
        "billed_min": 6750,
        "target_min": 7980,
        "gap_min": -390,
        "need_per_day_min": 615,
        "text": "112.5 / 133 h · behind 6.5 h",
        "need_text": "needs 10.3 h/day on Tweelin",
        "short": "Tweelin −6.5 h",
        "at_risk": True,
    }
    assert out[1] == {
        "code": "RES",
        "name": "R&D",
        "billed_min": 1104,
        "target_min": None,
        "gap_min": None,
        "need_per_day_min": None,
        "text": "18.4 h · no target",
        "need_text": None,
        "short": None,
        "at_risk": False,
    }


def test_fixed_target_ignores_leave():
    out = month(rows("Tweelin", 0), feb_days(), {"projects": [{**TWE, "prorate": False}]}, FEB, today=date(2027, 2, 25))
    assert out[0]["target_min"] == 8400


def test_targets_come_first_then_the_rest_by_billed_hours():
    r = rows("Alpha", 100) + rows("Beta", 900) + rows("Tweelin", 10)
    out = month(r, feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 2, 25))
    assert [p["name"] for p in out] == ["Tweelin", "Beta", "Alpha"]
    assert out[1]["code"] == "BET"


def test_project_ahead_has_no_short_and_a_met_target_needs_nothing():
    out = month(rows("Tweelin", 9000), feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 2, 25))
    p = out[0]
    assert (p["gap_min"], p["need_per_day_min"], p["need_text"], p["short"]) == (1860, None, None, None)
    assert p["text"] == "150.0 / 133 h · ahead 31.0 h"


def test_a_target_with_no_hours_yet_still_shows():
    out = month([], feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 2, 1))
    assert (out[0]["billed_min"], out[0]["gap_min"], out[0]["need_per_day_min"]) == (0, 0, 420)


def test_a_past_month_has_no_days_left_to_need():
    out = month(rows("Tweelin", 6750), feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 3, 15))
    assert (out[0]["need_per_day_min"], out[0]["gap_min"]) == (None, -1230)


def test_load_fills_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert load() == {"dailyMinimum": 8.5, "projects": []}


def test_prorating_divides_by_the_months_working_days_holidays_out_leave_in():
    # Design example: October 2026 has 22 weekdays, holidays 2 and 20 Oct (20 working days), leave 9 Oct (19 available).
    from datetime import date as d_
    from datetime import timedelta

    from pace.targets import month

    days = []
    for n in range(31):
        day = d_(2026, 10, 1) + timedelta(n)
        kind = {2: "holiday", 20: "holiday", 9: "leave"}.get(day.day, "weekend" if day.weekday() >= 5 else "working")
        days.append({"date": day.isoformat(), "type": kind, "working": 1 if kind == "working" else 0})
    targets = {"projects": [{"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": True}]}
    [twe] = month([], days, targets, d_(2026, 10, 1), today=d_(2026, 10, 1))
    assert twe["target_min"] == 140 * 60 * 19 // 20  # 133 h


# -- under pace is not behind: only a need beyond the daily target is a risk (112 h target, 20 working days) ----------------
def _project(billed_h, left, **kw):
    from pace.targets import project

    t = {"code": "TWE", "name": "Tweelin", "monthly_h": 112, "prorate": False}
    return project("TWE", "Tweelin", round(billed_h * 60), t, 20, left, 20, **kw)


def test_a_gap_the_daily_target_can_close_is_under_pace_not_behind():
    p = _project(33, 11)  # expected 50.4 h by now: 17.4 h under, but needs only 7.2 h/day
    assert p["gap_min"] < 0 and p["need_per_day_min"] == 431
    assert (p["short"], p["at_risk"]) == (None, False)
    assert p["text"] == "33.0 / 112 h · 17.4 h under pace"


def test_a_need_above_the_daily_target_is_behind_and_at_risk():
    p = _project(33, 6)  # needs 13.2 h/day
    assert p["at_risk"] is True and p["short"] == "Tweelin −45.4 h"
    assert p["text"] == "33.0 / 112 h · behind 45.4 h"


def test_the_daily_target_is_a_parameter():
    assert _project(33, 10)["at_risk"] is False  # needs 7.9 h/day
    assert _project(33, 10, daily_min=360)["at_risk"] is True  # but not within 6 h/day


def test_no_days_left_and_still_short_is_at_risk():
    p = _project(100, 0)
    assert (p["at_risk"], p["need_per_day_min"]) == (True, None) and p["short"]


def test_on_pace_and_ahead_are_not_at_risk():
    p = _project(0, 20)
    assert p["text"].endswith("· on pace") and not p["at_risk"]
    p = _project(120, 5)
    assert p["text"].endswith("· ahead 36.0 h") and not p["at_risk"] and p["short"] is None


def test_month_threads_the_daily_minimum_from_targets():
    r = rows("Tweelin", 6750)
    t = {"projects": [TWE], "dailyMinimum": 12}
    assert month(r, feb_days(), t, FEB, today=date(2027, 2, 25))[0]["at_risk"] is False  # needs 10.3 h/day <= 12
    assert month(r, feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 2, 25))[0]["at_risk"] is True


def test_two_projects_each_doable_alone_but_not_together_are_both_at_risk():
    a = {"code": "AAA", "name": "Alpha", "monthly_h": 100, "prorate": False}
    b = {"code": "BBB", "name": "Beta", "monthly_h": 100, "prorate": False}
    # 20 working days, 10 days left: each needs ~5.5 h/day, together over 8.5 h
    r = rows("Alpha", 3000) + rows("Beta", 3000)
    out = month(r, feb_days(), {"projects": [a, b], "dailyMinimum": 8.5}, FEB, today=date(2027, 2, 16))
    assert all(p["need_per_day_min"] <= 510 for p in out) and sum(p["need_per_day_min"] for p in out) > 510
    assert [p["at_risk"] for p in out] == [True, True] and all(p["short"] for p in out)
    alone = month(rows("Alpha", 3000), feb_days(), {"projects": [a], "dailyMinimum": 8.5}, FEB, today=date(2027, 2, 16))
    assert alone[0]["at_risk"] is False and "under pace" in alone[0]["text"]
