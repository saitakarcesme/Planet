import QtQuick
import Quickshell

Item {
    id: glow
    property bool animate: visible
    property real phase: 0
    // Only four narrow strips are shaded; the desktop centre costs no fragments.
    NumberAnimation on phase {
        from: 0; to: 6.2831853; duration: 7200
        loops: Animation.Infinite; running: glow.animate
    }
    Repeater {
        model: 4
        ShaderEffect {
            required property int index
            x: index === 3 ? glow.width - 56 : 0
            y: index === 1 ? glow.height - 56 : index > 1 ? 56 : 0
            width: index < 2 ? glow.width : 56
            height: index < 2 ? 56 : Math.max(0, glow.height - 112)
            property vector2d viewport: Qt.vector2d(glow.width, glow.height)
            property vector2d origin: Qt.vector2d(x, y)
            property vector2d extent: Qt.vector2d(width, height)
            property real phase: glow.phase
            fragmentShader: "file://" + Quickshell.env("PLANET_ROOT") + "/.build/edge.frag.qsb"
        }
    }
}
