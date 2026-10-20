import QtQuick

Item {
    id: glyph
    property bool stopping: false
    property bool hovered: false
    property bool pressed: false
    width: 28; height: 28
    scale: pressed ? 0.9 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
    Rectangle {
        anchors.fill: parent
        radius: 14
        color: glyph.hovered ? "#30ffffff" : "transparent"
    }
    Canvas {
        id: ink
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.clearRect(0, 0, width, height);
            ctx.strokeStyle = "#e4e4e4";
            ctx.fillStyle = "#e4e4e4";
            ctx.lineWidth = 1.8;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            if (glyph.stopping) {
                // Four rounded corners, with no enclosing button border.
                ctx.beginPath();
                ctx.moveTo(11, 9); ctx.lineTo(17, 9);
                ctx.quadraticCurveTo(19, 9, 19, 11); ctx.lineTo(19, 17);
                ctx.quadraticCurveTo(19, 19, 17, 19); ctx.lineTo(11, 19);
                ctx.quadraticCurveTo(9, 19, 9, 17); ctx.lineTo(9, 11);
                ctx.quadraticCurveTo(9, 9, 11, 9);
                ctx.fill();
            } else {
                // A small open chevron and stem, drawn independently of fonts.
                ctx.beginPath();
                ctx.moveTo(9, 13); ctx.lineTo(14, 8); ctx.lineTo(19, 13);
                ctx.moveTo(14, 8); ctx.lineTo(14, 20);
                ctx.stroke();
            }
        }
    }
    onStoppingChanged: ink.requestPaint()
}
