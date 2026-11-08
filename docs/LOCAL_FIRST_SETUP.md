# Aleena Local-First / Free Mode

## Goal

Run Aleena's core PC, web and (after the mobile connection step) Android experience using local disk and local inference. The required path does not depend on Render PostgreSQL, a paid AI API, a hosted vector database or a paid subscription.

This is a local-first setup, not a promise that every optional internet feature works offline.

## What this branch changes

- Node API: explicit `DATABASE_MODE=sqlite` uses `data/aleena.sqlite` on the PC.
- Node chat: `AI_PROVIDER=ollama` calls the local Ollama server at `127.0.0.1:11434`.
- The Ollama path returns a clear local-service error and does not fall through to Gemini or Pollinations.
- The PC app's new-install defaults select Ollama and offline Windows TTS (pyttsx3).
- The existing PostgreSQL/Gemini cloud path remains available when deliberately configured for production compatibility.
- Existing PC SQLite history and JSON task/reminder files are retained; this change does not move or delete them.

## Local storage layout

| Data | Local path / storage |
|---|---|
| Node users, chat sessions and chat messages | `data/aleena.sqlite` |
| PC assistant chat/core/episodic memory | `data/chat_history.db` |
| PC tasks and reminders | `data/tasks.json` |
| PC settings and encryption key | `data/settings.json`, `data/secret.key` |
| Generated media | `data/generated/`, `data/generated_images/` |
| Android tasks, reminders, app secrets and activity metadata | Android app-private storage (existing encrypted preferences / local stores) |

All these runtime files are ignored by Git. Keep a separate backup of the local `data` folder. Back up while Aleena is stopped, or use a database-aware backup command in a future release.

## Windows setup

1. Install a supported Node.js version (18.3 or newer) and Python 3.12.
2. Install Ollama from [ollama.com/download](https://ollama.com/download).
3. Open Command Prompt and check Ollama:
   ```cmd
   ollama --version
   ```
4. Pull the configured local model. The starter default is `deepseek-r1:8b`; change `OLLAMA_MODEL` in your private `.env` if your PC needs a smaller model.
   ```cmd
   ollama pull deepseek-r1:8b
   ```
5. In the repository root:
   ```cmd
   copy .env.example .env
   ```
6. Edit `.env`. Keep `DATABASE_MODE=sqlite`, `AI_PROVIDER=ollama`, and `DATABASE_URL=`. Set a private `JWT_SECRET` with at least 32 random characters. Do not commit `.env`.
   Generate a secret with Python:
   ```cmd
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
7. Install packages:
   ```cmd
   npm install
   cd web
   npm install
   cd ..
   python -m pip install -r requirements.txt
   ```
8. Initialize the local database:
   ```cmd
   npm run migrate
   ```
9. Start the existing local stack:
   ```cmd
   start_aleena.bat
   ```
10. Verify the local API:
   ```cmd
   curl http://127.0.0.1:8765/api/health
   ```
   Expected fields include `database: "connected"`, `database_mode: "sqlite"` and `ai_provider: "ollama"`.

## Costs and network boundaries

- SQLite storage is on the user's disk; there is no hosted database fee.
- Ollama inference runs on the PC; the configured local `/api/chat` call does not send prompts to a hosted model.
- Offline PC TTS uses Windows voices through pyttsx3. The existing PC speech-recognition implementation still uses Google's online recognizer; fully offline STT needs a separately installed local model and is not claimed in this first slice.
- Weather, news, internet research, online translation, social publishing and external media generation naturally require internet services. They are optional integrations, not prerequisites for local chat/storage.
- Local models use disk, RAM and CPU/GPU resources. Their quality and speed depend on the computer and the chosen model.
- This does not require a paid API key, subscription or cloud database.

## Android and web status

The PC and browser development stack can run locally on the PC. The Android app currently has local encrypted app data, but its chat base URL still defaults to the hosted Render API in the existing Android branch. A follow-up mobile change is required to let the user pair the phone with the PC's local LAN address. Do not change the Android base URL to a guessed IP address.

Until that pairing flow is implemented and tested, do not describe Android chat as local-only. Phone-to-PC sync will require the PC to be powered on and both devices on the same trusted home Wi-Fi network.

## Data safety

- Do not delete the existing Render database or old service as part of this change.
- Do not copy a cloud database credential into the local `.env`.
- Do not expose the Node API to public networks. The example binds to loopback (`127.0.0.1`); LAN pairing requires a separate authenticated setup and firewall review.
- The local SQLite file is not encrypted by sql.js. Protect it with the Windows account, disk encryption and separate backups. The Android secure preference store remains app-private.
- Never place `.env`, JWT secrets, model credentials or local database files in GitHub.

## Known limitations of this first implementation slice

- It creates a new local users/chat database. It does not recover chat records from the suspended Render PostgreSQL resource.
- It does not automatically import PC's older `chat_history.db` into Node's new `aleena.sqlite`.
- Android LAN pairing, offline speech recognition, local image generation and comprehensive offline search remain follow-up work.
- The local SQLite WebAssembly driver loads the database into the Node process and saves a file snapshot after each write. This is appropriate for a personal single-PC service and modest chat volume; it is not intended as a multi-server database.
