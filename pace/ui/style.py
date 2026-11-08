"""The app stylesheet as a string, so packaging needs no data files."""

CSS = """/* Pace: libadwaita defaults plus a few pills, tiles and heat colours. Dark mode follows the system through the named colours. */

.pace-value { font-size: 26px; font-weight: 800; font-feature-settings: "tnum"; }
.pace-value-sm { font-size: 20px; font-weight: 800; font-feature-settings: "tnum"; }
.pace-tile { padding: 14px 16px; }
.pace-sub { font-size: 12px; opacity: .65; }
.pace-tag { font-size: 11px; font-weight: 700; opacity: .65; }

.pace-pill { border-radius: 99px; padding: 1px 9px; font-size: 11px; font-weight: 800; }
.pace-pill.green { background: alpha(@success_color, .18); color: @success_color; }
.pace-pill.amber { background: alpha(@warning_color, .20); color: @warning_color; }
.pace-pill.red { background: alpha(@error_color, .18); color: @error_color; }
.pace-pill.blue { background: alpha(@accent_color, .18); color: @accent_color; }
.pace-pill.grey { background: alpha(currentColor, .10); }

.pace-day { padding: 10px 6px; min-height: 96px; border-radius: 12px; }
.pace-day.today { box-shadow: inset 0 0 0 2px @accent_bg_color; }
.pace-day.short { background: alpha(@warning_color, .14); }
.pace-day.half_leave { background-image: repeating-linear-gradient(135deg, alpha(@warning_color, .20) 0 6px, transparent 6px 12px); }
.pace-day.future, .pace-day.pending { opacity: .75; }
.pace-day.holiday, .pace-day.leave, .pace-day.weekend { opacity: .6; }
.pace-day-text { font-size: 20px; font-weight: 800; font-feature-settings: "tnum"; }

.pace-warning { background: alpha(@warning_color, .16); border-radius: 12px; padding: 10px 14px; }
.pace-info { background: alpha(@accent_color, .10); border-radius: 12px; padding: 10px 14px; }
.pace-stale { opacity: .55; }

.pace-table-head { font-size: 12px; font-weight: 700; opacity: .65; }
.pace-table-total { font-weight: 800; }
.pace-table-btn { padding: 0 0 0 0; min-height: 0; }
.pace-table-row { padding: 6px 0; border-radius: 8px; }

.heat-cell { border-radius: 10px; padding: 6px; min-height: 64px; min-width: 64px; }
.heat-ok { background: alpha(@success_color, .24); }
.heat-mid { background: alpha(@warning_color, .24); }
.heat-low { background: alpha(@error_color, .22); }
.heat-pending { background: alpha(currentColor, .07); }
.heat-holiday { background: alpha(@accent_color, .18); }
.heat-leave { background-image: repeating-linear-gradient(135deg, alpha(@accent_color, .22) 0 6px, transparent 6px 12px); }
.heat-off, .heat-none { opacity: .35; }
.heat-cell.today { box-shadow: inset 0 0 0 2px @accent_bg_color; }
.heat-day { font-size: 11px; opacity: .7; }
.heat-val { font-size: 14px; font-weight: 700; font-feature-settings: "tnum"; }
.swatch { border-radius: 4px; min-width: 14px; min-height: 14px; }

/* B10 mini widget: a rounded card on a transparent, undecorated window */
window.pace-widget { background: transparent; }
.pace-widget-card { background: @card_bg_color; color: @card_fg_color; border-radius: 16px; padding: 14px 16px;
  box-shadow: 0 0 0 1px alpha(currentColor, .12), 0 6px 18px alpha(black, .28); }
.pace-widget-card .big { font-size: 24px; font-weight: 800; font-feature-settings: "tnum"; }
.pace-widget-card .title { font-size: 13px; font-weight: 800; }
.pace-dot { border-radius: 99px; min-width: 10px; min-height: 10px; }
.pace-dot.green { background-color: #2ec27e; }
.pace-dot.amber { background-color: #e5a50a; }
.pace-dot.red { background-color: #e01b24; }
.pace-dot.blue { background-color: #3584e4; }
.pace-dot.grey { background-color: alpha(currentColor, .45); }
.pace-widget-sep { background: alpha(currentColor, .12); min-height: 1px; margin: 6px 0; }
"""
