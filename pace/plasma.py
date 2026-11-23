"""KDE Plasma 6: the Pace applet (plasma/io.github.xixas.Pace), the KDE counterpart of the GNOME panel extension.

Whether it's on a panel (paced then leaves the tray ring out), and putting it there for the person (onboarding A10 and
the app menu). No GTK here.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

APPLET = "io.github.xixas.Pace"

# Plasma's scripting API (evaluateScript): add the applet to the first panel unless some panel already has it
ADD_SCRIPT = f"""
var have = panels().some(function (p) {{ return p.widgets().some(function (w) {{ return w.type === "{APPLET}"; }}); }});
if (!have && panels().length) panels()[0].addWidget("{APPLET}");
"""


def appletsrc() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasma-org.kde.plasma.desktop-appletsrc"


def applet_on_panel(path: Path | None = None) -> bool:
    """The applet is on a panel or the desktop: Plasma lists every applet in its config, by plugin id."""
    try:
        text = (path or appletsrc()).read_text(errors="replace")
    except OSError:
        return False
    return any(line.strip() == f"plugin={APPLET}" for line in text.splitlines())


def add_to_panel(run=subprocess.run) -> bool:
    """Ask plasmashell to put the applet on the first panel. False when Plasma didn't answer (not running, too old)."""
    r = run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.kde.plasmashell",
            "--object-path",
            "/PlasmaShell",
            "--method",
            "org.kde.PlasmaShell.evaluateScript",
            ADD_SCRIPT,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r.returncode == 0
