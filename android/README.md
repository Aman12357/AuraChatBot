# Aleena Mobile (Android)

Native Android companion for AuraChatBot. This module is isolated from the PC web app, Node/Python backend source, Render configuration and Neon database.

## Target and build
- Target device: Xiaomi Redmi 13 5G, Android 16. Real-device validation is still required.
- Kotlin, Android SDK 36, JDK 17, Porcupine Android, Android SpeechRecognizer, TextToSpeech, encrypted preferences and OkHttp.
- Open the `android/` folder in Android Studio, install Android SDK Platform 36 and JDK 17, sync Gradle, then build `:app:assembleDebug`.
- GitHub Actions builds and uploads `aleena-mobile-debug` for the Android branch.

## Existing backend integration
- Login: `POST https://aleena-ai-backend.onrender.com/api/auth/login`.
- Chat: authenticated `POST /api/chat`.
- The client keeps the returned `session_id` encrypted and reuses it for text and voice chat; signing out clears the local session identifier.
- No new server route, database migration, Render variable or Neon resource is added by this Android client.

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
- A WebView entry point to the original hosted PC Next.js/3D avatar companion; its HTTPS URL is editable in the Android screen.
- Selectable Android `VoiceInteractionService` entry point.

## Limits and setup requirements
- The PC VRM avatar is opened through the existing hosted web companion, not reimplemented as a native Kotlin 3D scene.
- The hosted web companion must be deployed and reachable. The default address is `https://aleena-ai-web.onrender.com`; the user can edit it in the app.
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