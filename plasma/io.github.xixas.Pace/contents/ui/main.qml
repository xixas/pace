// Pace for KDE Plasma: the panel indicator and its popup, the KDE counterpart of the GNOME extension
// (extension/pace@osmosys). Like every Pace frontend it only draws status.json, which paced writes; the wording comes
// from ../code/model.js (the KDE copy of look.js). Actions go to paced over D-Bus (docs/contract.md section 4).
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami
import "../code/model.js" as Model

PlasmoidItem {
    id: root

    readonly property string statusCmd: "sh -c 'cat \"${XDG_STATE_HOME:-$HOME/.local/state}/pace/status.json\" 2>/dev/null'"
    property var json: null          // status.json text, or null when there is none yet
    property real now: Date.now()
    readonly property var l: Model.look(json, now)
    readonly property var m: Model.menuModel(json, now)
    property string flash: ""

    function colour(name) {
        return Model.HEX[name] || Model.HEX.grey;
    }

    // ---- status.json --------------------------------------------------------------------------------------------
    P5Support.DataSource {
        id: reader
        engine: "executable"
        interval: 10000
        connectedSources: [root.statusCmd]
        onNewData: (source, data) => {
            var out = (data.stdout || "").trim();
            root.json = out === "" ? null : out;
            root.now = Date.now();
        }
    }

    function reread() {
        reader.disconnectSource(statusCmd);
        reader.connectSource(statusCmd);
    }

    // ---- actions --------------------------------------------------------------------------------------------------
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            if (data["exit code"] !== 0 && source.indexOf("gdbus") >= 0)
                root.flash = Model.NO_PACED;
            flashTimer.restart();
            root.reread();
        }
    }

    Timer {
        id: flashTimer
        interval: 4000
        onTriggered: root.flash = ""
    }

    // paced's method, or `pace <fallback>` when paced isn't on the bus (contract section 4)
    function call(method, fallback) {
        var dbus = "gdbus call --session --dest io.github.xixas.Pace --object-path /io/github/xixas/Pace --method io.github.xixas.Pace1." + method;
        runner.connectSource(fallback ? dbus + " >/dev/null 2>&1 || pace " + fallback : dbus);
    }

    function refresh() { call("Refresh"); }
    function snooze(on) { call(on ? "Snooze" : "Unsnooze"); }
    function signIn() { call("SignIn", "sign-in"); }
    function toggleWidget() { runner.connectSource("pace widget --toggle"); }
    function dashboard() { runner.connectSource("pace"); }
    function settings() { runner.connectSource("pace settings"); }
    function openUrl(url) { Qt.openUrlExternally(url); }

    // Re-judge staleness and the "N min ago" footer every 30 s even when the file doesn't change
    Timer {
        interval: 30000
        repeat: true
        running: true
        onTriggered: root.now = Date.now()
    }

    onExpandedChanged: if (expanded) reread()

    preferredRepresentation: compactRepresentation
    compactRepresentation: CompactView {}
    fullRepresentation: FullView {}
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 14

    toolTipMainText: "Pace"
    toolTipSubText: (m.title ? m.title + "\n" : "") + (l.text || "") + (m.updated ? "\n" + m.updated : "")
    Plasmoid.icon: "io.github.xixas.Pace"
}
