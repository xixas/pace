// The Pace mini widget, drawn inside GNOME Shell so it sits above windows on every workspace (a GTK window can't on Wayland).
// Chrome, not a window: not in Alt-Tab or the overview, hidden over a fullscreen app. What it shows is widgetModel's job.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {clampToArea, isLight, monitorAt, parseSaved, serializeSaved, startPosition, widgetModel} from './widgetModel.js';

const CARD_W = 240;
const PAD = 16;
const TRACK_W = CARD_W - 2 * PAD;
export const BUS_NAME = 'io.github.xixas.Pace.Shell';
const BUS_PATH = '/io/github/xixas/Pace/Shell';
const BUS_XML = `<node><interface name="${BUS_NAME}">
  <method name="ShowWidget"/>
  <method name="HideWidget"/>
  <method name="WidgetVisible"><arg type="b" name="visible" direction="out"/></method>
</interface></node>`;

function label(text, styleClass) {
    return new St.Label({text, style_class: styleClass, y_align: Clutter.ActorAlign.CENTER});
}

function sectionActor(s) {
    const box = new St.BoxLayout({vertical: true, style_class: 'pace-w-section'});
    const head = new St.BoxLayout();
    const name = label(s.label, 'pace-w-label');
    name.x_expand = true;
    name.clutter_text.ellipsize = Pango.EllipsizeMode.END;
    head.add_child(name);
    head.add_child(label(s.word, `pace-w-word pace-w-${s.colour}`));
    box.add_child(head);
    if (s.big) {
        const nums = new St.BoxLayout({style_class: 'pace-w-nums'});
        nums.add_child(label(s.big, 'pace-w-big'));
        const unit = label(s.unit, 'pace-w-unit');
        unit.y_align = Clutter.ActorAlign.END;
        nums.add_child(unit);
        box.add_child(nums);
    }
    if (s.fill !== null) {
        const track = new St.Widget({style_class: 'pace-w-track', width: TRACK_W, height: 4});
        const w = s.fill > 0 ? Math.max(4, Math.round(TRACK_W * s.fill / 100)) : 0;
        if (w > 0)
            track.add_child(new St.Widget({style_class: `pace-w-fill pace-w-bar-${s.colour}`, width: w, height: 4}));
        box.add_child(track);
    }
    s.lines.forEach((line, i) => {
        const l = label(line, i === 0 ? 'pace-w-caption pace-w-first' : 'pace-w-caption');
        l.clutter_text.line_wrap = true;
        l.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
        l.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        box.add_child(l);
    });
    return box;
}

function statePath() {
    return GLib.build_filenamev([GLib.get_user_state_dir(), 'pace', 'shell-widget.json']);
}

// Owns the card's actor, the remembered state and the D-Bus name the Pace app uses to show or hide it.
export class WidgetController {
    constructor({openDashboard}) {
        this._openDashboard = openDashboard;
        this._json = null;
        this._dim = false;
        this._sig = null;
        this._actor = null;
        this._ids = [];
        this._saved = parseSaved(this._load());
        this._ifaceSettings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._schemeId = this._ifaceSettings.connect('changed::color-scheme', () => this._style());
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._place());
        this._overviewIds = [
            Main.overview.connect('showing', () => this._card?.hide()),
            Main.overview.connect('hidden', () => this._card?.show()),
        ];
        this._exported = Gio.DBusExportedObject.wrapJSObject(BUS_XML, this);
        this._nameId = Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            conn => {
                this._exported.export(conn, BUS_PATH);
                this._onBus = true;
            }, null, null);
        if (this._saved.visible) {
            try { // a failed card must not abort enable(): destroy() still has to release the signals and bus name
                this._build();
            } catch (e) {
                logError(e, 'Pace: could not draw the mini widget');
            }
        }
    }

    // ---- D-Bus methods (the Pace app calls these) ----
    ShowWidget() {
        this._saved.visible = true;
        this._persist();
        this._build();
    }

    HideWidget() {
        this._saved.visible = false;
        this._persist();
        this._teardown();
    }

    WidgetVisible() {
        return this._saved.visible;
    }

    // ---- status ----
    setStatus(json, dim) {
        const sig = JSON.stringify([json, dim]);
        if (sig === this._sig)
            return;
        this._sig = sig;
        this._json = json;
        this._dim = dim;
        this._fill();
    }

    destroy() {
        this._teardown();
        this._ifaceSettings.disconnect(this._schemeId);
        Main.layoutManager.disconnect(this._monitorsId);
        this._overviewIds.forEach(id => Main.overview.disconnect(id));
        if (this._onBus)
            this._exported.unexport();
        Gio.bus_unown_name(this._nameId);
    }

    // ---- building ----
    _build() {
        if (this._actor)
            return;
        this._actor = new St.Bin({style_class: 'pace-widget', reactive: true, track_hover: false});
        this._card = new St.BoxLayout({vertical: true, style_class: 'pace-widget-card', width: CARD_W});
        this._actor.set_child(this._card);
        // Above windows on every workspace, outside Alt-Tab, hidden over fullscreen apps. Input region: chrome's default (GNOME 50 dropped the affectsInputRegion option and rejects it)
        Main.layoutManager.addChrome(this._actor, {trackFullscreen: true});
        this._actor.connect('button-press-event', (_a, ev) => this._press(ev));
        this._actor.connect('motion-event', (_a, ev) => this._motion(ev));
        this._actor.connect('button-release-event', () => this._release());
        this._makeMenu();
        this._style();
        this._fill();
        const [, h] = this._actor.get_preferred_height(CARD_W);
        const [x, y] = startPosition(this._saved, CARD_W, h, this._areaFor(this._saved.x ?? 0, this._saved.y ?? 0, h));
        this._actor.set_position(x, y);
        Object.assign(this._saved, {x, y});
        if (Main.overview.visible)
            this._card.hide();
        this._persist();
    }

    _teardown() {
        this._release();
        this._menu?.destroy();
        this._menu = null;
        if (this._actor) {
            Main.layoutManager.removeChrome(this._actor);
            this._actor.destroy();
        }
        this._actor = this._card = null;
    }

    _fill() {
        if (!this._actor)
            return;
        const m = widgetModel(this._json);
        this._card.destroy_all_children();
        this._card.add_child(sectionActor(m.week));
        if (m.project) {
            this._card.add_child(new St.Widget({style_class: 'pace-w-sep', height: 1}));
            this._card.add_child(sectionActor(m.project));
        }
        this._card.opacity = this._dim ? 120 : 255;
        this._place();
    }

    _style() {
        if (!this._actor)
            return;
        const light = isLight(this._ifaceSettings.get_string('color-scheme'));
        if (light)
            this._actor.add_style_class_name('pace-widget-light');
        else
            this._actor.remove_style_class_name('pace-widget-light');
    }

    _makeMenu() {
        this._menu = new PopupMenu.PopupMenu(this._actor, 0.5, St.Side.TOP);
        this._menu.addAction('Open dashboard', () => this._openDashboard());
        this._menu.addAction('Hide widget', () => this.HideWidget());
        Main.uiGroup.add_child(this._menu.actor);
        this._menu.actor.hide();
        this._manager = new PopupMenu.PopupMenuManager(this._actor);
        this._manager.addMenu(this._menu);
    }

    // ---- position ----
    _areaFor(x, y, h) {
        const mon = monitorAt(x, y, CARD_W, h, Main.layoutManager.monitors) ?? Main.layoutManager.primaryMonitor;
        if (!mon) // no monitor yet (headless start, hotplug): the whole stage, so nothing throws
            return {x: 0, y: 0, width: global.stage.width, height: global.stage.height};
        return Main.layoutManager.getWorkAreaForMonitor(mon.index);
    }

    // Keep the card on screen after it changed size or the monitors changed
    _place() {
        if (!this._actor || this._drag)
            return;
        const [, h] = this._actor.get_preferred_height(CARD_W);
        const [x, y] = clampToArea(this._actor.x, this._actor.y, CARD_W, h, this._areaFor(this._actor.x, this._actor.y, h));
        this._actor.set_position(x, y);
    }

    _press(ev) {
        const button = ev.get_button();
        if (button === 3) {
            this._menu.open();
            return Clutter.EVENT_STOP;
        }
        if (button !== 1)
            return Clutter.EVENT_PROPAGATE;
        const [px, py] = ev.get_coords();
        this._drag = {dx: px - this._actor.x, dy: py - this._actor.y, grab: global.stage.grab(this._actor)};
        return Clutter.EVENT_STOP;
    }

    _motion(ev) {
        if (!this._drag)
            return Clutter.EVENT_PROPAGATE;
        const [px, py] = ev.get_coords();
        const [, h] = this._actor.get_preferred_height(CARD_W);
        const x = px - this._drag.dx, y = py - this._drag.dy;
        const [cx, cy] = clampToArea(x, y, CARD_W, h, this._areaFor(px, py, h));
        this._actor.set_position(cx, cy);
        return Clutter.EVENT_STOP;
    }

    _release() {
        if (!this._drag)
            return Clutter.EVENT_PROPAGATE;
        this._drag.grab.dismiss();
        this._drag = null;
        Object.assign(this._saved, {x: this._actor.x, y: this._actor.y});
        this._persist();
        return Clutter.EVENT_STOP;
    }

    // ---- remembered state: a file in Pace's state dir, so it survives the lock screen disabling the extension ----
    _load() {
        try {
            return new TextDecoder().decode(Gio.File.new_for_path(statePath()).load_contents(null)[1]);
        } catch {
            return '';
        }
    }

    _persist() {
        try {
            Gio.File.new_for_path(statePath()).replace_contents(
                new TextEncoder().encode(serializeSaved(this._saved)), null, false, Gio.FileCreateFlags.REPLACE_DESTINATION, null);
        } catch (e) {
            console.warn(`Pace: couldn't save the widget position: ${e.message}`);
        }
    }
}
