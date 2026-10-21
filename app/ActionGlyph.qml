import QtQuick
import QtQuick.Shapes

Item {
    id: glyph
    property bool stopping: false
    property bool hovered: false
    property bool pressed: false
    width: 32
    height: 32
    scale: pressed ? 0.92 : 1
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: "#ffffff"
        opacity: glyph.pressed ? 0.13 : glyph.hovered ? 0.07 : 0
        antialiasing: true
        Behavior on opacity { NumberAnimation { duration: 160 } }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: glyph.stopping ? 0 : 1
        scale: glyph.stopping ? 0.8 : 1
        Behavior on opacity { NumberAnimation { duration: 140 } }
        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        ShapePath {
            strokeColor: "#e9e9e9"
            strokeWidth: 1.65
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            startX: 10.5; startY: 14
            PathLine { x: 16; y: 8.5 }
            PathLine { x: 21.5; y: 14 }
            PathMove { x: 16; y: 8.5 }
            PathLine { x: 16; y: 23 }
        }
    }
    Rectangle {
        width: 10
        height: 10
        anchors.centerIn: parent
        radius: 2.5
        color: "#e9e9e9"
        antialiasing: true
        opacity: glyph.stopping ? 1 : 0
        scale: glyph.stopping ? 1 : 0.7
        Behavior on opacity { NumberAnimation { duration: 140 } }
        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }
}
