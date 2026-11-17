# Pace architecture

One daemon computes everything. Several frontends only draw what it wrote. All the maths and all the
wording happen once, in `paced`, so the GNOME panel, the tray, the widget and the notifications can never
disagree. The keys and the D-Bus members are specified in [`contract.md`](contract.md). This page explains
how they fit together.

```
 Entra (browser, PKCE) ──► hrms-api ──► paced ──► $XDG_STATE_HOME/pace/status.json ──► GNOME extension (panel, menu)
                           my-hours      │                                        ├─► tray (KDE and others, inside paced)
                           my-days       │                                        ├─► GTK app / GTK mini widget
                                         │                                        └─► nudges (org.freedesktop.Notifications)
                                         └── D-Bus io.github.xixas.Pace ◄── frontends call Refresh, Snooze, SignIn, …
```

## The daemon: `paced`

`pace/daemon.py` uses Gio and never imports GTK. At login it paints the cached week straight away, then
polls hrms-api every `refresh_minutes`, which is 15 by default and set in `settings.json`. A fresh fetch is limited to one a minute.

| Step | Module |
|---|---|
| Entra token → HRMS session, refresh | `pace/client.py`, `pace/signin.py`, `pace/tokens.py` |
| hrms-api rows → engine inputs | `pace/hrms.py` (pure) |
| One poll cycle: ledger → verdict → status dict | `pace/poll.py` |
| Week verdict and LOP maths | `pace/engine.py` (pure, ported from `sim/week-rules-v4.js`) |
| Month per-project maths, `at_risk` | `pace/targets.py` |
| Panel wording, `status.json` write | `pace/status.py` |
| Nudges | `pace/notify.py` |
| D-Bus name `io.github.xixas.Pace`, interface `io.github.xixas.Pace1` | `pace/service.py` |
| Offline retry (from 30 s, doubling up to the refresh interval) | `pace/daemon.py` (`offline_delay`, `next_poll_in`) |
| Scheduling the polls, polling on `network-changed` | `pace/cli.py` (`poll_now`) |

`status.json` is replaced by an atomic rename and is mode 600, because it holds one person's hours. The
same goes for every file in `pace/files.py`. Bump `VERSION` in `pace/status.py` on any breaking change to
its keys.

## Frontends

| Frontend | Where | How it learns of changes |
|---|---|---|
| GNOME panel indicator and menu | `extension/pace@osmosys/extension.js`, `look.js`, `menu.js` | Watches the state **directory**, since a rename replaces the file, and re-reads once a minute so it can tell when paced has stopped |
| GNOME mini widget | `extension/pace@osmosys/widget.js`, `widgetModel.js` | Drawn by the shell, so it stays on top and on every workspace. It owns the bus name `io.github.xixas.Pace.Shell`, and `pace/shell.py` toggles it |
| Tray ring and menu | `pace/tray.py` (StatusNotifierItem plus a hand-written dbusmenu), `pace/trayicon.py` (pycairo) | Runs inside paced on desktops other than GNOME that have a StatusNotifier watcher (`tray_wanted` in `pace/cli.py`) |
| GTK app | `pace/ui/` | Reads the status, profile, settings and targets files. It writes `settings.json` and `targets.json` |
| GTK mini widget | `pace/ui/miniwidget.py` | The fallback when the shell extension is not running, which `pace/shell.py` reports by returning `None` or `False` |

Frontends never recompute verdicts. They format nothing beyond what `status.json` already carries.
`look.js` maps the keys to colours and icons.

## Rules that shape the code

- **The core never imports GTK.** `pace status` and `paced` must run without it. `pace.cli.main` imports
  `pace.ui` lazily, only for app commands.
- **Pure modules stay pure.** `engine.py` and `hrms.py` do no I/O, so their tests need no bus, network or
  keyring. In `targets.py`, only `load()` reads a file and the maths is pure.
- **Hours are whole minutes and times are naive local ISO 8601**, everywhere.
- **The contract wins on data and the design wins on look and wording.** That means `docs/contract.md`
  and `docs/design.html` respectively, with section ids like B3 and C10 that the code comments cite.

## Sign-in and sessions

Pace is an Entra public client: auth code plus PKCE, redirected to a one-shot loopback server. The Osmosys
tenant has granted admin consent for the whole organisation, so users see no consent prompt. The resulting
HRMS session (`access`, `refresh`) is stored according to the `token_store` setting (`session_store` in
`pace/cli.py`):

- `keyring`: the Secret Service keyring when it has a default collection (`KeyringFirst`), otherwise a
  mode-600 file (`FileStore`).
- `file`: always the file.
- `none`: memory only, so you sign in at each login.

A locked KWallet at login currently blocks paced's main loop, because the keyring read happens on it.

## Upstream limits

- `my-days` returns 1 or 0 per day, so a half-day leave counts as a full leave day.
- LOP follows hrms-api's formula: `lop_count = max(0, d - (total // 9 h + (total % 9 h >= 5 h)))` per
  Monday-to-Friday week, where `total` is billable plus non-billable minutes.
