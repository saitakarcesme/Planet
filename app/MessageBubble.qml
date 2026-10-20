import QtQuick

Item {
    id: row
    required property string body
    required property string role
    property bool motion: true
    property bool entrance: false
    width: parent ? parent.width : 310
    height: bubble.height
    opacity: entrance ? 1 : 0
    property alias surface: bubble
    Behavior on opacity { NumberAnimation { duration: row.motion ? 180 : 0 } }
    Component.onCompleted: entrance = true
    Rectangle {
        id: bubble
        width: Math.min(row.width * 0.92, label.implicitWidth + 24)
        height: label.height + 16
        x: row.role === "user" ? row.width - width : 0
        y: row.entrance ? 0 : 8
        radius: 17
        color: row.role === "user" ? "#e4e4e7" : "#fafafa"
        Behavior on y { NumberAnimation { duration: row.motion ? 220 : 0; easing.type: Easing.OutCubic } }
        Text {
            id: label
            x: 12; y: 8
            width: Math.min(implicitWidth, row.width * 0.92 - 24)
            text: row.body
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: "Inter"
            font.pixelSize: 13
            lineHeight: 1.16
            color: "#171719"
        }
    }
}
