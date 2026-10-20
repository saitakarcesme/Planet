import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    property bool opened: false
    property bool motion: true
    property bool dragging: false
    property string grabOwner: ""
    property int dragEvents: 0
    property int dragCancels: 0
    property bool priming: false
    readonly property int orbSize: 60
    property real globalX: 1360
    property real globalY: 940
    property string owner: Quickshell.screens.length ? Quickshell.screens[0].name : ""
    property string phase: "idle"
    property real clock: 0
    property string draft: ""
    property int demoStep: 0
    property bool demoRunning: false
    property var windows: []
    property bool workerReplied: false
    property bool desktopControl: false
    property bool cancelled: false
    property string activity: ""
    property string requestPayload: ""
    function cancelTask() {
        if (worker.running) { cancelled=true; worker.signal(15); activity="Stopping…"; }
    }
    property bool ready: false
    readonly property string projectRoot: Quickshell.env("PLANET_ROOT")
    readonly property bool busy: demoRunning || worker.running
    signal focusInput()
    signal scrollBottom()
    ListModel { id: messages }
    FileView {
        id: savedState
        path: ""
        printErrors: false
        onLoaded: root.restore(text())
        onLoadFailed: root.ready = true
    }
    function save() {
        if (!ready) return;
        let history=[];
        for (let i=0; i<messages.count; i++) history.push({role:messages.get(i).role,body:messages.get(i).body});
        savedState.setText(JSON.stringify({x:globalX,y:globalY,motion:motion,draft:draft,messages:history}));
    }
    function restore(serialized) {
        if (ready) return;
        try {
            const state=JSON.parse(serialized);
            if (typeof state.x === "number" && typeof state.y === "number") { globalX=state.x; globalY=state.y; }
            if (typeof state.motion === "boolean") motion=state.motion;
            draft=typeof state.draft === "string" ? state.draft.slice(0,4000) : "";
            for (let item of (state.messages || []).slice(-80))
                if ((item.role === "user" || item.role === "assistant") && typeof item.body === "string") messages.append(item);
            settle();
        } catch(e) { console.warn("Planet: saved session could not be restored:", String(e)); }
        ready=true;
    }
    onDraftChanged: saveTimer.restart()
    onOpenedChanged: saveTimer.restart()
    Timer { id: saveTimer; interval: 350; onTriggered: root.save() }

    function screenAt(x, y) {
        let fallback=Quickshell.screens[0];
        for (let s of Quickshell.screens) {
            if (x >= s.x && x < s.x+s.width && y >= s.y && y < s.y+s.height) return s;
            if (s.name === owner) fallback=s;
        }
        return fallback;
    }
    function settle() {
        let s = screenAt(globalX+orbSize/2, globalY+orbSize/2);
        if (!s) return;
        owner = s.name;
        globalX = Math.max(s.x+12, Math.min(globalX, s.x+s.width-orbSize-12));
        globalY = Math.max(s.y+12, Math.min(globalY, s.y+s.height-100));
        saveTimer.restart();
    }
    function toggle() {
        if (worker.running) { cancelTask(); opened=true; desktopControl=false; return; }
        opened = !opened;
        if (opened) desktopControl=false;
        if (opened) {
            settle(); priming = true; primeTimer.restart();
            Qt.callLater(() => root.focusInput());
            Qt.callLater(() => root.scrollBottom());
        }
    }
    function add(role, body) {
        if (messages.count >= 80) messages.remove(0);
        messages.append({role:role, body:body});
        saveTimer.restart();
        Qt.callLater(() => root.scrollBottom());
    }
    function preview() {
        if (worker.running) return;
        if (!opened) toggle();
        demoRunning = true; demoStep = 0;
        phase = "thinking";
        add("assistant", "Motion preview started. No real action will be performed.");
        demoTimer.restart();
    }
    function submit(text) {
        text = text.trim();
        if (text === "/stop") { cancelTask(); return; }
        if (!text || busy) return;
        if (!opened) toggle();
        draft = "";
        if (text === "/demo") { preview(); return; }
        if (text === "/clear") { messages.clear(); saveTimer.restart(); return; }
        if (text === "/motion") {
            motion = !motion;
            add("assistant", motion ? "Animations enabled." : "Reduced motion enabled."); return;
        }
        if (text === "/error") {
            phase = "error";
            add("assistant", "Error-state preview. No real action has failed.");
            resetTimer.restart(); return;
        }
        if (text === "/help") {
            add("assistant", "Drag the dots to move Planet. Click or press Super+Alt+P to toggle chat. Press Esc to close.\n\n/demo → preview animations\n/error → preview error state\n/motion → toggle reduced motion\n/clear → clear conversation\n\nLocal models can open installed apps and operate observed controls. Use the stop button or /stop to cancel. Actions already completed are kept."); return;
        }
        let context=[];
        for (let i=Math.max(0,messages.count-8);i<messages.count;i++) context.push({role:messages.get(i).role,body:messages.get(i).body});
        requestPayload=JSON.stringify({text:text,history:context})+"\n";
        add("user", text);
        phase = "thinking"; workerReplied = false; cancelled=false; desktopControl=false;
        activity="Connecting to local models…";
        worker.command = ["python", root.projectRoot + "/scripts/bridge.py"];
        worker.running = true;
    }
    Timer {
        interval: 33
        running: root.motion; repeat: true
        onTriggered: {
            root.clock += interval / 1000;
        }
    }
    Timer { id: primeTimer; interval: 120; onTriggered: root.priming = false }
    Timer { id: resetTimer; interval: 800; onTriggered: if (!root.busy) root.phase = "idle" }
    Timer {
        id: demoTimer; interval: 1400; repeat: true
        onTriggered: {
            root.demoStep++;
            if (root.demoStep === 1) {
                root.add("user", "Demo · Process a sample request."); root.phase = "thinking";
            } else if (root.demoStep === 2) {
                root.phase = "acting";
                root.add("assistant", "Demo · Action in progress");
            } else if (root.demoStep === 3) {
                root.phase = "success";
                root.add("assistant", "Preview complete. Returning to idle.");
            } else {
                stop(); root.demoRunning = false; root.phase = "idle";
            }
        }
    }
    Process {
        id: worker
        stdinEnabled: true
        onStarted: write(root.requestPayload)
        stdout: SplitParser {
            onRead: data => {
                try {
                    let event = JSON.parse(data);
                    if (event.type === "state") {
                        root.phase=event.phase;
                        root.activity=event.message || "Working…";
                        if (event.desktop) { root.desktopControl=true; root.priming=false; }
                    } else if (event.type === "result") {
                        root.workerReplied = true;
                        root.desktopControl=false;
                        root.activity=event.code==="needs_input" ? "Needs your input" : event.ok ? "Done" : "Stopped";
                        root.add("assistant", event.message);
                        root.phase = event.ok ? "success" : "error";
                        resetTimer.restart();
                    }
                } catch(e) { console.warn("Planet bridge: invalid event"); }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn(text.trim()) }
        onExited: (code, status) => {
            root.desktopControl=false;
            if (!root.workerReplied) {
                root.add("assistant", root.cancelled ? "Stopped. Steps already completed were kept." : "No result was received. Please try again.");
                root.phase = "error"; resetTimer.restart();
            }
        }
    }
    IpcHandler {
        target: "planet"
        function toggle(): void { root.toggle(); }
        function close(): void { root.opened = false; }
        function cancel(): void { root.cancelTask(); }
        function demo(): void { root.preview(); }
        function submit(text: string): void { root.submit(text); }
        function move(x: int, y: int): void { root.globalX=x; root.globalY=y; root.settle(); }
        function clear(): void { if (!root.busy) { messages.clear(); root.save(); } }
        function quit(): void { root.cancelTask(); root.save(); savedState.waitForJob(); Qt.quit(); }
        function status(): string {
            return JSON.stringify({opened:root.opened, phase:root.phase, x:root.globalX, y:root.globalY, screen:root.owner, messages:messages.count, busy:root.busy, motion:root.motion, dragging:root.dragging, dragEvents:root.dragEvents, dragCancels:root.dragCancels});
        }
        function inspect(): string {
            return JSON.stringify(root.windows.map(w => ({screen:w.screen.name, width:w.width, height:w.height, x:w.localX, y:w.localY, active:w.active, reveal:w.reveal, mask:w.bubbleRegions.length, layout:w.layoutInfo()})));
        }
        function capture(path: string): void {
            for (let w of root.windows) if (w.screen.name === root.owner)
                w.scene.grabToImage(result => result.saveToFile(path));
        }
    }
    Component.onCompleted: {
        const s = Quickshell.screens[0];
        if (s) { globalX=s.x+s.width-560; globalY=s.y+s.height-130; owner=s.name; }
        savedState.path=root.projectRoot + "/.local-state.json";
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"
            WlrLayershell.namespace: "planet"
            WlrLayershell.layer: WlrLayer.Overlay
            // Moving keyboard focus between layer surfaces during a pointer grab
            // cancels that grab on Hyprland. Transfer it only after release.
            WlrLayershell.keyboardFocus: root.opened && !root.desktopControl && (root.grabOwner || root.owner) === screen.name
                ? (root.priming ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.OnDemand)
                : WlrKeyboardFocus.None
            property bool active: root.owner === screen.name
            property real localX: root.globalX-screen.x
            property real localY: root.globalY-screen.y
            property real chatWidth: Math.min(320, width-84)
            property real chatX: Math.max(12, Math.min(localX+root.orbSize+10+chatWidth <= width-12 ? localX+root.orbSize+10 : localX-chatWidth-10, width-chatWidth-12))
            property real composeY: Math.max(100, Math.min(localY+(root.orbSize-38)/2, height-composer.height-48))
            property real reveal: root.opened && !root.desktopControl && active ? 1 : 0
            Behavior on reveal { NumberAnimation { duration: root.motion ? 210 : 0; easing.type: Easing.OutCubic } }
            property var bubbleRegions: []
            property alias scene: scene
            function layoutInfo() {
                return {chatWidth:chatWidth, composerHeight:composer.height, historyHeight:history.height, historyContentHeight:history.contentHeight, scrollY:history.contentY, scrollable:history.contentHeight>history.height, scrollbarVisible:historyBar.visible};
            }
            function refreshRegions() {
                let regions = [orbRegion, dragRegion, composerRegion, statusRegion, scrollRegion];
                for (let i=0; i<rows.count; i++) {
                    const item=rows.itemAt(i);
                    if (item) regions.push(item.hitRegion);
                }
                bubbleRegions=regions;
            }
            mask: Region { regions: panel.bubbleRegions }
            Region { id: orbRegion; x: panel.localX-5; y: panel.localY-5; width: root.orbSize+10; height: root.orbSize+10; shape: RegionShape.Ellipse }
            // Keep the source surface's input region stable throughout the grab.
            Region { id: dragRegion; width: orbMouse.pressed ? panel.width : 0; height: orbMouse.pressed ? panel.height : 0 }
            Region {
                id: scrollRegion
                x: history.x+history.width-10; y: history.y
                width: root.opened && !root.desktopControl && panel.active && history.contentHeight>history.height ? 10 : 0
                height: root.opened && !root.desktopControl && panel.active ? history.height : 0
            }
            Region {
                id: composerRegion
                x: composer.x; y: composer.y
                width: root.opened && !root.desktopControl && panel.active ? composer.width : 0
                height: root.opened && !root.desktopControl && panel.active ? composer.height : 0
            }
            Region {
                id: statusRegion
                x: status.x; y: status.y
                width: root.opened && !root.desktopControl && panel.active && status.visible ? status.width : 0
                height: root.opened && !root.desktopControl && panel.active && status.visible ? status.height : 0
            }
            Component.onCompleted: { root.windows.push(panel); refreshRegions(); }
            Component.onDestruction: root.windows = root.windows.filter(w => w !== panel)
            Connections {
                target: root
                function onFocusInput() { if (panel.active) editor.forceActiveFocus(); }
                function onScrollBottom() { scrollEnd.restart(); }
            }
            Timer { id: scrollEnd; interval: 35; onTriggered: history.contentY = Math.max(0, history.contentHeight-history.height) }
            Item {
            id: scene
            anchors.fill: parent
            // This input surface never moves, scales or hides with the animated orb.
            // Wayland's implicit pointer grab therefore survives fast/cross-screen drags.
            MouseArea {
                id: orbMouse
                anchors.fill: parent
                hoverEnabled: true
                preventStealing: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                property bool overOrb: Math.pow(mouseX-panel.localX-root.orbSize/2,2)+Math.pow(mouseY-panel.localY-root.orbSize/2,2)<Math.pow(root.orbSize/2+5,2)
                cursorShape: pressed ? Qt.ClosedHandCursor : overOrb ? Qt.OpenHandCursor : Qt.ArrowCursor
                property point origin
                property point offset
                property bool moved: false
                onPressed: mouse => {
                    if (!overOrb) { mouse.accepted=false; return; }
                    origin=mapToGlobal(mouse.x,mouse.y);
                    offset=Qt.point(origin.x-root.globalX,origin.y-root.globalY);
                    moved=false;
                    root.grabOwner=panel.screen.name;
                    root.dragEvents=0;
                }
                onPositionChanged: mouse => {
                    if (!pressed || !(pressedButtons & Qt.LeftButton)) return;
                    const p=mapToGlobal(mouse.x,mouse.y);
                    if (Math.hypot(p.x-origin.x,p.y-origin.y)>4) moved=true;
                    if (!moved) return;
                    root.dragging=true;
                    root.dragEvents++;
                    root.globalX=p.x-offset.x;
                    root.globalY=p.y-offset.y;
                    const destination=root.screenAt(p.x,p.y);
                    if (destination) root.owner=destination.name;
                }
                onReleased: mouse => {
                    root.dragging=false;
                    root.grabOwner="";
                    if (moved) root.settle();
                    else if (mouse.button===Qt.RightButton) root.preview();
                    else root.toggle();
                }
                onCanceled: { root.grabOwner=""; root.dragCancels++; root.dragging=false; root.settle(); }
                onWheel: wheel => wheel.accepted=false
            }
            DotOrb {
                id: orb
                width: root.orbSize; height: root.orbSize
                x: panel.localX; y: panel.localY
                visible: x+width>0 && x<panel.width && y+height>0 && y<panel.height
                clock: root.clock; phase: root.phase; motion: root.motion
                hovered: orbMouse.containsMouse && orbMouse.overOrb
                pressed: root.dragging || (orbMouse.pressed && orbMouse.overOrb)
            }
            Flickable {
                id: history
                x: panel.chatX
                width: panel.chatWidth
                height: Math.min(contentHeight, 360, Math.max(60, panel.composeY-48))
                y: panel.composeY-height-10+(1-panel.reveal)*8
                contentWidth: width
                contentHeight: column.height
                clip: true
                visible: panel.reveal>0
                opacity: panel.reveal
                boundsBehavior: Flickable.StopAtBounds
                interactive: root.opened
                ScrollBar.vertical: ScrollBar {
                    id: historyBar
                    width: 8
                    minimumSize: 0.12
                    policy: history.contentHeight>history.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    contentItem: Rectangle {
                        implicitWidth: 3; radius: 1
                        color: historyBar.pressed ? "#ffffff" : "#888888"
                    }
                    background: Rectangle { color: "transparent" }
                }
                Column {
                    id: column
                    width: history.width-12
                    spacing: 7
                    Repeater {
                        id: rows
                        model: messages
                        onItemAdded: panel.refreshRegions()
                        onItemRemoved: Qt.callLater(panel.refreshRegions)
                        delegate: MessageBubble {
                            id: message
                            required property int index
                            motion: root.motion
                            property Region hitRegion: Region {
                                x: history.x+message.surface.x
                                y: Math.max(history.y, history.y+message.y-history.contentY)
                                width: root.opened && !root.desktopControl && panel.active ? message.surface.width : 0
                                height: root.opened && !root.desktopControl && panel.active ? Math.max(0, Math.min(history.y+history.height, history.y+message.y-history.contentY+message.height)-y) : 0
                            }
                        }
                    }
                    move: Transition { NumberAnimation { properties: "y"; duration: root.motion ? 180 : 0; easing.type: Easing.OutCubic } }
                }
            }
            Rectangle {
                id: composer
                x: panel.chatX+(1-panel.reveal)*8
                y: panel.composeY
                width: panel.chatWidth
                height: Math.max(38, Math.min(76, editor.contentHeight+18))
                radius: 19
                visible: panel.reveal>0
                opacity: panel.reveal
                color: "#1c1c1c"
                Behavior on height { NumberAnimation { duration: root.motion ? 160 : 0; easing.type: Easing.OutCubic } }
                Flickable {
                    id: inputScroll
                    x: 12; y: 9; width: parent.width-52; height: parent.height-18
                    contentWidth: width; contentHeight: editor.contentHeight
                    clip: true
                    TextEdit {
                        id: editor
                        width: inputScroll.width
                        text: root.draft
                        font.family: "Inter"; font.pixelSize: 13
                        color: "#f5f5f5"
                        selectionColor: "#666666"
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        textFormat: TextEdit.PlainText
                        onTextChanged: { if (text.length > 4000) text=text.slice(0,4000); root.draft=text; }
                        onCursorRectangleChanged: {
                            if (cursorRectangle.y+cursorRectangle.height>inputScroll.contentY+inputScroll.height)
                                inputScroll.contentY=cursorRectangle.y+cursorRectangle.height-inputScroll.height;
                            else if (cursorRectangle.y<inputScroll.contentY) inputScroll.contentY=cursorRectangle.y;
                        }
                        Keys.onEscapePressed: root.opened=false
                        Keys.onPressed: event => {
                            if (event.key===Qt.Key_PageUp || event.key===Qt.Key_PageDown) {
                                const direction=event.key===Qt.Key_PageUp ? -1 : 1;
                                history.contentY=Math.max(0,Math.min(history.contentHeight-history.height,history.contentY+direction*history.height*0.8));
                                event.accepted=true;
                                return;
                            }
                            if ((event.key===Qt.Key_Return || event.key===Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
                                root.submit(text); event.accepted=true;
                            }
                        }
                    }
                    Text {
                        visible: !editor.text.length
                        text: "Ask anything…"; color: "#aaaaaa"
                        font.family: "Inter"; font.pixelSize: 13
                    }
                }
                Item {
                    width: 32; height: parent.height
                    anchors.right: parent.right; anchors.rightMargin: 4
                    opacity: 1
                    Text { anchors.centerIn: parent; text: root.busy ? "■" : "↑"; font.pixelSize: 23; color: "#f5f5f5" }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.busy ? root.cancelTask() : root.submit(editor.text) }
                }
            }
            Text {
                id: status
                x: panel.chatX+4; y: composer.y+composer.height+8
                visible: root.opened && !root.desktopControl && panel.active && root.phase !== "idle"
                text: root.demoRunning ? "Motion preview" : root.activity || (root.phase === "error" ? "Needs attention" : "Done")
                color: "#bcbcbc"; font.pixelSize: 11
            }
            }
        }
    }
}
