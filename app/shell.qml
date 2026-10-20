import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    readonly property string projectRoot: Quickshell.env("PLANET_ROOT")
    property bool opened: false
    property bool suspended: false
    property bool motion: true
    property string owner: Quickshell.screens.length ? Quickshell.screens[0].name : ""
    property string draft: ""
    property string output: ""
    property string phase: "idle"
    property string activity: ""
    property string payload: ""
    property var context: ({})
    property var panels: []
    property bool replied: false
    property bool cancelled: false
    readonly property bool busy: worker.running
    property bool loadingContext: false
    property real glow: opened || busy ? 1 : 0
    Behavior on glow { NumberAnimation { duration: root.motion ? 240 : 0; easing.type: Easing.OutCubic } }
    signal focusInput()

    function toggle() {
        if (busy && suspended) { opened=true; suspended=false; return; }
        if (opened) { opened=false; return; }
        if (busy) { opened=true; suspended=false; return; }
        if (contextProbe.running) return;
        loadingContext=true;
        contextProbe.running=true;
    }
    function cancelTask() {
        if (worker.running) { cancelled=true; worker.signal(15); activity="Stopping…"; }
    }
    function submit(text) {
        text=text.trim();
        if (text==="/stop") { cancelTask(); return; }
        if (!text || busy) return;
        if (text==="/help") {
            output="Enter a command, then press Enter. Esc closes this panel. Use Stop to cancel a running task.\n\n/skills shows the 100 built-in capabilities.\n\nExamples: Open Spotify · Play ABBA on Spotify · Pause music · Create folder ~/Desktop/Project · Calculate 17 * 23";
            draft=""; return;
        }
        output=""; draft=""; replied=false; cancelled=false;
        phase="thinking"; activity="Working…";
        payload=JSON.stringify({text:text,context:context})+"\n";
        worker.command=["python",root.projectRoot+"/scripts/bridge.py"];
        worker.running=true;
    }
    Process {
        id: contextProbe
        command: ["python", root.projectRoot+"/scripts/ui_context.py"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.context=JSON.parse(text); if (root.context.screen) root.owner=root.context.screen; }
                catch(e) { root.context=({}); }
            }
        }
        onExited: {
            root.loadingContext=false; root.suspended=false; root.opened=true;
            Qt.callLater(() => root.focusInput());
        }
    }
    Process {
        id: worker
        stdinEnabled: true
        onStarted: write(root.payload)
        stdout: SplitParser {
            onRead: data => {
                try {
                    const event=JSON.parse(data);
                    if (event.type==="state") {
                        root.phase=event.phase; root.activity=event.message || "Working…";
                        if (event.desktop) root.suspended=true;
                    } else if (event.type==="result") {
                        root.replied=true; root.suspended=false;
                        root.output=event.message || "";
                        root.phase=event.ok ? "success" : "error";
                        root.activity=event.ok ? "" : "Needs attention";
                        root.opened=!!root.output;
                        if (root.opened) Qt.callLater(() => root.focusInput());
                    }
                } catch(e) { console.warn("Planet: invalid worker event"); }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn(text.trim()) }
        onExited: {
            if (!root.replied) {
                root.output=root.cancelled ? "Stopped. Completed steps were kept." : "The task ended without a verified result.";
                root.phase="error"; root.opened=true; root.suspended=false;
            }
        }
    }
    IpcHandler {
        target: "planet"
        function toggle(): void { root.toggle(); }
        function close(): void { root.opened=false; }
        function cancel(): void { root.cancelTask(); }
        function clear(): void { if (!root.busy) { root.output=""; root.draft=""; } }
        function submit(text: string): void {
            if (!root.busy) {
                // CLI/tests have no overlay keyboard focus; the executor reads
                // the current native target when no captured context is supplied.
                if (!root.opened) root.context=({});
                root.opened=true; root.submit(text);
            }
        }
        function quit(): void { root.cancelTask(); Qt.quit(); }
        function status(): string { return JSON.stringify({opened:root.opened,busy:root.busy,phase:root.phase,screen:root.owner,suspended:root.suspended,output:root.output.length,history:0,glow:root.glow}); }
        function inspect(): string { return JSON.stringify(root.panels.map(p=>({screen:p.screen.name,active:p.active,width:p.width,height:p.height,card:p.layout(),glow:p.active ? root.glow : 0}))); }
        function capture(path: string): void { for (const p of root.panels) if (p.active) p.scene.grabToImage(r=>r.saveToFile(path)); }
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            anchors { top:true; bottom:true; left:true; right:true }
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"
            WlrLayershell.namespace: "planet"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: panel.active && root.opened && !root.suspended && !root.busy ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
            property bool active: root.owner===screen.name
            property alias scene: scene
            function layout() { return {x:card.x,y:card.y,width:card.width,height:card.height,visible:card.visible,outputHeight:resultScroll.height,scrollY:resultScroll.contentY,contentHeight:resultScroll.contentHeight}; }
            mask: Region { x:card.x; y:card.y; width:card.visible ? card.width : 0; height:card.visible ? card.height : 0 }
            Component.onCompleted: root.panels.push(panel)
            Component.onDestruction: root.panels=root.panels.filter(p=>p!==panel)
            Connections { target:root; function onFocusInput() { if(panel.active) editor.forceActiveFocus(); } }
            Item {
                id:scene
                anchors.fill:parent
                // Layered 1px strokes form an inward, neutral white glow. The
                // input region excludes these edges so the desktop stays usable.
                Item {
                    anchors.fill:parent
                    opacity:panel.active ? root.glow : 0
                    visible:opacity>0
                    Repeater {
                        model:18
                        Rectangle {
                            required property int index
                            anchors.fill:parent; anchors.margins:index
                            color:"transparent"; border.width:1
                            border.color:Qt.rgba(1,1,1,0.48*Math.exp(-index/4.1))
                            radius:Math.max(0,10-index/2)
                        }
                    }
                }
                Rectangle {
                    id:card
                    width:Math.min(780,panel.width-64)
                    height:compose.height+(root.output ? resultScroll.height+32 : 0)+(root.busy ? 30 : 0)
                    x:Math.round((panel.width-width)/2)
                    y:Math.round((panel.height-height)/2)
                    radius:24
                    color:"#eeeeef"
                    visible:panel.active && root.opened && !root.suspended
                    opacity:visible ? 1 : 0
                    scale:visible ? 1 : 0.985
                    Behavior on scale { NumberAnimation { duration:root.motion ? 160 : 0; easing.type:Easing.OutCubic } }
                    Item {
                        id:compose
                        width:parent.width
                        height:Math.max(84,Math.min(156,editor.contentHeight+48))
                        Flickable {
                            id:inputScroll
                            x:26; y:24; width:parent.width-104; height:parent.height-48
                            contentWidth:width; contentHeight:editor.contentHeight
                            clip:true
                            TextEdit {
                                id:editor
                                width:inputScroll.width
                                text:root.draft
                                color:"#18181b"; selectionColor:"#c5c5cc"; selectedTextColor:"#111114"
                                font.family:"Inter"; font.pixelSize:21
                                wrapMode:TextEdit.Wrap; textFormat:TextEdit.PlainText; selectByMouse:true
                                readOnly:root.busy
                                onTextChanged: { if(text.length>4000) text=text.slice(0,4000); root.draft=text; }
                                onCursorRectangleChanged: {
                                    inputScroll.contentY=Math.max(0,Math.min(cursorRectangle.y,Math.max(0,editor.contentHeight-inputScroll.height)));
                                }
                                Keys.onEscapePressed:root.opened=false
                                Keys.onPressed:event=> {
                                    if ((event.key===Qt.Key_Return || event.key===Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) { root.submit(text); event.accepted=true; }
                                }
                            }
                            Text {
                                text:root.busy ? "Working on your command…" : "What would you like to do?"
                                visible:!editor.text.length
                                color:"#77777f"; font.family:"Inter"; font.pixelSize:21
                            }
                        }
                        Item {
                            anchors.right:parent.right; anchors.rightMargin:18
                            anchors.verticalCenter:parent.verticalCenter
                            width:40; height:40
                            ActionGlyph { anchors.centerIn:parent; width:32;height:32; stopping:root.busy; hovered:actionMouse.containsMouse; pressed:actionMouse.pressed }
                            Accessible.role:Accessible.Button
                            Accessible.name:root.busy ? "Stop task" : "Run command"
                            Accessible.onPressAction:root.busy ? root.cancelTask() : root.submit(editor.text)
                            MouseArea { id:actionMouse; anchors.fill:parent; hoverEnabled:true; cursorShape:Qt.PointingHandCursor; onClicked:root.busy ? root.cancelTask() : root.submit(editor.text) }
                        }
                    }
                    Text {
                        x:26; y:compose.height-4
                        visible:root.busy
                        text:root.activity; color:"#696970"; font.pixelSize:12
                    }
                    Flickable {
                        id:resultScroll
                        x:26;y:compose.height+8;width:parent.width-52
                        height:root.output ? Math.min(resultText.contentHeight,Math.max(80,Math.min(340,panel.height-280))) : 0
                        contentWidth:width;contentHeight:resultText.contentHeight
                        clip:true;visible:!!root.output
                        boundsBehavior:Flickable.StopAtBounds
                        ScrollBar.vertical:ScrollBar { policy:resultScroll.contentHeight>resultScroll.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
                        TextEdit {
                            id:resultText;width:resultScroll.width-12
                            text:root.output;readOnly:true;selectByMouse:true;textFormat:TextEdit.PlainText
                            color:root.phase==="error" ? "#45454b" : "#252529"
                            font.family:"Inter";font.pixelSize:15;wrapMode:TextEdit.Wrap
                            onTextChanged:resultScroll.contentY=0
                            Keys.onEscapePressed:root.opened=false
                        }
                    }
                }
            }
        }
    }
}
