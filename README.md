# Pace

Pace shows your PineStem billed hours on the Linux desktop panel. It compares them with your weekly target,
the loss-of-pay (LOP) line and your monthly per-project targets, so you can see whether the week is on track
without opening PineStem.

It signs in with your Osmosys Microsoft (Entra) account. It reads hours and leave days from hrms-api
(`/api/billing-report/my-hours/`, `/api/calendar/my-days/`), and never writes anything back.

| Desktop | What you get |
|---|---|
| GNOME | A top-bar indicator and menu, plus a mini widget drawn by GNOME Shell (always on top, on every workspace) |
| KDE Plasma, COSMIC, XFCE, Cinnamon | A tray ring icon with a menu, plus the mini widget as a GTK window |
| Any desktop | The `pace` app: dashboard, targets, preferences, onboarding |

## Install

Releases are on GitHub (`xixas/pace`, a private repo). Every release ships an rpm, a deb and an Arch
package. It ships an AppImage too when that best-effort build succeeds.

| Distro | Command |
|---|---|
| Fedora | `sudo dnf install ./pace-X.Y.Z-1.fc44.noarch.rpm` |
| Ubuntu / Debian | `sudo apt install ./pace_X.Y.Z_all.deb` |
| Arch / CachyOS / Manjaro | `sudo pacman -U pace-X.Y.Z-1-any.pkg.tar.zst` |

**After installing, log out and back in.** GNOME on Wayland loads extension code only at login. The
autostart entry starts `paced` at login too. Then run `pace` to sign in.

The packages pull in `python3` (3.11 or newer), PyGObject, pycairo, GTK 4, libadwaita and libsecret. KDE
installs deliberately do not pull in GNOME Shell. The AppImage is best-effort: it has no autostart and it
relies on host libraries.

## Use

| Command | Does |
|---|---|
| `pace` | Opens the app: the dashboard, or onboarding when you are signed out |
| `pace sign-in` | Browser sign-in (auth code + PKCE, with a loopback redirect) |
| `pace status` | Prints the current `status.json` |
| `pace widget` / `pace settings` | Opens the mini widget or the preferences |
| `paced` | The daemon. It polls hrms-api and publishes the status |
| `paced --once` | Runs one poll and exits |

| File | Holds |
|---|---|
| `$XDG_CONFIG_HOME/pace/config.json` | Optional server override (`base_url`, `tenant`, `client_id`, `api_client_id`). The built-in default is production hrms-api |
| `$XDG_CONFIG_HOME/pace/settings.json` | Preferences, written by the app |
| `$XDG_CONFIG_HOME/pace/targets.json` | Weekly and per-project monthly targets |
| `$XDG_STATE_HOME/pace/status.json` | The current verdict. Every frontend reads it |
| keyring (or a mode-600 file) | The HRMS session |

## Develop

```sh
uv run pytest -q
uvx ruff check . && uvx ruff format --check .
gjs -m extension/tests/look.test.js
gjs -m extension/tests/widget.test.js
make check          # desktop-file and AppStream validation
```

To run against a local stand-in for hrms-api instead of production, start
`python3 dev/mock_hrms.py --data snapshot.json` and point `config.json` at
`"base_url": "http://127.0.0.1:8001/api"`. Keep `snapshot.json` outside the repo: it is personal billing
data.

Unit tests miss whole classes of UI bugs. For the headless GNOME Shell harness, the GTK app over
Broadway, the KDE container and the package smoke tests, see [`docs/testing.md`](docs/testing.md).

## Layout

| Path | What |
|---|---|
| `pace/` | Core in plain Python: the engine, polling, `paced`, D-Bus, sign-in, tokens, tray. No GTK |
| `pace/ui/` | The GTK 4 / libadwaita app and the GTK mini widget |
| `extension/pace@osmosys/` | The GNOME Shell extension: indicator, menu, shell-drawn widget |
| `extension/tests/` | gjs unit tests, panel and menu fixtures, the headless-shell screenshot harness |
| `tests/` | pytest suite |
| `packaging/` | rpm spec, Debian files, PKGBUILD, AppImage, build and smoke-test scripts |
| `data/` | `.desktop` files, icons, AppStream metainfo |
| `dev/mock_hrms.py` | Local stand-in for hrms-api |
| `sim/` | The original JS model of the week rules that `pace/engine.py` was ported from |
| `docs/` | Architecture, contract, design, testing |

For how the pieces fit together, see [`docs/architecture.md`](docs/architecture.md). The data contract
between them is [`docs/contract.md`](docs/contract.md). Screens and wording are specified in
`docs/design.html`, which you open in a browser.

## Release

1. Bump `Version:` in `packaging/rpm/pace.spec`, and add an entry to its `%changelog` and to
   `packaging/debian/changelog`. The spec is the single version source: the Makefile and
   `packaging/build-arch.sh` read it.
2. Commit `build: release X.Y.Z` on `main` and push.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`. `.github/workflows/release.yml` builds each package and
   smoke-tests it in a clean container. It publishes the GitHub release only when the rpm, deb and Arch
   packages all pass. A tag with a dash (`v0.2.0-rc1`) publishes as a prerelease.

## License

MIT
