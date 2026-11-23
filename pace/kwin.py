"""KDE Plasma: a KWin window rule that pins the GTK mini widget (B10) above other windows, on every desktop.

GNOME Shell draws the widget itself (always on top, every workspace). On KDE the GTK card is an ordinary window, and
Wayland gives an app no way to keep itself on top, so Pace asks KWin: one rule, in its own group of kwinrulesrc,
matching only the widget (the app id plus its window title). Written with kwriteconfig6 the first time the widget
opens on KDE; never touches other rules. No GTK here.
"""

from __future__ import annotations

import shutil
import subprocess

RULE_GROUP = "pace-mini-widget"
APP_ID = "io.github.xixas.Pace.App"  # pace/ui/app.py APP_ID, the Wayland app id of every Pace window
WIDGET_TITLE = "Pace mini widget"  # pace/ui/miniwidget.py TITLE
RULES_FILE = "kwinrulesrc"

# KWin rule policies: 1 match exactly (wmclass/title), 2 force, 4 remember
RULE = {
    "Description": "Pace mini widget (added by Pace): above other windows, on every desktop",
    "wmclass": APP_ID,
    "wmclassmatch": "1",
    "wmclasscomplete": "false",
    "title": WIDGET_TITLE,
    "titlematch": "1",
    "above": "true",
    "aboverule": "2",
    "desktops": "\\0",
    "desktopsrule": "2",
    "skiptaskbar": "true",
    "skiptaskbarrule": "2",
    "skippager": "true",
    "skippagerrule": "2",
    "skipswitcher": "true",
    "skipswitcherrule": "2",
    "positionrule": "4",
}


def is_kde(desktop: str) -> bool:
    return "KDE" in desktop.upper()


def _read(run, group: str, key: str) -> str:
    r = run(["kreadconfig6", "--file", RULES_FILE, "--group", group, "--key", key], capture_output=True, text=True)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def _write(run, group: str, key: str, value: str) -> None:
    run(["kwriteconfig6", "--file", RULES_FILE, "--group", group, "--key", key, value], capture_output=True, text=True)


def ensure_widget_rule(desktop: str, run=subprocess.run, which=shutil.which) -> bool:
    """Make sure the rule exists. True when it was written now; False when it was already there or this isn't KDE."""
    if not is_kde(desktop) or not (which("kwriteconfig6") and which("kreadconfig6")):
        return False
    order = [g for g in _read(run, "General", "Order").split(",") if g]
    if RULE_GROUP in order and _read(run, RULE_GROUP, "title") == WIDGET_TITLE:
        return False
    for key, value in RULE.items():
        _write(run, RULE_GROUP, key, value)
    if RULE_GROUP not in order:
        _write(run, "General", "Order", ",".join([*order, RULE_GROUP]))
    run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.kde.KWin",
            "--object-path",
            "/KWin",
            "--method",
            "org.kde.KWin.reconfigure",
        ],
        capture_output=True,
        text=True,
    )
    return True
