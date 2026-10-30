"""status.json: the one file the panel extension, tray and mini widget read. No GTK.

Panel text follows the B1 mockup in docs/design.html. Bump VERSION on any breaking change to the keys.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from pace.engine import Verdict, hours

VERSION = 1


# engine verdict → (state, colour, icon). Colours are the claude-usage palette names the extension maps to hex.
LOOK = {
    "ON TRACK": ("on_track", "green", "dot"),
    "AHEAD": ("ahead", "green", "triangle"),
    "TIGHT": ("tight", "amber", "dot"),
    "BEHIND": ("behind", "amber", "dot"),
    "PAY RISK": ("pay_risk", "red", "dot"),
    "BILL": ("bill", "blue", "ring"),
    "DONE": ("done", "green", "check"),
    "SHORT (pay safe)": ("short", "amber", "dot"),
    "LOP": ("lop", "red", "dot"),
    "ON LEAVE": ("on_leave", "grey", "circle"),
}
PAY_NEEDS = re.compile(r" · (pay needs [\d.]+ h)")


def status(v: Verdict | None, as_of: datetime | None, problem: str | None = None) -> dict:
    """v and as_of are the last good fetch. problem: "offline" (keep the numbers, greyed) or "signed_out"."""
    if problem == "signed_out":
        state, colour, icon, text = "signed_out", "amber", "dot", "Sign in again"
    else:
        head = v.label.split(" · ")[0]
        state, colour, icon = LOOK["LOP" if head.startswith("LOP ") else head]
        text = panel_text(state, v)
        if problem == "offline":
            state, colour, icon, text = "offline", "grey", "circle", f"{text} · {as_of:%H:%M}"
    return {
        "version": VERSION,
        "as_of": as_of.isoformat() if as_of else None,
        "state": state,
        "colour": colour,
        "icon": icon,
        "text": text,
        "verdict": v.label if v else None,
        "logged_min": v.logged if v else None,
        "target_min": v.target if v else None,
    }


def panel_text(state: str, v: Verdict) -> str:
    if state == "on_leave":
        return "On leave"
    if state == "done":
        return f"{hours(v.logged)} h"
    if state == "lop":
        n = v.label.split(" · ")[0].removeprefix("LOP ").removesuffix("d")
        return f"{hours(v.logged)} h · LOP {n} {'day' if float(n) <= 1 else 'days'}"
    text = f"{hours(v.logged)} / {hours(v.target)} h"
    if state == "behind":
        return f"{text} · pay {hours(v.lop_need)}/day"
    if state == "pay_risk":
        return f"{text} · pay risk"
    if state == "short":
        return f"{text} · pay safe"
    if m := PAY_NEEDS.search(v.label):  # last working day under the pay line: the gap is always in the label
        return f"{text} · {m.group(1)}"
    return text


def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "pace"


def write_status(s: dict) -> Path:
    """Replace status.json atomically, so a reader never sees half a file."""
    path = state_dir() / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".status-")
    with os.fdopen(fd, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, path)
    return path
