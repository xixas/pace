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
  "lines": {"lop_min": 2460, "target_min": 2550, "expected_min": 2700},
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

- `stale_after` = `as_of` + 3 × refresh interval. A frontend shows the stale look (grey, time appended)
  once now > `stale_after`. Absent → fall back to 15 min.
- `days[].kind` ∈ billed, today, future, off (weekend/holiday/leave; `text` "off" or "½ off"), pending
  (not billed yet; `text` "not yet"), short (a past working day under 8.5 h counted in `warning`).
  Mon–Fri always present; Sat/Sun only when they have hours.
- `month.projects[]` order: projects with targets first, then by billed desc. Billable minutes only.
- `problem.kind` ∈ offline, signed_out, no_mapping, skew (C10). `null` when healthy.
- B2–B6/B12 menus, B7–B9 tray tooltip/menu and B10 widget are all rendered from these keys.

## 2. `$XDG_CONFIG_HOME/pace/settings.json` (written by the GTK app, read by paced)

```json
{
  "panel_text": "hours",
  "refresh_minutes": 15,
  "start_at_login": true,
  "expected_daily_h": 9.0,
  "notify": {
    "pay_risk":  {"on": true},
    "friday":    {"on": true, "at": "16:00"},
    "daily":     {"on": true, "at": "20:00"},
    "monday":    {"on": true, "at": "12:30"},
    "signed_out":{"on": true}
  }
}
```

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

A lead's preset file (`*.pace-targets.json`, C8) has the same `projects` shape plus `"from": "Anand"`.
Import marks rows `source: "lead"` (locked; personal targets may only raise them).
Prorate: `eff_target = monthly × avail_days ÷ month_working_days`; `need/day = (eff_target − billed) ÷ remaining avail_days`.

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

## 6. Module ownership (parallel build)

| Owner | Files |
|---|---|
| core | `pace/{engine,hrms,poll,status,daemon,cli,files,settings,targets,notify,service}.py`, `tests/test_*` for them |
| extension | `extension/**` |
| tray | `pace/tray.py`, `pace/trayicon.py`, `tests/test_tray*.py` |
| app | `pace/ui/**`, `tests/test_ui*.py` |
| packaging | `packaging/**`, `data/**`, `.github/**` |

Nobody edits `pyproject.toml` or another owner's files: report the change needed instead.
