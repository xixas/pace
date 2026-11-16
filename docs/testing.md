# Testing Pace beyond pytest

Unit tests: `uv run pytest -q`, `uvx ruff check . && uvx ruff format --check .`, and
`gjs -m extension/tests/look.test.js` / `gjs -m extension/tests/widget.test.js`. These
miss whole classes of bug (an empty shell menu from a JS error, a widget that never
opens), so check UI changes in a real shell or app too.

## GNOME Shell extension (headless)

```
PACE_PRIVATE_BUS=1 dbus-run-session -- python3 extension/tests/screenshots.py --out DIR
```

- Without `PACE_PRIVATE_BUS=1` it refuses to run.
- It starts `gnome-shell --headless` with the extension plus a test-only helper,
  `extension/tests/helper/pace-test@osmosys`, and drives the shell through
  `<state>/pace/menu-cmd`.
- The shell's own log is `DIR/gnome-shell.log`. Look there for `could not render`
  errors: a render error leaves the menu empty and the menu then refuses to open.
- One write to `menu-cmd` fires several file-monitor events, so the helper dedupes
  repeats that arrive within 500 ms. Space harness writes more than 1 s apart.

## GTK app and the regular-window widget (Broadway)

Start `gtk4-broadwayd :N`, then run the app with `GDK_BACKEND=broadway BROADWAY_DISPLAY=:N`,
and screenshot `http://127.0.0.1:808N` with Playwright
(`uv run --with playwright python ...`).

## KDE Plasma (container)

- Use a `fedora:44` docker container with `kwin-wayland` and `plasma-workspace`
  installed, and `ksecretd` as the Secret Service.
- Inside a `dbus-run-session`, run
  `kwin_wayland --virtual --xwayland -- plasmashell` with `XDG_CURRENT_DESKTOP=KDE`.
- Pass the host render node into the container (`--device /dev/dri/renderD128`).
  Software rendering segfaults on screenshot.
- Cap memory with
  `systemd-run --user --scope -p MemoryMax=4G -- docker run --memory=4g ...`.

## Packages

The release workflow builds and smoke-tests every package with
`packaging/smoke-test.sh rpm|deb|arch`:

| Package | Built in | Smoke-tested in |
|---|---|---|
| rpm | `fedora:44` | `fedora:44` |
| deb | `ubuntu:24.04` | `ubuntu:24.04` |
| Arch | `archlinux` | `cachyos/cachyos` |

The same scripts run locally under docker. In a bare container pacman prints
`command failed` lines from its install hooks; these are harmless.

## After installing a new build

- GNOME on Wayland loads extension code only at login, so extension changes need a
  log out and back in.
- `paced` and the app are plain Python. Restart `paced` (kill it by PID and start
  `/usr/bin/paced`) to pick up new code without logging out.
