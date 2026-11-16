// Test-only (never shipped): lets extension/tests/screenshots.py open and close the Pace menu in a headless Shell.
// "overview-hide" leaves the overview a headless shell starts in. It also sets the desktop colour scheme for the widget shots: "scheme-light" / "scheme-dark".
// The harness writes "open", "close", "toggle-snooze" or "toggle-widget" to $XDG_STATE_HOME/pace/menu-cmd.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export default class PaceTestHelper extends Extension {
    enable() {
        const dir = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_state_dir(), 'pace']));
        try {
            dir.make_directory_with_parents(null);
        } catch {
            // already there
        }
        this._monitor = dir.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
        this._monitor.connect('changed', (_m, file, other) => {
            const f = [file, other].find(x => x?.get_basename() === 'menu-cmd');
            if (!f)
                return;
            let cmd = '';
            try {
                cmd = new TextDecoder().decode(f.load_contents(null)[1]).trim();
            } catch {
                return;
            }
            // One write fires several 'changed' events; a toggle must run once per write (the harness spaces writes >1 s)
            const now = GLib.get_monotonic_time();
            if (cmd === this._lastCmd && now - this._lastAt < 500000)
                return;
            this._lastCmd = cmd;
            this._lastAt = now;
            const menu = Main.panel.statusArea['pace@osmosys']?.menu;
            if (cmd === 'open')
                menu?.open(false);
            else if (cmd === 'close')
                menu?.close(false);
            else if (cmd === 'overview-hide')
                Main.overview.hide();
            else if (cmd === 'scheme-light' || cmd === 'scheme-dark')
                new Gio.Settings({schema_id: 'org.gnome.desktop.interface'}).set_string('color-scheme', cmd === 'scheme-dark' ? 'prefer-dark' : 'default');
            else if (cmd === 'toggle-snooze' || cmd === 'toggle-widget') {
                const want = cmd === 'toggle-snooze' ? 'Snooze today' : 'Mini widget';
                const find = a => (a.accessible_name === want ? a : a.get_children().map(find).find(Boolean));
                const pill = (menu?._getMenuItems() ?? []).map(find).find(Boolean);
                if (pill)
                    pill.checked = !pill.checked;
            }
        });
    }

    disable() {
        this._monitor?.cancel();
        this._monitor = null;
    }
}
