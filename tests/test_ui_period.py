from datetime import date

from pace.ui import period
from tests.ui_fixtures import history_rows, status_on_track

TODAY = date(2026, 10, 29)


def rows():
    return history_rows(date(2026, 10, 1), date(2026, 10, 31), TODAY)


def test_month_bounds_and_navigation():
    assert period.month_bounds(date(2026, 2, 14)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert period.shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert period.shift_month(date(2026, 12, 1), 1) == date(2027, 1, 1)


def test_heat_classes():
    def cell(**kw):
        return period.heat_class(
            {"date": "2026-10-20", "type": "working", "billable_min": 0, "non_billable_min": 0, **kw}, TODAY, 8.5
        )  # noqa: E731

    assert cell(billable_min=510) == "heat-ok"
    assert cell(billable_min=450) == "heat-mid"  # 7.5 h
    assert cell(billable_min=300) == "heat-low"
    assert cell(billable_min=0) == "heat-low"  # a finished working day with nothing
    assert cell(type="holiday") == "heat-holiday"
    assert cell(type="leave") == "heat-leave"
    assert cell(type="weekend") == "heat-off"
    assert (
        period.heat_class({"date": "2026-10-30", "type": "working", "billable_min": 0, "non_billable_min": 0}, TODAY, 8.5)
        == "heat-future"
    )
    today_row = {"date": "2026-10-29", "type": "working", "billable_min": 100, "non_billable_min": 0}
    assert period.heat_class(today_row, TODAY, 8.5) == "heat-pending"  # today is never red or amber while it is still going
    assert cell(billable_min=60, non_billable_min=450) == "heat-ok"  # colour uses billable + non-billable


def test_calendar_grid_october_2026():
    grid = period.calendar_grid(rows(), date(2026, 10, 1), TODAY, 8.5)
    assert len(grid) == 5 and all(len(w) == 7 for w in grid)
    assert [c["day"] for c in grid[0]] == [28, 29, 30, 1, 2, 3, 4]  # 1 Oct 2026 is a Thursday
    assert [c["outside"] for c in grid[0]] == [True, True, True, False, False, False, False]  # Sept days are muted, not blank
    assert grid[0][0]["date"] == "2026-09-28" and grid[0][0]["cls"] == "heat-none" and grid[0][0]["label"] == ""
    assert grid[4][6]["day"] == 1 and grid[4][6]["outside"]  # Sun 1 Nov closes the last week
    assert grid[0][4]["label"] == "Holiday" and grid[0][4]["cls"] == "heat-holiday"
    assert grid[1][4]["label"] == "Leave"
    today_cell = grid[4][3]
    assert today_cell["day"] == 29 and today_cell["today"]
    assert grid[4][4]["label"] == "" and grid[4][4]["cls"] == "heat-future"  # no dash on a day that has not happened
    assert grid[0][5]["label"] == "" and grid[0][5]["cls"] == "heat-off" and grid[0][5]["weekend"]
    assert grid[3][0]["split"] and grid[3][0]["split"][0][0] == "TWE" and grid[3][0]["total_min"] > 0
    assert "TWE" in grid[3][0]["tip"] and "RES" in grid[3][0]["tip"]


def test_week_table_groups_mon_fri_and_totals():
    table = period.week_table(rows(), date(2026, 10, 1))
    assert table["codes"] == ["TWE", "RES"]
    first = table["weeks"][0]
    assert first["label"] == "1–2 Oct" and first["days"] == 1.0
    assert table["weeks"][-1]["label"] == "26–30 Oct"
    total = table["total"]
    assert total["days"] == sum(w["days"] for w in table["weeks"])
    assert total["total_min"] == sum(w["total_min"] for w in table["weeks"])
    assert total["by_code"]["TWE"] == sum(w["by_code"].get("TWE", 0) for w in table["weeks"])


def test_week_table_total_includes_non_billable_but_codes_do_not():
    r = [
        {
            "date": "2026-10-05",
            "type": "working",
            "working": 1.0,
            "billable_min": 480,
            "non_billable_min": 30,
            "projects": [{"code": "TWE", "name": "Tweelin", "billable_min": 480, "non_billable_min": 30}],
        }
    ]
    wk = period.week_table(r, date(2026, 10, 1))["weeks"][0]
    assert wk["by_code"] == {"TWE": 480} and wk["total_min"] == 510


def test_cumulative_series_and_expected_line():
    series = period.cumulative(rows(), "TWE")
    assert series[0][0] == date(2026, 10, 1)
    assert series[-1][1] == sum(p["billable_min"] for r in rows() for p in r["projects"] if p["code"] == "TWE")
    exp = period.expected_line(rows(), 7980)
    assert exp[-1][1] == 7980 and exp[0][1] < exp[-1][1]
    assert exp[0][1] == 0 or exp[0][1] > 0


def test_month_projects_uses_core_when_present_else_status_for_current_month():
    status = status_on_track()
    cur = period.month_projects(rows(), {"projects": []}, date(2026, 10, 1), status, TODAY, core=None)
    assert [p["code"] for p in cur] == ["TWE", "RES"] and cur[0]["text"].startswith("112.5 / 133")
    calls = []

    def fake(r, days, targets, month, today=None):
        calls.append(month)
        return [
            {
                "code": "X",
                "name": "X",
                "billed_min": 60,
                "target_min": None,
                "gap_min": None,
                "need_per_day_min": None,
                "text": "1.0 h · no target",
                "need_text": None,
                "short": None,
            }
        ]

    out = period.month_projects(rows(), {"projects": []}, date(2026, 10, 1), status, TODAY, core=fake)
    assert out[0]["code"] == "X" and calls == [date(2026, 10, 1)]


def test_month_projects_fallback_sums_when_other_month_and_no_core():
    out = period.month_projects(rows(), {"projects": []}, date(2026, 9, 1), status_on_track(), TODAY, core=None)
    assert {p["code"] for p in out} == {"TWE", "RES"}
    assert all(p["target_min"] is None for p in out)
    assert out[0]["billed_min"] >= out[1]["billed_min"]


def test_project_badge_and_sub():
    p = {"code": "TWE", "name": "Tweelin", "billed_min": 6750, "target_min": 7980, "gap_min": -390, "at_risk": True}
    assert period.project_badge(p) == ("BEHIND 6.5 h", "amber")
    assert period.project_badge({**p, "at_risk": False}) == ("UNDER PACE 6.5 h", "grey")
    assert period.project_badge({**p, "gap_min": 30, "at_risk": False}) == ("ON PACE", "green")
    assert period.project_badge({**p, "target_min": None, "gap_min": None}) == ("no target", "grey")
    t = {"projects": [{"code": "TWE", "monthly_h": 140, "prorate": True, "source": "lead", "lead": "Anand"}]}
    assert period.target_note(t, "TWE") == "140 prorated · lead's choice"
    assert period.target_note(t, "RES") == "No target set"
    t["projects"][0].update(prorate=False, source="personal")
    assert period.target_note(t, "TWE") == "140 fixed"


def test_no_mapping_cards_leave_and_next_holiday():
    r = history_rows(date(2026, 10, 1), date(2026, 11, 30), TODAY)
    for row in r:
        if row["date"] == "2026-11-02":
            row["type"] = "holiday"
    cards = period.no_mapping_cards(r, TODAY)
    assert cards[0] == ("This week", "—", "no billing data")
    assert cards[1] == ("Leave · Oct", "1 day", "9 Oct")
    assert cards[2] == ("Next holiday", "Mon 2 Nov", "")


def test_footnote_names_holidays_and_leave():
    r = rows()
    r[19]["type"] = "holiday"  # 20 Oct is a Tuesday
    assert period.footnote(r) == "Holidays 2 and 20 Oct, leave 9 Oct."
    assert period.footnote([x for x in r if x["type"] == "working"]) == ""


def test_dataset_week_table_matches_the_design():
    t = period.week_table(rows(), date(2026, 10, 1))
    got = [(w["label"], w["days"], w["by_code"]["TWE"] / 60, w["by_code"]["RES"] / 60, w["total_min"] / 60) for w in t["weeks"]]
    assert [(a, b) for a, b, *_ in got] == [("1–2 Oct", 1), ("5–9 Oct", 4), ("12–16 Oct", 5), ("19–23 Oct", 4), ("26–30 Oct", 5)]
    assert [round(x[2], 1) for x in got] == [7.6, 28.0, 25.2, 25.9, 25.8]
    assert [round(x[3], 1) for x in got] == [0.6, 4.2, 5.0, 4.3, 4.3]
    assert [round(x[4], 1) for x in got] == [8.9, 35.2, 44.1, 35.0, 30.1]
    tot = t["total"]
    assert (
        tot["days"],
        round(tot["by_code"]["TWE"] / 60, 1),
        round(tot["by_code"]["RES"] / 60, 1),
        round(tot["total_min"] / 60, 1),
    ) == (19, 112.5, 18.4, 153.3)


def test_dataset_agrees_with_status_and_calendar_and_footnote():
    s = status_on_track()
    month = {p["code"]: p["billed_min"] for p in s["month"]["projects"]}
    t = period.week_table(rows(), date(2026, 10, 1))["total"]["by_code"]
    assert month == t
    by_date = {r["date"]: r for r in rows()}
    for d in s["days"][:4]:
        assert period.total_min(by_date[d["date"]]) == d["min"]
    assert by_date["2026-10-20"]["type"] == "holiday"
    grid = period.calendar_grid(rows(), date(2026, 10, 1), TODAY, 8.5)
    assert grid[3][1]["label"] == "Holiday"
    assert period.footnote(rows()) == "Holidays 2 and 20 Oct, leave 9 Oct."


def test_axis_labels_for_the_sparkline():
    ys, first, last = period.axis_labels(7980, rows())
    assert ys == ["133", "90", "45", "0"]
    assert (first, last) == ("1 Oct", "30 Oct")


def test_month_projects_hands_core_my_hours_and_days_shapes():
    seen = {}

    def fake(hours_rows, days, targets, month, today=None):
        seen.update(hours=hours_rows, days=days, today=today)
        return []

    period.month_projects(rows(), {"projects": []}, date(2026, 10, 1), status_on_track(), TODAY, core=fake)
    assert {"date", "project_name", "billable_min"} <= set(seen["hours"][0])
    assert seen["hours"][0]["project_name"] == "Tweelin"
    assert {"date", "working"} <= set(seen["days"][0]) and len(seen["days"]) == 31 and seen["today"] == TODAY


def test_weekend_hours_show_and_count():
    row = {"date": "2026-10-24", "type": "weekend", "working": 0, "billable_min": 120, "non_billable_min": 0, "projects": []}
    grid = period.calendar_grid([row], date(2026, 10, 1), TODAY, 8.5)
    cell = next(c for w in grid for c in w if c["date"] == "2026-10-24")
    assert cell["label"] == "2.0" and cell["cls"] == "heat-off"
    assert period.day_detail(row, TODAY, 8.5)["verdict"] == "Weekend hours count toward the week"


def test_day_detail_for_a_working_day_a_holiday_and_the_future():
    by_date = {r["date"]: r for r in rows()}
    d = period.day_detail(by_date["2026-10-06"], TODAY, 8.5)
    assert d["title"] == "Tuesday 6 October 2026" and d["kind"] == "Working day"
    assert d["total"].endswith(" h") and d["target"] == "of 8.5 h target"
    assert d["colour"] in ("green", "amber", "red") and d["projects"] and d["billable"] != "–"
    holiday = period.day_detail(by_date["2026-10-20"], TODAY, 8.5)
    assert holiday["kind"] == "Holiday" and holiday["colour"] == "blue" and holiday["fill"] is None and holiday["target"] == ""
    future = period.day_detail(by_date["2026-10-30"], TODAY, 8.5)
    assert future["verdict"] == "Not yet" and future["colour"] == "grey"
    short = {"date": "2026-10-06", "type": "working", "billable_min": 300, "non_billable_min": 0, "projects": []}
    assert period.day_detail(short, TODAY, 8.5)["verdict"] == "3.5 h under the target"


def test_project_sub_leaves_the_verdict_to_the_pill():
    twe, res = status_on_track()["month"]["projects"]
    assert period.project_sub(twe) == "112.5 / 133 h · needs 10.3 h/day on Tweelin"
    assert period.project_sub(res) == "18.4 h"
