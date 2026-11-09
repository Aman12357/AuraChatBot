# 👑 Aleena AI Master Companion — Full Package

Aleena AI is a Next.js + FastAPI powered AI Digital Human Companion featuring real-time chat, memory management, voice synthesis, task orchestration, and Master Aura User Oversight.

---

## ⚡ Quick Start Setup

### Step 1: Install Python Backend Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install Node.js Frontend Dependencies
```bash
cd web
npm install
cd ..
```

### Step 3: Launch Aleena AI
Double click `start_aleena.bat` OR run manually:
```bash
# Terminal 1 (Backend):
python web_server.py

# Terminal 2 (Frontend):
cd web
npm run dev
```

### Step 4: Open in Browser
👉 **http://localhost:3000**

The integrated hologram interface is available from the **Hologram** tab in the main dashboard, or directly at **http://localhost:3000/aleena-companion.html**. It uses the same PC-local Gemini 3.8 API and reuses the signed-in Aleena account session.

---

## ✨ Features Included:
- 👑 **Master Aura Oversight**: View all Aura AI users, signup dates, and inspect chat history inside Settings.
- 💬 **Next.js Web Frontend**: Built with Next.js 14, Tailwind CSS, TypeScript, and Lucide icons.
- 🎙️ **Voice Synthesis & STT Engine**: Real-time speech recognition & Edge-TTS voice generation.
- 🧠 **Memory Engine**: Long-term SQLite memory management & context tracking.
- ⚡ **FastAPI Bridge Server**: High speed WebSocket streaming & REST endpoints.
