"""status.json: what the panel extension, tray and mini widget read. Expected text is the B1 mockup in docs/design.html."""

from datetime import datetime

import pytest

from pace.engine import Verdict
from pace.status import status

AS_OF = datetime(2026, 10, 29, 14, 10)


def test_on_track_shows_hours_over_target_with_a_green_dot():
    s = status(Verdict("ON TRACK", 1806, target=2550), AS_OF)
    assert (s["state"], s["colour"], s["icon"], s["text"]) == ("on_track", "green", "dot", "30.1 / 42.5 h")
    assert (s["version"], s["as_of"], s["logged_min"], s["target_min"], s["verdict"]) == (
        1,
        "2026-10-29T14:10:00",
        1806,
        2550,
        "ON TRACK",
    )


@pytest.mark.parametrize(
    "verdict, expected",
    [
        (Verdict("AHEAD", 1704, target=2550), ("ahead", "green", "triangle", "28.4 / 42.5 h")),
        (Verdict("TIGHT", 1380, target=2550), ("tight", "amber", "dot", "23.0 / 42.5 h")),
        (Verdict("BEHIND", 1260, lop_need=600, target=2550), ("behind", "amber", "dot", "21.0 / 42.5 h · pay 10.0/day")),
        (
            Verdict("PAY RISK · pay needs 13.9 h · Mon 0 h", 1626, target=2550),
            ("pay_risk", "red", "dot", "27.1 / 42.5 h · pay risk"),
        ),
        (Verdict("BILL · Fri not billed yet", 2040, target=2550), ("bill", "blue", "ring", "34.0 / 42.5 h")),
        (
            Verdict("ON TRACK · pay needs 1.0 h", 2400, target=2550),
            ("on_track", "green", "dot", "40.0 / 42.5 h · pay needs 1.0 h"),
        ),
        (Verdict("TIGHT · pay needs 9.0 h", 1920, target=2550), ("tight", "amber", "dot", "32.0 / 42.5 h · pay needs 9.0 h")),
        (Verdict("DONE", 2550, target=2550), ("done", "green", "check", "42.5 h")),
        (Verdict("SHORT (pay safe)", 2508, target=2550), ("short", "amber", "dot", "41.8 / 42.5 h · pay safe")),
        (Verdict("LOP 1d", 2370, target=2550), ("lop", "red", "dot", "39.5 h · LOP 1 day")),
        (Verdict("LOP 2d", 1890, target=2550), ("lop", "red", "dot", "31.5 h · LOP 2 days")),
        (Verdict("ON LEAVE", 0), ("on_leave", "grey", "circle", "On leave")),
    ],
)
def test_each_verdict_has_its_b1_panel_label(verdict, expected):
    s = status(verdict, AS_OF)
    assert (s["state"], s["colour"], s["icon"], s["text"]) == expected


def test_offline_keeps_the_last_good_numbers_greyed_with_the_fetch_time():
    s = status(Verdict("ON TRACK", 1596, target=2550), datetime(2026, 10, 29, 9, 40), problem="offline")
    assert (s["state"], s["colour"], s["icon"], s["text"], s["verdict"]) == (
        "offline",
        "grey",
        "circle",
        "26.6 / 42.5 h · 09:40",
        "ON TRACK",
    )


def test_signed_out_asks_to_sign_in_again_even_with_no_numbers_yet():
    s = status(None, None, problem="signed_out")
    assert (s["state"], s["colour"], s["icon"], s["text"], s["as_of"], s["logged_min"]) == (
        "signed_out",
        "amber",
        "dot",
        "Sign in again",
        None,
        None,
    )


def test_write_status_lands_in_xdg_state_dir_atomically(tmp_path, monkeypatch):
    import json

    from pace.status import write_status

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    s = status(Verdict("DONE", 2550, target=2550), AS_OF)
    path = write_status(s)
    assert path == tmp_path / "pace" / "status.json"
    assert json.loads(path.read_text()) == s
    assert [p.name for p in path.parent.iterdir()] == ["status.json"]  # no temp file left behind
