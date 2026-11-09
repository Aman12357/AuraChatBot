# Aleena: Gemini AI with Local PC Storage

## Goal

Use Google's Gemini API for AI responses while keeping Aleena's application database and personal PC data on the local computer. No hosted PostgreSQL, Neon database, Ollama installation, or paid database subscription is needed for the local PC setup.

This is not fully offline: Gemini requires an internet connection. Aleena sends the prompt and relevant recent conversation context to Google Gemini to generate a response. The local SQLite database remains on the PC.

## What this setup uses

- **AI provider:** Gemini only. The Node API and Python desktop assistant do not fall back to Ollama, Groq, Pollinations, or another AI provider.
- **Database:** SQLite in `data/aleena.sqlite` for web/Node users, sessions, and messages.
- **PC assistant memory:** SQLite at `data/chat_history.db`, plus local JSON settings/tasks/reminders.
- **Text-to-speech:** the default PC voice engine uses Windows voices through pyttsx3.
- **Internet boundary:** Gemini and existing online speech recognition, weather/news/research, and external integrations require an internet connection.

## Local storage layout

| Data | Local path / storage |
|---|---|
| Node users, chat sessions and chat messages | `data/aleena.sqlite` |
| PC assistant chat/core/episodic memory | `data/chat_history.db` |
| PC tasks and reminders | `data/tasks.json` |
| PC settings and encryption key | `data/settings.json`, `data/secret.key` |
| Generated media | `data/generated/`, `data/generated_images/` |
| Android app-private data | Android app-private storage; phone-to-PC chat sync is not yet implemented |

All these runtime files are ignored by Git. Keep a separate backup of the local `data` folder. Back up while Aleena is stopped, or use a database-aware backup command in a future release.

## Windows setup

1. Install Node.js 18.3 or newer and Python 3.12.
2. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/app/apikey). The example uses the stable `gemini-3.8-flash` model; confirm access in your AI Studio project. Never paste the key into GitHub or a public chat.
3. In the repository root, create `.env` only if it does not already exist:
   ```cmd
   if not exist .env copy .env.example .env
   ```
   If `.env` already exists, back it up and edit only the local-mode settings. Do not overwrite existing secrets or production configuration blindly.
4. Edit the private `.env` file and set:
   ```env
   NODE_ENV=development
   DATABASE_MODE=sqlite
   ALEENA_DATA_DIR=./data
   DATABASE_URL=
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_private_key
   GEMINI_MODEL=gemini-3.8-flash
   GEMINI_REASONING_MODEL=gemini-3.8-flash
   GEMINI_THINKING_LEVEL=low
   GEMINI_COMPLEX_THINKING_LEVEL=medium
   HOST=127.0.0.1
   ```
   Generate a private JWT secret with:
   ```cmd
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Put the generated value in `JWT_SECRET`. Keep your real `.env` file private.
5. Install packages:
   ```cmd
   npm install
   cd web
   npm install
   cd ..
   python -m pip install -r requirements.txt
   ```
6. Initialize the local SQLite database:
   ```cmd
   npm run migrate
   ```
7. Start the existing local stack:
   ```cmd
   start_aleena.bat
   ```
8. Verify the local API:
   ```cmd
   curl http://127.0.0.1:8765/api/health
   ```
   Expected values include `database: "connected"`, `database_mode: "sqlite"`, and `ai_provider: "gemini"`. `ai_provider_configured` should be `true` when the key is valid and loaded.

## Faster replies

All default web, Android and Node-backend requests use the stable `gemini-3.8-flash` model. Routine chat uses `thinking_level=low` for faster replies; substantial coding, debugging, architecture, proof or analysis tasks use `thinking_level=medium` for additional reasoning. Gemini 3.8 Flash does not support `minimal`, so old saved `minimal` settings are normalized to `low` at startup.

The Node API streams real Gemini output chunks to the web WebSocket and Android HTTPS/SSE client. The client can start showing text before the model finishes the full response. The API also uses the newest 12 messages for model context rather than loading the earliest messages from long conversations.

To check the model currently selected by the PC, run:
```cmd
curl http://127.0.0.1:8765/api/health
```
Read the `model`, `reasoning_model`, and `thinking_level` fields. Each chat response also reports the actual model used for that request. Previous Aleena defaults (`gemini-3.5-flash-lite` and `gemini-3.6-flash`) are automatically upgraded to `gemini-3.8-flash`; deliberately configured custom model IDs are preserved. The desktop assistant also upgrades its prior saved model defaults to 3.8.

## Costs, quotas and privacy

- SQLite storage runs on the PC's disk; it does not need a hosted database subscription.
- Gemini API has a free tier for eligible models, but access, quotas, and rate limits vary by model and account. It is not unlimited. Check the current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) and active [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- Do not enable paid billing unless you intentionally choose to. A free-tier model may stop responding after its quota is reached.
- Prompts and relevant recent chat context are sent to Google Gemini. The local database stores the saved conversation history on the PC; this does not mean the content sent for inference stays only on the PC.
- Google states that free-tier content may be used to improve its products; review the current policy before sending sensitive material.
- Weather, news, internet research, online speech recognition, social publishing and external media generation are optional internet features, not local database services.

## Existing PC settings

On startup, the desktop application now migrates any saved provider selection such as Ollama or Groq to Gemini. Existing chat history, tasks, reminders, generated files and encryption key are not deleted by this provider migration.

If the Gemini API key is missing or its quota is exhausted, AI responses will report the Gemini configuration/service issue. The assistant will not silently switch to another AI provider.

## Secure Android-to-PC pairing

The Android client can connect to the PC-local Node API over a second, optional HTTPS listener. The ordinary PC/browser API remains bound to loopback, and the Android listener is disabled unless you explicitly enable it.

1. Install the project Python requirements so the `cryptography` package is present.
2. From the repository root, run:
   ```cmd
   python scripts/generate_local_tls.py
   ```
   The script creates `data/local-server-cert.pem`, `data/local-server-key.pem`, and `data/local-pairing.key`; it prints the PC's discovered private LAN addresses, the certificate SHA-256 fingerprint, and a random local pairing key. These files are local secrets and are ignored by Git. The pairing key is reused on later script runs.
3. In the private root `.env`, keep `DATABASE_MODE=sqlite`, `DATABASE_URL=`, `AI_PROVIDER=gemini`, and configure `GEMINI_API_KEY`. Enable the mobile listener with:
   ```env
   LOCAL_LAN_ENABLED=true
   LOCAL_LAN_HOST=0.0.0.0
   LOCAL_LAN_PORT=8767
   LOCAL_TLS_CERT_FILE=./data/local-server-cert.pem
   LOCAL_TLS_KEY_FILE=./data/local-server-key.pem
   ```
   Keep the ordinary `HOST=127.0.0.1` so the web API is not unnecessarily exposed to the LAN.
4. Restart Aleena on the PC. Allow the Node process through Windows Defender Firewall only for your **Private** home network. Do not allow it on Public networks.
5. On Android, enter the exact PC address (for example `https://192.168.1.20:8767`), the 64-character SHA-256 fingerprint, and the random local pairing key printed by the PC script. Save the connection and run **Check PC connection**.
6. Sign in with the account created in the PC-local Aleena web application. The local PC database is the account authority for this setup.

The Android client trusts only the exact certificate fingerprint stored in encrypted Android preferences. HTTPS hostname validation is still enforced against the certificate's subject-alternative names. The Node API also requires the separate local pairing key in an `X-Aleena-Pairing-Key` header for every HTTPS LAN API request. If the PC certificate is regenerated, copy the new fingerprint to the phone again. The PC and phone must be on the same trusted Wi-Fi; this pairing is not an internet relay or remote-access service.

Android chat is sent over the LAN to the PC. The PC then sends the prompt and relevant recent conversation context to Gemini for inference. Chat history is stored on the PC's SQLite file, while phone settings, authentication token, tasks, reminders and explicit core memories remain in Android app-private storage. Gemini itself is not local: prompts leave the PC to reach Google's API.

## Data safety

- Do not delete the existing Render database or legacy service as part of this change.
- Keep `DATABASE_MODE=sqlite` and `DATABASE_URL=` in the private local `.env` file.
- Do not expose the Node API to public networks. The example binds to loopback (`127.0.0.1`); LAN pairing requires a separate authenticated setup and firewall review.
- The local SQLite file is not encrypted by sql.js. Protect it with the Windows account, disk encryption and separate backups. The Android secure preference store remains app-private.
- Never place `.env`, JWT secrets, Gemini credentials or local database files in GitHub.

## Known limitations

- The local SQLite WebAssembly driver loads the database into the Node process and saves a file snapshot after each write. This is appropriate for a personal single-PC service and modest chat volume, not a multi-server database.
- This creates a local Node database. It does not recover chat records from the suspended Render PostgreSQL resource or automatically import older PC history into `aleena.sqlite`.
- Android LAN pairing, fully offline speech recognition, local image generation and offline web research are not included in this change.
- The current PC speech-recognition implementation still uses Google's online recognizer. Offline Windows TTS does not make speech recognition offline.
