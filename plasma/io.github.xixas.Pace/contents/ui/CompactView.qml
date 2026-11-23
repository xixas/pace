// The panel indicator (B1): the bell-off while snoozed, the marker (dot or glyph) in the verdict colour, then the text.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

MouseArea {
    id: compact

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property color ink: root.colour(root.l.colour)

    Layout.minimumWidth: vertical ? -1 : row.implicitWidth + Kirigami.Units.smallSpacing * 2
    Layout.preferredWidth: Layout.minimumWidth
    hoverEnabled: true
    onClicked: root.expanded = !root.expanded

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Kirigami.Units.smallSpacing
        opacity: root.l.dim ? 0.6 : 1

        Kirigami.Icon {
            visible: !!root.l.snoozed
            source: "notifications-disabled-symbolic"
            Layout.preferredWidth: Kirigami.Units.iconSizes.small
            Layout.preferredHeight: Kirigami.Units.iconSizes.small
        }
        Rectangle {
            visible: root.l.marker === "dot"
            width: Kirigami.Units.gridUnit * 0.55
            height: width
            radius: width / 2
            color: compact.ink
        }
        PlasmaComponents.Label {
            visible: root.l.marker !== "dot"
            text: root.l.marker
            color: compact.ink
        }
        PlasmaComponents.Label {
            visible: root.l.text !== "" && !compact.vertical
            text: root.l.text
        }
    }
}
