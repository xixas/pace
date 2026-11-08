"""The app stylesheet as a string, so packaging needs no data files.

libadwaita does the heavy lifting (cards, rows, pills, title classes). What is here: the type scale for numbers, the verdict
colours mapped onto the named colours (so light, dark and high contrast follow the system), the day and heat-map tiles, and
the mini widget card.
"""

CSS = """
/* ---- numbers -------------------------------------------------------------------------------------------------------- */
.pace-hero { font-size: 48px; font-weight: 800; line-height: 1; font-feature-settings: "tnum"; letter-spacing: -0.02em; }
.pace-value { font-size: 22px; font-weight: 700; font-feature-settings: "tnum"; }
.pace-day-text { font-size: 24px; font-weight: 700; font-feature-settings: "tnum"; }

/* ---- verdict colours on text, pills, dots and drawn bars ---------------------------------------------------------------- */
.pace-pill { border-radius: 99px; padding: 2px 10px; font-size: 11px; font-weight: 700; letter-spacing: 0.02em; }
.pace-pill.green { background: alpha(var(--success-color), .15); color: var(--success-color); }
.pace-pill.amber { background: alpha(var(--warning-color), .18); color: var(--warning-color); }
.pace-pill.red { background: alpha(var(--error-color), .15); color: var(--error-color); }
.pace-pill.blue { background: alpha(var(--accent-color), .15); color: var(--accent-color); }
.pace-pill.grey { background: alpha(currentColor, .10); color: alpha(currentColor, .8); }

.pace-ink.green { color: var(--success-color); }
.pace-ink.amber { color: var(--warning-color); }
.pace-ink.red { color: var(--error-color); }
.pace-ink.blue { color: var(--accent-color); }
.pace-ink.grey { color: alpha(currentColor, .5); }

.pace-dot { border-radius: 99px; min-width: 10px; min-height: 10px; }
.pace-dot.green { background-color: var(--success-bg-color); }
.pace-dot.amber { background-color: var(--warning-bg-color); }
.pace-dot.red { background-color: var(--error-bg-color); }
.pace-dot.blue { background-color: var(--accent-bg-color); }
.pace-dot.grey { background-color: alpha(currentColor, .4); }

.pace-stale { opacity: .6; }

/* ---- week: hero card and the day strip ------------------------------------------------------------------------------- */
.pace-hero-card { padding: 22px 24px 18px; }
.pace-stat { padding: 0; }

.pace-day { padding: 12px 6px 10px; border-radius: 12px; }
.pace-day.today { box-shadow: inset 0 0 0 2px var(--accent-bg-color); }
.pace-day.short { background: alpha(var(--warning-color), .14); }
.pace-day.half_leave { background-image: repeating-linear-gradient(135deg, alpha(var(--warning-color), .18) 0 6px, transparent 6px 12px); }
.pace-day.future .pace-day-text, .pace-day.pending .pace-day-text { opacity: .4; }
.pace-day.holiday, .pace-day.leave, .pace-day.weekend { opacity: .55; }

/* ---- month: table ------------------------------------------------------------------------------------------------------ */
.pace-table { padding: 6px 0 4px; }
.pace-table-head { font-size: 12px; font-weight: 700; opacity: .55; padding: 2px 16px 8px; }
.pace-table-row { padding: 8px 16px; border-radius: 0; }
.pace-table-btn { padding: 0; min-height: 0; border-radius: 0; }
.pace-table-total { font-weight: 700; padding: 10px 16px 6px; border-top: 1px solid var(--border-color); }
.pace-table-title { padding: 14px 16px 4px; }

/* ---- calendar: heat map ------------------------------------------------------------------------------------------------ */
.heat-cell { border-radius: 10px; padding: 8px; min-height: 60px; min-width: 56px; }
.heat-ok { background: alpha(var(--success-color), .22); }
.heat-mid { background: alpha(var(--warning-color), .26); }
.heat-low { background: alpha(var(--error-color), .22); }
.heat-pending { background: alpha(currentColor, .06); }
.heat-holiday { background: alpha(var(--accent-color), .18); }
.heat-leave { background-image: repeating-linear-gradient(135deg, alpha(var(--accent-color), .22) 0 6px, transparent 6px 12px); }
.heat-off { opacity: .4; }
.heat-cell.today { box-shadow: inset 0 0 0 2px var(--accent-bg-color); }
.heat-day { font-size: 11px; font-weight: 700; opacity: .6; }
.heat-val { font-size: 15px; font-weight: 700; font-feature-settings: "tnum"; }
.swatch { border-radius: 4px; min-width: 14px; min-height: 14px; }

/* ---- B10 mini widget: a rounded card on a transparent, undecorated window -------------------------------------------- */
window.pace-widget { background: transparent; }
.pace-widget-card { background: var(--card-bg-color); color: var(--card-fg-color); border-radius: 18px; padding: 16px 18px 14px;
  box-shadow: 0 0 0 1px var(--card-shade-color), 0 8px 24px alpha(black, .22); }
.pace-widget-card .big { font-size: 30px; font-weight: 800; line-height: 1; font-feature-settings: "tnum"; letter-spacing: -0.02em; }
.pace-widget-card .title { font-size: 13px; font-weight: 700; }
.pace-widget-sep { background: var(--card-shade-color); min-height: 1px; margin: 10px 0 8px; }
"""
