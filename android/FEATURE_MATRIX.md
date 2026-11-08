# Aleena Android Feature Matrix

Status meanings: Implemented in source = code exists but still needs automated/device verification; Setup required = user must provide credentials/model or grant Android access; Not implemented = do not treat as available.

| Area | Feature | Current status | Acceptance check |
|---|---|---|---|
| Account | Sign in through existing Aleena API | Implemented in source | Valid login stores token; invalid login shows useful error |
| Account | Sign out / clear token | Not implemented | Sign out clears token and returns to signed-out state |
| Chat | Voice request to authenticated /api/chat | Implemented in source | Request returns spoken response; expired token prompts re-login |
| Chat | On-screen text chat | Not implemented | User can submit text and read response |
| Voice | Hey Aleena wake word | Setup required | Valid custom Android .ppn and AccessKey start local detection |
| Voice | Speech recognition | Implemented in source | English (India) and Hindi (India) recognition tested on device |
| Voice | Spoken response | Implemented in source | TTS speaks response and resumes wake detection |
| Voice | Start/stop controls | Implemented in source | Persistent foreground notification appears and service stops cleanly |
| Phone | Open Settings, adjust media volume | Implemented in source | Each allowlisted phrase performs the matching action |
| Phone | Open alarm screen and dialer | Implemented in source | System UI opens; no call is placed automatically |
| Phone | Launch installed apps by name | Implemented in source | Matching launcher app opens; missing app is reported |
| Phone | Broader advanced device controls | Not implemented | Each additional action requires an explicit safe implementation and permission review |
| WhatsApp | Notification summaries | Setup required | Notification access enabled; supported incoming notifications are grouped and spoken |
| WhatsApp | Local activity history and clear | Implemented in source | Metadata is stored locally and can be cleared |
| WhatsApp | Silent typing activity detection | Not implemented | NotificationListenerService cannot observe personal-account typing states |
| Android assistant | VoiceInteractionService entry point | Implemented in source; device validation pending | Aleena appears in Android voice-input settings; selecting/invoking it opens Aleena and requests voice startup |
| Privacy | Lock-screen generic announcements | Implemented in source | Sensitive notification preview is not spoken while locked |
| Reliability | Permission denial, provider absence, offline and service errors | Partial | Each failure has visible recovery guidance and no stuck listening state |
| Delivery | CI debug APK | Implemented in source | GitHub Actions build passes; APK is installable on target Android version |

## Release gate
Do not mark the Android app complete or distribute it as production-ready until all visible controls have acceptance tests, automated tests pass, and the Redmi 13 5G / Android 16 device test is recorded. Third-party Picovoice credentials and Android special access must remain explicit setup steps.