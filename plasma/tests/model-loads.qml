// CI check that Qt's JavaScript engine (stricter than gjs and node) loads the applet's model and draws a fixture.
// Run: QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qml plasma/tests/model-loads.qml   (exit 0 and "model ok")
import QtQuick
import "../io.github.xixas.Pace/contents/code/model.js" as Model

QtObject {
    Component.onCompleted: {
        var json = JSON.stringify({version: 1, state: "on_track", colour: "green", icon: "dot", text: "30.1 / 42.5 h",
            as_of: "2026-10-29T14:06:00", title: "On track", subtitle: "needs 8.0 h/day",
            logged_min: 1806, lines: {lop_min: 2460, target_min: 2550, expected_min: 2700}, days: []});
        var l = Model.look(json, new Date(2026, 9, 29, 14, 10).getTime());
        var m = Model.menuModel(json, new Date(2026, 9, 29, 14, 10).getTime());
        if (l.text !== "30.1 / 42.5 h" || m.title !== "Week · On track" || !m.bar) {
            console.warn("model wrong:", JSON.stringify(l), JSON.stringify(m));
            Qt.exit(1);
        } else {
            console.warn("model ok");
            Qt.exit(0);
        }
    }
}
