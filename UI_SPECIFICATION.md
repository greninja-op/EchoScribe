# EchoScribe — Complete UI Architecture, Component Hierarchy & Metadata Specification

This document provides an exhaustive inventory of every visual region, container, layout coordinate, button, dropdown, modal, and state handler present in the cleaned-up EchoScribe interface (`echoscribe/static/index.html`, `static/css/styles.css`, `static/js/app.js`).

---

## 1. High-Level Viewport Layout Grid

The interface is structured as an edge-to-edge desktop application running at `100vw × 100vh` with `overflow: hidden`, split into a persistent top shell, a 3-region horizontal body split, and floating modal overlays:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [TOPBAR: .window-topbar] (Height: 44px, Flex Row, Fixed Top, z-index: 100)            │
│  - Wordmark ("EchoScribe") + Air-Gap Badge ("● Air-Gap Active")                       │
│  - Right Actions: ⚡ Command Mode (Alt+C), Swarm Bridge Toggle                         │
├───────────────────┬────────────────────────────────────────────────┬───────────────────┤
│ [REGION 1]        │ [REGION 2: MAIN CONTENT PANE]                  │ [REGION 3]        │
│ .left-sidebar     │ .main-pane (Flex: 1, Height: calc(100vh - 44px)│ .right-panel      │
│ Width: 240px      │                                                │ Width: 440px      │
│ (Fixed Left)      │ ┌────────────────────────────────────────────┐ │ (Toggleable Right)│
│                   │ │ .dictation-feed-container                  │ │                   │
│ - Primary Nav:    │ │  .conversation-thread (max-width: 760px)   │ │ - Universal Header│
│   • New Dictation │ │   - Welcome Turn                           │ │   - Corrected/Raw │
│   • Personal Dict │ │   - Live Streaming Turn (#liveStreamingTurn)│ │     (Dict mode) │
│   • Snippets (⌘K) │ └────────────────────────────────────────────┘ │   - Copy Button   │
│   • Settings      │ ┌────────────────────────────────────────────┐ │   - Close (✕)     │
│                   │ │ [COMPOSER ZONE: .composer-container]       │ │                   │
│ - Recent Sessions │ │  - App-Context Line (#appContextLine)      │ │ - Artifact Body:  │
│   (Live history)  │ │  - Command Diff Review (#commandDiffContainer)   • Dictionary or │
│                   │ │  - Composer Pill with Embedded Mic,        │ │   • Real Settings │
│                   │ │    Pause/Resume Toggle, Copy, & Dispatch   │ │     Panel         │
│                   │ │  - Auto-Learned Chips (#suggestionsStrip)  │ │                   │
│                   │ └────────────────────────────────────────────┘ │                   │
└───────────────────┴────────────────────────────────────────────────┴───────────────────┘
[FLOATING OVERLAY]: .palette-overlay (#paletteOverlay) — Command Palette (⌘K) Modal
```

---

## 2. Container Hierarchy Tree

```yaml
html, body.claude-theme:
  ├── header.window-topbar:
  │     ├── div.topbar-left:
  │     │     ├── span.app-wordmark ("EchoScribe")
  │     │     └── span.airgap-status-quiet#airgapBadge:
  │     │           ├── span.status-dot ("●")
  │     │           └── span ("Air-Gap Active")
  │     └── div.topbar-right:
  │           ├── button.icon-nav-btn#btnCommandMode ("⚡ Command Mode", kbd: "Alt+C")
  │           └── button.icon-nav-btn#bridgeToggleBtn ("Swarm Bridge", SVG)
  │
  └── div.app-container:
        ├── aside.left-sidebar#appSidebar (Region 1):
        │     ├── nav.sidebar-primary-nav:
        │     │     ├── button.sidebar-nav-item#btnNewDictation ("New Dictation", SVG "+")
        │     │     ├── button.sidebar-nav-item#btnNavDictionary ("Personal Dictionary", SVG book)
        │     │     ├── button.sidebar-nav-item#btnNavSnippets ("Macros & Snippets", SVG bolt)
        │     │     └── button.sidebar-nav-item#btnNavSettings ("Settings", SVG gear)
        │     └── div.sidebar-section.flex-grow:
        │           ├── div.sidebar-section-header ("Recent Sessions")
        │           └── div.sidebar-list#sidebarRecentList (Dynamic recent history from SQLite)
        │
        ├── main.main-pane#mainContentPane (Region 2):
        │     ├── div.dictation-feed-container#dictationFeedContainer:
        │     │     └── div.conversation-thread#conversationThread:
        │     │           ├── div.dictation-turn (Welcome greeting)
        │     │           └── div.dictation-turn.live-turn#liveStreamingTurn:
        │     │                 ├── div.turn-header (Live audio status)
        │     │                 └── div.turn-body:
        │     │                       ├── div.live-transcript-text#liveTranscriptText
        │     │                       └── div.replacements-applied-chips#liveReplacementsContainer
        │     └── div.composer-container:
        │           ├── div.app-context-line#appContextLine:
        │           │     ├── span#currentAppTarget ("dictating into VS Code")
        │           │     ├── span#currentToneLabel ("Tone: Clean")
        │           │     ├── span#currentEngineLabel ("Engine: Windows Local")
        │           │     └── span#currentEgressLabel ("0 bytes egress (Air-Gapped)")
        │           ├── div.command-diff-container#commandDiffContainer:
        │           │     ├── div.command-diff-header:
        │           │     │     ├── span.diff-title-badge ("⚡ Command Edit Diff")
        │           │     │     └── div.diff-actions:
        │           │     │           ├── button#btnDiscardCommand ("Discard")
        │           │     │           └── button#btnAcceptCommand ("Accept Edit")
        │           │     └── div.command-diff-body#commandDiffBody
        │           ├── div.composer-pill#composerPill:
        │           │     ├── button.composer-mic-btn#composerMicBtn (Audio-Reactive Pulsing Mic SVG)
        │           │     ├── button.composer-pause-btn#composerPauseBtn (Pause/Resume Toggle SVG)
        │           │     ├── div.composer-placeholder#composerPlaceholder ("Hold Space...")
        │           │     └── div.composer-actions:
        │           │           ├── button.composer-action-btn#copyLatestBtn (SVG Copy)
        │           │           └── button.composer-action-btn#dispatchSwarmBtn (SVG Play/Send)
        │           └── div.suggestions-strip#suggestionsStrip:
        │                 ├── span.suggestions-label ("Auto-Learned:")
        │                 └── div.suggestions-chips-row#suggestionsChipsRow
        │
        └── aside.right-panel#rightArtifactPanel (Region 3):
              ├── div.artifact-header:
              │     ├── div.artifact-header-left:
              │     │     ├── div.artifact-view-toggle#artifactViewToggle:
              │     │     │     ├── button#btnArtifactCorrected ("Corrected")
              │     │     │     └── button#btnArtifactRaw ("Raw")
              │     │     ├── span#artifactTitle ("Personal Dictionary" or "Settings")
              │     │     └── span#artifactBadge ("· DICT" or "· CONFIG")
              │     └── div.artifact-header-right:
              │           ├── button#btnArtifactCopy ("Copy")
              │           └── button#btnArtifactClose ("✕")
              └── div.artifact-body#artifactContentBody:
                    ├── Personal Dictionary Mode: table of homophones + add term form
                    └── Settings Mode:
                          ├── Microphone Input Device Selector (#settingAudioDevice)
                          ├── Transcription Engine Selector (#settingTranscriptionEngine)
                          ├── Correction Strength Selector (#settingCorrectionStrength)
                          ├── Air-Gap Privacy Toggle (#settingAirGapToggle)
                          └── Swarm Bridge Endpoint Status

modal.palette-overlay#paletteOverlay:
  └── div.palette-modal:
        ├── div.palette-search-row:
        │     ├── input#paletteSearchInput ("Type a tone, snippet...")
        │     └── kbd ("ESC")
        └── div.palette-sections:
              ├── div.palette-group ("Wispr Flow Tones")
              ├── div.palette-group ("Snippets & Macros")
              └── div.palette-group ("Dictionary Actions")
```

---

## 3. Inventory of Every Interactive Control

### A. Window Topbar Controls (Top Shell, `y: 0–44px`)

| ID / Selector | Element Type | Visible Label / Icon | Hotkey | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|---|
| `#btnCommandMode` | `<button>` | `⚡ Command Mode` | `Alt+C` | Triggers voice edit against active text selection. | `POST /api/command/apply` |
| `#bridgeToggleBtn` | `<button>` | `Swarm Bridge` | Click | Arms/disarms auto-dispatching finalized transcripts to CLI Workflow. | Client state `this.swarmArmed` |

*(Note: Redundant dictionary and palette buttons were removed. Tone switcher and live engine/strength dropdowns were moved into Settings view and read-only `#appContextLine`)*.

---

### B. Left Sidebar Controls (Region 1, `x: 0–240px, y: 44px–100vh`)

| ID / Selector | Element Type | Visible Label / Icon | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|
| `#btnNewDictation` | `<button>` | `+ New Dictation` | Clears current view and arms mic stream. | `startRecording()` |
| `#btnNavDictionary` | `<button>` | `Personal Dictionary` | Opens Right-Panel Artifact Viewer with dictionary list. | `openDictionaryArtifact()` |
| `#btnNavSnippets` | `<button>` | `Macros & Snippets` | Opens Command Palette filtered to Snippets group. | `openPalette()` |
| `#btnNavSettings` | `<button>` | `Settings` | Opens Dedicated Settings View in Right-Panel. | `openSettingsArtifact()` |
| `#sidebarRecentList .sidebar-row` | `<div>` (Dynamic) | Recent session preview & timestamp | Click to restore past finalized session turn into feed. | `GET /api/history` |

*(Note: Hardcoded `#sidebarPinnedList` and stats footer were removed)*.

---

### C. Main Composer & Feed Controls (Region 2, Center Pane)

| ID / Selector | Element Type | Visible Label / Icon | Hotkey | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|---|
| `#composerMicBtn` | `<button>` | Microphone Icon + Audio Pulse | `Spacebar` (Hold) | Starts/stops streaming speech capture; triggers dynamic audio pulse animation. | `toggleRecording()`, `/ws/transcribe` |
| `#composerPauseBtn` | `<button>` | Pause / Resume Icon | `P` / Click | Pauses or resumes the active speech capture without ending the turn. | `togglePause()` |
| `#copyLatestBtn` | `<button>` | Copy SVG | Click | Copies the most recently finalized transcript to system clipboard. | `navigator.clipboard.writeText()` |
| `#dispatchSwarmBtn` | `<button>` | Play/Dispatch SVG | Click | Sends latest transcript to CLI Workflow Swarm orchestrator. | `POST http://localhost:8099/api/swarm/execute` |
| `#btnAcceptCommand` | `<button>` | `Accept Edit` | Click | Accepts Command Mode diff replacement and updates the target turn. | `acceptCommandEdit()` |
| `#btnDiscardCommand` | `<button>` | `Discard` | `ESC` | Rejects proposed Command Mode edit and hides diff container. | `discardCommandEdit()` |
| `#suggestionsChipsRow .chip-btn` | `<button>` (Dynamic) | Learned word chip (e.g. `+ FastAPI`) | Click | Inserts learned technical term into dictionary. | `POST /api/dictionary` |

---

### D. Universal Right-Panel Controls (Region 3, `x: calc(100vw - 440px)–100vw`)

| ID / Selector | Element Type | Visible Label / Icon | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|
| `#btnArtifactCorrected` | `<button>` | `Corrected` | (In Dict mode) Shows interactive table of homophones and category tags. | `setArtifactMode("corrected")` |
| `#btnArtifactRaw` | `<button>` | `Raw` | (In Dict mode) Shows raw editable JSON syntax view of the dictionary database. | `setArtifactMode("raw")` |
| `#btnArtifactCopy` | `<button>` | `Copy` | Copies dictionary JSON or settings JSON to clipboard depending on active view. | `copyArtifactData()` |
| `#btnArtifactClose` | `<button>` | `✕` | Closes the right artifact viewer panel. | `closeArtifact()` |
| `#settingAudioDevice` | `<select>` | List of audio inputs | Switches active audio input stream across available microphones. | `navigator.mediaDevices.getUserMedia` |
| `#settingTranscriptionEngine` | `<select>` | Auto / Windows / Mac / Model | Switches speech recognition engine between A, B, and C. | `POST /api/transcription/engine/select` |
| `#settingCorrectionStrength` | `<select>` | Full / Light / Off | Sets filler word removal and disfluency cleaning intensity. | `POST /api/flow/correct` |
| `#settingAirGapToggle` | `<input type="checkbox">` | Toggle switch | Toggles strict 0-byte egress air-gap mode. | `POST /api/config/local-only` |

---

### E. Command Palette Modal Controls (`#paletteOverlay`, z-index: 500)

| Selector | Item Category | Action Value | Action Triggered |
|---|---|---|---|
| `.palette-item` | Wispr Flow Tones | `clean`, `professional`, `bullets`, `code`, `raw` | Changes active dictation tone. |
| `.palette-item` | Snippets & Macros | `!pr`, `!todo`, `!sign` | Inserts template text into active dictation feed. |
| `.palette-item` | Dictionary Actions | `open-dictionary` | Opens right-hand personal dictionary panel. |
| `.palette-item` | Air-Gap Security | `toggle-local-only` | Forces 0-network egress air-gapped mode. |

---

## 4. Summary of Cleanups Applied

1. **Top Bar Cleaned**:
   - Removed duplicate `#openDictionaryTopBtn` and `#openPaletteBtn`.
   - Removed `.tone-switcher` 5-button strip (tone now adapts per app or via Command Mode / ⌘K).
   - Moved `#correctionStrengthSelect` and `#transcriptionEngineSelect` dropdowns into Settings view. Current engine remains quietly visible in `#appContextLine`.
2. **Sidebar Simplified**:
   - Removed unpopulated sample list `#sidebarPinnedList`.
   - Removed static stats footer (`#statWordCount`, `#statWpm`, `#statTimeSaved`).
   - Fixed `#btnNavSettings` to open a real Settings view instead of pointing to the dictionary.
3. **Pill & Interaction Upgraded**:
   - Added `#composerPauseBtn` Pause/Resume toggle next to `#composerMicBtn`.
   - Integrated audio-level pulse animation (`@keyframes audioPulse`) directly inside `#composerMicBtn` with live Web Audio API amplitude reactivity.
   - Added physical audio input device selector (`#settingAudioDevice`) in the Settings panel.
