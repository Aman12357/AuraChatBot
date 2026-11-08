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

## WhatsApp activity summaries (first notification milestone)
1. Open Aleena Mobile and choose **Enable WhatsApp notification access**.
2. In Android notification access settings, enable Aleena.
3. Return to Aleena and use **Check WhatsApp access** to confirm.
4. Keep WhatsApp notifications enabled and allow previews in Android/WhatsApp notification settings if you want preview-based summaries while the phone is unlocked.

The listener processes only notifications from the standard WhatsApp package (`com.whatsapp`). It groups available notification previews briefly in memory, announces a grouped summary and stores only event metadata (conversation, sender label, count and time) in encrypted app preferences. Preview text is not stored in event history or sent to Aleena's cloud backend by this feature. When the lock screen is active, speech is reduced to a generic activity announcement. Do Not Disturb suppresses speech.

**Typing is not implemented by notification access.** WhatsApp does not provide personal-account typing events through the standard Android notification stream. Any future visible-UI investigation is a separate, permission- and policy-gated feasibility task; it cannot promise detection when WhatsApp is closed or in the background.

## Android default-assistant entry point

The Android client now declares a `VoiceInteractionService` and session service so the user can try selecting Aleena under Android's voice-input / digital-assistant settings. Invocation opens Aleena and requests voice startup. This is separate from the custom **Hey Aleena** wake-word listener: Android's system-wide always-on hotword integration is not claimed as implemented, and availability depends on the device's settings and firmware.
