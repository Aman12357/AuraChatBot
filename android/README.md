# Aleena Mobile (Android)
Native Android companion for AuraChatBot. Isolated from existing Next.js, Express, Python and Neon services.

## Target
- Device target: Xiaomi Redmi 13 5G, Android 16 (real-device validation remains required).
- Kotlin, Android foreground microphone service, Porcupine, Android SpeechRecognizer and TextToSpeech.
- Existing backend: https://aleena-ai-backend.onrender.com
- Existing API: POST /api/auth/login and authenticated POST /api/chat.

## Build
1. Open this android/ folder in Android Studio.
2. Install Android SDK Platform 36 and JDK 17.
3. Sync Gradle and install on the Redmi with USB debugging enabled.

## Configure Hey Aleena
1. Create a Picovoice Console account and obtain an AccessKey.
2. Create a Porcupine Android custom keyword model for **Hey Aleena**.
3. Download the Android .ppn file.
4. In Aleena Mobile, save the AccessKey and select the model.
5. Sign in, grant microphone/notification permissions and tap Start voice assistant.

The model and AccessKey are intentionally excluded from Git. The key uses Android encrypted preferences; the model is stored in app-private storage.

## Implemented starter features
- Existing backend login and authenticated chat.
- Foreground microphone service with persistent notification.
- Local Porcupine wake-word detection after model/key configuration.
- Android speech recognition and TTS after activation; English (India) and Hindi (India).
- Initial allowlisted actions: open Settings, media volume up/down, open alarm UI, open dialer, launch installed apps by name.

## Android 16 / Xiaomi notes
- Start the microphone foreground service while the app is visible. Android restricts starting microphone foreground services from the background.
- HyperOS may stop background processes. For longer sessions, the user may need to allow Autostart/background activity and set battery use to No restrictions for Aleena. Labels vary by HyperOS build.
- This starter deliberately does not auto-start microphone use at boot.
- Only wake-word detection is local. Android speech recognition may use the configured recognition provider; AI messages go to the Aleena backend after activation.
- Calls open the dialer rather than placing calls automatically.
- System assistant role / VoiceInteractionService, notification access, messaging, media-session controls, brightness and deeper automation are planned follow-up work, not claimed complete.

No Gemini key, database credential or server secret is packaged in this application.