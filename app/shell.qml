import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
    id: root
    readonly property string projectRoot: Quickshell.env("PLANET_ROOT")
    property bool opened: false
    property bool suspended: false
    property bool motion: Quickshell.env("PLANET_REDUCED_MOTION") !== "1"
    property real lightPhase: 0
    property int renderedFrames: 0
    property real worstFrame: 0
    property real frameSeconds: 0
    property int slowFrames: 0
    property int frameWarmup: 0
    property bool capturePending: false
    property bool openingRequested: false
    property string queuedText: ""
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
    Behavior on glow { NumberAnimation { duration: root.motion ? (root.opened || root.busy ? 600 : 300) : 0; easing.type: Easing.OutCubic } }
    FrameAnimation {
        running: root.glow > 0.001 && root.motion
        onRunningChanged: root.frameWarmup = 2
        onTriggered: {
            root.lightPhase = (root.lightPhase + Math.min(frameTime, 0.05) * 0.32) % (Math.PI * 2);
            if (root.frameWarmup > 0) root.frameWarmup--;
            else {
                root.renderedFrames++;
                root.frameSeconds += frameTime;
                root.worstFrame = Math.max(root.worstFrame, frameTime);
                if (frameTime > 0.025) root.slowFrames++;
            }
        }
    }
    Timer { id: captureDelay; interval: 360; onTriggered: root.captureBackground() }
    Timer { id: captureTimeout; interval: 180; onTriggered: root.completeOpen() }
    function completeOpen() {
        if (!capturePending) return;
        capturePending = false;
        captureTimeout.stop();
        opened = true;
        Qt.callLater(() => root.focusInput());
        if (queuedText) { const text = queuedText; queuedText = ""; submit(text); }
    }
    function prepareVisual() {
        capturePending = true;
        if (panels.some(p => p.layout().visible)) captureDelay.restart();
        else captureBackground();
    }
    function captureBackground() {
        if (!capturePending) return;
        for (const p of panels) if (p.active) p.prepareBackdrop();
        captureTimeout.restart();
    }
    function closePanel() {
        opened = false;
        openingRequested = false;
        capturePending = false;
        queuedText = "";
        captureDelay.stop();
        captureTimeout.stop();
        for (const p of panels) p.scheduleRelease();
    }
    function showResult(message, ok) {
        const wasVisible = opened && !suspended;
        output = message;
        phase = ok ? "success" : "error";
        activity = ok ? "" : "Needs attention";
        suspended = false;
        if (!message) closePanel();
        else if (!wasVisible) { opened = false; prepareVisual(); }
    }
    signal focusInput()

    function toggle() {
        if (capturePending || loadingContext) {
            closePanel();
            if (contextProbe.running) contextProbe.signal(15);
            return;
        }
        if (busy && suspended) { suspended=false; opened=false; prepareVisual(); return; }
        if (opened) { closePanel(); return; }
        if (busy) { suspended=false; prepareVisual(); return; }
        openingRequested=true; loadingContext=true; contextProbe.running=true;
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
            root.loadingContext=false;
            if (!root.openingRequested) return;
            root.openingRequested=false; root.suspended=false;
            root.prepareVisual();
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
                        root.replied=true;
                        root.showResult(event.message || "", event.ok);
                    }
                } catch(e) { console.warn("Planet: invalid worker event"); }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn(text.trim()) }
        onExited: {
            if (!root.replied) {
                root.showResult(root.cancelled ? "Stopped. Completed steps were kept." : "The task ended without a verified result.", false);
            }
        }
    }
    IpcHandler {
        target: "planet"
        function toggle(): void { root.toggle(); }
        function close(): void { root.closePanel(); }
        function cancel(): void { root.cancelTask(); }
        function clear(): void { if (!root.busy) { root.output=""; root.draft=""; } }
        function submit(text: string): void {
            if (!root.busy) {
                // Opening first captures the same native context as the shortcut.
                if (root.opened && !root.suspended) root.submit(text);
                else { root.queuedText=text; root.toggle(); }
            }
        }
        function quit(): void { root.cancelTask(); Qt.quit(); }
        function status(): string { return JSON.stringify({opened:root.opened,busy:root.busy,phase:root.phase,screen:root.owner,suspended:root.suspended,output:root.output.length,history:0,glow:root.glow}); }
        function inspect(): string { return JSON.stringify(root.panels.map(p=>({screen:p.screen.name,active:p.active,width:p.width,height:p.height,card:p.layout(),glow:p.active ? root.glow : 0}))); }
        function performance(): string { return JSON.stringify({frames:root.renderedFrames,seconds:root.frameSeconds,worstFrame:root.worstFrame,slowFrames:root.slowFrames}); }
        function resetPerformance(): void { root.renderedFrames=0; root.worstFrame=0; root.frameSeconds=0; root.slowFrames=0; root.frameWarmup=2; }
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
            // Keep typing focus through local computation. Release it only
            // when the executor explicitly needs the native desktop.
            WlrLayershell.keyboardFocus: panel.active && root.opened && !root.suspended ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
            property bool active: root.owner===screen.name
            property alias scene: scene
            function layout() { return {x:card.x,y:card.y,width:card.width,height:card.height,visible:card.visible,ready:backdrop.ready,reveal:card.reveal,radius:card.cornerRadius,captures:backdrop.windows.length,inputReady:editor.activeFocus && editor.Window.active && !root.busy && card.requested,outputHeight:resultScroll.height,scrollY:resultScroll.contentY,contentHeight:resultScroll.contentHeight}; }
            function prepareBackdrop() { releaseTimer.stop(); backdrop.prepare(); }
            function releaseBackdrop() { backdrop.release(); }
            function scheduleRelease() { releaseTimer.restart(); }
            mask: Region { x:card.x; y:card.y; width:card.requested ? card.width : 0; height:card.requested ? card.height : 0 }
            DesktopBackdrop {
                id:backdrop
                screen:panel.screen
                sampleRect:Qt.rect(card.x-48, card.y-48, card.width+96, card.height+96)
                streaming:panel.active && card.visible
                onCaptured:if(panel.active) root.completeOpen()
            }
            Timer { id: releaseTimer; interval:420; onTriggered:if(!card.requested) backdrop.release() }
            Component.onCompleted: root.panels.push(panel)
            Component.onDestruction: root.panels=root.panels.filter(p=>p!==panel)
            Connections { target:root; function onFocusInput() { if(panel.active) editor.forceActiveFocus(); } }
            Item {
                id:scene
                anchors.fill:parent
                EdgeGlow {
                    anchors.fill:parent
                    opacity:panel.active ? root.glow : 0
                    visible:opacity>0
                    phase:root.lightPhase
                    energy:root.busy ? 0.6 : 0
                    pixelRatio:panel.screen.devicePixelRatio
                }
                Item {
                    id:card
                    readonly property bool requested: panel.active && root.opened && !root.suspended
                    property real reveal: requested ? 1 : 0
                    readonly property real cornerRadius: Math.min(34,height/2)
                    property real hoverAmount: cardHover.hovered ? 1 : 0
                    property real pressure: actionMouse.pressed ? 1 : 0
                    Behavior on reveal { NumberAnimation { duration:root.motion ? 340 : 0; easing.type:Easing.OutQuint } }
                    Behavior on hoverAmount { NumberAnimation { duration:180; easing.type:Easing.OutCubic } }
                    Behavior on pressure { NumberAnimation { duration:100; easing.type:Easing.OutCubic } }
                    width:Math.min(720,panel.width-64)
                    height:compose.height+(root.output ? resultScroll.height+32 : 0)+(root.busy ? 26 : 0)
                    Behavior on height { NumberAnimation { duration:root.motion ? 320 : 0; easing.type:Easing.OutQuint } }
                    x:(panel.width-width)/2
                    y:(panel.height-height)/2 + (1-reveal)*8
                    visible:reveal>0.001
                    scale:0.965+0.035*reveal-pressure*0.002
                    onRequestedChanged: { if(requested) releaseTimer.stop(); else releaseTimer.restart(); }
                    HoverHandler { id:cardHover; enabled:card.requested }
                    LiquidGlass {
                        anchors.fill:parent
                        background:backdrop.texture
                        backgroundReady:backdrop.ready
                        cornerRadius:card.cornerRadius
                        reveal:card.reveal
                        hover:card.hoverAmount
                        pressure:card.pressure
                        pointer:Qt.vector2d(cardHover.point.position.x,cardHover.point.position.y)
                        pixelRatio:panel.screen.devicePixelRatio
                    }
                    Item {
                        anchors.fill:parent
                        clip:true
                        opacity:Math.max(0,Math.min(1,(card.reveal-0.12)/0.88))
                    Item {
                        id:compose
                        width:parent.width
                        height:Math.max(68,Math.min(140,editor.contentHeight+42))
                        Flickable {
                            id:inputScroll
                            x:26; y:21; width:parent.width-94; height:parent.height-42
                            contentWidth:width; contentHeight:editor.contentHeight
                            clip:true
                            TextEdit {
                                id:editor
                                width:inputScroll.width
                                text:root.draft
                                color:"#f1f1f1"; selectionColor:"#666666"; selectedTextColor:"#ffffff"
                                font.family:"Inter"; font.pixelSize:20; font.letterSpacing:-0.3
                                wrapMode:TextEdit.Wrap; textFormat:TextEdit.PlainText; selectByMouse:true
                                readOnly:root.busy
                                onTextChanged: { if(length>4000) remove(4000,length); root.draft=text; }
                                onCursorRectangleChanged: {
                                    inputScroll.contentY=Math.max(0,Math.min(cursorRectangle.y,Math.max(0,editor.contentHeight-inputScroll.height)));
                                }
                                Keys.onEscapePressed:root.closePanel()
                                Keys.onPressed:event=> {
                                    if ((event.key===Qt.Key_Return || event.key===Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) { root.submit(text); event.accepted=true; }
                                }
                            }
                            Text {
                                text:root.busy ? "Working on your command…" : "What would you like to do?"
                                visible:!editor.text.length
                                color:"#b7b7b7"; font.family:"Inter"; font.pixelSize:20; font.letterSpacing:-0.3
                            }
                        }
                        Item {
                            anchors.right:parent.right; anchors.rightMargin:12
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
                        text:root.activity; color:"#b7b7b7"; font.pixelSize:12
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
                            color:"#e4e4e4"; selectionColor:"#666666"; selectedTextColor:"#ffffff"
                            font.family:"Inter";font.pixelSize:15;wrapMode:TextEdit.Wrap
                            onTextChanged:resultScroll.contentY=0
                            Keys.onEscapePressed:root.closePanel()
                        }
                    }
                    }
                }
            }
        }
    }
}
