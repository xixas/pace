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
        "text": "112.5 / 133 h · behind 6.5",
        "need_text": "needs 10.3 h/day on Tweelin",
        "short": "Tweelin −6.5 h",
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
    assert p["text"] == "150.0 / 133 h · ahead 31.0"


def test_a_target_with_no_hours_yet_still_shows():
    out = month([], feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 2, 1))
    assert (out[0]["billed_min"], out[0]["gap_min"], out[0]["need_per_day_min"]) == (0, 0, 420)


def test_a_past_month_has_no_days_left_to_need():
    out = month(rows("Tweelin", 6750), feb_days(), {"projects": [TWE]}, FEB, today=date(2027, 3, 15))
    assert (out[0]["need_per_day_min"], out[0]["gap_min"]) == (None, -1230)


def test_load_fills_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert load() == {"dailyMinimum": 8.5, "projects": []}
