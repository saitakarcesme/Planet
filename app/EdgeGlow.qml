import QtQuick
import Quickshell

Item {
    id: glow
    property real phase: 0
    property real energy: 0
    property real pixelRatio: 1
    // Only four narrow strips are shaded; the desktop centre costs no fragments.
    Repeater {
        model: 4
        ShaderEffect {
            required property int index
            x: index === 3 ? glow.width - 96 : 0
            y: index === 1 ? glow.height - 96 : index > 1 ? 96 : 0
            width: index < 2 ? glow.width : 96
            height: index < 2 ? 96 : Math.max(0, glow.height - 192)
            property vector2d viewport: Qt.vector2d(glow.width, glow.height)
            property vector2d origin: Qt.vector2d(x, y)
            property vector2d extent: Qt.vector2d(width, height)
            property real phase: glow.phase
            property real energy: glow.energy
            property real pixelRatio: glow.pixelRatio
            fragmentShader: "file://" + Quickshell.env("PLANET_ROOT") + "/.build/edge.frag.qsb"
        }
    }
}
