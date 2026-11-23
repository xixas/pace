// The popup: the GNOME dropdown (buildMenu in extension/pace@osmosys/menu.js) drawn with Plasma components, from
// menuModel(). Absent keys drop their block, exactly as on GNOME.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

PlasmaExtras.Representation {
    id: full
    readonly property var m: root.m
    readonly property color dimText: tint(0.7)

    // GNOME's menu is always dark and uses white; Plasma themes can be light, so tints follow the theme's text colour
    function tint(a) {
        return Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, a);
    }

    Layout.minimumWidth: Kirigami.Units.gridUnit * 20
    Layout.preferredWidth: Kirigami.Units.gridUnit * 22
    Layout.minimumHeight: content.implicitHeight + Kirigami.Units.largeSpacing * 2
    collapseMarginsHint: true

    component Small: PlasmaComponents.Label {
        font: Kirigami.Theme.smallFont
        color: full.dimText
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
    component Banner: Rectangle {
        property string title
        property string detail
        property color tint
        default property alias extra: more.data
        Layout.fillWidth: true
        radius: 9
        color: tint
        implicitHeight: col.implicitHeight + 16
        ColumnLayout {
            id: col
            anchors.fill: parent
            anchors.margins: 8
            spacing: 2
            PlasmaComponents.Label { text: title; font.weight: Font.Bold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Small { text: detail; visible: detail !== "" }
            ColumnLayout { id: more }
        }
    }
    component Pill: QQC2.Button {
        checkable: true
        Layout.fillWidth: true
        display: QQC2.AbstractButton.TextBesideIcon
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing

        Banner {
            visible: !!full.m.problem
            tint: Qt.rgba(1, 0.745, 0.435, 0.16)
            title: full.m.problem ? "⚠ " + full.m.problem.message : ""
            detail: full.m.problem ? full.m.problem.detail : ""
        }
        Banner {
            visible: !!full.m.lastWeek
            tint: Qt.rgba(0.208, 0.518, 0.894, 0.28)
            title: full.m.lastWeek ? "ⓘ " + full.m.lastWeek.text : ""
            detail: full.m.lastWeek ? full.m.lastWeek.detail : ""
            PlasmaComponents.ToolButton {
                text: "Open PineStem"
                onClicked: root.openUrl(full.m.lastWeek.url || full.m.pinestemUrl)
            }
        }
        PlasmaComponents.Label {
            visible: !!full.m.notice
            text: full.m.notice || ""
            font.weight: Font.Bold
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Small { visible: !!full.m.noticeDetail; text: full.m.noticeDetail || "" }

        RowLayout {
            visible: !!full.m.title
            Layout.fillWidth: true
            PlasmaComponents.Label {
                text: full.m.title || ""
                font.weight: Font.Bold
                color: full.m.titleColour || Kirigami.Theme.textColor
                Layout.fillWidth: true
            }
            Small { text: full.m.subtitle || ""; visible: !!full.m.subtitle; Layout.fillWidth: false }
        }
        Small { visible: !!full.m.title && !!full.m.note; text: full.m.note || "" }

        Runway {
            visible: !!full.m.bar
            bar: full.m.bar || null
            Layout.fillWidth: true
        }
        RowLayout {
            visible: !!full.m.bar
            Layout.fillWidth: true
            Small { text: full.m.bar ? full.m.bar.caption.hours : ""; Layout.fillWidth: false }
            Small {
                text: full.m.bar ? full.m.bar.caption.text : ""
                horizontalAlignment: Text.AlignRight
                color: full.m.bar && full.m.bar.tone ? full.m.bar.tone : full.dimText
            }
        }

        RowLayout {
            visible: !!full.m.days
            spacing: 4
            Layout.fillWidth: true
            Repeater {
                model: full.m.days || []
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool quiet: ["future", "weekend", "holiday", "leave", "half_leave"].indexOf(modelData.kind) >= 0
                    Layout.fillWidth: true
                    implicitHeight: chip.implicitHeight + 10
                    radius: 8
                    color: modelData.kind === "pending" ? Qt.rgba(0.47, 0.682, 0.929, 0.18) : full.tint(0.07)
                    border.width: modelData.kind === "today" ? 1.5 : 0
                    border.color: "#78aeed"
                    ColumnLayout {
                        id: chip
                        anchors.centerIn: parent
                        spacing: 0
                        PlasmaComponents.Label {
                            text: modelData.dow
                            font: Kirigami.Theme.smallFont
                            opacity: quiet ? 0.5 : 0.8
                            Layout.alignment: Qt.AlignHCenter
                        }
                        PlasmaComponents.Label {
                            text: modelData.text
                            font.weight: Font.Bold
                            opacity: quiet ? 0.5 : 1
                            color: modelData.kind === "short" ? "#ff7b63" : modelData.kind === "pending" ? "#99c1f1" : Kirigami.Theme.textColor
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }
            }
        }

        ColumnLayout {
            visible: !!full.m.warning
            spacing: 2
            Layout.fillWidth: true
            PlasmaComponents.Label {
                text: "⚠ " + (full.m.warning || "")
                font.weight: Font.Bold
                color: "#ff7b63"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Small { visible: !!full.m.warningDetail; text: full.m.warningDetail || "" }
        }

        PlasmaComponents.Button {
            visible: !!full.m.action
            text: full.m.action ? full.m.action.label : ""
            Layout.fillWidth: true
            onClicked: root.openUrl(full.m.action.url)
        }

        ColumnLayout {
            visible: !!full.m.month
            spacing: 2
            Layout.fillWidth: true
            Kirigami.Separator { Layout.fillWidth: true; Layout.topMargin: 4; Layout.bottomMargin: 4 }
            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Label { text: full.m.month ? full.m.month.name : ""; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Small { text: full.m.month ? full.m.month.left : ""; Layout.fillWidth: false }
            }
            Repeater {
                model: full.m.month ? full.m.month.projects : []
                delegate: ColumnLayout {
                    required property var modelData
                    spacing: 2
                    Layout.fillWidth: true
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents.Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                        Small { text: modelData.text; color: modelData.colour || full.dimText; Layout.fillWidth: false }
                    }
                    Rectangle {
                        visible: modelData.fill !== null
                        Layout.fillWidth: true
                        height: 8
                        radius: 4
                        color: full.tint(0.13)
                        Rectangle {
                            width: Math.max(parent.height, parent.width * (modelData.fill || 0) / 100)
                            visible: (modelData.fill || 0) > 0
                            height: parent.height
                            radius: parent.radius
                            color: modelData.colour || "#9a9996"
                        }
                    }
                    Small { visible: !!modelData.needText; text: modelData.needText || "" }
                }
            }
        }

        Kirigami.Separator { Layout.fillWidth: true; Layout.topMargin: 4 }
        PlasmaComponents.ItemDelegate {
            visible: full.m.signIn
            text: "Sign in…"
            Layout.fillWidth: true
            onClicked: root.signIn()
        }
        PlasmaComponents.ItemDelegate { text: "Open dashboard"; Layout.fillWidth: true; onClicked: root.dashboard() }
        PlasmaComponents.ItemDelegate { text: "Settings…"; Layout.fillWidth: true; onClicked: root.settings() }
        PlasmaComponents.ItemDelegate { text: "Open PineStem"; Layout.fillWidth: true; onClicked: root.openUrl(full.m.pinestemUrl) }

        Kirigami.Separator { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            Pill {
                text: "Mini widget"
                icon.name: "window-pin"
                checkable: false
                onClicked: root.toggleWidget()
            }
            Pill {
                visible: full.m.state !== "skew"
                text: "Snooze today"
                icon.name: "notifications-disabled-symbolic"
                checked: !!full.m.snoozed
                onToggled: root.snooze(checked)
            }
        }

        Kirigami.Separator { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            Small {
                text: root.flash || full.m.updated || ""
                color: root.flash ? "#ffbe6f" : full.dimText
                elide: Text.ElideRight
                wrapMode: Text.NoWrap
            }
            PlasmaComponents.ToolButton {
                text: full.m.problem ? "Retry now" : "Refresh"
                icon.name: "view-refresh"
                onClicked: root.refresh()
            }
        }
    }
}
