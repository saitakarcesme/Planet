import QtQuick
import Quickshell

Item {
    id: glass
    required property var background
    property bool backgroundReady: false
    property real cornerRadius: 34
    property real reveal: 1
    property real hover: 0
    property real pressure: 0
    property vector2d pointer: Qt.vector2d(width * 0.5, height * 0.5)
    property real pixelRatio: 1
    readonly property int padding: 48
    ShaderEffect {
        x: -glass.padding
        y: -glass.padding
        width: glass.width + glass.padding * 2
        height: glass.height + glass.padding * 2
        property var source: glass.background
        property vector2d extent: Qt.vector2d(width, height)
        property vector2d cardSize: Qt.vector2d(glass.width, glass.height)
        property vector2d pointer: glass.pointer
        property real radius: Math.min(glass.cornerRadius, glass.height * 0.5)
        property real reveal: glass.reveal
        property real hover: glass.hover
        property real pressure: glass.pressure
        property real ready: glass.backgroundReady ? 1 : 0
        Behavior on ready { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        property real pixelRatio: glass.pixelRatio
        fragmentShader: "file://" + Quickshell.env("PLANET_ROOT") + "/.build/glass.frag.qsb"
    }
}
