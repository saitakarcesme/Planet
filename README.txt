Planet — local desktop action assistant

CURRENT TARGET
  This build runs on the current Linux / Hyprland (Lua) desktop, using
  Quickshell 0.3.2 and Qt Quick. It is not a macOS build.

RUN
  ./planet start       Start with only the animated dot companion visible.
  ./planet toggle      Open or close the floating conversation.
  ./planet cancel      Stop the current task; completed steps remain completed.
  ./planet status      Print UI, task and drag state.
  ./planet close       Collapse the conversation.
  ./planet stop        Save the session and quit Planet.
  ./planet demo        Run the explicitly labelled animation preview.

  The Wayland pointer helper is built locally on first start. Dependencies:
  Quickshell, Python 3 with PyGObject/Gio/AT-SPI, wtype, xdotool, grim, tesseract with
  English data, ImageMagick, a C compiler, pkg-config, wayland-client and wayland-scanner.
  The development machine uses a signature-verified local xdotool package
  under .build/x11/; other installations should provide xdotool on PATH.
  Other dependencies are installed on the development machine. No root service is added.

NATIVE ACCESSIBILITY
  Planet reads deep native AT-SPI control trees, retaining library/table/dialog
  context and discarding invisible rows. GTK applications launched by Planet
  no longer inherit NO_AT_BRIDGE, which had disabled their accessibility bridge.
  Already-running applications may need a normal restart before exposing controls.

  For an installed Chromium/CEF app that does not expose its controls:
    python scripts/enable-accessibility.py spotify.desktop
  This opt-in setup copies that installed desktop manifest into the user's
  applications directory and adds --force-renderer-accessibility. It also
  enables the session accessibility bus. It does not restart apps, modify the
  packaged manifest, add an action recipe, or map requests to app shortcuts.
  Wrapped launchers must be configured manually. The current Spotify launcher
  is configured this way, and a normal relaunch was tested.
  To undo a newly created override, remove that local desktop file; if it
  replaced a pre-existing override, restore its adjacent .planet-backup-* file.
  Accessibility remains enabled for other applications unless changed separately.
  Chromium documents the flag at:
    https://www.chromium.org/developers/accessibility/testing/automated-testing/ax-inspect/

CONTROLS
  Drag the dots to move Planet across monitors. Click to open the chat.
  Super+Alt+P toggles the chat through the existing local Hyprland binding.
  During a task, clicking the companion/using that shortcut stops the task and
  reveals the conversation. The square button and /stop also cancel work.
  Enter submits; Shift+Enter adds a line; Esc collapses the chat.
  Scroll on messages or drag the scrollbar; PageUp/PageDown also work.
  /help, /clear, /motion, /demo and /error are explicit UI commands.

DESIGN
  Monochrome, borderless, floating messages with no parent background.
  A 76 x 76 companion contains 31 irregularly placed white dots. Independent
  size changes, drift and rotation keep the field animated. The continuous
  minimum dot separation at this size is 2.17 px, including maximum drift.
  Dots retain a visible minimum size throughout their animation. User messages
  and the composer use pale gray with dark text. Send/stop glyphs are drawn
  with rounded strokes/shapes instead of platform-dependent font characters.
  Chat width is 320 px; history is capped at 360 px and scrolls. Composer
  height grows from 38 to 76 px. Empty desktop space passes clicks through.
  The overlay sits above application windows, including fullscreen windows.
  Lock screens and compositor security surfaces are outside its control.

  Pointer input uses an unscaled, stationary surface separate from the
  animation. The source surface retains the pointer grab throughout a drag,
  including across monitors. Movement is applied directly without position
  interpolation. The input mask expands only for the duration of a grab.

MODELS AND ROUTING
  H2O-Lightning: http://127.0.0.1:8741/v1/systemone
  Preferred Qwen: http://127.0.0.1:18020/v1 (HyperQwen / Qwen3.8-27B)
  Fallback Qwen: http://127.0.0.1:11446/v1 (existing EXL3 service)
  Optional overrides: PLANET_DECISION_URL, PLANET_QWEN_URL (OpenAI base URL).

  The model installations are external to this repository. Weights and API
  keys are not bundled. On the current machine the optimized resident pair
  is managed by ~/Projects/omarchypet-model-lab/control:
    control status     Inspect that pair.
    control start      Start it if ports, RAM and GPUs are available.
    control stop       Stop only its own services.
  It does not evict competing models. Do not run competing GPU profiles at
  once. The current pair uses H2O on GPU0 and HyperQwen on GPU1. Its services
  are transient; they do not survive a reboot. No autostart is installed by
  Planet. README and reports describe the tested profile, not a speed promise.

  1. H2O classifies the task from its meaning and recent conversation.
  2. For a confident simple launch, H2O selects from the actual installed
     application catalog. There are no phrase-to-app or phrase-to-URL maps.
  3. Qwen handles new arguments, multi-step tasks, questions and writing.
     It receives the available typed tools and observed desktop state.
     H2O can select a relevant existing window for an initial native observation,
     avoiding a Qwen turn just to choose that window. The installed app catalog
     is fetched on demand; existing-window tasks do not carry it on every turn.
     An observed editable field can be focused, replaced and confirmed in one
     fill_field call. CEF fields with EDITABLE state use a focus-checked keyboard
     fallback when they do not expose the EditableText interface.
  4. Before a mutation, H2O checks the proposed step against the human request
     and resolved target. Uncertain steps receive a second, tool-free Qwen
     authorization assessment. Model confidence is not user permission.
  5. Results return to the controller. Completion requires observed evidence
     and an independent Qwen outcome assessment against the actual request;
     unsupported or unverified work is reported explicitly.
  Successful action-only requests finish silently, without automatic chat
  confirmations or a translation pass. Requested information, generated text,
  necessary questions and failures remain visible. Each model/tool duration
  is recorded privately so playback onset and total verification time can be
  distinguished. Multi-step native UI tasks do not have a one-second guarantee.

CAPABILITIES
  - Discover/open/focus installed native applications via desktop manifests.
  - Read application controls with AT-SPI, with temporary window-cropped OCR
    when text is not exposed. No screenshots are sent to cloud models.
  - Click observed controls, edit accessible fields, type text, send bounded
    keyboard chords and scroll. Click IDs must match their expected labels.
    OCR row activation supports double-clicking. Repeated clicks on unchanged
    controls are rejected so the planner can choose a different method.
    Wayland uses wtype/virtual pointer; Xwayland uses XTEST through xdotool.
    Small tiled windows are temporarily maximized and restored at task end;
    oversized off-screen dialogs are fitted to their monitor. New app windows
    and dialogs from the same process are observed after input.
  - Discover/list/create folders inside home, and open folders through the
    native FileManager1 API, verifying the reported location.
  - Discover media players and control playback through standard MPRIS APIs;
    read actual playback status, track and artist metadata. After choosing a
    track through the observed app UI, wait_for_media checks the chosen title,
    playback state, stable track ID and an advancing playback position.
  - Verify requested saved UTF-8 files against their expected text without
    returning file contents. This complements application-side Save observations.
  - Write and answer questions with the local Qwen model.

BOUNDARIES AND LIMITATIONS
  No model-generated shell, eval, arbitrary executable, URL fallback, deletion,
  purchase or message-send tool is provided. Generic UI interaction can still
  have effects, so actions are scoped to the user request. The semantic model
  check is not a security sandbox or a guarantee against model mistakes.
  Focus, window geometry, observed IDs, labels and tool argument types are
  checked. A lost focus or stale target stops input rather than typing into
  another app. Failed mutations are not blindly retried. Duplicate launch
  attempts within one task are suppressed.

  The resident models are text-only. OCR can miss icons, small text, occluded
  windows or custom controls. Accessibility coverage varies by application;
  screenshots do not reveal hidden application state. Large text lines are
  re-read separately to reduce sparse-segmentation OCR errors. Generic desktop tasks
  are bounded to 18 model steps / 180 seconds and can remain incomplete.
  OCR uses raw TSV parsing, a second high-contrast pass, and line crops.
  A second model assessment reduces unsupported completion claims but is not
  an independent sensor or a correctness guarantee.
  No claim is made that every application, account flow or arbitrary task is
  supported. A model's evidence quote is not a universal correctness proof;
  the live acceptance suite additionally checks independent postconditions.
  English is the product language. User-authored names/text are preserved;
  a tool-free local English rewrite pass normalizes response prose before display.

LOCAL DATA
  .local-state.json retains up to 80 messages, draft, position and motion
  preference. .planet-runs/ stores private request/tool traces for debugging.
  output/ contains local benchmark fixtures, screenshots and raw evidence.
  All are excluded from Git. Screenshots used for OCR are temporary and removed.
  Reports committed under reports/ are aggregate/sanitized test evidence.

VALIDATION
  Latest latency/UI measurements: reports/LATENCY-UI-2026-10-20.txt.
  Existing-app focus completed in 0.787s; a fresh artist-search trial reached
  Playing in 19.293s. Replaying an already-selected artist is measured separately.
  Arbitrary music searches have not reached the one-second target.
  Latest native workflow results: reports/NATIVE-FOLLOWUP-2026-10-20.txt.
  Personal Spotify collection playback passed 3/3 final reruns, new Writer
  plain-text documents 2/2, and representative core tasks 11/11. The report
  includes exploratory failures and the independent acceptance criteria.
  reports/VALIDATION-2026-10-20.txt retains the historical baseline.

  python -m unittest discover -s tests -v
  node tests/test_dots.cjs
  bash -n planet scripts/build-pointer
  scripts/build-pointer

  Explicit live trials (operate the real desktop and local models):
    python tests/live_suite.py --tag my-pilot --sample
    python tests/live_suite.py --tag my-full-run
    python tests/live_drag.py --tag my-drag
    python tests/live_drag.py --open-chat --tag my-open-drag
  Use a fresh tag for each run; old evidence is not overwritten. The live suite
  creates only its own output/live-fixtures/ tree. Runs containing music cases
  mute media and pause playback before restoring the original volume. It does not test
  external posting, payments, deletion, account changes or software installs.

FILES
  app/shell.qml         Overlay, persistence, model bridge events and controls
  app/DotOrb.qml        Animated companion canvas
  app/DotField.js       Deterministic irregular particle field
  app/MessageBubble.qml Message layout
  scripts/bridge.py     Local model routing, planning, validation and cancellation
  scripts/desktop.py    Typed desktop, filesystem and media capabilities
  scripts/accessibility.py Bounded native UI snapshots with control ancestry
  scripts/pointer.c     Small native Wayland pointer transport
  tests/                Unit, geometry and opt-in live acceptance checks
  design/explorations/  Earlier design explorations, not live application assets

REFERENCES
  https://doc.qt.io/qt-6/qml-qtquick-mousearea.html
  https://quickshell.org/docs/types/Quickshell/PanelWindow
  https://github.com/swaywm/wlr-protocols
  https://github.com/jordansissel/xdotool/blob/main/xdotool.pod
  https://specifications.freedesktop.org/mpris/latest/Player_Interface.html
  https://www.freedesktop.org/wiki/Specifications/file-manager-interface/

DEVELOPMENT MACHINE SERVICE NOTE
  The unresponsive EXL3 profile (llmrig-homelab.service, ports 11445/11446)
  and the previous H2O balanced profile were stopped for the tested resident
  pair. Their files and enablement were preserved. Only the resident pair is
  running now. A reboot may start the old enabled profile instead: inspect
  services before starting the lab pair to avoid competing GPU allocations.
