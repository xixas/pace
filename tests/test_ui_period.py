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
        == "heat-pending"
    )
    assert cell(billable_min=60, non_billable_min=450) == "heat-ok"  # colour uses billable + non-billable


def test_calendar_grid_october_2026():
    grid = period.calendar_grid(rows(), date(2026, 10, 1), TODAY, 8.5)
    assert len(grid) == 5 and all(len(w) == 7 for w in grid)
    assert [c["day"] for c in grid[0]] == [None, None, None, 1, 2, 3, 4]  # 1 Oct 2026 is a Thursday
    assert grid[0][4]["label"] == "Holiday" and grid[0][4]["cls"] == "heat-holiday"
    assert grid[1][4]["label"] == "Leave"
    today_cell = grid[4][3]
    assert today_cell["day"] == 29 and today_cell["today"]
    assert grid[4][4]["label"] == "–" and grid[4][4]["cls"] == "heat-pending"
    assert grid[0][5]["label"] == "" and grid[0][5]["cls"] == "heat-off"
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

    def fake(r, days, targets, month):
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
    p = {"code": "TWE", "name": "Tweelin", "billed_min": 6750, "target_min": 7980, "gap_min": -390}
    assert period.project_badge(p) == ("BEHIND 6.5 h", "amber")
    assert period.project_badge({**p, "gap_min": 30}) == ("ON TRACK", "green")
    assert period.project_badge({**p, "target_min": None, "gap_min": None}) == ("no target", "grey")
    t = {"projects": [{"code": "TWE", "monthly_h": 140, "prorate": True, "source": "lead", "lead": "Anand"}]}
    assert period.target_note(t, "TWE") == "140 prorated · lead's choice"
    assert period.target_note(t, "RES") == "tracked only · billable"
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
