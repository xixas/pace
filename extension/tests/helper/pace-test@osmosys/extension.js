// Test-only (never shipped): lets extension/tests/screenshots.py open and close the Pace menu in a headless Shell.
// The harness writes "open" or "close" to $XDG_STATE_HOME/pace/menu-cmd.

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
            const menu = Main.panel.statusArea['pace@osmosys']?.menu;
            if (cmd === 'open')
                menu?.open(false);
            else if (cmd === 'close')
                menu?.close(false);
        });
    }

    disable() {
        this._monitor?.cancel();
        this._monitor = null;
    }
}
