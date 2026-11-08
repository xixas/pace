# Pace internal contract (v1)

The single source of truth that paced, the GNOME extension, the tray, the mini widget and the GTK app
share. Screens are specified in `docs/design.html` (section ids A1–A14, B1–B12, C1–C12). Where this file
and the design disagree on *data*, this file wins; on *look and wording*, the design wins.

Everything is local time, naive ISO 8601 (`2026-10-29T14:10:00`), as paced writes it.
Durations are whole minutes (`*_min`). Display strings are pre-formatted by paced so every
frontend shows identical text; frontends never recompute verdict maths.

## 1. `$XDG_STATE_HOME/pace/status.json` (written by paced, atomic rename, mode 600)

Existing keys (unchanged): `version` (1), `as_of`, `state`, `colour`, `icon`, `text`, `verdict`,
`logged_min`, `target_min`, `last_week`.

`state` ∈ on_track, ahead, tight, behind, pay_risk, bill, done, short, lop, on_leave, offline,
signed_out, no_mapping. `colour` ∈ green, amber, red, blue, grey. `icon` ∈ dot, triangle, ring,
check, circle.

`text` is the GNOME label **already in the user's chosen panel format** (settings `panel_text`, B11);
`""` for icon-only. All formats are also in `labels`.

Added keys (all may be `null` when there is no data, e.g. signed out):

```json
{
  "stale_after": "2026-10-29T14:55:00",
  "title": "On track",
  "subtitle": "needs 8.0 h/day",
  "note": "4.5 h left today",
  "lines": {"lop_min": 2460, "target_min": 2550, "expected_min": 2700, "emphasis": "lop"},
  "gap_text": "1.0 h to the loss-of-pay line · 2.5 h to target",
  "days": [
    {"date": "2026-10-26", "dow": "Mon", "min": 552, "kind": "billed", "text": "9.2"},
    {"date": "2026-10-29", "dow": "Thu", "min": 210, "kind": "today", "text": "3.5"},
    {"date": "2026-10-30", "dow": "Fri", "min": null, "kind": "future", "text": "–"}
  ],
  "warning": "Short days: Wed 6.0 h · Thu 3.5 h",
  "warning_detail": "Even 10.5 h today ends 3.4 h under the line, about 1 day of loss of pay.",
  "action": {"label": "Open PineStem to bill Fri", "url": "https://pinestem.com/dashboard.html#/tasks"},
  "month": {
    "name": "October", "working_days_left": 2,
    "projects": [
      {"code": "TWE", "name": "Tweelin", "billed_min": 6750, "target_min": 7980, "gap_min": -390,
       "need_per_day_min": 618, "text": "112.5 / 133 h · behind 6.5", "need_text": "needs 10.3 h/day on Tweelin",
       "short": "Tweelin −6.5 h"},
      {"code": "RES", "name": "R&D", "billed_min": 1104, "target_min": null, "gap_min": null,
       "need_per_day_min": null, "text": "18.4 h · no target", "need_text": null, "short": null}
    ]
  },
  "labels": {"hours": "30.1 / 42.5 h", "percent": "71%", "gap": "−6.5 h TWE", "left_today": "4.5 h left today"},
  "problem": {"kind": "offline", "message": "Can't reach DhiHRMS", "retry_at": "2026-10-29T14:12:00"},
  "snoozed_until": null,
  "pinestem_url": "https://pinestem.com/dashboard.html#/tasks"
}
```

- `lines.emphasis`: `"lop"` when the LOP tick should be emphasised (B3, B4), else `null`. `gap_text`: the B3
  line under the day chips, `null` when not shown.
- `stale_after` = `as_of` + 3 × refresh interval. A frontend shows the stale look (grey, time appended)
  once now > `stale_after`. Absent → fall back to 15 min.
- `days[].kind` ∈ billed, today, future, pending (not billed yet; `text` "not yet"), short (a past
  working day under 8.5 h, counted in `warning`), holiday, leave, half_leave (`text` "½ leave" or the
  hours), weekend. Mon–Fri always present; Sat/Sun only when they have hours.
- `last_week` (B12): `null`, or `{"text": "Last week: Fri 30 Oct not billed yet", "detail": "Bill by 12:00
  today or it counts as 34.0 h → LOP 1 day.", "url": pinestem_url}`.
- `tray` (B7–B9), built by core so every tray shows identical text:
  `{"number": "30", "tooltip_title": "Pace — Week · On track", "tooltip_lines": ["30.1 / 42.5 h · needs 8.0 h/day",
  "Tweelin Oct 112.5 / 133 h (−6.5)"], "info_rows": ["Week · On track — 30.1 / 42.5 h", "Needs 8.0 h/day · 4.5 h left today",
  "Tweelin −6.5 h (Oct)"], "fill": 0.71}` (`fill` = logged ÷ target, capped at 1, for the ring).
- `widget` (B10): `{"title": "Week on track", "big": "30.1 / 42.5", "side": "8.0/day", "lines": ["Wed 6.0 h · Thu 3.5 h"],
  "project": {"title": "Tweelin −6.5 h", "big": "112.5 / 133", "side": "10.3/day"} | null}`.
- Offline: paced already appends the fetch time to `text`; frontends add the stale suffix only when
  `state` is not `offline`.
- `month.projects[]` order: projects with targets first, then by billed desc. Billable minutes only.
- `problem.kind` ∈ offline, signed_out, no_mapping. `null` when healthy. Version skew (C10) is
  detected by each frontend itself (`version` ≠ the one it knows), never by paced.
- B2–B6/B12 menus, B7–B9 tray tooltip/menu and B10 widget are all rendered from these keys.

## 2. `$XDG_CONFIG_HOME/pace/settings.json` (written by the GTK app, read by paced)

```json
{
  "panel_text": "hours",
  "refresh_minutes": 15,
  "start_at_login": true,
  "expected_daily_h": 9.0,
  "notify": {
    "pay_risk":       {"on": true, "at": "11:00"},
    "friday":         {"on": true, "at": "16:00"},
    "daily":          {"on": true, "at": "20:00"},
    "monday":         {"on": true, "at": "12:30"},
    "zero_hour":      {"on": true, "at": "12:00"},
    "project_behind": {"on": true, "at": "10:30"},
    "signed_out":     {"on": true}
  },
  "widget_at_login": false,
  "token_store": "keyring"
}
```

`token_store` ∈ keyring, file, none (A9). The exact rule behind each nudge is in design C6.

Start at login uses XDG autostart, which works on every desktop. Packaging ships
`/etc/xdg/autostart/io.github.xixas.Pace.daemon.desktop` (`Exec=paced`). When `start_at_login` is
false, the app writes `~/.config/autostart/io.github.xixas.Pace.daemon.desktop` with `Hidden=true`,
and deletes it when true. `widget_at_login` works the same way with `io.github.xixas.Pace.widget.desktop`.

`panel_text` ∈ hours, percent, gap, left_today, icon. Missing file or key → these defaults.
paced re-reads it on change (Gio file monitor), no restart needed.

## 3. `$XDG_CONFIG_HOME/pace/targets.json` (A11, A12, C8)

```json
{
  "dailyMinimum": 8.5,
  "projects": [
    {"code": "TWE", "name": "Tweelin", "monthly_h": 140, "prorate": true, "source": "lead", "lead": "Anand"},
    {"code": "RES", "name": "R&D", "monthly_h": null, "prorate": false, "source": "personal"}
  ]
}
```

A lead's preset file (`*.pace-targets.json`, C8) is `{"from": "Anand", "projects": [...]}` with the
same snake_case project keys (the camelCase in the C8 mock is illustrative only).
Import marks rows `source: "lead"` (locked; personal targets may only raise them).
Prorate: `eff_target = monthly × avail_days ÷ month_working_days`; `need/day = (eff_target − billed) ÷ remaining avail_days`.

## 3a. Profile and history (core provides, the app reads)

- `$XDG_STATE_HOME/pace/profile.json`, written by core at sign-in from hrms-api's login reply:
  `{"name": "Vikas Kyatannawar", "email": "vikas.k@osmosys.co", "employee_id": "...", "pinestem_mapped": true}`.
- `pace.history.load(start: date, end: date) -> list[dict]`, a core module the app imports (raises
  `pace.client.Offline` / `SignedOut`). Ranges over 92 days are split internally. One dict per date:
  `{"date": "2026-10-26", "type": "working|weekend|holiday|leave|half_leave", "working": 1.0|0.5|0,
  "billable_min": 480, "non_billable_min": 30, "projects": [{"code": "TWE", "name": "Tweelin",
  "billable_min": 480, "non_billable_min": 0}]}`.
- `pace.targets.month(projects_rows, days, targets, month) -> list[dict]` returns the `month.projects[]`
  shape above for any month, so the dashboard Month view (C3) uses the same maths as status.json.

## 3b. In-process tray (tray owner implements, core starts it)

```python
# pace/tray.py
class Tray:
    def __init__(self, bus: Gio.DBusConnection, on_action: Callable[[str], None]): ...
    def update(self, status: dict) -> None: ...  # called after every status.json write
    def close(self) -> None: ...
```

`on_action` strings: refresh, snooze, unsnooze, dashboard, pinestem, widget, quit. Core creates a
`Tray` only when `XDG_CURRENT_DESKTOP` does not contain GNOME and an SNI watcher
(`org.kde.StatusNotifierWatcher`) is on the bus. No GTK in paced: draw the icon with pycairo
into ARGB32 pixmaps, and build the menu as a hand-written `com.canonical.dbusmenu` object.

## 4. D-Bus: paced on the session bus

Name `io.github.xixas.Pace`, object `/io/github/xixas/Pace`, interface `io.github.xixas.Pace1`:

| Member | Kind | Effect |
|---|---|---|
| `Refresh()` | method | poll now with `fresh=1` (hrms-api allows 1/min) |
| `Snooze()` | method | mute nudges until 00:00 local (`snoozed_until`) |
| `Unsnooze()` | method | undo |
| `SignIn()` | method | run the browser sign-in (same as `pace sign-in`) |
| `ShowWidget()` | method | start `pace widget` (the B10 mini widget) |
| `Quit()` | method | exit paced |
| `StatusChanged(s json)` | signal | emitted after each status.json write |

Frontends call these; if paced is not on the bus they fall back to spawning `pace <cmd>` or show
"Pace isn't running".

## 5. Commands

`pace` (GTK app, opens the dashboard, or onboarding when signed out) · `pace sign-in` · `pace status` ·
`pace widget` · `pace settings` · `paced` (daemon) · `paced --once`.

`pace.cli.main` (core) handles `sign-in` and `status` itself and hands everything else, including no
arguments, to `pace.ui.main(argv) -> int` (the app owner), imported lazily so the CLI never loads GTK.

## 6. Module ownership (parallel build)

| Owner | Files |
|---|---|
| core | `pace/{engine,hrms,poll,status,daemon,cli,files,settings,targets,notify,service}.py`, `tests/test_*` for them |
| extension | `extension/**` |
| tray | `pace/tray.py`, `pace/trayicon.py`, `tests/test_tray*.py` |
| app | `pace/ui/**`, `tests/test_ui*.py` |
| packaging | `packaging/**`, `data/**`, `.github/**` |

Nobody edits `pyproject.toml` or another owner's files: report the change needed instead.
