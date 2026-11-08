"""Screenshot the Pace panel label for every fixture in a headless GNOME Shell (slice 4 acceptance).

Run inside its own D-Bus so nothing touches the real session, settings or status.json:
    dbus-run-session -- python3 extension/tests/screenshots.py --out /path/to/dir

The shell gets temp XDG dirs and keyfile GSettings with only pace@osmosys enabled. Each fixture is put in
place the way paced does (write + rename), then the right end of the top bar is captured to <out>/<name>.png.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

HERE = Path(__file__).resolve().parent
EXT = HERE.parent / "pace@osmosys"
UUID = "pace@osmosys"
W, H = 1600, 900
STRIP = 640  # right end of the top bar: the Pace label plus the system indicators
# Shell only takes screenshots from callers owning one of these names (ui/screenshot.js, GNOME 50)
ALLOWED_NAME = "org.gnome.SettingsDaemon.MediaKeys"

KEYFILE = f"""[org/gnome/shell]
enabled-extensions=['{UUID}']
disable-user-extensions=false
welcome-dialog-last-shown-version='999'

[org/gnome/desktop/interface]
clock-show-weekday=true
"""


def call(bus, method, args, reply):
    return bus.call_sync(
        "org.gnome.Shell.Screenshot",
        "/org/gnome/Shell/Screenshot",
        "org.gnome.Shell.Screenshot",
        method,
        args,
        GLib.VariantType(reply),
        Gio.DBusCallFlags.NONE,
        10000,
        None,
    )


def wait_for_shell(bus, shell, probe, timeout=60):
    end, err = time.monotonic() + timeout, None
    while time.monotonic() < end:
        if shell.poll() is not None:
            sys.exit(f"gnome-shell exited with {shell.returncode}")
        try:
            call(bus, "ScreenshotArea", GLib.Variant("(iiiibs)", (0, 0, 1, 1, False, str(probe))), "(bs)")
            return
        except GLib.Error as e:
            err = e.message
            time.sleep(0.5)
    sys.exit(f"gnome-shell didn't come up: {err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fixtures", type=Path, default=HERE / "fixtures")
    a = ap.parse_args()
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ or not os.environ.get("PACE_PRIVATE_BUS"):
        sys.exit("run me as: PACE_PRIVATE_BUS=1 dbus-run-session -- python3 extension/tests/screenshots.py --out DIR")
    a.out.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="pace-shot-"))
    env = dict(os.environ)
    for k in ("DATA", "CONFIG", "STATE", "CACHE", "RUNTIME"):
        d = root / k.lower()
        d.mkdir(mode=0o700)
        env[f"XDG_{k}_HOME" if k != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(d)
    exts = root / "data" / "gnome-shell" / "extensions"
    exts.mkdir(parents=True)
    (exts / UUID).symlink_to(EXT)
    (root / "config" / "glib-2.0" / "settings").mkdir(parents=True)
    (root / "config" / "glib-2.0" / "settings" / "keyfile").write_text(KEYFILE)
    env["GSETTINGS_BACKEND"] = "keyfile"
    for k in ("WAYLAND_DISPLAY", "DISPLAY"):
        env.pop(k, None)
    state = root / "state" / "pace"
    state.mkdir()

    log = open(a.out / "gnome-shell.log", "w")
    shell = subprocess.Popen(
        ["gnome-shell", "--headless", "--wayland", "--no-x11", "--virtual-monitor", f"{W}x{H}"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        Gio.bus_own_name_on_connection(bus, ALLOWED_NAME, Gio.BusNameOwnerFlags.NONE, None, None)
        wait_for_shell(bus, shell, root / "probe.png")
        time.sleep(3)  # startup animation into the desktop
        for f in sorted(a.fixtures.glob("*.json")):
            tmp = state / ".status.json.tmp"
            shutil.copyfile(f, tmp)
            tmp.replace(state / "status.json")
            time.sleep(1.0)
            png = a.out / f"{f.stem}.png"
            ok, _ = call(bus, "ScreenshotArea", GLib.Variant("(iiiibs)", (W - STRIP, 0, STRIP, 32, False, str(png))), "(bs)")
            print(("ok   " if ok else "FAIL ") + png.name)
    finally:
        shell.terminate()
        shell.wait(10)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
