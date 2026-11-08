# Aleena Android Feature Matrix

Status legend: **CI verified** means the latest source compiled in GitHub Actions; it does not mean the feature has been exercised on the Redmi. **Setup required** means the user must grant Android access or provide a provider key/model. **Not implemented** means it is not available yet.

| PC capability | Android implementation in this branch | Current status / limit |
|---|---|---|
| Account login | Existing Aleena Node `/api/auth/login`; token stored with encrypted preferences | CI verified; real account/device test pending |
| Chat and conversation continuity | Text chat + voice chat through `/api/chat`; session ID returned by Node is reused and cleared on sign-out | CI verified; Node persists each user's default session; native session list/switch/history UI not implemented |
| PC AI provider selection (Gemini/Groq/Ollama) | Uses the existing Aleena Node chat service | Not ported as an in-app provider selector; no backend or API-secret changes made |
| Voice STT/TTS | Android SpeechRecognizer + Android TextToSpeech; language choices for 15 locales | CI verified; available voices/STT languages depend on installed phone engines and locale data |
| Custom wake phrase | Porcupine Android with user-supplied AccessKey and custom `Hey Aleena` `.ppn` file | Setup required; must be tested on phone; not system-level always-on hotword |
| Default Android assistant | VoiceInteractionService/session entry point launches Aleena | CI verified; default-role selection and invocation need Redmi test |
| PC 3D avatar and room | HTTPS WebView opens existing hosted Next.js/VRM companion at configurable URL | Code added; requires working deployed website and login; WebView performance/device test pending |
| PC app/website launcher | Launch installed Android apps; open common websites, Google search and Maps | CI verified; Windows-only executables are not Android apps |
| PC system controls | Volume, mute/unmute; opens Wi-Fi/Bluetooth/Display settings; opens camera, dialer, alarm, Maps; battery and RAM status | CI verified; Android restricted settings are changed by the user in system screens; no elevated access |
| Weather, news, translation shortcuts | Opens Google weather search, Google News, and Google Translate | Browser shortcuts only; PC `internet_manager` itself is missing/unverified |
| WhatsApp send | Opens a prefilled `wa.me` draft; user reviews and sends | CI verified; no unattended sending |
| WhatsApp incoming summaries | Notification listener groups notification content into sender/conversation summaries | Setup required; access and previews controlled by Android/WhatsApp; real-device test pending |
| WhatsApp typing state | Not available through standard NotificationListenerService | Not implemented; typing indicators must remain silent and are not detectable through this feed |
| Tasks | Encrypted local tasks, list, complete and delete; voice commands | Code compiled in CI; functional device test pending |
| Reminders | Encrypted reminder store, AlarmManager scheduling, notification and reboot rescheduling | Code compiled in CI; alarms are inexact; notification permission and Xiaomi battery policy matter |
| Core memory | Encrypted local facts; save/list/forget/clear; basic keyword relevance | Code compiled in CI; cloud sharing is opt-in and off by default; advanced vector/episodic/graph memory not yet ported |
| PDF export | Android native PDF export via system document picker from current chat snippet | Code compiled in CI; local PDF export, not the missing PC PDF generator |
| Clipboard and files | Read clipboard only after user taps while Aleena is open; user selects files through Android picker | Code compiled in CI; no background clipboard/file scraping |
| Multi-agent research/coding | Not ported | PC coding agent runs local Python scripts; Android version needs a sandboxed design and separate review |
| Advanced memory (vector/episodic/knowledge graph/habits) | Not ported | Only explicit local core facts and keyword matching exist today |
| Market/options/gold/backtesting | Not ported | PC `market_intelligence` package is absent from tracked repository tree |
| Social media manager, weather/news manager | Not ported as managers | PC references `internet_manager` and `social_manager`, but their implementations are absent in the tracked tree |
| Image generation | Not ported to Android client | Existing Node API has no image-generation route; PC image path uses different modules |
| Face login | Not ported | PC settings have flags only; no actual face-login implementation found in inspected source |

## Verification gate
- Latest Android Gradle debug APK build passed on commit `0a46372539e99d640ff2a846f23e721de0667b87` before the additional chat-session-continuity edits; those edits are running through CI separately.
- Existing Node syntax, Next.js build and Python compile validation passed on that same commit.
- No physical-device installation, audio, notification, background, or WebView test has been completed yet.
- Do not label the app production-ready until all visible controls have acceptance tests and the Redmi 13 5G / Android 16 device tests are recorded.