# Kelvra Voice — Talkback TTS Engines: Piper (local) + Deepgram (cloud) Build Spec
Session 3 (this session), 2026-09-03. New, standalone file — the original `kelvra-voice-talkback-spec.md` has already been handed to the editor and built. This file is the next-phase plan: the two concrete TTS engines that spec decided on (§2/§6 there) get their own full build-out here, since the editor needs a dedicated, focused document for this specific piece of work.

## 0. Scope
Two new features, planned together because they're two halves of one decision (local-free vs. cloud-general TTS), but each gets full detail below so the editor can build both cleanly:
1. **Piper** — local model download and integration (the free, no-GPU, no-account tier)
2. **Deepgram** — cloud API integration (the general/production tier)

Both plug into the Talkback pipeline already built: `STT → intent parsing → action dispatch → [TTS] spoken + text reply`. This file only concerns the `[TTS]` stage and its supporting settings UI — it doesn't touch STT, parsing, or dispatch, all of which are already done.

## 1. Piper — local model, download, and integration

### 1.1 Installation
```
pip install piper-tts --break-system-packages
```
No GPU dependency, no account, no API key. This should be bundled/installed as part of Kelvra Voice's own setup, not left as a manual step for the end user.

### 1.2 Voice file management
- Piper needs a voice model file (small, 14–30MB) downloaded once before first use. This is a one-time download, not a per-session cost.
- Kelvra Voice should ship with **one default preset voice already selected**, downloading it automatically on first run of the Talkback feature (or during initial app setup) — not something the user has to go find and configure manually before Talkback works at all.
- Store the downloaded voice file(s) in Kelvra Voice's local app-data directory (consistent with wherever the transcription engine's own local model files, per the multi-engine spec, already get stored — reuse that same storage location convention rather than inventing a new one).
- Support downloading/caching **more than one** preset voice, since the persona/voice-picker requirement (from the original Talkback spec §4) means the user may want to switch between a few different Piper voices, not just the one default.

### 1.3 Settings UI for Piper
- Shows which preset voice is currently active/downloaded.
- A way to browse and download additional available Piper preset voices (list pulled from Piper's own published voice catalog).
- A preview/test button per voice (speak a short sample) so the user can pick by ear before committing — same preview pattern already specified for persona selection generally.
- No credential fields needed for this engine — nothing to authenticate.

### 1.4 Runtime integration
- When Talkback needs to speak a reply and Piper is the active engine, the text goes to the locally-installed Piper process/library, which returns synthesized audio to play immediately.
- Since Piper runs on-device, this path has no network dependency and no per-use cost — it should remain fully functional even with no internet connection, which is a meaningful advantage worth preserving (don't accidentally route Piper synthesis through a network call anywhere in the implementation).
- Expected latency: real-time on CPU, no meaningful delay to budget for beyond normal local inference time — but still worth measuring once built, per the end-to-end latency-budget point from the original Talkback spec (§3 there).

## 2. Deepgram — cloud integration

### 2.1 Account and API key (for the user, outside the app)
Not something Kelvra Voice automates — this is the user's own one-time setup:
1. Sign up at deepgram.com (email/password or an OAuth option if offered — confirm on their actual signup page).
2. Verify the account (email confirmation, and possibly phone verification — worth confirming directly on Deepgram's current signup flow before assuming which).
3. No credit card required to claim the $200 free credit.
4. Generate an API key from the Deepgram dashboard.

### 2.2 Settings UI for Deepgram
- A single API-key input field, under the "Deepgram (cloud)" engine option in Voice Assistant settings.
- Store the key using the same `keyring`/OS-keychain approach already used for every other provider credential in Kelvra (per `settings-panel-api-keys-spec.md`) — never plaintext, no separate storage mechanism invented just for this one key.
- Once a key is entered, offer a quick validation check (a trivial test call to Deepgram, showing success/failure) — same two-tier validation pattern (free model-list-style check, then optional live test) already specified for provider keys generally in the Settings panel spec, applied here too rather than reinvented.
- A visible indicator of engine status: "Deepgram connected" vs. "no key set, using Piper" — so the user always knows which engine is actually live, especially important given the fallback behavior in §3.

### 2.3 Runtime integration
- When Talkback needs to speak a reply and Deepgram is the active/available engine, the text is sent to Deepgram's Aura-2 TTS endpoint (REST or WebSocket streaming — streaming preferred, since it starts returning audio from the first byte rather than waiting for the full response, which matters for the near-zero-latency requirement from the original Talkback spec).
- Requires network connectivity — unlike Piper, this path fails gracefully (falls back to Piper, §3) if offline or if the API call errors.
- Worth surfacing remaining free-credit usage somewhere in Settings if Deepgram's API exposes that data, so the user isn't caught off guard by the credit running low — a nice-to-have, not a hard requirement, but cheap to add if the data's available.

## 3. Engine selection and fallback logic
- A toggle/radio choice in Settings: **Piper (local)** vs. **Deepgram (cloud)** — whichever is selected is what actually generates audio at runtime.
- **Piper is the default and the automatic fallback**: if Deepgram is selected but no valid API key is present (or a Deepgram call fails at runtime — network issue, expired credit, etc.), Talkback should transparently fall back to Piper rather than simply failing silently or producing no speech at all. This mirrors the same local-first-with-cloud-fallback resilience pattern already used for transcription (Mode B/C in the multi-engine spec) — same shape of solution, applied to the output side.
- This fallback behavior should be visible, not silent — e.g. a brief indicator or log entry noting "Deepgram unavailable, using Piper" so the user isn't confused about why the voice suddenly sounds different.

## 4. New backend/infra surface this requires
- Piper process/library wiring inside Kelvra Voice's synthesis pipeline, plus a voice-file download/cache manager (list available voices, download, store, switch active voice).
- Deepgram API client integration (streaming synthesis call), API-key storage via `keyring`, and a key-validation endpoint/check.
- Engine-selection state (which engine is active) stored in Voice's local settings, plus the runtime fallback logic described in §3.
- Optional: a Deepgram usage/credit-remaining fetch, if exposed by their API, surfaced in Settings.

## 5. Open items for Arun
1. Which specific Piper preset voice ships as the default on first run — needs picking from Piper's actual voice catalog, not decided here.
2. Whether Deepgram's signup flow requires phone verification in addition to email — flagged as unconfirmed in the original conversation, worth checking directly before building the "sign up" instructions into any onboarding copy.
3. Whether to surface Deepgram credit-remaining in Settings (§2.3) — nice-to-have, not committed.
4. Exact wording/placement of the fallback indicator (§3) — a toast notification, a small icon change, or something else; not designed here, just required to exist in some form.
