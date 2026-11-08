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
2. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/app/apikey). The example uses `gemini-3.6-flash`; confirm that this model is available in your AI Studio project. Never paste the key into GitHub or a public chat.
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
   GEMINI_MODEL=gemini-3.6-flash
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

## Android and web status

The PC and browser development stack can use the PC's local SQLite database. The Android app still uses its existing configured API base URL; secure phone-to-PC pairing over the local network is a separate unfinished step. Do not change the Android base URL to a guessed IP address or expose the PC API to public networks.

Until pairing is implemented and tested, Android chat must not be described as using the PC's SQLite database. The PC must be powered on for future phone-to-PC sync.

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
