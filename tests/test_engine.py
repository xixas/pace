"""Replays the week-rules v4 simulation (sim/week-rules-v4.js) and checks the engine against its recorded output."""

import re
from pathlib import Path

import pytest

from pace.engine import Entry, hours, week_verdict

SIM_OUT = Path(__file__).resolve().parent.parent / "sim" / "week-rules-v4-out.txt"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
POLLS = [9, 12.5, 18.5, 20.5]
W5 = [1, 1, 1, 1, 1, 0, 0]


def daily(hrs, entered_hour=18, lag=0):
    return [Entry(for_day=i, seen_day=i + lag, seen_hour=entered_hour, minutes=round(h * 60)) for i, h in enumerate(hrs) if h]


SCENARIOS = {
    "1 steady 8.5 billed 18:00": (W5, daily([8.5, 8.5, 8.5, 8.5, 8.5])),
    "2 steady 8.5 billed next morning 10:00": (W5, daily([8.5, 8.5, 8.5, 8.5, 8.5], 10, 1)),
    "3 front-loaded 10,10,10,8,4.5": (W5, daily([10, 10, 10, 8, 4.5])),
    "4 back-loaded 0,0,10.5,10.5,10.5": (W5, daily([0, 0, 10.5, 10.5, 10.5])),
    "5 Monday zero (sick, no leave) then 9.5": (W5, daily([0, 9.5, 9.5, 9.5, 9.5])),
    "6 leave Wed, 8.5x4": ([1, 1, 0, 1, 1, 0, 0], daily([8.5, 8.5, 0, 8.5, 8.5])),
    "7 holiday Mon, 8x4": ([0, 1, 1, 1, 1, 0, 0], daily([0, 8, 8, 8, 8])),
    "8 batch biller, each day entered Fri 17:00": (W5, [Entry(i, 4, 17, 510) for i in range(5)]),
    "9 9,9,9,9,4 (1 h under LOP)": (W5, daily([9, 9, 9, 9, 4])),
    "10 8x5 then Sat 3h": (W5, [*daily([8, 8, 8, 8, 8]), Entry(5, 5, 12, 180)]),
    "11 on leave all week": ([0, 0, 0, 0, 0, 0, 0], []),
    "12 trickle hourly to 8.5/day": (
        W5,
        [Entry(d, d, hr, 120 if k < 4 else 30) for d in range(5) for k, hr in enumerate([11, 13, 15, 17, 18])],
    ),
    "13 exactly 41: 9,9,9,9,5": (W5, daily([9, 9, 9, 9, 5])),
    "14 half-day leave Thu (d=4.5), 8.5,8.5,8.5,4.5,8.5": ([1, 1, 1, 0.5, 1, 0, 0], daily([8.5, 8.5, 8.5, 4.5, 8.5])),
    "15 Friday billed Saturday 10:00": (W5, [*daily([8.5, 8.5, 8.5, 8.5]), Entry(4, 5, 10, 510)]),
    "16 3-day week (Mon,Tue holidays) 8.5x3": ([0, 0, 1, 1, 1, 0, 0], daily([0, 0, 8.5, 8.5, 8.5])),
    "17 50 h week: 10x5": (W5, daily([10, 10, 10, 10, 10])),
    "18 Thu partial 3.5 entered, rest never": (W5, daily([9.2, 8.4, 9.0, 3.5, 8.5])),
}

# Where the engine deliberately differs from the sim: {(scenario, day, hour): {field index: engine value}}.
# Scenario 18: today-left is 477 min (7.95 h) and 267 min (4.45 h); JS floats make them 7.9499.. and 4.4499.., so the
# sim shows 7.9 / 4.4. The engine works in whole minutes and rounds half up: 8.0 / 4.5.
OVERRIDES = {
    ("18 Thu partial 3.5 entered, rest never", 3, 9.0): {4: 8.0},
    ("18 Thu partial 3.5 entered, rest never", 3, 12.5): {4: 8.0},
    ("18 Thu partial 3.5 entered, rest never", 3, 18.5): {4: 4.5},
}

ROW = re.compile(r"^(\w{3}) +([\d.]+)  (.*?) +logged +(\S+)(?:  today-left (\S+)  need/day (\S+)  lopNeed (\S+))?$")


def sim_rows():
    """{scenario: [(day, hour, label, logged, today_left, need, lop_need)]} with '-' / absent as None."""
    out, cur = {}, None
    for line in SIM_OUT.read_text().splitlines():
        if line.startswith("## "):
            cur = out.setdefault(line[3:], [])
        elif m := ROW.match(line):
            day, hour, label, *nums = m.groups()
            cur.append((DAYS.index(day), float(hour), label, *(None if n in (None, "-") else float(n) for n in nums)))
    return out


def h(minutes, places):
    """Engine minutes → hours at the sim's precision (JS toFixed rounds half-up)."""
    from decimal import ROUND_HALF_UP, Decimal

    return None if minutes is None else float(Decimal(minutes / 60).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP))


def expected(name):
    rows = []
    for row in ROWS[name]:
        fix = OVERRIDES.get((name, row[0], row[1]), {})
        rows.append(tuple(fix.get(i, v) for i, v in enumerate(row)))
    return rows


ROWS = sim_rows()


@pytest.mark.parametrize("name", SCENARIOS)
def test_matches_sim(name):
    work, entries = SCENARIOS[name]
    got = []
    for day, hour, *_ in ROWS[name]:
        r = week_verdict(work, entries, day, hour)
        got.append((day, hour, r.label, h(r.logged, 1), h(r.today_left, 1), h(r.need, 2), h(r.lop_need, 2)))
    assert got == expected(name)


def test_monday_morning_with_last_friday_still_pending():
    """Friday unbilled is only "not billed yet" until 12:00 next Monday (day 7); then it is lost pay."""
    entries = daily([8.5, 8.5, 8.5, 8.5])
    at_nine = week_verdict(W5, entries, 7, 9)
    assert (at_nine.label, at_nine.logged) == ("BILL · Fri not billed yet", 2040)
    assert week_verdict(W5, entries, 7, 12).label == "LOP 1d"  # 34 h: 3 full days + 7 h (>= 5 h) = 4 of 5


def test_hours_display_rounds_half_up():
    assert hours(267) == "4.5"  # 4.45 h
    assert hours(477) == "8.0"  # 7.95 h
    assert hours(480, trim=True) == "8"


def test_verdict_carries_the_week_target():
    assert week_verdict(W5, [], 0, 9).target == 2550  # 42.5 h
    assert week_verdict([1, 1, 1, 0.5, 1, 0, 0], [], 0, 9).target == 2460  # half-day week: pay line 41 h wins over 38.25 h


def test_custom_rules_change_lop_count_lop_line_and_the_week_verdict():
    from pace.engine import DEFAULT, Rules, lop_count, lop_line

    assert DEFAULT == Rules(target=510, full=540, part=300)
    loose = Rules(target=480, full=480, part=240)
    assert lop_count(2400, 5) == 1  # 40 h at 9/5: 4 full days + 4 h < 5 h
    assert lop_count(2400, 5, loose) == 0  # 40 h at 8/4: 5 full days
    assert lop_line(5, loose) == 480 * 4 + 240 == 2160
    entries = daily([8, 8, 8, 8, 8])
    assert week_verdict(W5, entries, 5, 12).label == "LOP 1d"
    v = week_verdict(W5, entries, 5, 12, loose)
    assert (v.label, v.target) == ("DONE", 2400)
