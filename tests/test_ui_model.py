from datetime import datetime

import pytest

from pace.ui import model
from tests.ui_fixtures import leave_rows, status_on_leave, status_on_track, status_pay_risk_half_leave

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


def test_week_bar_is_the_runway():
    v = model.week_view(status_on_track(), 9.0)
    bar = v["bar"]
    assert bar["fill"] == pytest.approx(1806 / 2550) and bar["band"] == pytest.approx(2460 / 2550)
    assert bar["ink"] == "neutral" and bar["ghost"] is None and not bar["emphasis"]
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
    assert pay["sub"] == "13.9 h to go · loss-of-pay risk"
    assert v["cards"][3]["foot"] == "½ leave" and v["cards"][3]["text"] == "3.5"


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
    assert model.empty_state(s) is None  # a leave week has its own view, leave_view
    s = status_on_track()
    s.update(logged_min=0, days=[{**d, "min": None, "kind": "future", "text": "–"} for d in s["days"]])
    e = model.empty_state(s)
    assert e["title"] == "Nothing billed yet this week"
    assert "42.5 h" in e["body"]


def test_widget_view_from_status_and_without():
    v = model.widget_view(status_on_track())
    assert (v["week"]["word"], v["week"]["big"], v["week"]["colour"]) == ("on track", "30.1 / 42.5", "green")
    assert (v["project"]["word"], v["project"]["colour"]) == ("behind 6.5 h", "amber")
    out = model.widget_view({"state": "signed_out", "text": "Sign in again", "colour": "amber"})
    assert out["week"]["label"] == "PACE" and out["week"]["lines"] == ["Sign in again"] and out["project"] is None


def test_ui_entry_point_is_importable_without_loading_gtk():
    import pace.ui

    assert callable(pace.ui.main)


def test_badge_is_the_verdict_word_only():
    s = status_pay_risk_half_leave()
    s["verdict"] = "PAY RISK · pay needs 13.9 h · Mon 0 h"
    v = model.week_view(s, 9.0)
    assert v["stats"][0]["badge"] == "PAY RISK" and v["stats"][0]["sub"] == "pay needs 13.9 h"
    assert v["colour"] == "red"


def test_colour_class_covers_every_status_colour_and_greys_unknowns():
    for c in ("green", "amber", "red", "blue", "grey"):
        assert model.colour_class(c) == c
    assert model.colour_class(None) == "grey" and model.colour_class("purple") == "grey"
    bill = {**status_on_track(), "state": "bill", "colour": "blue"}
    bill["widget"]["week"]["colour"] = "purple"
    assert model.widget_view(bill)["week"]["colour"] == "grey"


def test_stale_week_is_grey():
    assert model.week_view(status_on_track(), 9.0, stale=True)["colour"] == "grey"


def test_h_short_rounds_to_one_decimal():
    assert model.h_short(7255) == "120.9" and model.h_short(7980) == "133" and model.h_short(2550) == "42.5"


def _s(state="on_track", logged=1806, kinds=("billed", "billed", "billed", "today", "future"), note=None, lop=2460, target=2550):
    days = [
        {"date": f"2026-10-{26 + i}", "dow": d, "min": 0, "kind": k}
        for i, (d, k) in enumerate(zip(("Mon", "Tue", "Wed", "Thu", "Fri"), kinds, strict=True))
    ]
    return {
        "state": state,
        "logged_min": logged,
        "lines": {"lop_min": lop, "target_min": target},
        "days": days,
        "note": note,
    }


def test_runway_colour_only_on_risk():
    ink = lambda **kw: model.runway(_s(**kw))["ink"]  # noqa: E731
    assert ink() == "neutral" and ink(state="ahead") == "neutral" and ink(state="tight") == "neutral"
    assert ink(state="behind") == "neutral" and ink(state="bill") == "neutral" and ink(state="short") == "neutral"
    assert ink(state="pay_risk") == "red" and ink(state="lop") == "red"
    assert ink(state="done", logged=2550) == "green"
    assert ink(state="offline") == "grey"
    assert model.runway(_s(), stale=True)["ink"] == "grey"


def test_runway_band_runs_from_the_pay_line_to_the_track_end():
    assert model.runway(_s(lop=2460, target=2550))["band"] == pytest.approx(2460 / 2550)
    # half-day leave: pay line above the target, so the track is the line and the band is empty
    r = model.runway(_s(lop=2460, target=2295))
    assert r["band"] == 1.0
    # shorter week: the band widens
    assert model.runway(_s(lop=1920, target=2040))["band"] == pytest.approx(1920 / 2040)


def test_runway_pending_day_is_a_ghost_continuing_the_fill():
    r = model.runway(_s(state="bill", logged=2040, kinds=("billed",) * 4 + ("pending",)))
    assert r["ghost"] == pytest.approx((0.8, 0.8 + 510 / 2550)) and r["ink"] == "neutral"


def test_runway_overtime_caps_at_the_track_end():
    r = model.runway(_s(state="done", logged=3300, kinds=("billed",) * 5))
    assert r["fill"] == 1.0 and r["ghost"] is None
    assert r["caption"] == "target met · +12.5 h"


def test_runway_ghost_is_clipped_to_the_track():
    r = model.runway(_s(logged=2500, kinds=("billed",) * 4 + ("pending",)))
    assert r["ghost"][1] == 1.0


def test_runway_last_day_gap_keeps_a_neutral_fill_with_a_red_band():
    r = model.runway(_s(logged=2400, kinds=("billed",) * 4 + ("today",), note="Last working day · 40.0 of the 41 h line"))
    assert r["ink"] == "neutral" and r["emphasis"]
    assert r["caption"] == "pay needs 1.0 h · 2.5 h to target"


def test_runway_captions():
    cap = lambda **kw: model.runway_caption(_s(**kw))  # noqa: E731
    assert cap() == "10.9 h to pay line · 12.4 h to target"
    assert cap(state="bill", logged=2040, kinds=("billed",) * 4 + ("pending",)) == "7.0 h to pay line · bill Fri to finish"
    assert cap(logged=1560, kinds=("billed",) * 2 + ("pending", "today", "future")) == "15.0 h to pay line · Wed not billed yet"
    assert cap(state="short", logged=2508, kinds=("billed",) * 5) == "pay safe · 0.7 h under target"
    assert cap(logged=2520) == "pay safe · 0.5 h to target"
    assert cap(state="lop", logged=2370, kinds=("billed",) * 5) == "1.5 h under the pay line"
    assert cap(state="done", logged=2550, kinds=("billed",) * 5) == "target met"
    assert cap(state="done", logged=2670, kinds=("billed",) * 5) == "target met · +2.0 h"


def rules():
    from pace.engine import DEFAULT

    return DEFAULT


def test_leave_view_banner_without_history():
    v = model.leave_view(status_on_leave(), None, rules())
    assert v["banner"]["title"] == "On leave · 9–13 Nov, back Mon 16 Nov"
    assert [c["kind"] for c in v["cards"]] == ["holiday", "leave", "leave", "leave", "leave"]
    assert v["last_week"] is None and v["next_week"] is None
    assert v["month"]["projects"][0]["code"] == "TWE"
    assert model.leave_view(status_on_track(), None, rules()) is None


def test_leave_view_last_week_result_and_next_week_needs():
    v = model.leave_view(status_on_leave(), leave_rows(), rules())
    last = v["last_week"]
    assert last["label"] == "Last week · 2–8 Nov" and last["total"] == "45.0 h" and last["verdict"] == "TARGET MET"
    assert last["colour"] == "green" and [d["dow"] for d in last["days"]] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    nxt = v["next_week"]
    assert nxt["label"] == "Next week · 16–20 Nov" and nxt["days"] == "5 working days"
    assert nxt["target"] == "42.5 h" and nxt["per_day"] == "8.5 h/day" and "Pay line 41 h" in nxt["lop"]
    assert not nxt["estimated"]


def test_leave_view_last_week_below_the_pay_line_is_loss_of_pay():
    v = model.leave_view(status_on_leave(), leave_rows((540, 540, 540, 300, 0)), rules())  # 32 h
    assert v["last_week"]["verdict"].startswith("LOSS OF PAY") and v["last_week"]["colour"] == "red"
    v = model.leave_view(status_on_leave(), leave_rows((540, 540, 540, 540, 300)), rules())  # 41 h: on the line
    assert v["last_week"]["verdict"].startswith("PAY SAFE") and v["last_week"]["colour"] == "amber"


def test_back_date_skips_a_holiday_after_the_leave():
    rows = leave_rows()
    for r in rows:
        if r["date"] == "2026-11-16":
            r.update(type="holiday", working=0)
    assert model.back_date(status_on_leave(), rows).isoformat() == "2026-11-17"


def test_widget_view_on_leave_has_content_not_an_empty_card():
    v = model.widget_view(status_on_leave(), rules())
    w = v["week"]
    assert (w["label"], w["word"], w["big"], w["colour"], w["fill"]) == ("ON LEAVE", "back Mon 16 Nov", "", "grey", None)
    assert w["lines"][0] == "Away 9–13 Nov"
    assert w["lines"][1] == "November: TWE 33.0 h · RES 12.0 h"
    assert w["lines"][2] == "Next week needs 42.5 h, pay line 41 h"
    assert v["project"] is None
    assert len(model.widget_view(status_on_leave())["week"]["lines"]) == 2  # without rules there is no next-week line
