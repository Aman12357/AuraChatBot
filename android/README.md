# Aleena Mobile (Android)

Native Android companion for AuraChatBot. Android source remains a separate Gradle module, and its chat client connects only to the user's PC-local Node API over certificate-pinned HTTPS. It does not use the Render API for chat in this local-PC configuration.

## Target and build
- Target device: Xiaomi Redmi 13 5G, Android 16. Real-device validation is still required.
- Kotlin, Android SDK 36, JDK 17, Porcupine Android, Android SpeechRecognizer, TextToSpeech, encrypted preferences and OkHttp.
- Open the `android/` folder in Android Studio, install Android SDK Platform 36 and JDK 17, sync Gradle, then build `:app:assembleDebug`.
- GitHub Actions builds and uploads `aleena-mobile-debug` for the Android branch.

## Secure PC pairing and local chat storage
1. On the PC, follow the root [Gemini + local SQLite setup guide](../docs/LOCAL_FIRST_SETUP.md).
2. Install the Python dependencies, then run `python scripts/generate_local_tls.py` from the repository root.
3. Copy the local HTTPS address, SHA-256 certificate fingerprint, and local pairing key printed by the script.
4. In the PC's private `.env`, set `LOCAL_LAN_ENABLED=true`, keep `DATABASE_MODE=sqlite`, `AI_PROVIDER=gemini`, and set a private `GEMINI_API_KEY`. Keep the ordinary `HOST=127.0.0.1`; the optional mobile listener uses `LOCAL_LAN_HOST=0.0.0.0` and port `8767`.
5. Restart the PC backend. In Windows Firewall, allow the Aleena Node process only on your **Private** home network, not Public networks.
6. On Android, enter the PC address (for example `https://192.168.1.20:8767`), exact 64-character SHA-256 fingerprint, and local pairing key, save them, and tap **Check PC connection**.
7. Sign in using the account created on the PC-local Aleena web app.

- Login and chat use certificate-pinned HTTPS. The app trusts only the exact self-signed certificate whose fingerprint was copied from the PC, and the server also requires the separately generated local pairing key in every API request.
- The PC API validates that it is running `DATABASE_MODE=sqlite` and `AI_PROVIDER=gemini` before the app reports a successful pairing.
- The client keeps its token, PC address, certificate pin and returned `session_id` in Android encrypted app-private preferences.
- The phone and PC must remain on the same trusted Wi-Fi network. The PC must be powered on and the LAN listener enabled.
- Android sends prompt text to the PC over the local network; the PC forwards the prompt and relevant chat history to Gemini for inference. The response and saved chat records stay in the PC's local SQLite database.
- The previous hosted Render API is no longer the default mobile chat destination. No Render variable, Neon resource or cloud deployment is changed by this client.

## Voice setup
1. Create a Picovoice Console account and obtain an AccessKey.
2. Create a Porcupine Android custom keyword model for **Hey Aleena**.
3. Download the Android `.ppn` model.
4. In Aleena, store the AccessKey and import the model.
5. Sign in, grant microphone and notification permissions, then tap Start voice assistant while the app is visible.

The AccessKey is saved in encrypted app-private preferences. The custom model is saved in app-private storage. Neither is committed to Git.
Android speech recognition may use the device's configured recognition provider. TTS and speech recognition language availability depend on installed providers and voice data.

## Android features ported from the PC version
- Authenticated chat and server-backed default chat-session continuity.
- Android-native SpeechRecognizer/TTS with selectable English, Hindi and additional locale presets.
- Voice commands for locally encrypted tasks, scheduled reminders and explicit core memories.
- Optional memory context sharing with cloud chat; the default is **off**.
- Local PDF export for the currently displayed chat snippet using Android's document picker.
- Foreground-only clipboard reading and user-selected file browsing.
- Phone-native controls: media volume, mute/unmute, camera, dialer, alarm UI, Maps/navigation, system settings, battery/RAM status, web search and common website shortcuts.
- WhatsApp draft composition that requires the user to review and press Send.
- WhatsApp notification summaries and metadata-only local activity history.
- The hosted 3D WebView has been disabled in this local-only mobile build so it cannot route a conversation through the old Render web/backend path.
- Selectable Android `VoiceInteractionService` entry point.

## Limits and setup requirements
- The PC VRM avatar is opened through the existing hosted web companion, not reimplemented as a native Kotlin 3D scene.
- The VRM avatar and 3D room are not yet served through the secure local PC listener, so the Android 3D companion screen is intentionally disabled rather than loading a hosted Render URL.
- Porcupine AccessKey and custom model are required for the **Hey Aleena** wake phrase.
- System-wide always-on custom hotword integration is not claimed. Android's microphone foreground-service rules and Xiaomi HyperOS battery/autostart policies may affect background listening.
- WhatsApp notification access only exposes notification content provided by Android and WhatsApp. Personal-account typing indicators are not provided by `NotificationListenerService`.
- WhatsApp sends are not automated; Aleena opens a prefilled draft and the user sends it.
- Wi-Fi, Bluetooth and display controls open the relevant Android Settings screen; Aleena does not bypass Android system restrictions.
- Reminder alarms use `setAndAllowWhileIdle`, so exact-to-the-minute delivery is not guaranteed. Notifications require notification permission.
- The Android app currently uses the existing Node AI chat service. PC Gemini/Groq/Ollama provider selection, local Python multi-agent coding, advanced vector/episodic/knowledge-graph memory, social manager, market package and image-generation pipeline are not ported.
- The PC source references missing `internet_manager`, `social_manager`, `market_intelligence`, `aura_module.py` and `utils/pdf_generator.py` implementations. These are not treated as verified PC capabilities.
- The face-login settings flags found in PC source do not constitute an implemented face-login system.

## Privacy boundaries
- WhatsApp notification previews are transient and are not uploaded to the AI backend by this feature.
- Local activity history contains metadata only and is encrypted; it is user-clearable.
- Core memories are encrypted locally. They are included with a chat request only when the explicit memory-sharing toggle is enabled.
- Clipboard access occurs only after the user taps the control while Aleena is open. Files are selected through Android's system picker.
- No root, hidden APIs, private WhatsApp APIs, background clipboard scraping or unattended messaging are used.

## WhatsApp activity summaries
1. Choose **Enable WhatsApp notification access** in Aleena.
2. Enable Aleena in Android Notification Access settings.
3. Return and use **Check WhatsApp access**.
4. Keep WhatsApp notifications enabled. Allow previews in Android/WhatsApp notification settings if preview-based summaries are wanted while unlocked.

When the device is locked, announcements are generic rather than disclosing message previews. Do Not Disturb suppresses announcements where Android grants notification-policy access.

## Validation status
- GitHub Actions Android build and existing repository validation have passed for earlier parity commits; the latest code changes must also pass the latest CI run before a fresh APK is recommended.
- Compilation does not prove all UI actions work on the phone.
- Real Redmi 13 5G / Android 16 checks remain mandatory for install, microphone lifecycle, TTS/STT, notification access, reminders, WebView, Android assistant selection and HyperOS background behavior.
- The PR remains a draft and is not merged into `main`.