from datetime import datetime

from pace.ui import model
from tests.ui_fixtures import status_on_track, status_pay_risk_half_leave

NOW = datetime(2026, 10, 29, 14, 14)


def test_hours_one_decimal():
    assert model.hours(1806) == "30.1"
    assert model.hours(2460) == "41.0"
    assert model.hours(None) == "–"


def test_as_of_text_ago_and_clock():
    s = status_on_track()
    assert model.as_of_text(s, NOW) == "4 min ago"
    assert model.as_of_text(s, datetime(2026, 10, 29, 14, 10, 30)) == "just now"
    assert model.as_of_text(s, datetime(2026, 10, 29, 16, 40)) == "2 h ago"
    assert model.as_of_text({"as_of": None}, NOW) == "never"


def test_stale_uses_stale_after_then_falls_back_to_15_min():
    s = status_on_track()
    assert not model.is_stale(s, NOW)
    assert model.is_stale(s, datetime(2026, 10, 29, 14, 56))
    s["stale_after"] = None
    assert not model.is_stale(s, datetime(2026, 10, 29, 14, 24))
    assert model.is_stale(s, datetime(2026, 10, 29, 14, 26))
    assert not model.is_stale({"as_of": None}, NOW)


def test_skew_direction():
    s = status_on_track()
    assert model.skew(s) is None
    s["version"] = 2
    assert model.skew(s) == "app_old"
    s["version"] = 0
    assert model.skew(s) == "service_old"


def test_week_stats_on_track():
    v = model.week_view(status_on_track(), expected_daily_h=9.0)
    stats = {s["label"]: s for s in v["stats"]}
    assert stats["This week"]["value"] == "30.1 h"
    assert stats["This week"]["badge"] == "ON TRACK"
    assert stats["This week"]["sub"] == "needs 8.0 h/day"
    assert stats["Average / working day"]["value"] == "8.87 h"
    assert stats["Average / working day"]["sub"] == "3 finished days · 26.6 h"
    assert stats["Pay line"]["value"] == "41 h"
    assert stats["Pay line"]["sub"] == "10.9 h to go"
    assert stats["Projected Fri"]["value"] == "44.6 h"
    assert stats["Projected Fri"]["sub"] == "at the 9.0 h/day expected pace"


def test_week_bar_ticks():
    v = model.week_view(status_on_track(), 9.0)
    bar = v["bar"]
    assert (bar["logged"], bar["lop"], bar["target"], bar["expected"]) == (1806, 2460, 2550, 2700)
    assert bar["max"] >= 2700
    assert v["bar_text"] == "30.1 / 42.5 h"


def test_week_cards():
    cards = model.week_view(status_on_track(), 9.0)["cards"]
    assert [c["dow"] for c in cards] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert cards[0]["text"] == "9.2" and cards[0]["kind"] == "billed"
    assert cards[3]["foot"] == "4.5 left" and cards[3]["today"]
    assert cards[4]["foot"] == "needs 8.0" and cards[4]["text"] == "–"


def test_week_split_by_project_from_history():
    split = {"2026-10-26": [("TWE", "7.7"), ("RES", "1.5")]}
    cards = model.week_view(status_on_track(), 9.0, split=split)["cards"]
    assert cards[0]["split"] == [("TWE", "7.7"), ("RES", "1.5")]
    assert cards[1]["split"] == []


def test_half_leave_week_has_target_card_and_warning():
    v = model.week_view(status_pay_risk_half_leave(), 9.0)
    target = next(s for s in v["stats"] if s["label"] == "Target")
    assert target["value"] == "41 h" and target["sub"] == "half-day leave Thu"
    assert v["warning"].startswith("Short days")
    pay = next(s for s in v["stats"] if s["label"] == "Pay line")
    assert pay["sub"] == "13.9 h to go · LOP risk"
    assert v["cards"][3]["foot"] == "½ leave"


def test_week_view_none_without_numbers():
    assert model.week_view({"state": "signed_out", "logged_min": None}, 9.0) is None


def test_banner_kinds():
    s = status_on_track()
    assert model.banner(s) is None
    s["state"] = "signed_out"
    assert model.banner(s)["kind"] == "signed_out"
    s = status_on_track()
    s["problem"] = {"kind": "no_mapping", "message": "x", "retry_at": None}
    assert model.banner(s)["kind"] == "no_mapping"
    s = status_on_track()
    s["last_week"] = {"text": "Last week: Fri 30 Oct not billed yet", "detail": "Bill by 12:00 today.", "url": "u"}
    b = model.banner(s)
    assert b["kind"] == "last_week" and b["text"].startswith("Last week")


def test_empty_state_kinds():
    s = status_on_track()
    assert model.empty_state(s) is None
    s["state"] = "on_leave"
    e = model.empty_state(s)
    assert e["title"] == "Enjoy your leave" and e["pill"] == "ON LEAVE · 26–30 Oct"
    s = status_on_track()
    s.update(logged_min=0, days=[{**d, "min": None, "kind": "future", "text": "–"} for d in s["days"]])
    e = model.empty_state(s)
    assert e["title"] == "Nothing billed yet this week"
    assert "42.5 h" in e["body"]
