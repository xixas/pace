"""The 13 B1 top-bar states as status.json files, each built from a real week, for the extension's tests and screenshots.

The fixtures must be what paced really writes: this test rebuilds each one with status() and compares.
Regenerate after a deliberate change: python3 -c "import sys; sys.path.insert(0, 'tests'); from test_panel_fixtures import write; write()"
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from test_status_details import MON, TWE, build

from pace.status import status

DIR = Path(__file__).parent.parent / "extension" / "tests" / "fixtures"
RES = {"code": "RES", "name": "R&D", "monthly_h": None, "prorate": False, "source": "personal"}
TARGETS = {"projects": [TWE, RES]}
ROWS = [
    {"date": "2026-10-05", "project_id": 1, "project_name": "Tweelin", "billable_min": 6750, "non_billable_min": 0},
    {"date": "2026-10-06", "project_id": 2, "project_name": "R&D", "billable_min": 1104, "non_billable_min": 0},
]
ALL_LEAVE = [(MON + timedelta(i), "leave") for i in range(5)]


def week(minutes, at, **kw):
    return build(minutes, at, targets=TARGETS, rows=ROWS, **kw)


def at(day, hour, minute=0):
    return datetime(2026, 10, 26 + day, hour, minute)


CASES = {
    "01-on-track": week([552, 504, 540, 210], at(3, 14, 10), now_day=3),
    "02-ahead": week([570, 570, 564], at(2, 20, 30)),
    "03-tight": week([480, 450, 450, 0], at(3, 9, 30)),
    "04-behind": week([420, 420, 420, 0], at(3, 9, 30)),
    "05-pay-risk": week([552, 504, 360, 210, 0], at(4, 11)),
    "06-bill": week([510, 510, 510, 510, 0], at(4, 20, 30)),
    "07-last-day-gap": week([552, 504, 540, 540, 264], at(4, 18, 30), now_day=4),
    "08-done": week([600, 600, 600, 750], at(3, 18, 30)),
    "09-short": week([510, 510, 510, 510, 468], at(5, 9)),
    "10-lop": week([510, 510, 510, 510, 330], at(5, 9)),
    "11-on-leave": week([0], at(2, 10), off=ALL_LEAVE),
    "12-offline": week([552, 504, 540, 0], at(3, 9, 40), problem="offline", retry_at=at(3, 14, 12)),
    "13-signed-out": status(None, None, problem="signed_out"),
}


def write():
    DIR.mkdir(parents=True, exist_ok=True)
    for name, s in CASES.items():
        (DIR / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("name", CASES)
def test_fixture_is_what_paced_writes(name):
    assert json.loads((DIR / f"{name}.json").read_text()) == CASES[name]


def test_no_stray_fixtures():
    assert sorted(p.stem for p in DIR.glob("*.json")) == sorted(CASES)
