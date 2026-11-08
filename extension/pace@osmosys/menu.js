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

// Rounded track, the fill, and the LOP / target / expected ticks (design: .bar with <b> ticks)
function drawBar(area, bar) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const th = 8, y = (h - th) / 2;
    const pill = (x0, x1, c, a) => {
        const r = th / 2;
        cr.setSourceRGBA(...c, a);
        cr.newSubPath();
        cr.arc(x0 + r, y + r, r, Math.PI / 2, 1.5 * Math.PI);
        cr.arc(x1 - r, y + r, r, 1.5 * Math.PI, Math.PI / 2);
        cr.closePath();
        cr.fill();
    };
    pill(0, w, [1, 1, 1], 0.13);
    const fillW = Math.max(th, w * bar.fill / 100);
    if (bar.fill > 0)
        pill(0, fillW, rgb(bar.colour ?? '#9a9996'), 1);
    if (bar.project) {
        cr.$dispose();
        return;
    }
    const tick = (pct, tw, th2, c, a) => {
        const x = Math.min(w - tw, Math.max(0, w * pct / 100 - tw / 2));
        cr.setSourceRGBA(...c, a);
        cr.rectangle(x, (h - th2) / 2, tw, th2);
        cr.fill();
    };
    tick(bar.target, 2, 14, [1, 1, 1], 0.55);
    tick(100, 2, 14, [1, 1, 1], 0.55);
    if (bar.emphasis) {
        tick(bar.lop, 7, 18, rgb('#ff7b63'), 0.25);
        tick(bar.lop, 3, 18, rgb('#ff7b63'), 1);
    } else {
        tick(bar.lop, 2, 14, [1, 1, 1], 0.55);
    }
    cr.$dispose();
}

function bar(b) {
    const area = new St.DrawingArea({x_expand: true, style_class: 'pace-bar'});
    area.connect('repaint', a => drawBar(a, b));
    return area;
}

function legend(items, emphasis) {
    const r = new St.BoxLayout({x_expand: true, style_class: 'pace-legend'});
    const aligns = [Clutter.ActorAlign.START, Clutter.ActorAlign.CENTER, Clutter.ActorAlign.END];
    items.forEach((t, i) => {
        const l = label(t, i === 0 && emphasis ? 'pace-lop' : 'pace-sm');
        l.x_expand = true;
        l.x_align = aligns[i];
        r.add_child(l);
    });
    return r;
}

function days(list) {
    const r = new St.BoxLayout({x_expand: true, style_class: 'pace-days'});
    const w = Math.floor((WIDTH - 4 * (list.length - 1)) / list.length);
    for (const d of list) {
        const chip = vbox(`pace-chip pace-chip-${d.kind}`, [d.dow, d.text].map((t, i) => {
            const l = label(t, i === 0 ? 'pace-chip-dow' : 'pace-chip-val');
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

function staticItem(menu, widget) {
    const it = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false, style_class: 'pace-static'});
    it.add_child(widget);
    menu.addMenuItem(it);
    return it;
}

// menu: a PopupMenu; m: look.menuModel(); flash: transient footer message; act: {dashboard, signIn, open, refresh, snooze, unsnooze}
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
        content.add_child(bar(m.bar));
        content.add_child(legend(m.bar.legend, m.bar.emphasis));
    }
    if (m.days)
        content.add_child(days(m.days));
    if (m.gap)
        content.add_child(label(m.gap, 'pace-sm pace-gap', {wrap: true}));
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
                content.add_child(bar({fill: p.fill, lop: 0, target: 0, colour: p.colour, emphasis: false, project: true}));
            if (p.needText)
                content.add_child(label(p.needText, 'pace-sm'));
        }
    }
    staticItem(menu, content);

    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    if (m.signIn)
        item(menu, 'Sign in…', act.signIn);
    item(menu, 'Open dashboard', act.dashboard);
    item(menu, 'Open PineStem', () => act.open(m.pinestemUrl));
    if (m.state === 'skew')
        return;
    if (m.snoozed) {
        const r = new St.BoxLayout({x_expand: true});
        r.add_child(label('Nudges snoozed until midnight', 'pace-snoozed', {style: null}));
        r.get_children()[0].x_expand = true;
        r.add_child(button('Undo', 'pace-link', act.unsnooze));
        staticItem(menu, r);
    } else {
        item(menu, 'Snooze nudges today', act.snooze);
    }

    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    const foot = new St.BoxLayout({x_expand: true});
    const l = label(flash ?? m.updated ?? '', flash ? 'pace-sm pace-flash' : 'pace-sm');
    l.x_expand = true;
    foot.add_child(l);
    foot.add_child(button(m.problem ? 'Retry now' : 'Refresh', 'pace-link', act.refresh));
    staticItem(menu, foot);
}
