"""Week verdict: no GTK, no I/O. A port of sim/week-rules-v4.js, working in whole minutes.

LOP (loss of pay) follows hrms-api: lop_count = max(0, d - (total // 9 h + (total % 9 h >= 5 h))), per Mon-Fri week,
total = billable + non-billable.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
T = 510  # 8.5 h: the day's target
FULL = 540  # 9 h: one LOP-safe day
PART = 300  # 5 h: the remainder that still counts as a day
EOD = 20  # hour the day's own work window closes
MAXDAY = 630  # 10.5 h: the most a day can reasonably take
GRACE_UNTIL = 12  # hour of the next working day until which an unbilled day is only "not billed yet"


@dataclass(frozen=True)
class Entry:
    for_day: int  # 0 = Mon: the day the hours are billed against
    seen_day: int  # when Pace first saw it (7 = next Monday)
    seen_hour: float
    minutes: int


@dataclass(frozen=True)
class Verdict:
    label: str
    logged: int
    today_left: float | None = None  # minutes still to bill today; None once the day is over
    need: float | None = None  # minutes per working day to reach the target
    lop_need: float | None = None  # minutes per working day to stay clear of LOP
    target: float | None = None  # the week's target in minutes; None on a week of leave
    pending: tuple[int, ...] = ()  # working days with nothing billed yet, still inside their grace (0 = Mon)


def lop_count(total: float, d: float) -> float:
    return 0 if d <= 0 else max(0, d - (total // FULL + (1 if total % FULL >= PART else 0)))


def lop_line(d: float) -> int:
    """Smallest weekly total with no LOP: 41 h for both 5 and 4.5 working days."""
    return FULL * (math.ceil(d) - 1) + PART


def week_verdict(work: Sequence[float], entries: Sequence[Entry], day: int, hour: float) -> Verdict:
    """work: fraction of each day Mon..Sun that is a working day (1, 0.5, 0). day/hour: now."""
    # Weekend billings count toward the total, as in hrms-api's Mon 00:00 - Sun 23:59 window (report-window.ts:75-79).
    seen = [e for e in entries if e.seen_day < day or (e.seen_day == day and e.seen_hour <= hour)]

    def for_day(i: int) -> int:
        return sum(e.minutes for e in seen if e.for_day == i)

    logged = sum(e.minutes for e in seen)
    d = sum(work)
    if d == 0:
        return Verdict("ON LEAVE", logged)
    lop = lop_line(d)
    target = max(T * d, lop)  # half-day weeks: 38.25 h < 41 h, pay wins
    last_work = max(i for i, w in enumerate(work) if w)

    def next_work(i: int) -> int:
        return next((j for j in range(i + 1, 7) if work[j]), 7)  # 7 = next Monday

    # A working day with ZERO hours billed is "not billed yet" (not a shortfall) from its EOD until 12:00 of the
    # next working day (Fri -> Mon 12:00). Partial days count as billed.
    credit, pending = 0.0, []
    for i in range(min(day, 6) + 1):
        if not work[i] or for_day(i) > 0:
            continue
        closed = i < day or hour >= EOD
        nw = next_work(i)
        if closed and (day < nw or (day == nw and hour < GRACE_UNTIL)):
            credit += T * work[i]
            pending.append(i)
    eff = logged + credit
    tag = f" · {','.join(DAYS[i] for i in pending)} not billed yet" if pending else ""

    if day > last_work:
        n = lop_count(eff, d)
        return Verdict(
            ("DONE" if logged >= target else "BILL" if eff >= target else f"LOP {n:g}d" if n > 0 else "SHORT (pay safe)") + tag,
            logged,
            target=target,
            pending=tuple(pending),
        )

    after_eod = hour >= EOD
    rem = sum(work[day + 1 :]) + (0 if after_eod else work[day])
    today = for_day(day)
    in_today = not after_eod and work[day] > 0
    base = eff - today if in_today else eff  # today's hours don't move need/day until EOD
    need = (target - base) / rem if rem > 0 else None
    lop_need = (lop - base) / rem if rem > 0 else None
    today_left = max(0, need * work[day] - today) if in_today else None

    past_days = sum(work[: day + (1 if after_eod else 0)])
    before = logged if after_eod else logged - today
    if logged >= target:
        label = "DONE"
    elif eff >= target:
        label = "BILL"
    elif eff < lop and (rem == 0 or lop_need > MAXDAY):
        label = "PAY RISK"
    elif rem == 0:
        label = "SHORT (pay safe)"
    elif need > MAXDAY:
        label = "BEHIND"
    elif need > FULL:
        label = "TIGHT"
    elif past_days > 0 and day != last_work and before >= FULL * past_days:
        label = "AHEAD"
    else:
        label = "ON TRACK"
    if day == last_work and eff < lop:  # last working day: show the hard pay gap next to the band
        label += f" · pay needs {hours(lop - eff)} h"
    # red points at the fixable day: closed working days under 8.5 h this week
    short_days = [
        f"{DAYS[i]} {hours(for_day(i), trim=True)} h"
        for i in range(day + 1)
        if work[i] and (i < day or after_eod) and i not in pending and for_day(i) < T * work[i] - 15
    ]
    if label.startswith("PAY RISK") and short_days:
        label += " · " + ", ".join(short_days)
    label += tag
    return Verdict(label, logged, today_left, need, lop_need, target, tuple(pending))


def hours(minutes: float, trim: bool = False) -> str:
    """Minutes as hours to one decimal, rounding half up: 267 min shows 4.5. trim drops a trailing .0."""
    text = f"{math.floor(minutes / 6 + 0.5) / 10:.1f}"
    return text.removesuffix(".0") if trim else text
