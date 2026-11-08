# PC-to-Android Feature Parity

This document compares the desktop implementation in `main.py`, `web_server.py` and `web/src/**` with the Android companion. It distinguishes code that is present from items that are merely configured, referenced but missing, or not safe/possible to reproduce with normal Android permissions.

## Desktop capabilities found in the repository

| PC capability | PC source evidence | Android plan/status | Important difference |
|---|---|---|---|
| Chat, authenticated account, sessions and history | Node API and desktop WebSocket chat bridge | Partial: account login and text/voice chat use certificate-pinned HTTPS to the paired PC | PC local SQLite stores users, sessions and messages; Android does not yet reproduce the complete PC session/history UI |
| AI provider selection | `main.py` and Node API are now Gemini-only in the local-first branch | Uses the PC's Gemini-only Node API over the paired local connection | Gemini API key remains only in the PC `.env`; it is never packaged in the APK |
| Multi-agent research/coding and learned lessons | `AgentOrchestrator`, WEB_AGENT, CODING_AGENT, local Python sandbox | Not ported | Local Python script execution is desktop-only and must not be silently recreated on Android |
| Voice input and output | SpeechRecognition, VoiceEngine, Edge TTS, gTTS, pyttsx3, ElevenLabs, MiniMax | Partial: Porcupine wake-word + Android SpeechRecognizer + Android TTS | Provider keys and voices differ; Android TTS language availability depends on installed voice data |
| Wake word | Desktop setting has a configurable wake-word string; Android uses Porcupine custom keyword model | Setup required | Android needs a Picovoice AccessKey and an Android `.ppn` model; continuous listening is subject to Android foreground microphone rules |
| Local core memory | SQLite `core_memory` table and remember/forget commands | Implemented in this Android branch | Encrypted app-private local facts; explicit opt-in before relevant facts are included in cloud chat prompts |
| Vector, episodic and graph memory; habit profile | SQLite tables and AIClient context-retrieval logic | Not yet ported | Android has only explicit core facts and simple keyword matching at this milestone |
| Tasks and reminders | `TaskManager`, task list and reminder watcher | Implemented in this Android branch | Stored encrypted locally; Android reminders are inexact alarms and notifications need permission |
| Windows app launcher and websites | `AppLauncher`, Windows executable mappings and `WEBSITE_MAPPINGS` | Partial: launch installed Android apps, open sites, Google search, Maps and Camera | Windows-only apps such as VS Code desktop, Office executables and Task Manager are replaced with Android app equivalents or unavailable |
| Windows system controls and metrics | Command prompt documents volume, brightness, power, screenshot, clipboard, process, Wi-Fi, Bluetooth and system stats | Partial: media volume, Wi-Fi/Bluetooth/display settings, battery and RAM info | Android opens Settings for restricted changes; no hidden privilege or background screen/clipboard reading |
| WhatsApp send | `WhatsAppHandler` with pywhatkit | Safer compose flow only | Android opens a prefilled WhatsApp draft; the user must review and tap Send |
| WhatsApp incoming messages | Not part of the PC notification handler shown in `main.py` | Partial: Android NotificationListenerService summaries and local metadata history | Only notification content exposed by Android is available; personal typing indicators are not provided |
| Weather, news and social media manager | PC chat references `internet_manager` and `social_manager` | Not ported | Those manager definitions/modules are not present in the inspected repository tree, so the desktop references cannot be treated as a verified working implementation |
| Market, options, gold and backtesting | `main.py` lazily imports `market_intelligence.*` | Not ported | The `market_intelligence` package is not present in the inspected repository tree |
| Image generation | AIClient has Gemini Imagen calls; FastAPI also has a Pollinations image endpoint | Not ported to Android client | Existing Android Node API has no mobile image-generation route; needs a deliberate API/provider integration |
| PDF generation | FastAPI attempts `utils.pdf_generator` import | Not verified / unavailable in PC bridge | Startup explicitly reports PDF generation disabled when the module is absent |
| 3D digital human, VRM room, emotions, gestures, lip-sync and eye tracking | `web/src/components/Avatar/**` and `web/public/avatar.vrm` | Not ported to native screen yet | Can be embedded or rebuilt for mobile after Android core functions are reliable; requires performance and lifecycle work |
| Face login | PC settings include `face_login_enabled` and backup PIN | Not implemented | The inspected PC source only exposes settings fields; no face-recognition implementation was found |

## Android feature work added in this branch
- Secure PC pairing using a self-signed TLS certificate with a manually verified SHA-256 fingerprint.
- Local HTTPS chat to the PC Node API; mobile pairing health-checks that the PC is using SQLite and Gemini.
- Android stores the PC address, certificate fingerprint, authentication token and chat-session ID in encrypted app-private storage.
- Encrypted local tasks with complete/delete actions.
- Scheduled local reminders with notification delivery and pending-reminder rescheduling after device reboot.
- Encrypted local core memories with add/list/forget/clear actions.
- Optional memory context sharing, disabled by default and controlled by the user.
- Voice commands for tasks, reminders and core memory.
- Phone-native browser/search, website launching, Maps, camera, Wi-Fi/Bluetooth/display settings, battery/RAM status and a user-confirmed WhatsApp message draft.

## Remaining phases for full parity

### Phase A — Android-native productivity and safe device actions
Finish acceptance tests for the new task/reminder/memory code, improve task editing, add device status and complete the safe app/website command catalog.

### Phase B — Pairing and provider security
The current implementation pairs Android with the PC using a locally generated TLS certificate and certificate fingerprint pinning. Future work should add QR-based transfer of the address/fingerprint, device revocation, and automated tests for token/session handling. Gemini credentials stay on the PC and must never be placed in the APK.

### Phase C — Research, web data, image and document generation
Use maintained online APIs or a controlled backend adapter for search, weather, news, image generation and PDFs. First restore/verify missing PC modules; do not port calls that currently reference undefined managers.

### Phase D — Advanced memory and social integrations
Add searchable episodic/semantic memory and knowledge relationships with a clear data export/delete policy. Social posting and notification access require official OAuth/platform APIs and explicit user confirmation.

### Phase E — Digital human and complete mobile experience
Bring the existing VRM avatar, room, emotions, gestures and audio lip-sync into an Android-compatible surface, then profile it on the Redmi 13 5G.

## Non-negotiable boundaries
- Do not change the PC web app, PC Python source, Node backend, Render configuration or Neon database as part of Android-only work.
- Do not bypass Android permissions, WhatsApp protections, app sandboxing, or user confirmation.
- Never claim feature parity until the feature is implemented and acceptance-tested on an Android device.
- The draft pull request is not merged into `main`; each Android milestone remains reviewable.