# Pace draft 2 — mockup brief (shared by all builders)

Pace = Linux desktop app for Osmosys employees: billed hours (PineStem, via hrms-api) vs targets, with leave/holidays (DhiHRMS).
**Linux only.** Toolkit = **Python + GTK4 + libadwaita** (same stack as the Lifeboat app), so app windows must look like real
libadwaita: header bar with centred title, boxed-list preference rows, pill buttons, AdwViewSwitcher tabs, AdwToast,
AdwStatusPage for empty/error states, AdwBanner for in-window warnings. The panel surfaces are: a GNOME Shell extension
(top-bar label + dropdown), a StatusNotifierItem tray icon on KDE Plasma 6 / COSMIC / XFCE / Cinnamon, and an optional
mini widget window. Notifications are native desktop notifications (GNOME banner look / KDE look).

## CSS — reuse, don't reinvent
The page already has these classes (file: draft1.css next to this brief — read it): `.gn-desk .gn-top .gn-pill .gn-menu
.gn-banner` (GNOME), `.kde-desk .kde-pop .kde-panel .tray-ic` (KDE), `.cos-desk .cos-top .cos-pop` (COSMIC), `.adw .adw-head
.adw-tabs .adw-body .adw-card .adw-btn(.flat) .adw-row .sw(.off) .chip(.ok/.warn/.hot/.mute) .day(.off/.today)` (app windows),
`.mini` (widget), `.bar > i` fill + `.bar > b` tick (`.fill-ok/.fill-warn/.fill-hot`), text `.ok .warn .hot`, `.caption`, `.mono`.
Tailwind v4 + DaisyUI 5 utilities are available for layout (grid, gap, flex, text sizes). Light page theme only.
New CSS you need goes in ONE `<style>` block at the top of your fragment, every selector prefixed with your fragment prefix
(given below) so fragments never collide. No external requests, no images: draw icons with inline SVG or unicode.

## Example data (use it everywhere unless a state needs other numbers)
Thursday 29 Oct 2026, 14:10. Week Mon 26–Fri 30, 5 working days. Mon 9.2 h, Tue 8.4, Wed 9.0, Thu 3.5 so far → logged 30.1 h.
Target 42.5 h (8.5 × 5). LOP line 41 h. Expected 45 h. need/day 8.0 h (Thu–Fri). Today: 4.5 h left. Verdict ON TRACK.
Month: Tweelin (TWE) target 140 h, prorated to 133 h (one leave day 9 Oct), billed 112.5 → behind 6.5 h, needs 10.3 h/day.
R&D (RES) 18.4 h, no target. User: Vikas K, vikas.k@osmosys.co, PineStem ID 2370. Holidays 2026: 14 loaded.

## Verdicts (rules v4, final) — label text and colour
| Verdict | Colour | Meaning / sample label |
|---|---|---|
| AHEAD | green | ahead of 9 h/day so far · never on the last working day |
| ON TRACK | green | need/day ≤ 9.0 |
| TIGHT | amber | 9.0 < need/day ≤ 10.5 |
| BEHIND | amber | 42.5 out of reach, pay still safe — show "pay needs N h/day" |
| PAY RISK | red | the LOP line (41 h) is out of reach at 10.5 h/day, or the week ended under it; names short days "Thu 3.5 h" |
| BILL | blue/grey | only unbilled days stand between you and DONE — "Mon not billed yet" (a zero-hour day stays "not billed yet", not a shortfall, from 20:00 that day until 12:00 next working day) |
| DONE | green ✓ | target met |
| SHORT (pay safe) | amber | week over, 41 ≤ hours < 42.5 |
| LOP n d | red | week over, under the line: "LOP 1 day" |
| ON LEAVE | neutral | whole week leave/holiday |
| Offline / stale | grey | last numbers kept, "as of 09:40" |
| Signed out | amber dot | "Sign in again" |
Last working day always shows the hard gap when under 41: "· pay needs 1.0 h".
Half-day leave week (d = 4.5): HR still needs 41 h for zero LOP, so target becomes 41 h, not 38.25.
Pay (LOP) always uses billable + non-billable. Project targets use billable only.

## Quality bar
- Every mock looks like the real platform at real size (fonts Cantarell/Noto Sans/Fira Sans as in CSS). Numbers consistent.
- Each mock gets a short heading "N · Name" and a one- or two-sentence `.caption` saying what triggers it and what clicking does.
- Make it responsive: wrap mocks in `grid gap-6 md:grid-cols-2` (or 3 for small ones); nothing overflows at 390 px wide.
- Output: a fragment file (no <html>/<head>/<body>), starting with your `<style>` block, then `<section>`s. Write ONLY your file.
