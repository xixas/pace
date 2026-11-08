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

import {look} from './look.js';

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

        this._verdict = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._verdict.label.add_style_class_name('pace-verdict');
        this.menu.addMenuItem(this._verdict);
        this._updated = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._updated.label.add_style_class_name('pace-sub');
        this.menu.addMenuItem(this._updated);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        // The Shell's PATH often lacks ~/.local/bin, where a per-user install puts pace
        const pace = GLib.find_program_in_path('pace') ?? GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'pace']);
        this._signIn = this.menu.addAction('Sign in…', () => this._spawn([pace, 'sign-in']));

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
            this._render(look(this._json ?? null, Date.now()));
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
        this._render(look(json, Date.now()));
    }

    _render(l) {
        COLOURS.forEach(c => this._box.remove_style_class_name(`pace-${c}`));
        this._box.add_style_class_name(`pace-${COLOURS.includes(l.colour) ? l.colour : 'grey'}`);
        this._dot.visible = l.marker === 'dot';
        this._ring.visible = l.marker === '◌';
        this._glyph.visible = !this._dot.visible && !this._ring.visible;
        this._glyph.text = this._glyph.visible ? l.marker : '';
        this._label.text = l.text;

        this._verdict.label.text = {
            none: 'Waiting for paced',
            skew: 'This panel is older than Pace: update the extension',
            signed_out: 'Your DhiHRMS session expired',
            stale: 'paced has stopped updating: these numbers are old',
        }[l.state] ?? l.verdict ?? l.text;
        const at = l.asOf ? GLib.DateTime.new_from_iso8601(l.asOf, GLib.TimeZone.new_local()) : null;
        this._updated.label.text = at ? `${['offline', 'stale'].includes(l.state) ? 'Last updated' : 'Updated'} ${at.format('%a %H:%M')}` : '';
        this._updated.visible = at !== null;
        this._signIn.visible = l.state === 'signed_out';
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
