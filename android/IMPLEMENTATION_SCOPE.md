# Aleena Android implementation scope

## Current foundation
This module is intentionally isolated from the existing web, Node/Express, Python and Neon components. It uses the existing authenticated Aleena endpoints:
- `POST /api/auth/login`
- `POST /api/chat`

## Locked product behaviour
- WhatsApp typing: record every typing state that can legitimately be detected, but do not announce it aloud.
- Incoming messages: group notifications into sender/conversation summaries.
- Announcements: maximum meaningful supported updates, with deduplication and batching.
- Privacy: hybrid, with local-first notification processing and explicit opt-in before notification-derived content is sent to cloud AI or memory.
- Assistant: provide the normal voice assistant and Android default-assistant integration.

## Current mobile milestone
- Restored native Android login, wake-word voice service, authenticated chat and allowlisted phone actions.
- Added a WhatsApp notification listener for the standard WhatsApp package, local batching, sender/conversation summaries and encrypted metadata-only activity history.
- Notification previews are used transiently for unlocked-device summaries; preview text is not retained in event history and is not sent to cloud.
- Typing monitoring, the Activity Center UI and Android default-assistant integration are not implemented yet.

## Implementation gates
- WhatsApp notification access is for notification content actually exposed by Android and WhatsApp settings.
- Typing detection is experimental and conditional on a legitimate, user-enabled accessibility use case and visible accessible UI. It is not guaranteed with WhatsApp closed, in the background, or on the lock screen.
- Never use root, hidden WhatsApp APIs, modified clients, encryption bypasses or covert screen scraping.
- Do not upload notification previews or typing activity by default.
- Sensitive speech on the lock screen is disabled by default.
- Microphone services must follow Android foreground-service and microphone permission rules.

## Scope protection
Only `android/**` and Android-specific CI/documentation may change during the mobile implementation. Do not modify `web/**`, `server.js`, `main.py`, `web_server.py`, Render configuration, database migrations or Neon settings.
