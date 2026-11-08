"""The 13 B1 top-bar states as status.json files, for the extension's tests and screenshots.

The fixtures must be what paced really writes: this test rebuilds each one with status() and compares.
Regenerate after a deliberate change: python3 -c "import sys; sys.path.insert(0, 'tests'); from test_panel_fixtures import write; write()"
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from pace.engine import Verdict
from pace.status import status

DIR = Path(__file__).parent.parent / "extension" / "tests" / "fixtures"
AT = datetime(2026, 10, 29, 14, 10)

CASES = {
    "01-on-track": status(Verdict("ON TRACK", 1806, target=2550), AT),
    "02-ahead": status(Verdict("AHEAD", 1704, target=2550), AT),
    "03-tight": status(Verdict("TIGHT", 1380, target=2550), AT),
    "04-behind": status(Verdict("BEHIND", 1260, lop_need=600, target=2550), AT),
    "05-pay-risk": status(Verdict("PAY RISK · pay needs 13.9 h · Mon 0 h", 1626, target=2550), AT),
    "06-bill": status(Verdict("BILL · Fri not billed yet", 2040, target=2550), AT),
    "07-last-day-gap": status(Verdict("ON TRACK · pay needs 1.0 h", 2400, target=2550), AT),
    "08-done": status(Verdict("DONE", 2550, target=2550), AT),
    "09-short": status(Verdict("SHORT (pay safe)", 2508, target=2550), AT),
    "10-lop": status(Verdict("LOP 1d", 2370, target=2550), AT),
    "11-on-leave": status(Verdict("ON LEAVE", 0), AT),
    "12-offline": status(Verdict("ON TRACK", 1596, target=2550), datetime(2026, 10, 29, 9, 40), problem="offline"),
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
