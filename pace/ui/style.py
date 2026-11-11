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
.pace-leave-banner { padding: 14px 18px; background: alpha(var(--accent-bg-color), .08); }

.pace-days > flowboxchild { padding: 0; }
.pace-day { padding: 12px 4px 10px; border-radius: 12px; }
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

/* ---- calendar: day cells ----------------------------------------------------------------------------------------------- */
.heat-cell { border-radius: 12px; padding: 6px 7px 6px; min-height: 66px; min-width: 36px; border: 1px solid transparent; }
.heat-ok { background: alpha(var(--success-color), .17); }
.heat-mid { background: alpha(var(--warning-color), .22); }
.heat-low { background: alpha(var(--error-color), .17); }
.heat-pending { background: alpha(currentColor, .05); border-color: alpha(var(--accent-bg-color), .55); }
.heat-future { background: transparent; border-color: alpha(currentColor, .14); }
.heat-off { background: alpha(currentColor, .045); }
.heat-off .heat-day { opacity: .5; }
.heat-holiday { background: alpha(var(--accent-color), .15); }
.heat-leave { background-image: repeating-linear-gradient(135deg, alpha(var(--accent-color), .20) 0 6px, transparent 6px 12px); }
.heat-none { background: transparent; }
.heat-outside { opacity: .32; background: transparent; }
button.heat-cell:focus-visible { outline: 2px solid var(--accent-bg-color); outline-offset: -2px; }
.heat-day { font-size: 12px; font-weight: 700; opacity: .65; padding: 1px 0; min-width: 18px; }
.heat-day.today { background: var(--accent-bg-color); color: var(--accent-fg-color); opacity: 1; border-radius: 99px; padding: 1px 6px; min-width: 0; }
.heat-val { font-size: 14px; font-weight: 700; font-feature-settings: "tnum"; }
.swatch { border-radius: 4px; min-width: 14px; min-height: 14px; }
.swatch.heat-ok, .swatch.heat-mid, .swatch.heat-low, .swatch.heat-holiday { border: 0; }

/* ---- B10 mini widget: a rounded card on a transparent, undecorated window -------------------------------------------- */
window.pace-widget { background: transparent; }
.pace-widget-card { background: var(--window-bg-color); color: var(--window-fg-color); border-radius: 18px; padding: 16px 18px 14px;
  box-shadow: 0 0 0 1px var(--card-shade-color), 0 8px 24px alpha(black, .22); }
.pace-widget-card .big { font-size: 30px; font-weight: 800; line-height: 1; font-feature-settings: "tnum"; letter-spacing: -0.02em; }
.pace-widget-card .title { font-size: 13px; font-weight: 700; }
.pace-widget-sep { background: var(--card-shade-color); min-height: 1px; margin: 10px 0 8px; }
"""
