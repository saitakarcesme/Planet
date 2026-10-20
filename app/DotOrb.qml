import QtQuick
import "DotField.js" as Field

Item {
    id: orb
    property real clock: 0
    property string phase: "idle"
    property bool hovered: false
    property bool pressed: false
    property bool motion: true
    width: 48; height: 48
    scale: pressed ? 0.96 : (hovered ? 1.025 : 1)
    Behavior on scale { NumberAnimation { duration: orb.motion ? 130 : 0; easing.type: Easing.OutCubic } }

    Canvas {
        id: paint
        anchors.fill: parent
        property var dots: Field.points(width)
        onPaint: {
            const ctx=getContext("2d");
            ctx.reset();
            ctx.clearRect(0,0,width,height);
            ctx.fillStyle="#ffffff";
            for (let dot of dots) {
                const r=Field.radiusAt(dot,orb.motion ? orb.clock : 0,orb.phase,orb.hovered);
                const p=Field.positionAt(dot,orb.motion ? orb.clock : 0);
                ctx.beginPath();
                ctx.arc(p.x,p.y,r,0,Math.PI*2);
                ctx.fill();
            }
        }
        onWidthChanged: requestPaint()
    }
    onClockChanged: if (visible) paint.requestPaint()
    onHoveredChanged: if (visible) paint.requestPaint()
    onPhaseChanged: if (visible) paint.requestPaint()
    onVisibleChanged: if (visible) paint.requestPaint()
    onMotionChanged: if (visible) paint.requestPaint()
    Component.onCompleted: paint.requestPaint()
}
