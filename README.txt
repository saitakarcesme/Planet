PROJECT PAUSED — 2026-10-21
  Latest source checkpoint; unfinished liquid-glass UI work is not fully validated.
  See reports/PAUSED-2026-10-21.txt before resuming. Earlier setup and validation
  notes below describe the previous installed environment, now removed locally.

Planet — local desktop action assistant

CURRENT TARGET
  This build runs on the current Linux / Hyprland (Lua) desktop, using
  Quickshell 0.3.2 and Qt Quick. It is not a macOS build.

RUN
  ./planet start       Start the invisible command overlay.
  ./planet toggle      Open or close the centered command panel.
  ./planet cancel      Stop the current task; completed steps remain completed.
  ./planet status      Print panel/task state.
  ./planet close       Hide the panel.
  ./planet clear       Clear the current result and draft when idle.
  ./planet skills      Print the 100 typed capabilities and their aliases as JSON.
  ./planet stop        Cancel any running task and quit.

  Current machine: Super+Alt+P is already bound to ./planet toggle.
  On another Hyprland installation, bind that chord to the absolute launcher
  path using that installation's configuration syntax. This repo does not
  install a global shortcut automatically. Model autostart is an explicit setup step below.

  Dependencies: Quickshell 0.3.2, Python 3 with PyGObject/Gio/AT-SPI, wtype,
  xdotool, grim, tesseract with English data, ImageMagick, C compiler, pkg-config,
  wayland-client, wayland-scanner and Qt 6 Shader Tools (qsb). Native recipes additionally use the
  installed wpctl, nmcli, xdg-user-dir, git, foot and systemd user tools.
  Editor/agent launch recipes require code, claude or codex on PATH.
  The Wayland pointer helper is built locally on first start. This development
  machine uses a signature-verified local xdotool package under .build/x11/;
  other installations should provide xdotool on PATH. No root service is added.

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
  packaged manifest, change the command catalog.
  Wrapped launchers must be configured manually. The current Spotify launcher
  is configured this way, and a normal relaunch was tested.
  To undo a newly created override, remove that local desktop file; if it
  replaced a pre-existing override, restore its adjacent .planet-backup-* file.
  Accessibility remains enabled for other applications unless changed separately.
  Chromium documents the flag at:
    https://www.chromium.org/developers/accessibility/testing/automated-testing/ax-inspect/

CONTROLS AND DESIGN
  Nothing is normally visible. Super+Alt+P opens one dark translucent, borderless
  command panel on the pointer's monitor. It is centered, up to 720 px wide,
  initially 62 px tall, with an 18 px corner radius. A grayscale light travels
  around all four screen edges. Four narrow GPU-shaded strips leave the centre
  unshaded; the animation stops when hidden. The compositor blurs the command
  surface using the layer rule in config/planet-glass.lua. The empty desktop
  remains transparent and receives pointer events.
  On Hyprland 0.56 Lua, copy that file to ~/.config/hypr/planet-glass.lua and
  add require("hypr.planet-glass") to the user hyprland.lua after backing it up.
  Run hyprctl reload and hyprctl configerrors. This machine is already configured.
  Enter submits, Shift+Enter adds a line, Escape hides the panel.
  /help explains controls; /skills lists the 100 built-in capabilities.

  There is no pet, conversation chain or message persistence. Requested output
  and errors replace the single result below the command field. The output
  scrolls within a maximum 340 px viewport. Successful action-only requests
  close silently. The user can enter Turkish; application copy is English.

  During native execution the card releases keyboard focus and hides, while
  the edge glow stays visible. The shortcut reveals the Stop button again;
  Stop or ./planet cancel cancels work. Completed side effects are not undone.
  Only the card receives pointer input; all other desktop space passes through.
  The overlay is above normal/fullscreen application windows, not lock screens.

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
  are transient. The installed planet-models.service now starts this pair at
  user login and monitors health. Install it explicitly for this existing lab:
    python scripts/install-runtime.py --model-control ~/Projects/omarchypet-model-lab/control
    systemctl --user status planet-models.service
    journalctl --user -u planet-models.service

  Healthy services are adopted without a restart. Three failed probes trigger
  recovery of only the controller's named services, after active model requests
  release their lease. Native aliases still work while models are unavailable.
  Other requests show "Starting local models…" and wait up to 150 seconds before
  inference; Stop remains available. Startup failures back off instead of evicting
  other GPU workloads. Runtime status is private in .planet-runs/runtime.json.
  To disable automatic recovery: systemctl --user disable --now planet-models.service.
  This stops the supervisor, not the resident models; use control stop separately.
  The installer is specific to the existing lab controller's ownership contract,
  not an arbitrary model server. README/reports are not a speed promise.

  1. Fully matched English/Turkish aliases select one of 100 typed native
     recipes without model inference. See design/CAPABILITIES.txt. Up to four
     wholly recognized clauses can compose a task; a partially matched request
     is never executed as a partial shortcut. Parameters retain original text.
  2. H2O selects a known capability for unseen wording at confidence >= 0.97.
     If that capability needs arguments, Qwen extracts a small typed object.
     Missing/invalid arguments, uncertain or unknown requests fall through.
     Spotify scope uses a second three-way gate (separately tested >= 0.90):
     unspecified music resumes the queue without text generation; named music
     extracts the actual target; extra conditions remain with the general planner.
     Wildcard search aliases reject personal collections and extra qualifiers.
  3. The general H2O/Qwen controller handles unfamiliar tasks and requested
     writing through observed native controls and typed tools. It checks each
     mutation against the request and assesses outcome evidence. There is no
     automatic browser substitution or model-generated shell execution.
  4. Known recipes verify native postconditions (window geometry, MPRIS state,
     advancing playback, actual filesystem contents, etc.). They do not need a
     model to reinterpret each deterministic step. Failed actions stop rather
     than silently launching a second planner that might repeat the mutation.

  Spotify recipes inspect the actual accessible native search/library controls.
  Search terms are parameters, not hard-coded artist shortcuts. Personal Liked
  Songs requires the user's library entry and collection owner, not a matching
  public playlist. Playback success requires matching metadata and advancing
  position. Native controls must be accessible and the account must be signed in.
  “Play some music on Spotify” / “Spotify'da bir şey çal” resumes the current
  Spotify queue directly through MPRIS without focusing the app or searching
  those words. With no playable queue it tries the observed personal library.
  Before native launches/observations Planet enables the session accessibility
  bus. If a flagged Spotify process predates that bus and never attaches, the
  Spotify recipe performs one graceful native restart, then waits for actual
  search/library controls to become ready. This recovery can take several seconds.
  Unknown desktop tasks still depend on model latency and accessibility coverage;
  neither generic tasks nor arbitrary Spotify searches have a one-second promise.

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
  The current overlay keeps only the draft/result in memory, not a chat log.
  Legacy .local-state.json is ignored and left untouched. .planet-runs/ stores
  private request/tool traces. output/ contains private benchmark fixtures,
  screenshots and raw evidence. These locations are excluded from Git.
  Planet notes live under ~/.local/share/planet/notes; PLANET_DATA_DIR overrides
  that location for tests. Notes use new private files and never overwrite.
  Timers are transient planet-timer-* units in the current user's systemd session.

VALIDATION
  Latest UI/runtime regression: reports/GLASS-RUNTIME-2026-10-20.txt.
  Previous Spotify regression: reports/SPOTIFY-RECOVERY-2026-10-20.txt.
  Full capability baseline: reports/COMMAND-CAPABILITIES-2026-10-20.txt and JSON.
  Final full run: 100 capabilities attempted, 98 passed, 2 unavailable because
  this machine has no default microphone. Of the 98 successful operations,
  96 completed in under 1 second; median full CLI latency was 0.2103 seconds.
  Spotify artist search: 2.5112 seconds. Personal Liked Songs: 2.3163 seconds.
  These are real bridge-process-to-verified-result timings on the current
  prepared desktop, not cold-start guarantees or inference-only timings.

  python -m unittest discover -s tests -v
  bash -n planet scripts/build-pointer
  python -m py_compile scripts/*.py tests/*.py

  Explicit live trials (operate the real desktop and local models):
    python tests/live_capabilities.py --read-only --tag my-readonly-run
    python tests/live_capabilities.py --all --tag my-full-run
    python tests/live_ui.py --tag my-ui-run
    python tests/live_spotify_recovery.py --tag my-spotify-run
    python tests/live_spotify_recovery.py --cold --tag my-spotify-startup-run
    python tests/live_spotify_recovery.py --paraphrases --tag my-language-run
    python tests/live_spotify_recovery.py --closed --tag my-closed-player-run
    python tests/live_runtime.py --tag my-model-recovery-run
    python tests/live_routing.py --tag my-routing-run
  Use fresh tags. Full trials create their own local fixtures and windows,
  temporarily change audio/workspaces and restore settings. Playback is muted
  during tests and left paused. Agent-terminal checks verify a visible terminal,
  not authentication or a completed agent response. Two microphone operations
  fail explicitly when no default source exists. No external posting, payments,
  deletion, account changes or software installs are tested.

  Older reports and tests/live_suite.py retain generic-controller history.
  The old dot/drag tests and companion components are historical artifacts;
  they are not the current UI's acceptance tests or loaded application assets.

FILES
  app/shell.qml            Centered command overlay and bridge events
  app/ActionGlyph.qml      Send/stop glyphs
  app/EdgeGlow.qml         Narrow grayscale shader strips
  app/edge.frag            Animated screen-edge light
  scripts/model_runtime.py Model readiness, inference leases and recovery
  scripts/install-runtime.py Explicit user-service installer
  scripts/skills.py        Exactly 100 typed capabilities and anchored aliases
  scripts/fast.py          Alias, semantic and composite routing
  scripts/capabilities.py  Native recipes and verified postconditions
  scripts/music.py         Observed native Spotify recipes
  scripts/ui_context.py    Capture target window and pointer monitor before focus
  scripts/bridge.py        General local-model planning/validation/cancellation
  scripts/desktop.py       Typed desktop, filesystem and media primitives
  scripts/accessibility.py Bounded native UI snapshots with control ancestry
  scripts/pointer.c        Native Wayland pointer transport
  tests/                   Unit and opt-in live acceptance checks
  design/CAPABILITIES.txt   Human-readable catalog
  design/explorations/     Historical design explorations

REFERENCES
  https://doc.qt.io/qt-6/qml-qtquick-mousearea.html
  https://quickshell.org/docs/types/Quickshell/PanelWindow
  https://github.com/swaywm/wlr-protocols
  https://github.com/jordansissel/xdotool/blob/main/xdotool.pod
  https://specifications.freedesktop.org/mpris/latest/Player_Interface.html
  https://www.freedesktop.org/wiki/Specifications/file-manager-interface/

DEVELOPMENT MACHINE SERVICE NOTE
  The separate llmrig-homelab router is currently enabled but loads GPU engines
  only on demand. Planet does not disable or evict it. Competing GPU model loads
  can prevent Planet startup; the supervisor reports that condition and retries.
  The resident Planet profile uses the two 3090s, with H2O on GPU0 and Qwen on GPU1.
