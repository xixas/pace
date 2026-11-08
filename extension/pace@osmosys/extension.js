// Pace: this week's billed hours in the GNOME top bar. Draws whatever paced last wrote to
// $XDG_STATE_HOME/pace/status.json and redraws when the file changes, plus once a minute to catch a stopped paced.

import GObject from 'gi://GObject';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import 'gi://cairo';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {look, menuModel, NO_PACED} from './look.js';
import {buildMenu} from './menu.js';

Gio._promisify(Gio.File.prototype, 'load_contents_async');

const COLOURS = ['green', 'amber', 'red', 'blue', 'grey'];

// Dashed circle in the CSS colour, one dash per 30°
function drawRing(area) {
    const cr = area.get_context();
    const [w, h] = area.get_surface_size();
    const r = Math.min(w, h) / 2 - 1;
    cr.setSourceColor(area.get_theme_node().get_foreground_color());
    cr.setLineWidth(2.2);
    const dash = Math.PI * r / 6;
    cr.setDash([dash * 0.55, dash * 0.45], 0);
    cr.arc(w / 2, h / 2, r, 0, 2 * Math.PI);
    cr.stroke();
    cr.$dispose();
}

const PaceIndicator = GObject.registerClass(
class PaceIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Pace');
        this._box = new St.BoxLayout({style_class: 'pace-box'});
        this._dot = new St.Widget({style_class: 'pace-dot', y_align: Clutter.ActorAlign.CENTER});
        this._glyph = new St.Label({style_class: 'pace-glyph', y_align: Clutter.ActorAlign.CENTER});
        this._ring = new St.DrawingArea({style_class: 'pace-ring', y_align: Clutter.ActorAlign.CENTER});
        this._ring.connect('repaint', area => drawRing(area));
        this._label = new St.Label({style_class: 'pace-label', y_align: Clutter.ActorAlign.CENTER});
        for (const a of [this._dot, this._ring, this._glyph, this._label])
            this._box.add_child(a);
        this.add_child(this._box);

        // The Shell's PATH often lacks ~/.local/bin, where a per-user install puts pace
        this._pace = GLib.find_program_in_path('pace') ?? GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'pace']);
        this._menuSig = null;
        this._flashText = null;

        const dir = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_state_dir(), 'pace']));
        try {
            dir.make_directory_with_parents(null);
        } catch (e) {
            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.EXISTS))
                throw e;
        }
        this._file = dir.get_child('status.json');
        this._cancellable = new Gio.Cancellable();
        // Watch the directory, not the file: paced replaces status.json by rename
        this._monitor = dir.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, this._cancellable);
        this._monitor.connect('changed', (_m, file, other) => {
            if ([file, other].some(f => f?.get_basename() === 'status.json'))
                this._read();
        });
        this._read();
        // Re-judge each minute: if paced stops, the file stops changing and only the clock can tell
        this._tick = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            this._render();
            return GLib.SOURCE_CONTINUE;
        });
    }

    async _read() {
        let json = null;
        try {
            const [bytes] = await this._file.load_contents_async(this._cancellable);
            json = new TextDecoder().decode(bytes);
        } catch (e) {
            if (e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                return;
        }
        this._json = json;
        this._render();
    }

    _render() {
        const now = Date.now();
        const l = look(this._json ?? null, now);
        COLOURS.forEach(c => this._box.remove_style_class_name(`pace-${c}`));
        this._box.add_style_class_name(`pace-${COLOURS.includes(l.colour) ? l.colour : 'grey'}`);
        this._dot.visible = l.marker === 'dot';
        this._ring.visible = l.marker === '◌';
        this._glyph.visible = !this._dot.visible && !this._ring.visible;
        this._glyph.text = this._glyph.visible ? l.marker : '';
        // Icon-only (B11): text is "" and only the marker shows
        this._label.visible = l.text !== '';
        this._label.text = l.text;

        const model = menuModel(this._json ?? null, now);
        const sig = JSON.stringify([model, this._flashText]);
        if (sig === this._menuSig)
            return;
        this._menuSig = sig;
        this.menu.removeAll();
        buildMenu(this.menu, model, this._flashText, {
            dashboard: () => this._spawn([this._pace]),
            signIn: () => this._spawn([this._pace, 'sign-in']),
            open: url => this._open(url),
            refresh: () => this._paced('Refresh'),
            snooze: () => this._paced('Snooze'),
            unsnooze: () => this._paced('Unsnooze'),
        });
    }

    // paced owns the work; no bus auto-start, so an absent paced shows up as an error we can report
    _paced(method) {
        Gio.DBus.session.call('io.github.xixas.Pace', '/io/github/xixas/Pace', 'io.github.xixas.Pace1', method,
            null, null, Gio.DBusCallFlags.NONE, 3000, this._cancellable, (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (e) {
                    if (e.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        return;
                    this._flash(NO_PACED);
                }
            });
    }

    _flash(text) {
        this._flashText = text;
        this._render();
        if (this._flashTimer)
            GLib.source_remove(this._flashTimer);
        this._flashTimer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 4, () => {
            this._flashTimer = null;
            this._flashText = null;
            this._render();
            return GLib.SOURCE_REMOVE;
        });
    }

    _open(url) {
        try {
            Gio.AppInfo.launch_default_for_uri(url, null);
        } catch (e) {
            Main.notifyError('Pace', `Couldn't open ${url}: ${e.message}`);
        }
    }

    _spawn(argv) {
        try {
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        } catch (e) {
            Main.notifyError('Pace', `Couldn't run ${argv.join(' ')}: ${e.message}`);
        }
    }

    destroy() {
        this._cancellable.cancel();
        this._monitor.cancel();
        GLib.source_remove(this._tick);
        if (this._flashTimer)
            GLib.source_remove(this._flashTimer);
        super.destroy();
    }
});

export default class PaceExtension extends Extension {
    enable() {
        this._indicator = new PaceIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
