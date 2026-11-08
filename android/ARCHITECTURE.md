# Aleena Android Architecture

## Goals
- Keep the Android client isolated from the existing web application, Node/Python services, Render configuration and Neon database.
- Use a small, explicit dependency direction: UI -> domain/use cases -> repositories -> platform or network adapters.
- Keep sensitive device data local by default.
- Make every visible control report a real success or a useful failure state.

## Target package layout

```
ai.aleena.mobile
  app/                 Application entry point and dependency wiring
  core/
    model/             UI-independent models and result types
    permissions/       Runtime permission and special-access checks
    security/          Encrypted preferences and secret handling
    platform/          Android system adapters (TTS, speech, notifications)
  data/
    remote/            Authenticated Aleena API client and DTO parsing
    local/             Encrypted preferences and local activity history
    repository/        Repository implementations
  domain/
    assistant/         Assistant state, command routing and use cases
    chat/              Chat/session models and send-message use case
    activity/          WhatsApp event rules and summaries
    phone/             Allowlisted device actions
  feature/
    home/              Main dashboard and status
    account/           Sign-in/sign-out
    voice/             Wake-word configuration and listening controls
    chat/              Text chat
    activity/          WhatsApp activity history and privacy controls
```

The current starter uses fewer packages. Refactoring into this layout will be incremental so working notification and API code is not discarded in one large rewrite.

## Data boundaries
- Credentials and API tokens: encrypted app-private storage only.
- Picovoice custom keyword model: app-private files only; never commit it.
- WhatsApp notification previews: transient processing only; never upload by default.
- WhatsApp activity history: metadata only, encrypted local storage, user-clearable.
- Chat text: sent only to the existing authenticated Aleena API after the user speaks or submits it. The existing backend persists chat messages.
- No new backend endpoints, database tables, Render settings or Neon changes are required for the mobile client.

## Core runtime flows

### Voice
1. User signs in and configures the Picovoice AccessKey and custom Hey Aleena model.
2. User grants microphone permission and explicitly starts the foreground microphone service while Aleena is visible.
3. Porcupine detects the wake phrase on-device.
4. Android SpeechRecognizer transcribes the request using the selected language.
5. The command router handles explicitly allowlisted local actions; other requests go to the existing authenticated chat endpoint.
6. Android TextToSpeech speaks the result.
7. Listening resumes only after the response completes or a recoverable error is handled.

### WhatsApp notifications
1. User explicitly enables Android Notification Access.
2. The listener accepts notifications only from the standard WhatsApp package.
3. The processor deduplicates and batches exposed notification content.
4. The activity repository stores metadata only.
5. The announcement manager applies lock-screen privacy and interruption-filter rules before speech.
6. Typing state is not available through NotificationListenerService and is not claimed as implemented.

## Engineering rules
- No UI control may be decorative: each button must invoke a real action, display progress, and show success/failure.
- Ask for runtime and special permissions only when the related feature is enabled.
- Handle permission denial, missing providers, offline requests, expired tokens, missing wake-word assets and service startup failures.
- Keep all device actions allowlisted and confirmation-based for consequential actions.
- Do not silently place calls, send messages, read notification previews to cloud AI, or bypass Android security controls.
- Keep Android code and CI changes inside android/** and Android-specific workflow files.

## Definition of done
- Clean Gradle build and automated tests pass.
- Each visible control has a documented acceptance test.
- Login, token persistence, authenticated chat, voice lifecycle, TTS, language selection, local phone actions, notification access, event history and history clearing are tested.
- Device-specific behaviour is verified on the Redmi 13 5G / Android 16 before a release is called device-tested.
- A feature that depends on a third-party key/model or Android special access is clearly marked as requiring user setup.