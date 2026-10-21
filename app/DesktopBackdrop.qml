import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

Item {
    id: backdrop
    required property var screen
    property rect sampleRect: Qt.rect(0, 0, 1, 1)
    property bool streaming: false
    property int generation: 0
    readonly property bool ready: snapshot.item?.hasContent ?? false
    property alias texture: texture
    signal captured()

    function prepare() {
        const request = ++generation;
        Hyprland.refreshToplevels();
        snapshot.active = false;
        Qt.callLater(() => { if (request === generation) snapshot.active = true; });
    }
    function release() { generation++; snapshot.active = false; }

    readonly property var monitor: Hyprland.monitors.values.find(m => m.name === screen.name)
    readonly property var windows: {
        if (!streaming) return [];
        const workspace = monitor?.activeWorkspace?.id;
        return Hyprland.toplevels.values.filter(t => {
            const w = t.lastIpcObject;
            if (!t.wayland || !w.at || !w.size || w.hidden || !w.mapped) return false;
            if (w.workspace?.id !== workspace && !w.pinned) return false;
            const x = w.at[0] - screen.x, y = w.at[1] - screen.y;
            return x < sampleRect.x + sampleRect.width && x + w.size[0] > sampleRect.x &&
                   y < sampleRect.y + sampleRect.height && y + w.size[1] > sampleRect.y;
        }).sort((a, b) => (b.lastIpcObject.focusHistoryID ?? 0) - (a.lastIpcObject.focusHistoryID ?? 0));
    }
    // The clean monitor frame is captured before the overlay appears. Only
    // native window exports update afterward, so the glass cannot capture itself.
    Item {
        id: composition
        width: backdrop.sampleRect.width
        height: backdrop.sampleRect.height
        clip: true
        Loader {
            id: snapshot
            active: false
            x: -backdrop.sampleRect.x
            y: -backdrop.sampleRect.y
            width: backdrop.screen.width
            height: backdrop.screen.height
            sourceComponent: ScreencopyView {
                captureSource: backdrop.screen
                live: false
                paintCursor: false
                onHasContentChanged: if (hasContent) backdrop.captured()
            }
        }
        Repeater {
            model: backdrop.windows
            ScreencopyView {
                required property var modelData
                readonly property var geometry: modelData.lastIpcObject
                x: geometry.at[0] - backdrop.screen.x - backdrop.sampleRect.x
                y: geometry.at[1] - backdrop.screen.y - backdrop.sampleRect.y
                width: geometry.size[0]
                height: geometry.size[1]
                captureSource: modelData.wayland
                live: backdrop.streaming
                paintCursor: false
            }
        }
    }
    ShaderEffectSource {
        id: texture
        sourceItem: composition
        hideSource: true
        visible: false
        live: backdrop.streaming || !backdrop.ready
        smooth: true
        textureSize: Qt.size(Math.ceil(composition.width * backdrop.screen.devicePixelRatio),
                             Math.ceil(Math.min(620, backdrop.screen.height) * backdrop.screen.devicePixelRatio))
    }
}
