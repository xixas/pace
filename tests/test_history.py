"""pace.history.load: day-by-day hours and calendar for any range, for the app's dashboard (contract section 3a)."""

from datetime import date, timedelta

from pace.history import load


class Api:
    def __init__(self):
        self.calls = []

    def my_days(self, start, end):
        self.calls.append(("days", start, end))
        out, d = [], start
        while d <= end:
            out.append({"date": d.isoformat(), "type": "weekend" if d.weekday() > 4 else "working", "working": d.weekday() < 5})
            d += timedelta(1)
        return out

    def my_hours(self, start, end):
        self.calls.append(("hours", start, end))
        row = {"date": "2026-10-26", "project_id": 1, "project_name": "Tweelin", "billable_min": 480, "non_billable_min": 30}
        return [row, {**row, "project_id": 2, "project_name": "R&D", "billable_min": 60, "non_billable_min": 0}]


def test_one_dict_per_date_with_projects_and_totals(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    out = load(date(2026, 10, 25), date(2026, 10, 27), api=Api())
    assert [d["date"] for d in out] == ["2026-10-25", "2026-10-26", "2026-10-27"]
    assert (out[0]["type"], out[0]["working"], out[0]["billable_min"], out[0]["projects"]) == ("weekend", 0, 0, [])
    mon = out[1]
    assert (mon["type"], mon["working"], mon["billable_min"], mon["non_billable_min"]) == ("working", 1.0, 540, 30)
    assert mon["projects"][0] == {"code": "TWE", "name": "Tweelin", "billable_min": 480, "non_billable_min": 30}


def test_a_range_over_92_days_is_split(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    api = Api()
    out = load(date(2026, 1, 1), date(2026, 6, 30), api=api)  # 181 days
    assert len(out) == 181
    assert all((end - start).days < 92 for _, start, end in api.calls)
    assert api.calls[0][1] == date(2026, 1, 1) and api.calls[-1][2] == date(2026, 6, 30)
