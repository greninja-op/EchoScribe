# EchoScribe — Complete UI Architecture, Component Hierarchy & Metadata Specification

This document provides an exhaustive inventory of every visual region, container, layout coordinate, button, dropdown, modal, and state handler currently present in the EchoScribe interface (`echoscribe/static/index.html`, `static/css/styles.css`, `static/js/app.js`).

---

## 1. High-Level Viewport Layout Grid

The interface is structured as an edge-to-edge desktop application running at `100vw × 100vh` with `overflow: hidden`, split into a persistent top shell, a 3-region horizontal body split, and floating modal overlays:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [TOPBAR: .window-topbar] (Height: 44px, Flex Row, Fixed Top, z-index: 100)            │
├───────────────────┬────────────────────────────────────────────────┬───────────────────┤
│ [REGION 1]        │ [REGION 2: MAIN CONTENT PANE]                  │ [REGION 3]        │
│ .left-sidebar     │ .main-pane (Flex: 1, Height: calc(100vh - 44px)│ .right-panel      │
│ Width: 240px      │                                                │ Width: 440px      │
│ (Fixed Left)      │ ┌────────────────────────────────────────────┐ │ (Toggleable Right)│
│                   │ │ .dictation-feed-container                  │ │                   │
│ - Primary Nav     │ │  .conversation-thread (max-width: 760px)   │ │ - Header Bar      │
│ - Pinned List     │ │   - Welcome Turn                           │ │   - Corrected/Raw │
│ - Recent Sessions │ │   - Live Streaming Turn (#liveStreamingTurn)│ │   - Copy / Expand │
│ - Stats Footer    │ └────────────────────────────────────────────┘ │   - Close (✕)     │
│                   │ ┌────────────────────────────────────────────┐ │                   │
│                   │ │ [COMPOSER ZONE: .composer-container]       │ │ - Artifact Body   │
│                   │ │  - App-Context Line (#appContextLine)      │ │   - Dictionary    │
│                   │ │  - Command Diff Review (#commandDiffContainer)   - Add Word Form │
│                   │ │  - Composer Input Pill (#composerPill)     │ │                   │
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
  │     ├── nav.tone-switcher#toneSwitcher:
  │     │     ├── button.tone-btn[data-tone="clean"] ("Clean")
  │     │     ├── button.tone-btn[data-tone="professional"] ("Executive")
  │     │     ├── button.tone-btn[data-tone="bullets"] ("Bullets")
  │     │     ├── button.tone-btn[data-tone="code"] ("Code")
  │     │     └── button.tone-btn[data-tone="raw"] ("Raw")
  │     └── div.topbar-right:
  │           ├── button.icon-nav-btn#btnCommandMode ("⚡ Command Mode", kbd: "Alt+C")
  │           ├── select.strength-select#correctionStrengthSelect (full / light / off)
  │           ├── select.engine-select#transcriptionEngineSelect (auto / windows_local / macos_native / model_api)
  │           ├── button.icon-nav-btn#bridgeToggleBtn ("Swarm Bridge", SVG)
  │           ├── button.icon-nav-btn#openDictionaryTopBtn ("Dictionary", SVG)
  │           └── button.icon-nav-btn#openPaletteBtn (kbd: "⌘K")
  │
  └── div.app-container:
        ├── aside.left-sidebar#appSidebar (Region 1):
        │     ├── nav.sidebar-primary-nav:
        │     │     ├── button.sidebar-nav-item#btnNewDictation ("New Dictation", SVG "+")
        │     │     ├── button.sidebar-nav-item#btnNavDictionary ("Personal Dictionary", SVG book)
        │     │     ├── button.sidebar-nav-item#btnNavSnippets ("Macros & Snippets", SVG bolt)
        │     │     └── button.sidebar-nav-item#btnNavSettings ("Settings", SVG gear)
        │     ├── div.sidebar-section:
        │     │     ├── div.sidebar-section-header ("Pinned")
        │     │     └── div.sidebar-list#sidebarPinnedList:
        │     │           ├── div.sidebar-row ("Engineering Log · Auth Service")
        │     │           └── div.sidebar-row ("Pull Request Description")
        │     ├── div.sidebar-section.flex-grow:
        │     │     ├── div.sidebar-section-header ("Recent Sessions")
        │     │     └── div.sidebar-list#sidebarRecentList (Dynamic recent entries)
        │     └── div.sidebar-footer:
        │           └── div.stats-summary-box:
        │                 ├── div.stat-line ("Dictated: #statWordCount")
        │                 ├── div.stat-line ("Speed: #statWpm")
        │                 └── div.stat-line ("Saved: #statTimeSaved")
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
        │           │     ├── button.composer-mic-btn#composerMicBtn (SVG Mic)
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
              │     │     ├── div.artifact-view-toggle:
              │     │     │     ├── button#btnArtifactCorrected ("Corrected")
              │     │     │     └── button#btnArtifactRaw ("Raw")
              │     │     ├── span#artifactTitle ("Personal Dictionary")
              │     │     └── span#artifactBadge ("· DICT")
              │     └── div.artifact-header-right:
              │           ├── button#btnArtifactCopy ("Copy")
              │           ├── button#btnArtifactExpand (Fullscreen toggle)
              │           └── button#btnArtifactClose ("✕")
              └── div.artifact-body#artifactContentBody (Dictionary editor & JSON view)

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

## 3. Comprehensive Inventory of Every Interactive Control

### A. Window Topbar Controls (Top Shell, `y: 0–44px`)

| ID / Selector | Element Type | Visible Label / Icon | Hotkey | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|---|
| `.tone-btn` | `<button>` (x5) | Clean, Executive, Bullets, Code, Raw | Click | Switches active correction tone. Updates `#currentToneLabel`. | Client state `this.activeTone` |
| `#btnCommandMode` | `<button>` | `⚡ Command Mode` | `Alt+C` | Triggers voice edit against active text selection. | `POST /api/command/apply` |
| `#correctionStrengthSelect` | `<select>` | Full / Light / Off | Change | Sets post-ASR disfluency and filler word removal intensity. | `POST /api/flow/correct` (`strength`) |
| `#transcriptionEngineSelect` | `<select>` | Auto / Windows / Mac / Model | Change | Switches speech recognition engine between A, B, and C. | `POST /api/transcription/engine/select` |
| `#bridgeToggleBtn` | `<button>` | `Swarm Bridge` | Click | Arms/disarms auto-dispatching finalized transcripts to CLI Workflow. | Client state `this.swarmArmed` |
| `#openDictionaryTopBtn` | `<button>` | `Dictionary` | Click | Opens Right-Panel Artifact Viewer showing Personal Dictionary. | `GET /api/dictionary` |
| `#openPaletteBtn` | `<button>` | `⌘K` | `⌘K` / `Ctrl+K` | Opens full Command Palette overlay modal. | DOM `#paletteOverlay` |

---

### B. Left Sidebar Controls (Region 1, `x: 0–240px, y: 44px–100vh`)

| ID / Selector | Element Type | Visible Label / Icon | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|
| `#btnNewDictation` | `<button>` | `+ New Dictation` | Clears current view and arms mic stream. | `startRecording()` |
| `#btnNavDictionary` | `<button>` | `Personal Dictionary` | Opens Right-Panel Artifact Viewer with dictionary list. | `openDictionaryArtifact()` |
| `#btnNavSnippets` | `<button>` | `Macros & Snippets` | Opens Command Palette filtered to Snippets group. | `openPalette()` |
| `#btnNavSettings` | `<button>` | `Settings` | Opens Settings / Dictionary configuration pane. | `openDictionaryArtifact()` |
| `#sidebarPinnedList .sidebar-row` | `<div>` (x2) | Engineering Log, PR Description | Click to reload pinned prompt or dictation template. | Client session loader |
| `#sidebarRecentList .sidebar-recent-item` | `<div>` (Dynamic) | Recent session timestamp and text preview | Click to restore past finalized session turn into feed. | `GET /api/history` |

---

### C. Main Composer & Feed Controls (Region 2, Center Pane)

| ID / Selector | Element Type | Visible Label / Icon | Hotkey | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|---|
| `#composerMicBtn` | `<button>` | Microphone Icon | `Spacebar` (Hold) | Starts/stops streaming speech capture; toggles recording pulse. | `toggleRecording()`, `/ws/transcribe` |
| `#copyLatestBtn` | `<button>` | Copy SVG | Click | Copies the most recently finalized transcript to system clipboard. | `navigator.clipboard.writeText()` |
| `#dispatchSwarmBtn` | `<button>` | Play/Dispatch SVG | Click | Sends latest transcript to CLI Workflow Swarm orchestrator. | `POST http://localhost:8099/api/swarm/execute` |
| `#btnAcceptCommand` | `<button>` | `Accept Edit` | Click | Accepts Command Mode diff replacement and updates the target turn. | `acceptCommandEdit()` |
| `#btnDiscardCommand` | `<button>` | `Discard` | `ESC` | Rejects proposed Command Mode edit and hides diff container. | `discardCommandEdit()` |
| `#suggestionsChipsRow .chip-btn` | `<button>` (Dynamic) | Learned word chip (e.g. `+ FastAPI`) | Click | Inserts learned technical term into composer or dictionary. | `POST /api/dictionary` |

---

### D. Universal Right-Panel Controls (Region 3, `x: calc(100vw - 440px)–100vw`)

| ID / Selector | Element Type | Visible Label / Icon | Function & Action Triggered | Target / API Endpoint |
|---|---|---|---|---|
| `#btnArtifactCorrected` | `<button>` | `Corrected` | Shows interactive visual table of homophones and category tags. | `setArtifactMode("corrected")` |
| `#btnArtifactRaw` | `<button>` | `Raw` | Shows raw editable JSON syntax view of the dictionary database. | `setArtifactMode("raw")` |
| `#btnArtifactCopy` | `<button>` | `Copy` | Copies full dictionary entries as formatted JSON to clipboard. | `copyDictionary()` |
| `#btnArtifactExpand` | `<button>` | Expand SVG | Toggles fullscreen overlay mode (`width: 100vw, z-index: 200`). | Right panel `.fullscreen` |
| `#btnArtifactClose` | `<button>` | `✕` | Closes the right artifact viewer panel. | `closeArtifact()` |
| `#dictAddForm` (inside body) | `<form>` | `+ Add` button | Adds a custom homophone replacement (`dictFrom` $\rightarrow$ `dictTo`). | `POST /api/dictionary` |

---

### E. Command Palette Modal Controls (`#paletteOverlay`, z-index: 500)

| Selector | Item Category | Action Value | Action Triggered |
|---|---|---|---|
| `.palette-item` | Wispr Flow Tones | `clean`, `professional`, `bullets`, `code`, `raw` | Changes active dictation tone. |
| `.palette-item` | Snippets & Macros | `!pr`, `!todo`, `!sign` | Inserts template text into active dictation feed. |
| `.palette-item` | Dictionary Actions | `open-dictionary` | Opens right-hand personal dictionary panel. |
| `.palette-item` | Air-Gap Security | `toggle-local-only` | Forces 0-network egress air-gapped mode. |

---

## 4. Candidate Identification: Usability Review & Triage

For trimming non-usable buttons and adding new ones:

### High-Utility / Core Controls (Keep)
1. `#composerMicBtn` (Core dictation trigger).
2. `#transcriptionEngineSelect` (Mode A/B/C selector).
3. `#correctionStrengthSelect` (Full/Light/Off Wispr Flow filter).
4. `#btnCommandMode` (Natural language voice edit).
5. `#btnAcceptCommand` & `#btnDiscardCommand` (Diff accept/reject).
6. `#btnNavDictionary` & `#btnArtifactClose` (Dictionary viewer).

### Redundant / Low-Utility Candidates (Potential Removal)
1. **Duplicate Dictionary Buttons**: `#openDictionaryTopBtn` (in topbar) and `#btnNavDictionary` (in sidebar) do the exact same thing.
2. **Duplicate Palette Buttons**: `#openPaletteBtn` (in topbar), `⌘K` keyboard shortcut, and `#btnNavSnippets` (in sidebar) all open the exact same palette.
3. `#btnArtifactExpand` (Rarely needed for a simple dictionary list).
4. `#sidebarPinnedList` (Static hardcoded list not yet wired to a persistent favorites backend).

### Suggested Additions
1. **Clear Conversation Button**: Button in main feed header to reset active turns.
2. **Audio Input Device Selector**: Dropdown to choose between system microphones.
3. **Live Decibel / Audio Level Meter**: Visual indicator next to `#composerMicBtn`.
4. **Direct Pause / Resume Button**: For long-form continuous lecture/meeting transcription.
