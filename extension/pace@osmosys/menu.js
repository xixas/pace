// Draws the dropdown (B2-B6, B12, C10, C12) from the model look.js builds. Widgets only: no data decisions here.

import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import 'gi://cairo';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const WIDTH = 330;

function label(text, styleClass, {wrap = false, style = null} = {}) {
    const l = new St.Label({text, style_class: styleClass, y_align: Clutter.ActorAlign.CENTER});
    if (style)
        l.style = style;
    if (wrap) {
        l.clutter_text.line_wrap = true;
        l.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
        l.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
    }
    return l;
}

function vbox(styleClass, children = []) {
    const b = new St.BoxLayout({vertical: true, x_expand: true, style_class: styleClass});
    children.forEach(c => b.add_child(c));
    return b;
}

// Title left, side text right
function row(left, right) {
    const r = new St.BoxLayout({x_expand: true});
    left.x_expand = true;
    left.x_align = Clutter.ActorAlign.START;
    r.add_child(left);
    if (right) {
        right.x_align = Clutter.ActorAlign.END;
        r.add_child(right);
    }
    return r;
}

function rgb(hex) {
    return [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
}

const RED = rgb('#ff7b63'), GREEN = rgb('#57e389'), BLUE = rgb('#78aeed');
const TRACK = 6;

// Rounded rect as a path (corner radius r), no fill
function roundRect(cr, x0, x1, y, h, r) {
    cr.newSubPath();
    cr.arc(x0 + r, y + r, r, Math.PI, 1.5 * Math.PI);
    cr.arc(x1 - r, y + r, r, 1.5 * Math.PI, 2 * Math.PI);
    cr.arc(x1 - r, y + h - r, r, 0, 0.5 * Math.PI);
    cr.arc(x0 + r, y + h - r, r, 0.5 * Math.PI, Math.PI);
    cr.closePath();
}

// The runway (direction D): 6 px track, lighter pay-safe band from the pay line to the end, the fill (neutral unless
// red/green), and the pending day's expected share as a dashed ghost continuing the fill. No ticks.
function drawRunway(area, r) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const y = (h - TRACK) / 2, rad = TRACK / 2;
    roundRect(cr, 0, w, y, TRACK, rad);
    cr.setSourceRGBA(1, 1, 1, 0.12);
    cr.fillPreserve();
    cr.save();
    cr.clip();
    const bx = Math.round(w * r.band);
    if (bx < w) {
        cr.setSourceRGBA(...(r.emphasis ? RED : [1, 1, 1]), r.emphasis ? 0.28 : 0.2);
        cr.rectangle(bx, y, w - bx, TRACK);
        cr.fill();
        cr.setSourceRGBA(...(r.emphasis ? RED : [1, 1, 1]), r.emphasis ? 1 : 0.55);
        cr.rectangle(bx, y, 1, TRACK);
        cr.fill();
    }
    cr.restore();
    if (r.ghost) {
        const [g0, g1] = r.ghost.map(f => Math.round(w * f));
        cr.setSourceRGBA(...BLUE, 1);
        cr.setLineWidth(1);
        cr.setDash([2.5, 2], 0);
        roundRect(cr, g0 + 0.5, Math.max(g1 - 0.5, g0 + 1.5), y + 0.5, TRACK - 1, rad - 0.5);
        cr.stroke();
        cr.setDash([], 0);
    }
    if (r.fill > 0) {
        const c = {red: [...RED, 1], green: [...GREEN, 1], grey: [1, 1, 1, 0.4]}[r.ink] ?? [1, 1, 1, 0.82];
        cr.setSourceRGBA(...c);
        roundRect(cr, 0, Math.min(w, Math.max(TRACK, w * r.fill)), y, TRACK, rad);
        cr.fill();
    }
    cr.$dispose();
}

// A project's month progress: rounded track and a coloured fill
function drawProject(area, p) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const th = 8, y = (h - th) / 2;
    const pill = (x1, c, a) => {
        cr.setSourceRGBA(...c, a);
        roundRect(cr, 0, x1, y, th, th / 2);
        cr.fill();
    };
    pill(w, [1, 1, 1], 0.13);
    if (p.fill > 0)
        pill(Math.max(th, w * p.fill / 100), rgb(p.colour ?? '#9a9996'), 1);
    cr.$dispose();
}

function bar(draw, data, styleClass) {
    const area = new St.DrawingArea({x_expand: true, style_class: styleClass});
    area.connect('repaint', a => draw(a, data));
    return area;
}

// Hours left, pay-line gap right (red/blue/green/amber when it matters)
function caption(c, tone) {
    const r = new St.BoxLayout({x_expand: true, style_class: 'pace-caption'});
    r.add_child(label(c.hours, 'pace-sm'));
    const t = label(c.text, tone ? 'pace-sm pace-tone' : 'pace-sm', {style: tone ? `color: ${tone};` : null});
    t.x_expand = true;
    t.x_align = Clutter.ActorAlign.END;
    r.add_child(t);
    return r;
}

function days(list) {
    const r = new St.BoxLayout({x_expand: true, style_class: 'pace-days'});
    const w = Math.floor((WIDTH - 4 * (list.length - 1)) / list.length);
    for (const d of list) {
        // A day off you billed on: full-brightness hours, with a small tag naming the day off
        const lines = d.tag ? [[d.dow, 'pace-chip-dow'], [d.text, 'pace-chip-val'], [d.tag.toUpperCase(), 'pace-chip-tag']]
            : [[d.dow, 'pace-chip-dow'], [d.text, 'pace-chip-val']];
        const chip = vbox(d.tag ? 'pace-chip pace-chip-worked' : `pace-chip pace-chip-${d.kind}`, lines.map(([t, cls]) => {
            const l = label(t, cls);
            l.x_align = Clutter.ActorAlign.CENTER;
            return l;
        }));
        chip.x_expand = false;
        chip.style = `width: ${w}px;`;
        r.add_child(chip);
    }
    return r;
}

// A reactive row (opens/does something) or a plain one-line row when `fn` is absent
function item(menu, text, fn) {
    return menu.addAction(text, fn);
}

function button(text, styleClass, fn) {
    const b = new St.Button({label: text, style_class: styleClass, can_focus: true, reactive: true, track_hover: true,
        y_align: Clutter.ActorAlign.CENTER});
    b.connect('clicked', () => {
        fn();
    });
    return b;
}

function toggle(icon, text, on, fn) {
    const box = new St.BoxLayout({x_expand: true, x_align: Clutter.ActorAlign.CENTER, style_class: 'pace-toggle-box'});
    box.add_child(new St.Icon({icon_name: icon, style_class: 'pace-toggle-icon'}));
    box.add_child(new St.Label({text, y_align: Clutter.ActorAlign.CENTER}));
    const b = new St.Button({child: box, style_class: 'pace-toggle', toggle_mode: true, checked: on, can_focus: true,
        x_expand: true, accessible_name: text});
    b.connect('notify::checked', () => fn(b.checked));
    return b;
}

function staticItem(menu, widget) {
    const it = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false, style_class: 'pace-static'});
    it.add_child(widget);
    menu.addMenuItem(it);
    return it;
}

// menu: a PopupMenu; m: look.menuModel(); flash: transient footer message; act: {dashboard, settings, signIn, open, refresh, snooze, unsnooze, widgetVisible, showWidget, hideWidget}
export function buildMenu(menu, m, flash, act) {
    const content = vbox('pace-content');
    content.style = `width: ${WIDTH}px;`;

    if (m.problem) {
        content.add_child(vbox('pace-banner pace-banner-warn', [
            label(`⚠ ${m.problem.message}`, 'pace-banner-title'),
            label(m.problem.detail, 'pace-sm'),
        ]));
    }
    if (m.lastWeek) {
        const b = vbox('pace-banner pace-banner-info', [
            label(`ⓘ ${m.lastWeek.text}`, 'pace-banner-title', {wrap: true}),
            label(m.lastWeek.detail, 'pace-sm', {wrap: true}),
        ]);
        b.add_child(button('Open PineStem', 'pace-link', () => act.open(m.lastWeek.url ?? m.pinestemUrl)));
        content.add_child(b);
    }
    if (m.notice) {
        content.add_child(label(m.notice, 'pace-title', {wrap: true}));
        if (m.noticeDetail)
            content.add_child(label(m.noticeDetail, 'pace-sm', {wrap: true}));
    }
    if (m.title) {
        content.add_child(row(
            label(m.title, 'pace-title', {style: m.titleColour ? `color: ${m.titleColour};` : null}),
            m.subtitle ? label(m.subtitle, 'pace-sm') : null));
        if (m.note)
            content.add_child(label(m.note, 'pace-sm', {wrap: true}));
    }
    if (m.bar) {
        content.add_child(bar(drawRunway, m.bar, 'pace-bar'));
        content.add_child(caption(m.bar.caption, m.bar.tone));
    }
    if (m.days)
        content.add_child(days(m.days));
    if (m.warning) {
        content.add_child(vbox('pace-warning', [
            label(`⚠ ${m.warning}`, 'pace-warning-title', {wrap: true}),
            m.warningDetail ? label(m.warningDetail, 'pace-sm', {wrap: true}) : null,
        ].filter(Boolean)));
    }
    if (m.action)
        content.add_child(button(m.action.label, `pace-btn${m.state === 'pay_risk' ? ' pace-btn-red' : ''}`, () => act.open(m.action.url)));
    if (m.month) {
        content.add_child(new St.Widget({style_class: 'pace-rule'}));
        content.add_child(row(label(m.month.name, 'pace-title-sm'), label(m.month.left, 'pace-sm')));
        for (const p of m.month.projects) {
            content.add_child(row(label(p.name, 'pace-project'),
                label(p.text, 'pace-sm', {style: p.colour ? `color: ${p.colour}; opacity: 1;` : null})));
            if (p.fill !== null)
                content.add_child(bar(drawProject, p, 'pace-bar'));
            if (p.needText)
                content.add_child(label(p.needText, 'pace-sm'));
        }
    }
    staticItem(menu, content);

    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    if (m.signIn)
        item(menu, 'Sign in…', act.signIn);
    item(menu, 'Open dashboard', act.dashboard);
    item(menu, 'Settings…', act.settings);
    item(menu, 'Open PineStem', () => act.open(m.pinestemUrl));
    // Quick-settings style pills: they fill with the accent colour when on, and the menu stays open on click
    const toggles = new St.BoxLayout({style_class: 'pace-toggles', x_expand: true});
    const widget = toggle('view-pin-symbolic', 'Mini widget', act.widgetVisible(), on => (on ? act.showWidget : act.hideWidget)());
    toggles.add_child(widget);
    // The widget can also be hidden from its own right-click menu: the indicator re-syncs this pill on open
    menu._paceWidgetToggle = on => (widget.checked = on);
    if (m.state !== 'skew')
        toggles.add_child(toggle('notifications-disabled-symbolic', 'Snooze today', m.snoozed, on => (on ? act.snooze : act.unsnooze)()));
    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    staticItem(menu, toggles);

    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    const foot = new St.BoxLayout({x_expand: true});
    const l = label(flash ?? m.updated ?? '', flash ? 'pace-sm pace-flash' : 'pace-sm');
    l.x_expand = true;
    foot.add_child(l);
    foot.add_child(button(m.problem ? 'Retry now' : 'Refresh', 'pace-link', act.refresh));
    staticItem(menu, foot);
}
