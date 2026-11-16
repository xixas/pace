import pytest

from pace import tray

B7 = {
    "colour": "green",
    "snoozed_until": None,
    "tray": {
        "number": "30",
        "tooltip_title": "Pace — Week · On track",
        "tooltip_lines": ["30.1 / 42.5 h · needs 8.0 h/day", "Tweelin Oct 112.5 / 133 h (−6.5)"],
        "info_rows": ["Week · On track — 30.1 / 42.5 h", "Needs 8.0 h/day · 4.5 h left today", "Tweelin −6.5 h (Oct)"],
        "fill": 0.71,
    },
}


def labels(items):
    return [i["props"].get("label", "---") for i in items]


def test_menu_items_for_b7_example():
    items = tray.menu_items(B7)
    assert labels(items) == [
        "Week · On track — 30.1 / 42.5 h",
        "Needs 8.0 h/day · 4.5 h left today",
        "Tweelin −6.5 h (Oct)",
        "---",
        "Open dashboard",
        "Open PineStem",
        "Show mini widget",
        "Snooze nudges today",
        "Refresh",
        "Quit",
    ]
    assert [i["props"]["enabled"] for i in items[:3]] == [False] * 3
    assert items[3]["props"]["type"] == "separator"
    assert all(i["props"]["enabled"] for i in items[4:])


def test_ids_are_unique_and_stable_across_updates():
    a = {i["props"].get("label"): i["id"] for i in tray.menu_items(B7)}
    b = tray.menu_items({**B7, "tray": {**B7["tray"], "info_rows": ["x"]}})
    assert len({i["id"] for i in b}) == len(b)
    assert {i["props"].get("label"): i["id"] for i in b}["Quit"] == a["Quit"]


def test_snoozed_row_becomes_undo():
    items = tray.menu_items({**B7, "snoozed_until": "2026-10-30T00:00:00"})
    assert "Nudges snoozed until midnight · Undo" in labels(items)
    assert "Snooze nudges today" not in labels(items)


def test_menu_without_tray_data_still_has_actions():
    items = tray.menu_items({"tray": None})
    assert labels(items)[0] == "Open dashboard"


def test_layout_shape():
    revision, (root_id, props, children) = tray.layout(B7, 1)
    assert revision == 1 and root_id == 0
    assert props["children-display"].unpack() == "submenu"
    assert len(children) == 10
    child_id, child_props, grandchildren = children[0].unpack()
    assert child_props["label"] == "Week · On track — 30.1 / 42.5 h" and grandchildren == []


@pytest.mark.parametrize(
    "label,action",
    [
        ("Open dashboard", "dashboard"),
        ("Open PineStem", "pinestem"),
        ("Show mini widget", "widget"),
        ("Snooze nudges today", "snooze"),
        ("Refresh", "refresh"),
        ("Quit", "quit"),
    ],
)
def test_action_for_menu_item(label, action):
    item = next(i for i in tray.menu_items(B7) if i["props"].get("label") == label)
    assert item["action"] == action


def test_signed_out_menu_leads_with_a_working_sign_in():
    items = tray.menu_items({"state": "signed_out", "tray": {"info_rows": ["Sign in again"]}})
    first_action = next(i for i in items if i.get("action"))
    assert (first_action["props"]["label"], first_action["action"]) == ("Sign in", "signin")
    assert "Sign in" not in labels(tray.menu_items(B7))


def test_unsnooze_action():
    item = next(i for i in tray.menu_items({**B7, "snoozed_until": "x"}) if i["props"].get("label", "").endswith("Undo"))
    assert item["action"] == "unsnooze"
