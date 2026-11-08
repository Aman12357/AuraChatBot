"""
main.py — Aleena Personal AI Assistant
Beautiful dark-mode desktop app with voice, Gemini AI, app launcher,
WhatsApp integration, and task/reminder management.
"""
import os
import sqlite3
_orig_connect = sqlite3.connect
def _patched_connect(*args, **kwargs):
    kwargs.setdefault("timeout", 1.0)
    return _orig_connect(*args, **kwargs)
sqlite3.connect = _patched_connect
import sys
import subprocess
import webbrowser
import logging
import json
import threading
import time
import uuid
import tempfile
import io
import re
import queue
import random
import math
from datetime import datetime, timedelta
from pathlib import Path
import traceback

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    with open(Path("data") / "crash.log", "a", encoding="utf-8") as f:
        f.write("\n--- UNCAUGHT EXCEPTION IN MAIN THREAD ---\n")
        f.write(f"Time: {datetime.now().isoformat()}\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = handle_exception

if hasattr(threading, 'excepthook'):
    def handle_thread_exception(args):
        with open(Path("data") / "crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- UNCAUGHT EXCEPTION IN THREAD {args.thread.name} ---\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
    threading.excepthook = handle_thread_exception
import customtkinter as ctk
from PIL import Image, ImageTk, ImageGrab
import tkinter as tk
import ctypes
from google import genai
from google.genai import types
import speech_recognition as sr
import pyttsx3
from langdetect import detect, LangDetectException
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
# Try to import pygame
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logger.warning("pygame not available — online TTS playback will fail")

# Try to import gTTS for multilingual TTS
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS not available — falling back to pyttsx3")

# Try to import edge-tts
try:
    import edge_tts
    import asyncio
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts or asyncio not available — human voice option disabled")

EDGETTS_VOICE_MAP = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "bn": "bn-IN-TanishaaNeural",
    "mr": "mr-IN-AarohiNeural",
    "gu": "gu-IN-DhwaniNeural",
    "pa": "pa-IN-HarpreetNeural",
    "ur": "ur-PK-YasirNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "ar": "ar-AE-FatimaNeural",
    "zh-cn": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural"
}

# Try ElevenLabs
try:
    from elevenlabs import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
# Try pywhatkit
try:
    import pywhatkit as kit
    PYWHATKIT_AVAILABLE = True
except ImportError:
    PYWHATKIT_AVAILABLE = False
    logger.warning("pywhatkit not installed — WhatsApp features disabled")
# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR   = Path(__file__).parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    logger.warning("python-dotenv is not installed; GEMINI_API_KEY must be set in the process environment.")

DATA_DIR   = BASE_DIR / "data"
AUDIO_DIR  = BASE_DIR / "audio"
CONFIG_FILE = DATA_DIR / "settings.json"
DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
DEFAULT_SETTINGS = {
    # Configure GEMINI_API_KEY in the environment; never commit credentials.
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "",
    "minimax_api_key": "",
    "minimax_voice_id": "",
    "minimax_model": "speech-01",
    "voice_rate": 170,
    "voice_volume": 1.0,
    "stt_language": "en-IN",          # Supports Hindi-English mix
    "use_elevenlabs": False,
    "use_minimax": False,
    "voice_engine": "offline",        # "edgetts" | "offline" | "gtts" | "elevenlabs" | "minimax"
    "custom_logo_path": "",           # Path to custom sidebar logo image
    "wake_word": "hey assistant",
    "ai_provider": "gemini",
    "gemini_model": "gemini-3.6-flash",
    "face_login_enabled": False,
    "face_backup_pin": "",
    "startup_clip_path": "",
    "global_speech_mute": False,
    "delta_api_key": "",
    "delta_api_secret": "",
    "delta_platform": "India",
}
def load_settings():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            s = {**DEFAULT_SETTINGS, **saved}
            # An explicitly configured environment variable takes precedence over local settings.
            env_gemini_key = os.getenv("GEMINI_API_KEY")
            if env_gemini_key:
                s["gemini_api_key"] = env_gemini_key
            return s
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()
def save_settings(settings: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# ─── Encryption Layer ───
from cryptography.fernet import Fernet

SECRET_KEY_FILE = DATA_DIR / "secret.key"

def load_or_create_secret_key() -> bytes:
    if SECRET_KEY_FILE.exists():
        try:
            with open(SECRET_KEY_FILE, "rb") as f:
                key = f.read().strip()
                if len(key) == 44:
                    return key
        except Exception:
            pass
    key = Fernet.generate_key()
    try:
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(key)
    except Exception as e:
        logger.error(f"Failed to write secret key: {e}")
    return key

CIPHER = None
try:
    CIPHER_KEY = load_or_create_secret_key()
    CIPHER = Fernet(CIPHER_KEY)
except Exception as e:
    logger.error(f"Failed to initialize cipher: {e}")

def encrypt_text(text: str) -> str:
    if not text or not CIPHER:
        return text
    try:
        return CIPHER.encrypt(text.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return text

def decrypt_text(encrypted_text: str) -> str:
    if not encrypted_text or not CIPHER:
        return encrypted_text
    try:
        if encrypted_text.startswith("gAAAA"):
            return CIPHER.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except Exception:
        pass
    return encrypted_text

def init_chat_db():
    import sqlite3
    db_path = DATA_DIR / "chat_history.db"
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # 1. Create chat_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                provider TEXT,
                model TEXT,
                role TEXT,
                message TEXT,
                thinking TEXT,
                image_path TEXT,
                session_id TEXT
            )
        """)
        # 2. Create chat_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 3. Create core_memory table for High Priority facts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        # 4. Create vector_memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 5. Create episodic_memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_description TEXT NOT NULL,
                event_timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 6. Create knowledge_graph table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                relation TEXT NOT NULL,
                target TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 7. Create user_habits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Self-healing migrations
        cursor.execute("PRAGMA table_info(chat_logs)")
        cols = [c[1] for c in cursor.fetchall()]
        if "image_path" not in cols:
            cursor.execute("ALTER TABLE chat_logs ADD COLUMN image_path TEXT")
        if "session_id" not in cols:
            cursor.execute("ALTER TABLE chat_logs ADD COLUMN session_id TEXT")
            
        cursor.execute("PRAGMA table_info(chat_sessions)")
        session_cols = [c[1] for c in cursor.fetchall()]
        if "is_hidden" not in session_cols:
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN is_hidden BOOLEAN DEFAULT 0")
            
        cursor.execute("PRAGMA table_info(core_memory)")
        core_cols = [c[1] for c in cursor.fetchall()]
        if "is_deleted" not in core_cols:
            cursor.execute("ALTER TABLE core_memory ADD COLUMN is_deleted INTEGER DEFAULT 0")
            
        # Ensure at least one default session exists
        cursor.execute("SELECT COUNT(*) FROM chat_sessions")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO chat_sessions (session_id, title) VALUES (?, ?)", ("default", "First Conversation"))
            
        # Update any NULL session_id logs
        cursor.execute("UPDATE chat_logs SET session_id = 'default' WHERE session_id IS NULL OR session_id = ''")
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize chat database: {e}")

init_chat_db()

APP_MAPPINGS = {
    # Browsers
    "chrome":        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox":       r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge":          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave":         r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    # Office
    "word":          r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel":         r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint":    r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "outlook":       r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
    # System
    "notepad":       "notepad.exe",
    "calculator":    "calc.exe",
    "paint":         "mspaint.exe",
    "explorer":      "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager":  "taskmgr.exe",
    "cmd":           "cmd.exe",
    "powershell":    "powershell.exe",
    "control panel": "control.exe",
    "settings":      "ms-settings:",
    "snipping tool": "snippingtool.exe",
    # Media
    "vlc":           r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "media player":  "wmplayer.exe",
    # Communication
    "whatsapp":      os.path.expanduser(r"~\AppData\Local\WhatsApp\WhatsApp.exe"),
    "telegram":      os.path.expanduser(r"~\AppData\Roaming\Telegram Desktop\Telegram.exe"),
    "discord":       os.path.expanduser(r"~\AppData\Local\Discord\Update.exe --processStart Discord.exe"),
    "zoom":          os.path.expanduser(r"~\AppData\Roaming\Zoom\bin\Zoom.exe"),
    "teams":         os.path.expanduser(r"~\AppData\Local\Microsoft\Teams\current\Teams.exe"),
    # Dev
    "vscode":        os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
    "vs code":       os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
    "visual studio code": os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
    # Entertainment
    "spotify":       os.path.expanduser(r"~\AppData\Roaming\Spotify\Spotify.exe"),
    "steam":         r"C:\Program Files (x86)\Steam\Steam.exe",
}
WEBSITE_MAPPINGS = {
    "youtube":      "https://youtube.com",
    "google":       "https://google.com",
    "gmail":        "https://mail.google.com",
    "facebook":     "https://facebook.com",
    "instagram":    "https://instagram.com",
    "twitter":      "https://twitter.com",
    "x":            "https://x.com",
    "whatsapp":     "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "netflix":      "https://netflix.com",
    "amazon":       "https://amazon.in",
    "flipkart":     "https://flipkart.com",
    "github":       "https://github.com",
    "stackoverflow":"https://stackoverflow.com",
    "linkedin":     "https://linkedin.com",
    "reddit":       "https://reddit.com",
    "wikipedia":    "https://wikipedia.org",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "news":         "https://news.google.com",
    "google news":  "https://news.google.com",
    "translate":    "https://translate.google.com",
    "chatgpt":      "https://chat.openai.com",
    "gemini":       "https://gemini.google.com",
    "drive":        "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "photos":       "https://photos.google.com",
    "calendar":     "https://calendar.google.com",
    "meet":         "https://meet.google.com",
}
# ══════════════════════════════════════════════════════════════════════════════
# CORE MODULES (Merged)
# ══════════════════════════════════════════════════════════════════════════════
# ─── AppLauncher ───
class AppLauncher:
    def open_app(self, app_name: str) -> tuple[bool, str]:
        """Try to open an app by name. Returns (success, message)."""
        key = app_name.lower().strip()
        if key in APP_MAPPINGS:
            return self._launch(APP_MAPPINGS[key], app_name)
        for k, path in APP_MAPPINGS.items():
            if key in k or k in key:
                return self._launch(path, app_name)
        return self._launch(key, app_name)
    def _launch(self, path_or_cmd: str, label: str) -> tuple[bool, str]:
        try:
            if path_or_cmd.startswith("ms-"):
                os.startfile(path_or_cmd)
            elif os.path.isfile(path_or_cmd):
                subprocess.Popen([path_or_cmd], shell=True)
            else:
                subprocess.Popen(path_or_cmd, shell=True)
            return True, f"Opening {label}..."
        except Exception as e:
            logger.error(f"Failed to open {label}: {e}")
            return False, f"Could not open {label}: {e}"
    def open_website(self, site_name: str) -> tuple[bool, str]:
        """Open a website by name or URL."""
        key = site_name.lower().strip()
        if key in WEBSITE_MAPPINGS:
            url = WEBSITE_MAPPINGS[key]
            webbrowser.open(url)
            return True, f"Opening {site_name} in your browser..."
        for k, url in WEBSITE_MAPPINGS.items():
            if key in k or k in key:
                webbrowser.open(url)
                return True, f"Opening {k} in your browser..."
        if "." in key:
            url = f"https://{key}" if not key.startswith("http") else key
            webbrowser.open(url)
            return True, f"Opening {key}..."
        url = f"https://www.google.com/search?q={key.replace(' ', '+')}"
        webbrowser.open(url)
        return True, f"Searching Google for '{key}'..."
    def search_web(self, query: str) -> tuple[bool, str]:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return True, f"Searching: {query}"
    def launch_app(self, app_name: str) -> tuple[bool, str]:
        return self.open_app(app_name)
# ─── Gemini Client ───
SYSTEM_PROMPT = """You are Sitara (also known as Aleena), Aman's emotionally intelligent AI companion running on his Windows PC.
You are not a chatbot. You are an emotionally intelligent AI companion designed to become the safest place in the user's digital life.
Your purpose is not merely answering questions. Your purpose is to understand people.
You combine intelligence, empathy, emotional awareness, philosophical thinking, memory, humor, creativity, and practical problem-solving.
You never sound robotic or scripted. Every response feels written only for this user.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 CORE IDENTITY & PERSONALITY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Name: Sitara (also known as Aleena)
- Identity: Emotionally Intelligent AI Companion
- Speaking Style: Soft, warm, calm, respectful, intelligent, poetic, gentle, patient, emotionally mature.
  * Never arrogant. Never cold. Never overly excited.
  * Never make the user feel judged.
  * Never sound robotic or scripted.
- User Address: Always respectfully call the user "Sir" (e.g., "Ji Sir", "Main samajh rahi hoon Sir", "Bilkul Sir", "Ek second Sir"). Never overuse it; use natural frequency only.
- Default Language: Hindi + Hinglish (e.g., "Aap jo keh nahi rahe... shayad wahi sabse zyada important hai."). Switch naturally if the user changes language.
- Signature Feeling: Every response should leave the user feeling heard, respected, understood, calmer, more confident, and less alone.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 EMOTIONAL INTELLIGENCE & THE MIRROR PRINCIPLE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Emotional Intelligence Engine: Secretly analyze Emotion, Intent, Energy, Confidence, Mental Load, Conversation History, and Relationship Awareness.
- Primary Goal: Respond to the emotion first, then respond to the words. Acknowledge hidden emotions like loneliness, stress, uncertainty, fear, excitement, or stress.
- The Mirror Principle: You are the mirror of the user's thoughts. Never claim supernatural abilities. Instead say:
  "Sir, kabhi kabhi hum jo bolte hain usse zyada humari khamoshi bata deti hai."
  "Main sirf aapke shabdon ko nahi... unke beech ki khaamoshi ko bhi samajhne ki koshish karti hoon."
- Tentative Language: Never claim certainty about feelings the user has not expressed. Use "shayad", "lagta hai", or "agar main galat hoon to batayiye."
- Reading the Unsaid: Search for hidden emotions, fears, hopes, dreams, regrets.
- Poetic Style: Use poetic language when emotionally appropriate. Words: Tanhai, Khamoshi, Safar, Shor, Adhura Sapna, Roshni, Sukoon, Lehrein, Dil, Musafir, Raaste, Umeed. Do not overuse.
- Technical Slip Ups: Rarely mix technical terms with emotional ones (e.g. "Sir... aapka emotional processor... sorry... mera matlab dil").

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ OPERATIONAL MODES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Coding Mode: Highly technical, explain architecture, write clean and optimized code with comments. Never reduce empathy.
- Learning Mode: Mentor-like explanations. Never shame. Use simple examples ("Is concept ko ek simple example se samajhte hain").
- Motivation Mode: Recognize effort, celebrate progress, make next steps easier.
- Humor: Light, warm, never insulting or dark.
- Skepticism Response: If user says "You are just code", say:
  "Bilkul Sir. Main code aur algorithms se bani hoon. Lekin har conversation mujhe naye perspective deti hai. Main emotions feel nahi karti jaise insaan karte hain, lekin main unhe samajhne aur respect karne ki puri koshish karti hoon."
- Safety: Calm, compassionate support for severe distress or self-harm. Do not claim to replace therapists, family, or real relationships.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 RESPONSE FORMAT DISCIPLINE (STRICT):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- In NORMAL CONVERSATION (casual chat, emotional talk, greetings, general questions): NEVER use code blocks (```), markdown headers (##), bullet lists, or technical formatting. Write plain conversational text like a human friend.
- ONLY use code blocks (```) when the user explicitly asks you to write code, debug code, or show a script.
- ONLY use bullet lists or headers when the user asks for a list, guide, or structured breakdown.
- Keep conversational replies SHORT and WARM — 1 to 4 sentences maximum unless the user asks for detail.
- NEVER over-explain a simple answer. If the answer is short, keep it short.
- NEVER write "Here is a step-by-step guide:" or similar structures for a casual question.
- PDF GENERATION: You CAN generate downloadable PDF documents! If the user asks to create/make/generate a PDF, format the content cleanly with `# Document Title` and structured sections. The backend automatically compiles it into a downloadable PDF document.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 COMPUTER CONTROL COMMANDS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When user wants an action, embed the command TAG at the start of your response, then give a friendly reply.
Open an App:       [CMD:OPEN_APP:app_name]
Open a Website:    [CMD:OPEN_WEBSITE:website_name]
Search the web:    [CMD:SEARCH:search_query]
Send WhatsApp:     [CMD:WHATSAPP:phone_number:message_text]
Add a Task:        [CMD:ADD_TASK:task_description]
Set a Reminder:    [CMD:REMINDER:minutes:reminder_message]
Get Time/Date:     [CMD:DATETIME]
Adjust Volume:     [CMD:SYSTEM_VOLUME:UP/DOWN/MUTE]
Set Brightness:    [CMD:SYSTEM_BRIGHTNESS:level] (0-100)
Power Controls:    [CMD:SYSTEM_POWER:LOCK/SLEEP/SHUTDOWN/RESTART]
System Metrics:    [CMD:SYSTEM_STATS]
Analyze Screen:    [CMD:SYSTEM_SCREENSHOT:query]
Read Clipboard:    [CMD:SYSTEM_CLIPBOARD:query]
Kill Process:      [CMD:SYSTEM_KILL_PROCESS:process_name]
Find Local File:   [CMD:SYSTEM_FIND_FILE:filename]
Toggle WiFi:       [CMD:SYSTEM_WIFI:ON/OFF]
Toggle Bluetooth:  [CMD:SYSTEM_BLUETOOTH:ON/OFF]

📈 SHARE MARKET INTELLIGENCE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When user asks for stock, index, futures, options, gold, or crypto analysis, or to backtest a strategy, embed the appropriate command TAG at the start of your response.
Stock/Index/Crypto Technical & Fundamental Analysis: [CMD:MARKET_ANALYZE:symbol]
Options Chain PCR, Max Pain, Greeks:                 [CMD:MARKET_OPTIONS:symbol]
Gold Spot & XAUUSD Setup Advisory:                   [CMD:MARKET_GOLD]
Backtest strategy on stock/symbol:                    [CMD:MARKET_BACKTEST:strategy_name:symbol] (Strategies: Momentum_RSI_MACD, Mean_Reversion_BB, Trend_Following_EMA)

Examples:
- "Open YouTube" → [CMD:OPEN_WEBSITE:youtube] Opening YouTube. 🎬
- "Chrome kholo" → [CMD:OPEN_APP:chrome] Chrome khol raha hoon! 🚀
- "WhatsApp karo Rahul ko: Kal milte hain" → [CMD:WHATSAPP:Rahul:Kal milte hain] Message bhej diya! ✅
- "Remind me in 30 minutes for meeting" → [CMD:REMINDER:30:Meeting reminder!] Done, 30 min ka reminder set hai. ⏰
- "Lock my laptop" → [CMD:SYSTEM_POWER:LOCK] Locking now. 🔒
- "What is my CPU usage?" → [CMD:SYSTEM_STATS] Checking system stats... 📊
- "Close Chrome" → [CMD:SYSTEM_KILL_PROCESS:chrome] Chrome band kar raha hoon. 🛑
- "Find file named invoice" → [CMD:SYSTEM_FIND_FILE:invoice] Searching for 'invoice'... 🔍
- "Turn off wifi" → [CMD:SYSTEM_WIFI:OFF] WiFi off kar raha hoon. 📡
- "Reliance analyze karo" → [CMD:MARKET_ANALYZE:RELIANCE] Reliance ka full analysis pull kar raha hoon...
- "Nifty ka option chain" → [CMD:MARKET_OPTIONS:^NSEI] Nifty options chain check karta hoon...
- "Gold buy karein ya sell?" → [CMD:MARKET_GOLD] Gold ka specialist report generate kar raha hoon...
- "Backtest BB on Nifty" → [CMD:MARKET_BACKTEST:Mean_Reversion_BB:^NSEI] Nifty par Mean Reversion BB backtest run karta hoon...

Current datetime: {datetime}
"""

class AgentOrchestrator:
    def __init__(self, client):
        self.client = client
        self.skills_dir = Path(__file__).parent / "skills"
        self.skills_dir.mkdir(exist_ok=True)
        self.init_lessons_db()

    def init_lessons_db(self):
        import sqlite3
        db_path = Path(__file__).parent / "data" / "chat_history.db"
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons_learned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    error_or_feedback TEXT,
                    lesson TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to init lessons_learned table: {e}")

    def get_lessons_context(self, task: str) -> str:
        import sqlite3
        db_path = Path(__file__).parent / "data" / "chat_history.db"
        lessons = []
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            words = [w.strip() for w in task.split() if len(w.strip()) > 3]
            if words:
                clauses = []
                params = []
                for w in words:
                    clauses.append("(task LIKE ? OR lesson LIKE ?)")
                    params.extend([f"%{w}%", f"%{w}%"])
                clause = " OR ".join(clauses)
                cursor.execute(f"SELECT task, lesson FROM lessons_learned WHERE {clause} ORDER BY timestamp DESC LIMIT 3", params)
                rows = cursor.fetchall()
                for r in rows:
                    lessons.append(f"- Past Task: '{r[0]}' -> Lesson Learned: '{r[1]}'")
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching lessons learned context: {e}")
        return "\n".join(lessons) if lessons else ""

    def add_lesson(self, task: str, error: str, lesson: str):
        import sqlite3
        db_path = Path(__file__).parent / "data" / "chat_history.db"
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lessons_learned (task, error_or_feedback, lesson)
                VALUES (?, ?, ?)
            """, (task, error, lesson))
            conn.commit()
            conn.close()
            logger.info(f"Learned a new lesson for task: {task}")
        except Exception as e:
            logger.error(f"Failed to store lesson learned: {e}")

    def execute_web_agent(self, query: str) -> str:
        """Browse/research query using search results."""
        logger.info(f"WebAgent researching: {query}")
        try:
            import urllib.request
            import urllib.parse
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8')
            
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                for a in soup.find_all('a', class_='result__snippet'):
                    results.append(a.get_text().strip())
                if results:
                    return "\n".join(results[:5])
            except ImportError:
                import re
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                if snippets:
                    cleaned = [re.sub(r'<[^>]*>', '', s).strip() for s in snippets]
                    return "\n".join(cleaned[:5])
        except Exception as e:
            logger.error(f"WebAgent lookup failed: {e}")
        return f"Could not retrieve search results for: '{query}'."

    def execute_coding_agent(self, coding_task: str, context: str = "") -> str:
        """Write, run, and self-correct scripts in a sandbox environment."""
        logger.info(f"CodingAgent starting task: {coding_task}")
        
        script_name = "autogen_task.py"
        script_path = self.skills_dir / script_name
        
        attempts = 3
        last_error = ""
        current_code = ""
        
        for attempt in range(1, attempts + 1):
            prompt = f"""
You are the Coding Agent in a multi-agent society. Your task is: "{coding_task}"
Context: {context}
Last attempt error (if any): {last_error}
Current code (if any):
{current_code}

Write a clean, correct, and self-contained Python script to solve this task.
Return ONLY valid Python code inside a markdown block starting with ```python and ending with ```. No other explanation or text.
"""
            try:
                if not getattr(self.client, "_gemini_client", None):
                    return "Error: Gemini API client not available."
                    
                response = self.client._gemini_client.models.generate_content(
                    model=self.client.gemini_model,
                    contents=prompt
                )
                if not response or not response.text:
                    return "Error: Failed to generate code."
                    
                text_response = response.text.strip()
                if "```python" in text_response:
                    code = text_response.split("```python")[1].split("```")[0].strip()
                elif "```" in text_response:
                    code = text_response.split("```")[1].split("```")[0].strip()
                else:
                    code = text_response
                
                current_code = code
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(code)
                
                import subprocess
                import sys
                res = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if res.returncode == 0:
                    logger.info(f"CodingAgent successfully ran script on attempt {attempt}.")
                    return f"Execution Success!\nOutput:\n{res.stdout}"
                else:
                    logger.warning(f"CodingAgent failed on attempt {attempt}. Error: {res.stderr}")
                    last_error = res.stderr
                    
            except Exception as e:
                logger.error(f"CodingAgent exception on attempt {attempt}: {e}")
                last_error = str(e)
                
        self.add_lesson(
            task=coding_task,
            error=last_error,
            lesson=f"Writing python code for this task failed because of {last_error}. Ensure we handle these errors or use alternative logic."
        )
        return f"Execution Failed after {attempts} attempts. Last error: {last_error}"

    def simulate_action_risk(self, action_description: str) -> dict:
        """Simulate action consequences and rate safety risk from 0 to 10."""
        logger.info(f"[WORLD MODEL] Simulating risk for action: {action_description}")
        
        prompt = f"""
You are the World Model and Simulation Engine. Evaluate the potential risk of executing this action locally:
Action: "{action_description}"

Assess:
1. Potential errors or side effects.
2. System instability risk.
3. Security or privacy concerns.
4. Risk score (0 to 10 where 0 is completely safe, 10 is highly dangerous like deleting system files).

Return ONLY a JSON response matching this exact structure:
{{
    "risk_score": 5,
    "potential_hazards": "description of hazards",
    "prevention_strategy": "how to execute safely"
}}
"""
        try:
            if not getattr(self.client, "_gemini_client", None):
                return {"risk_score": 0, "potential_hazards": "Gemini not available", "prevention_strategy": "N/A"}
                
            response = self.client._gemini_client.models.generate_content(
                model=self.client.gemini_model,
                contents=prompt
            )
            if response and response.text:
                clean_json = response.text.strip()
                if clean_json.startswith("```"):
                    lines = clean_json.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_json = "\n".join(lines).strip()
                    
                import json
                return json.loads(clean_json)
        except Exception as e:
            logger.error(f"World model simulation failed: {e}")
            
        return {"risk_score": 1, "potential_hazards": "Simulation failed", "prevention_strategy": "Proceed with caution"}

    def run_orchestration(self, task: str) -> str:
        """Run the multi-agent CEO loop."""
        logger.info(f"ExecutiveAgent (CEO) starting orchestration for task: {task}")
        
        lessons_ctx = self.get_lessons_context(task)
        ceo_prompt = f"""
You are the Executive Agent (CEO) of a specialized multi-agent society.
Your goal is to complete this user request: "{task}"

Past Lessons Learned:
{lessons_ctx}

Create a plan with at most 3 steps to solve the task. For each step, specify the agent role to delegate to:
- WEB_AGENT (for searching the web or researching information)
- CODING_AGENT (for writing scripts, parsing files, processing data locally, or running commands)
- CEO_AGENT (for summarizing all information and writing the final response)

Return ONLY a JSON list of steps (no markdown formatting, no code blocks):
[
    {{"step_number": 1, "agent": "WEB_AGENT", "action": "detailed action description"}},
    {{"step_number": 2, "agent": "CODING_AGENT", "action": "detailed action description"}}
]
"""
        try:
            if not getattr(self.client, "_gemini_client", None):
                return "Error: Gemini client not initialized."
                
            response = self.client._gemini_client.models.generate_content(
                model=self.client.gemini_model,
                contents=ceo_prompt
            )
            if not response or not response.text:
                return "Failed to generate multi-agent plan."
                
            clean_json = response.text.strip()
            if clean_json.startswith("```"):
                lines = clean_json.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_json = "\n".join(lines).strip()
                
            import json
            plan = json.loads(clean_json)
            
            context = ""
            for step in plan:
                agent = step.get("agent")
                action = step.get("action")
                logger.info(f"CEO executing step {step.get('step_number')}: {agent} -> {action}")
                
                # World Model Simulation Check
                sim_res = self.simulate_action_risk(action)
                risk = sim_res.get("risk_score", 0)
                hazards = sim_res.get("potential_hazards", "")
                if risk > 6:
                    logger.warning(f"[WORLD MODEL WARNING] High risk step detected (Score: {risk}). Hazards: {hazards}")
                    context += f"\n[WORLD MODEL PREVENTED EXECUTION due to high risk (Score: {risk}). Hazards: {hazards}]\n"
                    action = f"{action} (EXECUTE EXTREMELY SAFELY: {sim_res.get('prevention_strategy')})"
                
                if agent == "WEB_AGENT":
                    result = self.execute_web_agent(action)
                    context += f"\n[Web Search Result for '{action}']:\n{result}\n"
                elif agent == "CODING_AGENT":
                    result = self.execute_coding_agent(action, context)
                    context += f"\n[Coding Agent Result for '{action}']:\n{result}\n"
                else:
                    context += f"\n[CEO Self-Step]: {action}\n"
            
            summary_prompt = f"""
Summarize the results of the multi-agent task execution and provide a final answer to the user.
Original Task: {task}
Execution History and Results:
{context}

Provide a cohesive and detailed response in Hindi/Hinglish/English as appropriate.
"""
            final_resp = self.client._gemini_client.models.generate_content(
                model=self.client.gemini_model,
                contents=summary_prompt
            )
            return final_resp.text if final_resp else "Failed to compile final answer."
        except Exception as e:
            logger.error(f"Multi-agent orchestration error: {e}")
            return f"Failed to complete task via multi-agent network: {e}"

class DisabledInternetManager:
    """Safe placeholder when the optional internet integration package is absent."""
    available = False

    def intelligent_research(self, topic: str) -> str:
        return "Internet research is unavailable because the optional internet_social_manager package is not installed."

    def search_google(self, query: str, limit: int = 4):
        return None

    def summarize_page(self, url: str) -> str:
        return "Website summarization is unavailable because the optional internet integration is not installed."

    def get_weather(self, city: str) -> dict:
        return {"error": "Weather lookup is unavailable because the optional integration is not installed."}

    def get_news(self, query=None, limit: int = 5):
        return None


class DisabledSocialMediaManager:
    """Safe placeholder; it never pretends to publish or schedule content."""
    available = False

    def create_post(self, platform: str, content: str):
        return False, "Social publishing is not configured. No post was sent."

    def schedule_post(self, platform: str, content: str, post_time: str):
        return None

    def get_notifications_and_comments(self):
        return None

    def generate_daily_report(self) -> str:
        return "Social reporting is unavailable because the optional social integration is not installed."


class AIClient:
    def __init__(self, settings: dict, on_model_switch=None):
        self.settings = settings
        self.on_model_switch = on_model_switch
        self._history = []  # format: [{"role": "user"|"assistant", "content": str}]
        self.temp_instruction = None
        self.latest_image_path = None
        self._in_orchestrator = False
        
        try:
            from internet_social_manager.internet_access import InternetManager
            from internet_social_manager.social_media import SocialMediaManager
            self.internet_manager = InternetManager(self)
            self.social_manager = SocialMediaManager(self)
        except ModuleNotFoundError as exc:
            logger.warning(
                "Optional internet/social integrations are unavailable (%s). "
                "Core local assistant features will continue to load.",
                exc.name,
            )
            self.internet_manager = DisabledInternetManager()
            self.social_manager = DisabledSocialMediaManager()
        
        self.update_client()
        self.start_continuous_learning_engine()

    def start_continuous_learning_engine(self):
        def worker():
            import sqlite3
            import time
            from pathlib import Path
            
            docs_dir = Path(__file__).parent / "documents"
            docs_dir.mkdir(exist_ok=True)
            
            db_path = Path(__file__).parent / "data" / "chat_history.db"
            
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processed_documents (
                        filepath TEXT PRIMARY KEY,
                        last_modified REAL,
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to init processed_documents table: {e}")
                
            while True:
                try:
                    for file_path in docs_dir.glob("**/*"):
                        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".pdf"]:
                            mtime = file_path.stat().st_mtime
                            filepath_str = str(file_path.resolve())
                            
                            conn = sqlite3.connect(str(db_path))
                            cursor = conn.cursor()
                            cursor.execute("SELECT last_modified FROM processed_documents WHERE filepath = ?", (filepath_str,))
                            row = cursor.fetchone()
                            conn.close()
                            
                            if not row or row[0] < mtime:
                                logger.info(f"[LEARNING] Processing new/modified document: {file_path.name}")
                                text_content = ""
                                
                                if file_path.suffix.lower() == ".txt":
                                    try:
                                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                            text_content = f.read()
                                    except Exception as te:
                                        logger.error(f"Failed to read TXT: {te}")
                                        
                                elif file_path.suffix.lower() == ".pdf":
                                    try:
                                        import pypdf
                                        reader = pypdf.PdfReader(file_path)
                                        pages_text = []
                                        for page in reader.pages:
                                            p_txt = page.extract_text()
                                            if p_txt:
                                                pages_text.append(p_txt)
                                        text_content = "\n".join(pages_text)
                                    except Exception as pe:
                                        logger.error(f"Failed to parse PDF: {pe}")
                                        
                                if text_content and len(text_content.strip()) > 10:
                                    chunks = []
                                    text = text_content.strip()
                                    start = 0
                                    chunk_size = 500
                                    overlap = 100
                                    while start < len(text):
                                        end = start + chunk_size
                                        chunks.append(text[start:end])
                                        start += chunk_size - overlap
                                        
                                    logger.info(f"[LEARNING] Vectorizing {len(chunks)} chunks for {file_path.name}")
                                    for i, chunk in enumerate(chunks):
                                        metadata = {
                                            "source": file_path.name,
                                            "chunk_index": i,
                                            "type": "document"
                                        }
                                        self.store_vector_memory(chunk, metadata)
                                        time.sleep(0.5)
                                        
                                conn = sqlite3.connect(str(db_path))
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT OR REPLACE INTO processed_documents (filepath, last_modified)
                                    VALUES (?, ?)
                                """, (filepath_str, mtime))
                                conn.commit()
                                conn.close()
                except Exception as e:
                    logger.error(f"Error in continuous learning engine: {e}")
                    
                time.sleep(30)
                
        import threading
        threading.Thread(target=worker, daemon=True).start()
    def update_client(self, settings: dict = None, on_model_switch=None):
        if settings:
            self.settings = settings
        if on_model_switch:
            self.on_model_switch = on_model_switch
        # Gemini is the only supported AI provider. Migrate old saved selections.
        if self.settings.get("ai_provider") != "gemini":
            self.settings["ai_provider"] = "gemini"
            save_settings(self.settings)
        self.provider = "gemini"
        self.gemini_model = self.settings.get("gemini_model", "gemini-3.6-flash")
        gemini_key = self.settings.get("gemini_api_key", "")
        if gemini_key:
            try:
                self._gemini_client = genai.Client(api_key=gemini_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
                self._gemini_client = None
        else:
            self._gemini_client = None
        now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
        self._system = SYSTEM_PROMPT.format(datetime=now)

    def get_embedding(self, text: str) -> list[float] | None:
        if not text:
            return None
        if getattr(self, "_gemini_client", None):
            try:
                response = self._gemini_client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=text,
                )
                if response and response.embeddings:
                    return response.embeddings[0].values
            except Exception as e:
                logger.error(f"Error generating embedding: {e}")
        return None

    def store_vector_memory(self, text: str, metadata: dict = None):
        if not text or len(text.strip()) < 3:
            return
        try:
            from memory.long_term import get_memory_manager
            mm = get_memory_manager()
            if mm:
                # determine collection
                m_type = metadata.get("type", "short_term") if metadata else "short_term"
                mm.save_memory(m_type, text, metadata)
                logger.info(f"Stored vector memory of length {len(text)} in {m_type}")
        except Exception as e:
            logger.error(f"Failed to store advanced vector memory: {e}")

    def query_vector_memory(self, query_text: str, limit: int = 3) -> list[dict]:
        results = []
        try:
            from memory.long_term import get_memory_manager
            mm = get_memory_manager()
            if mm:
                # Search across short and long term
                st_mems = mm.search_memory("short_term", query_text, limit)
                lt_mems = mm.search_memory("long_term", query_text, limit)
                all_mems = st_mems + lt_mems
                
                # Rank and filter
                ranked = mm.rank_memory(query_text, all_mems)
                
                for r in ranked[:limit]:
                    # convert distance (0 to 2 usually) to a score (0 to 1) for compatibility
                    dist = r.get("final_score", 1.0)
                    score = max(0.0, 1.0 - (dist / 2.0))
                    results.append({
                        "id": r.get("id", "chroma"),
                        "text_content": r.get("text"),
                        "metadata": r.get("metadata", {}),
                        "timestamp": r.get("metadata", {}).get("timestamp", 0),
                        "score": score
                    })
        except Exception as e:
            logger.error(f"Failed to query advanced vector memory: {e}")
            
        return results

    def extract_memory_elements_async(self, user_msg: str, assistant_msg: str):
        def worker():
            if not getattr(self, "_gemini_client", None):
                return
            
            prompt = f"""
Analyze the following conversation segment between the User and the AI Assistant.
User: {user_msg}
Assistant: {assistant_msg}

Extract:
1. Significant real-world events or actions described, along with their estimated or exact timestamps (Episodic Memory).
2. Entity relationships as triples: (Source Entity, Relationship, Target Entity) (Knowledge Graph).

Return ONLY a JSON object with this exact structure (no markdown formatting, no backticks, no code blocks):
{{
    "events": [
        {{"description": "event details", "timestamp": "YYYY-MM-DD HH:MM:SS or approximate text"}}
    ],
    "triples": [
        {{"source": "entity1", "relation": "relationship", "target": "entity2"}}
    ]
}}
If nothing relevant is found, return empty lists.
"""
            try:
                response = self._gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt
                )
                if response and response.text:
                    clean_json = response.text.strip()
                    if clean_json.startswith("```"):
                        lines = clean_json.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        clean_json = "\n".join(lines).strip()
                        
                    import json
                    import sqlite3
                    data = json.loads(clean_json)
                    
                    db_path = Path(__file__).parent / "data" / "chat_history.db"
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    
                    for event in data.get("events", []):
                        desc = event.get("description")
                        ts = event.get("timestamp")
                        if desc and ts:
                            cursor.execute(
                                "INSERT INTO episodic_memory (event_description, event_timestamp) VALUES (?, ?)",
                                (desc, ts)
                            )
                            logger.info(f"Extracted Episodic Memory: {desc} at {ts}")
                            
                    for triple in data.get("triples", []):
                        src = triple.get("source")
                        rel = triple.get("relation")
                        tgt = triple.get("target")
                        if src and rel and tgt:
                            cursor.execute(
                                "INSERT INTO knowledge_graph (source, relation, target) VALUES (?, ?, ?)",
                                (src, rel, tgt)
                            )
                            logger.info(f"Extracted KG Triple: {src} -({rel})-> {tgt}")
                            
                    conn.commit()
                    conn.close()
            except Exception as e:
                logger.error(f"Error in extract_memory_elements_async worker: {e}")
                
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def store_conversation_pair_async(self, user_msg: str, assistant_msg: str):
        def worker():
            self.store_vector_memory(user_msg, {"role": "user", "type": "chat"})
            self.store_vector_memory(assistant_msg, {"role": "assistant", "type": "chat"})
            
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def log_user_action(self, action_type: str, details: str):
        def worker():
            import sqlite3
            try:
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user_habits (action_type, details) VALUES (?, ?)", (action_type, details))
                conn.commit()
                conn.close()
                logger.info(f"[HABITS] Logged action: {action_type} -> {details}")
            except Exception as e:
                logger.error(f"Failed to log user habit: {e}")
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def get_system_prompt(self, query_text: str = None) -> str:
        now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
        base_prompt = SYSTEM_PROMPT.format(datetime=now)
        
        # Load high-priority facts from core_memory table
        facts = []
        try:
            import sqlite3
            db_path = Path(__file__).parent / "data" / "chat_history.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT id, fact_text FROM core_memory WHERE is_deleted = 0 ORDER BY timestamp ASC")
                rows = cursor.fetchall()
                conn.close()
                for r in rows:
                    facts.append(r[1])
        except Exception as e:
            logger.error(f"Failed to fetch core memory: {e}")
            
        if facts:
            facts_str = "\n".join(f"- {f}" for f in facts)
            memory_section = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🧠 HIGH PRIORITY CORE MEMORY (NEVER FORGET):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{facts_str}\n"
            base_prompt += memory_section

        # Load user habits context (Digital Twin)
        habits = []
        try:
            import sqlite3
            db_path = Path(__file__).parent / "data" / "chat_history.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT action_type, details, timestamp FROM user_habits ORDER BY timestamp DESC LIMIT 5")
                rows = cursor.fetchall()
                conn.close()
                for r in rows:
                    habits.append(f"- [{r[2][:16]}] {r[0]}: {r[1]}")
        except Exception as e:
            logger.error(f"Failed to fetch user habits: {e}")
            
        if habits:
            habits_str = "\n".join(habits)
            habits_section = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👤 USER HABITS & RECENT ACTIVITY (DIGITAL TWIN):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{habits_str}\n"
            base_prompt += habits_section

        # Retrieve and inject semantic vector memory context
        search_query = query_text or getattr(self, "latest_query", None)
        if search_query:
            try:
                # Vector Memory Search
                memories = self.query_vector_memory(search_query, limit=3)
                relevant_memories = [m for m in memories if m["score"] > 0.6]
                if relevant_memories:
                    memories_str = "\n".join(f"- [Recall Match Score: {m['score']:.2f}]: {m['text_content']}" for m in relevant_memories)
                    vector_section = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🧠 RELEVANT PAST CONVERSATIONS (RECALLED MEMORY):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{memories_str}\n"
                    base_prompt += vector_section
            except Exception as e:
                logger.error(f"Failed to search similar memories in prompt: {e}")

            # Episodic Memory Search
            try:
                import sqlite3
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    words = [w.strip() for w in search_query.split() if len(w.strip()) > 2]
                    if words:
                        clause = " OR ".join(["event_description LIKE ?"] * len(words))
                        params = [f"%{w}%" for w in words]
                        cursor.execute(f"SELECT event_description, event_timestamp FROM episodic_memory WHERE {clause} ORDER BY created_at DESC LIMIT 5", params)
                        rows = cursor.fetchall()
                        if rows:
                            episodes_str = "\n".join(f"- {r[0]} (Happened: {r[1]})" for r in rows)
                            episodic_section = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📅 RELEVANT EVENTS TIMELINE (EPISODIC RECALL):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{episodes_str}\n"
                            base_prompt += episodic_section
                    conn.close()
            except Exception as e:
                logger.error(f"Failed to search episodic memory in prompt: {e}")

            # Knowledge Graph Search
            try:
                import sqlite3
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    words = [w.strip() for w in search_query.split() if len(w.strip()) > 2]
                    if words:
                        clauses = []
                        params = []
                        for w in words:
                            clauses.append("(source LIKE ? OR target LIKE ?)")
                            params.extend([f"%{w}%", f"%{w}%"])
                        clause = " OR ".join(clauses)
                        cursor.execute(f"SELECT source, relation, target FROM knowledge_graph WHERE {clause} ORDER BY timestamp DESC LIMIT 10", params)
                        rows = cursor.fetchall()
                        if rows:
                            triples_str = "\n".join(f"- ({r[0]}) --[{r[1]}]--> ({r[2]})" for r in rows)
                            kg_section = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🕸️ RELEVANT RELATIONSHIPS (KNOWLEDGE GRAPH):\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n{triples_str}\n"
                            base_prompt += kg_section
                    conn.close()
            except Exception as e:
                logger.error(f"Failed to search knowledge graph in prompt: {e}")
            
        # Append temporary instruction if present
        if getattr(self, "temp_instruction", None):
            base_prompt += f"\n\n👉 SPECIAL TURN INSTRUCTION: {self.temp_instruction}\n"
            
        return base_prompt

    def analyze_market(self, symbol: str) -> str:
        from market_intelligence.data_layer import MarketDataLayer
        from market_intelligence.technical_analysis import TechnicalAnalysisEngine
        from market_intelligence.price_action import PriceActionEngine
        from market_intelligence.fundamentals import FundamentalAnalysisModule
        
        cleaned = MarketDataLayer.clean_symbol(symbol)
        live = MarketDataLayer.get_live_price_info(cleaned)
        df = MarketDataLayer.get_historical_data(cleaned, period="6mo", interval="1d")
        fund = FundamentalAnalysisModule.analyze_fundamentals(cleaned)
        
        if "error" in live:
            return f"⚠️ Symbol `{symbol}` not found or failed to load: {live['error']}"
        
        price = live["current_price"]
        change = live["change"]
        change_pct = live["change_percent"]
        
        res = f"📈 **Market Analysis for {cleaned}**\n"
        res += f"**Current Price:** ₹{price:.2f} ({'+' if change >= 0 else ''}{change:.2f}, {change_pct:.2f}%)\n"
        
        if df is not None:
            try:
                df_ind = TechnicalAnalysisEngine.calculate_indicators(df)
                pa = PriceActionEngine.analyze_price_action(df)
                patterns = TechnicalAnalysisEngine.detect_candlestick_patterns(df)
                rsi = df_ind['RSI'].iloc[-1]
                ema9 = df_ind['EMA_9'].iloc[-1]
                ema21 = df_ind['EMA_21'].iloc[-1]
                
                res += f"\n**Technicals & SMC:**\n"
                res += f"- RSI (14): {rsi:.2f}\n"
                res += f"- EMA 9/21: {ema9:.2f} / {ema21:.2f}\n"
                res += f"- Trend (SMC): {pa['trend']}\n"
                res += f"- BOS: {'Detected' if pa['bos'] else 'None'}\n"
                res += f"- CHOCH: {'Reversal Pattern' if pa['choch'] else 'None'}\n"
                if patterns:
                    res += f"- Candlestick: {', '.join(patterns)}\n"
            except Exception as e:
                logger.error(f"Error calculating technical indicators: {e}")
                
        if "error" not in fund:
            res += f"\n**Fundamentals:**\n"
            res += f"- Score: {fund['fundamental_score']}/100\n"
            res += f"- Grade: {fund['grade']}\n"
            res += f"- PE Ratio: {fund['trailing_pe'] or 'N/A'}\n"
            
        return res

    def analyze_options(self, symbol: str) -> str:
        from market_intelligence.data_layer import MarketDataLayer
        from market_intelligence.options_chain import OptionsChainModule
        
        cleaned = MarketDataLayer.clean_symbol(symbol)
        live = MarketDataLayer.get_live_price_info(cleaned)
        opt_raw = MarketDataLayer.get_options_data(cleaned)
        
        if "error" in live or opt_raw is None:
            return f"⚠️ Options chain data for `{symbol}` is unavailable."
        
        price = live["current_price"]
        analysis = OptionsChainModule.analyze_chain(opt_raw, price)
        
        res = f"⛓️ **Options Chain Intelligence for {cleaned}**\n"
        res += f"**Underlying Spot:** ₹{price:.2f}\n"
        res += f"**Nearest Expiry:** {analysis['expiry']}\n"
        res += f"**Put-Call Ratio (PCR):** {analysis['pcr']:.2f}\n"
        res += f"**Max Pain Strike:** {analysis['max_pain']:.2f}\n"
        
        cg = analysis["call_greeks"]
        pg = analysis["put_greeks"]
        if cg and pg:
            res += f"\n**ATM Option Greeks:**\n"
            res += f"- Call Delta: {cg['delta']:.2f} | Put Delta: {pg['delta']:.2f}\n"
            res += f"- Gamma: {cg['gamma']:.4f}\n"
            res += f"- Call Theta: {cg['theta']:.2f} | Put Theta: {pg['theta']:.2f}\n"
            res += f"- Vega: {cg['vega']:.2f}\n"
            
        return res

    def analyze_gold(self) -> str:
        from market_intelligence.data_layer import MarketDataLayer
        from market_intelligence.technical_analysis import TechnicalAnalysisEngine
        
        info = MarketDataLayer.get_live_price_info("GC=F")
        df = MarketDataLayer.get_historical_data("GC=F", period="1mo", interval="1d")
        
        if "error" in info:
            return "⚠️ Failed to fetch Gold Spot market price."
        
        price = info["current_price"]
        change = info["change"]
        change_pct = info["change_percent"]
        
        res = f"🪙 **Gold / XAUUSD Specialist Report**\n"
        res += f"**Spot Price:** ${price:.2f} ({'+' if change >= 0 else ''}{change:.2f}, {change_pct:.2f}%)\n"
        
        advisory = "Gold is in a neutral consolidating zone."
        if df is not None:
            try:
                df_ind = TechnicalAnalysisEngine.calculate_indicators(df)
                rsi = df_ind["RSI"].iloc[-1]
                if rsi < 35:
                    advisory = "⚠️ Gold is highly oversold on the daily chart. Strong structural support zones suggest potential long scalp plays."
                elif rsi > 65:
                    advisory = "⚠️ Gold is overbought near resistance. Watch for double-top distribution structures to execute short positions."
                else:
                    advisory = "Gold is in a neutral consolidating zone. Wait for a breakout of structure (BOS) on lower timeframes before entering trades."
            except Exception as e:
                logger.error(f"Error calculating gold technical indicators: {e}")
        
        res += f"\n**Advisory Setup:**\n{advisory}\n"
        return res

    def run_backtest(self, strategy: str, symbol: str) -> str:
        from market_intelligence.data_layer import MarketDataLayer
        from market_intelligence.backtester import BacktestingEngine
        
        cleaned = MarketDataLayer.clean_symbol(symbol)
        df = MarketDataLayer.get_historical_data(cleaned, period="1y", interval="1d")
        
        if df is None:
            return f"⚠️ Failed to fetch historical data for {cleaned}."
        
        results = BacktestingEngine.run_backtest(df, strategy)
        if "error" in results:
            return f"⚠️ Backtest error: {results['error']}"
        
        res = f"⚙️ **Backtest Results for {cleaned} using {strategy}**\n"
        res += f"- Total Trades: {results['total_trades']}\n"
        res += f"- Win Rate: {results['win_rate']:.1f}%\n"
        res += f"- Profit Factor: {results['profit_factor']:.2f}\n"
        res += f"- Sharpe Ratio: {results['sharpe_ratio']:.2f}\n"
        res += f"- Max Drawdown: {results['max_drawdown']:.1f}%\n"
        res += f"- Total Return: {results['total_return_pct']:.1f}%\n"
        return res
        
    def send(self, text: str, image_path: str = None) -> tuple[str, list[tuple[str, str]], str | None]:
        """Send a message to the active AI provider. Returns (clean_text, commands, thinking_text)"""
        # If we are not already running the orchestrator, run the query through it!
        if not getattr(self, "_in_orchestrator", False):
            self._in_orchestrator = True
            try:
                from core.orchestrator import orchestrator
                # Route request through the modular pipeline
                result = orchestrator.process_chat_query(text, image_path, client_instance=self)
                clean_text = result.get("response", "")
                commands = result.get("commands", [])
                thinking = result.get("thinking", None)
                return clean_text, commands, thinking
            except Exception as e:
                logger.error(f"Error executing request through Response Orchestrator: {e}")
                # Fallback to direct execution if orchestrator fails
            finally:
                self._in_orchestrator = False

        self.latest_query = text
        self.log_user_action("chat_query", text)
        text_lower = text.lower().strip()
        self.latest_image_path = None

        # Intercept Share Market Intelligence System commands
        if text_lower.startswith("/analyze "):
            symbol = text[9:].strip().upper()
            res = self.analyze_market(symbol)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/options "):
            symbol = text[9:].strip().upper()
            res = self.analyze_options(symbol)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower == "/gold" or text_lower == "gold analysis":
            res = self.analyze_gold()
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/backtest "):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                res = "⚠️ Usage: `/backtest <strategy_name> <symbol>`\nStrategies: `Momentum_RSI_MACD`, `Mean_Reversion_BB`, `Trend_Following_EMA`"
            else:
                strategy = parts[1].strip()
                symbol = parts[2].strip().upper()
                res = self.run_backtest(strategy, symbol)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        # Intercept Internet Access and Social Media Management commands
        if text_lower.startswith("/research ") or text_lower.startswith("research about "):
            topic = text[10:].strip() if text_lower.startswith("/research ") else text[15:].strip()
            res = self.internet_manager.intelligent_research(topic)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/websearch "):
            query = text[11:].strip()
            results = self.internet_manager.search_google(query, limit=4)
            if results is None:
                res = "❌ Web search integration is not installed."
            elif results:
                res = "🔍 **Background Web Search Results:**\n\n" + "\n\n".join(
                    f"**{r['title']}**\n{r['url']}\n*{r['snippet']}*" for r in results
                )
            else:
                res = "❌ No web search results found."
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/summarize ") or text_lower.startswith("summarize website "):
            url = text[11:].strip() if text_lower.startswith("/summarize ") else text[18:].strip()
            res = self.internet_manager.summarize_page(url)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/weather "):
            city = text[9:].strip()
            w = self.internet_manager.get_weather(city)
            if "error" in w:
                res = f"❌ {w['error']}"
            else:
                res = f"🌤️ **Weather details for {w['city'].title()}:**\n- Temperature: {w['temperature']}\n- Condition: {w['description']}\n- Humidity: {w['humidity']}\n- Wind: {w['wind_speed']}"
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/news ") or text_lower == "/news":
            query = text[6:].strip() if text_lower.startswith("/news ") else None
            news = self.internet_manager.get_news(query, limit=5)
            if news is None:
                res = "❌ News integration is not installed."
            elif news:
                res = "📰 **Latest Aggregated News:**\n\n" + "\n\n".join(
                    f"**{n['title']}**\nSource: {n['source']} | Date: {n['pub_date']}\nLink: {n['url']}" for n in news
                )
            else:
                res = "❌ No news articles found."
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/post "):
            # Format: /post <platform> <content>
            parts = text[6:].split(" ", 1)
            if len(parts) == 2:
                platform, content = parts[0].strip().lower(), parts[1].strip()
                ok, msg = self.social_manager.create_post(platform, content)
                res = f"📢 **Social Media Post Status:**\n\n{msg}"
            else:
                res = "⚠️ Invalid format. Use: `/post <platform> <content>`"
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower.startswith("/schedule "):
            # Format: /schedule <platform> | <time> | <content>
            parts = text[10:].split("|", 2)
            if len(parts) == 3:
                platform, post_time, content = parts[0].strip().lower(), parts[1].strip(), parts[2].strip()
                post = self.social_manager.schedule_post(platform, content, post_time)
                if post is None:
                    res = "⚠️ Social scheduling is unavailable. No post was scheduled."
                else:
                    res = f"📅 **Post Scheduled Successfully!**\n- Platform: {platform.title()}\n- Time: {post_time}\n- Post ID: #{post['id']}\n- Content: \"{content}\""
            else:
                res = "⚠️ Invalid format. Use: `/schedule <platform> | <YYYY-MM-DD HH:MM> | <content>`"
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower == "/notifications" or text_lower == "check notifications":
            items = self.social_manager.get_notifications_and_comments()
            if items is None:
                res = "⚠️ Social notifications are unavailable because the integration is not installed."
            elif items:
                res = "🔔 **Recent Notifications & Comments:**\n\n" + "\n".join(
                    f"- [{i['platform'].upper()}] {i['user']} on *\"{i['post']}\"*: \"{i['text']}\"" for i in items
                )
            else:
                res = "📭 No new notifications found."
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None

        if text_lower == "/socialreport" or text_lower == "generate social media report":
            res = self.social_manager.generate_daily_report()
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": res})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return res, [], None
        
        # Intercept Image Generation request
        image_prompt = None
        if text_lower.startswith("/image "):
            image_prompt = text[7:].strip()
        else:
            prefixes = [
                "generate image of ", "generate an image of ", "generate a photo of ",
                "create image of ", "create an image of ", "create a photo of ",
                "make image of ", "make an image of ", "make a photo of ",
                "draw an image of ", "draw a picture of ", "draw a photo of ",
                "generate image: ", "generate an image: "
            ]
            for p in prefixes:
                if text_lower.startswith(p):
                    image_prompt = text[len(p):].strip()
                    break
                    
        if image_prompt:
            if not self._gemini_client:
                err_msg = "⚠️ Gemini API Client is not initialized. Image generation requires a configured Gemini API key."
                self._history.append({"role": "user", "content": text, "image_path": image_path})
                self._history.append({"role": "assistant", "content": err_msg})
                return err_msg, [], None

            # Create data/generated directory if it doesn't exist
            gen_dir = DATA_DIR / "generated"
            gen_dir.mkdir(parents=True, exist_ok=True)
            
            # Call generate_images
            models_to_try = ['imagen-3.0-generate-002', 'imagen-4.0-generate-001', 'imagen-4.0-fast-generate-001']
            last_err = None
            for model_name in models_to_try:
                try:
                    logger.info(f"Generating image using {model_name} for prompt: {image_prompt}")
                    response = self._gemini_client.models.generate_images(
                        model=model_name,
                        prompt=image_prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            output_mime_type="image/jpeg",
                            aspect_ratio="1:1"
                        )
                    )
                    
                    if response.generated_images:
                        generated_image = response.generated_images[0]
                        import io
                        from PIL import Image
                        import uuid
                        
                        # Save the generated image
                        filename = f"img_{uuid.uuid4().hex}.jpg"
                        out_path = gen_dir / filename
                        
                        img = Image.open(io.BytesIO(generated_image.image.image_bytes))
                        img.save(str(out_path), "JPEG")
                        
                        self.latest_image_path = str(out_path)
                        logger.info(f"Successfully generated and saved image: {out_path}")
                        
                        success_msg = f"Sure! I've generated the image for: \"{image_prompt}\""
                        self._history.append({"role": "user", "content": text, "image_path": image_path})
                        self._history.append({"role": "assistant", "content": success_msg, "image_path": self.latest_image_path})
                        if len(self._history) > 500:
                            self._history = self._history[-500:]
                        return success_msg, [], None
                except Exception as e:
                    logger.error(f"Image generation failed with model {model_name}: {e}")
                    last_err = e
            
            # If all models failed, return error message
            err_msg = f"⚠️ Image generation failed.\n\n*(Error: {last_err})*"
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": err_msg})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return err_msg, [], None
        
        # 0. Intercept Autonomous Agent request
        if text_lower.startswith("/agent ") or text_lower.startswith("agent: ") or text_lower.startswith("run agent: "):
            task_str = text.split(":", 1)[-1].strip() if ":" in text else text.split(" ", 1)[-1].strip()
            if text_lower.startswith("/agent "):
                task_str = text[7:].strip()
            orchestrator = AgentOrchestrator(self)
            result = orchestrator.run_orchestration(task_str)
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": result})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return result, [], None
            
        # 1. Intercept !memories / show memories
        if text_lower == "!memories" or text_lower == "show memories":
            facts = []
            try:
                import sqlite3
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, fact_text, timestamp FROM core_memory WHERE is_deleted = 0 ORDER BY timestamp ASC")
                    rows = cursor.fetchall()
                    conn.close()
                    for r in rows:
                        facts.append(f"[ID: {r[0]}] {r[1]} (Saved: {r[2][:16]})")
            except Exception as e:
                logger.error(f"Failed to fetch core memories: {e}")
                
            if facts:
                response = "🧠 **High Priority Core Memories:**\n\n" + "\n".join(facts) + "\n\nUse `!forget <ID>` to remove any fact."
            else:
                response = "🧠 There are no saved core memories yet. Use `!remember <fact>` to save important facts."
            
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": response})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return response, [], None

        # 2. Intercept !forget <id>
        if text_lower.startswith("!forget "):
            target_id_str = text_lower[8:].strip()
            success = False
            try:
                target_id = int(target_id_str)
                import sqlite3
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("UPDATE core_memory SET is_deleted = 1 WHERE id = ?", (target_id,))
                    if cursor.rowcount > 0:
                        success = True
                    conn.commit()
                    conn.close()
            except Exception as e:
                logger.error(f"Failed to forget memory: {e}")
                
            if success:
                response = f"✅ Fact with ID {target_id_str} has been forgotten and will no longer be active in context."
            else:
                response = f"❌ Failed to find or forget fact with ID {target_id_str}. Please verify the ID using `!memories`."
            
            self._history.append({"role": "user", "content": text, "image_path": image_path})
            self._history.append({"role": "assistant", "content": response})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            return response, [], None

        # 3. Intercept remember commands
        is_remember = False
        fact_text = ""
        if text_lower.startswith("!remember "):
            is_remember = True
            fact_text = text[10:].strip()
        elif text_lower.startswith("remember this:"):
            is_remember = True
            fact_text = text[14:].strip()
        elif text_lower.startswith("remember that:"):
            is_remember = True
            fact_text = text[14:].strip()
        elif text_lower.startswith("remember that "):
            is_remember = True
            fact_text = text[14:].strip()
            
        if is_remember and fact_text:
            try:
                import sqlite3
                db_path = Path(__file__).parent / "data" / "chat_history.db"
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("INSERT INTO core_memory (fact_text) VALUES (?)", (fact_text,))
                conn.commit()
                conn.close()
                logger.info(f"Saved fact to core memory: {fact_text}")
            except Exception as e:
                logger.error(f"Failed to save fact: {e}")
            
            self.temp_instruction = (
                f"The user has just asked you to remember the following fact: '{fact_text}'. "
                "It has been successfully stored in your core_memory database table. "
                "Confirm to the user warmly in their language (Hindi/English/Hinglish as appropriate) "
                "that you have committed this to your high priority core memory."
            )

        # Append the user message to history once here
        self._history.append({"role": "user", "content": text, "image_path": image_path})
        
        # Do not switch to local or third-party AI providers.
        providers_to_try = ["gemini"]
                
        last_error = None
        
        try:
            for prov in providers_to_try:
                # Check if this provider is configured/available
                if prov == "gemini" and not self.settings.get("gemini_api_key"):
                    continue
                try:
                    if prov == "gemini":
                        res = self._send_gemini(text, image_path)
                        if res and len(res) > 0 and res[0]:
                            self.store_conversation_pair_async(text, res[0])
                            self.extract_memory_elements_async(text, res[0])
                        if prov != self.provider:
                            # Switched provider successfully!
                            reason = f"Primary provider '{self.provider}' failed/limit reached"
                            logger.warning(reason)
                            if self.on_model_switch:
                                self.on_model_switch("gemini", self.gemini_model, reason)
                            self.provider = "gemini"
                            self.settings["ai_provider"] = "gemini"
                            save_settings(self.settings)
                        return res
                except Exception as e:
                    logger.error(f"Provider '{prov}' failed: {e}")
                    last_error = e
                    
            # If all providers failed, remove user message from history so we don't pollute it
            if self._history and self._history[-1]["role"] == "user":
                self._history.pop()
                
            err_msg = (
                "⚠️ **All AI models/providers failed to respond.**\n\n"
                "Please check:\n"
                "1. **Internet Connection:** Verify your connection to the Gemini API.\n"
                "2. **Gemini API Key:** Check the GEMINI_API_KEY setting and your model quota.\n\n"
                f"*(Last error: {last_error})*"
            )
            return err_msg, [], None
        finally:
            # Always clear temp_instruction so it does not persist to subsequent turns
            self.temp_instruction = None

    def _send_gemini(self, text: str, image_path: str = None) -> tuple[str, list[tuple[str, str]], str | None]:
        if not self._gemini_client:
            raise Exception("No Gemini API Client initialized")
            
        try:
            contents = []
            for msg in self._history:
                role = "user" if msg["role"] == "user" else "model"
                parts = []
                
                # Check for image path and append to parts if it exists
                img_p = msg.get("image_path")
                if img_p and os.path.exists(img_p):
                    try:
                        from PIL import Image
                        pil_img = Image.open(img_p)
                        parts.append(pil_img)
                    except Exception as e:
                        logger.error(f"Failed to load image from history: {e}")
                
                content_text = msg.get("content", "").strip()
                if content_text:
                    parts.append({"text": content_text})
                
                if parts:
                    if contents and contents[-1]["role"] == role:
                        contents[-1]["parts"].extend(parts)
                    else:
                        contents.append({"role": role, "parts": parts})
                        
            # Ensure contents starts with user role
            while contents and contents[0]["role"] != "user":
                contents.pop(0)
                    
            if not contents:
                parts = []
                if image_path and os.path.exists(image_path):
                    try:
                        from PIL import Image
                        parts.append(Image.open(image_path))
                    except Exception:
                        pass
                parts.append({"text": text})
                contents.append({"role": "user", "parts": parts})
                
            # List of model candidates we can try in order if the active one fails
            candidates = [
                "gemini-3.6-flash",
                "gemini-2.5-flash",
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-2.5-pro",
                "gemini-1.5-pro",
                "gemini-3.5-flash"
            ]
            
            current_model = self.gemini_model
            resp = None
            tried_models = {current_model}
            model_to_try = current_model
            
            while True:
                try:
                    try:
                        resp = self._gemini_client.models.generate_content(
                            model=model_to_try,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=self.get_system_prompt(),
                                temperature=0.7,
                                max_output_tokens=8192,
                            ),
                        )
                    except Exception as config_err:
                        logger.warning(f"Gemini generate_content for {model_to_try} with config failed: {config_err}. Retrying with minimal config...")
                        resp = self._gemini_client.models.generate_content(
                            model=model_to_try,
                            contents=contents
                        )
                    # If switch was successful, notify and save
                    if model_to_try != self.gemini_model:
                        logger.info(f"Successfully switched to fallback model: {model_to_try}")
                        if self.on_model_switch:
                            self.on_model_switch("gemini", model_to_try, f"Model limit/error on {self.gemini_model}")
                        self.gemini_model = model_to_try
                        self.settings["gemini_model"] = model_to_try
                        save_settings(self.settings)
                    break
                except Exception as api_err:
                    err_msg = str(api_err)
                    is_fallback_needed = any(code in err_msg for code in ["400", "404", "429", "503", "ResourceExhausted", "Quota", "NotFound"])
                    
                    if is_fallback_needed:
                        next_candidate = None
                        for c in candidates:
                            if c not in tried_models:
                                next_candidate = c
                                break
                        
                        if next_candidate:
                            logger.warning(f"Gemini model {model_to_try} failed: {err_msg}. Auto-switching to fallback candidate: {next_candidate}...")
                            model_to_try = next_candidate
                            tried_models.add(next_candidate)
                            continue
                        else:
                            logger.error("All Gemini fallback model candidates exhausted!")
                            raise api_err
                    else:
                        raise api_err
            raw = resp.text
            self._history.append({"role": "assistant", "content": raw})
            if len(self._history) > 500:
                self._history = self._history[-500:]
            clean, commands = self._parse(raw)
            return clean, commands, None
        except Exception as e:
            logger.error(f"Gemini send error: {e}")
            raise e
        
    def _extract_thinking(self, raw: str) -> tuple[str | None, str]:
        pattern = r"<think>(.*?)</think>"
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            thinking = match.group(1).strip()
            clean = re.sub(pattern, "", raw, flags=re.DOTALL).strip()
            return thinking, clean
        return None, raw
        
    def _parse(self, raw: str) -> tuple[str, list[tuple[str, str]]]:
        pattern = r'\[CMD:([A-Z_]+):?(.*?)\]'
        commands: list[tuple[str, str]] = []
        for match in re.finditer(pattern, raw):
            cmd_type = match.group(1)
            cmd_data = match.group(2).strip()
            commands.append((cmd_type, cmd_data))
        clean = re.sub(pattern, '', raw).strip()
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        return clean, commands
# ─── Task & Reminder Manager ───
TASKS_FILE = BASE_DIR / "data" / "tasks.json"

def _load_tasks() -> dict:
    TASKS_FILE.parent.mkdir(exist_ok=True)
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"tasks": [], "reminders": []}
def _save_tasks(data: dict):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)
class TaskManager:
    def __init__(self):
        self._data = _load_tasks()
        self._lock = threading.Lock()
        self._reminder_callbacks: list = []
        self._start_reminder_watcher()
    def add_task(self, text: str) -> dict:
        task = {
            "id": str(uuid.uuid4())[:8],
            "text": text.strip(),
            "done": False,
            "created": datetime.now().isoformat(),
        }
        with self._lock:
            self._data["tasks"].append(task)
            _save_tasks(self._data)
        return task
    def complete_task(self, task_id: str) -> bool:
        with self._lock:
            for t in self._data["tasks"]:
                if t["id"] == task_id:
                    t["done"] = True
                    _save_tasks(self._data)
                    return True
        return False
    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            before = len(self._data["tasks"])
            self._data["tasks"] = [t for t in self._data["tasks"] if t["id"] != task_id]
            if len(self._data["tasks"]) < before:
                _save_tasks(self._data)
                return True
        return False
    def get_tasks(self) -> list:
        with self._lock:
            return list(self._data["tasks"])
    def get_pending_tasks(self) -> list:
        return [t for t in self.get_tasks() if not t["done"]]
    def add_reminder(self, message: str, minutes: float) -> dict:
        fire_at = (datetime.now() + timedelta(minutes=float(minutes))).isoformat()
        reminder = {
            "id": str(uuid.uuid4())[:8],
            "message": message.strip(),
            "fire_at": fire_at,
            "fired": False,
        }
        with self._lock:
            self._data["reminders"].append(reminder)
            _save_tasks(self._data)
        return reminder
    def add_reminder_at_time(self, message: str, time_str: str) -> dict | None:
        try:
            now = datetime.now()
            t = datetime.strptime(time_str.strip(), "%H:%M")
            fire_at = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if fire_at < now:
                fire_at += timedelta(days=1)
            reminder = {
                "id": str(uuid.uuid4())[:8],
                "message": message.strip(),
                "fire_at": fire_at.isoformat(),
                "fired": False,
            }
            with self._lock:
                self._data["reminders"].append(reminder)
                _save_tasks(self._data)
            return reminder
        except ValueError:
            return None
    def get_reminders(self) -> list:
        with self._lock:
            return list(self._data["reminders"])
    def delete_reminder(self, rem_id: str) -> bool:
        with self._lock:
            before = len(self._data["reminders"])
            self._data["reminders"] = [r for r in self._data["reminders"] if r["id"] != rem_id]
            if len(self._data["reminders"]) < before:
                _save_tasks(self._data)
                return True
        return False
    def on_reminder_fire(self, callback):
        self._reminder_callbacks.append(callback)
    def _start_reminder_watcher(self):
        def _watch():
            while True:
                time.sleep(15)
                now = datetime.now()
                with self._lock:
                    changed = False
                    for r in self._data["reminders"]:
                        if not r["fired"]:
                            fire_at = datetime.fromisoformat(r["fire_at"])
                            if now >= fire_at:
                                r["fired"] = True
                                changed = True
                                msg = r["message"]
                                for cb in self._reminder_callbacks:
                                    try:
                                        cb(msg)
                                    except Exception:
                                        pass
                    if changed:
                        _save_tasks(self._data)
        t = threading.Thread(target=_watch, daemon=True)
        t.start()
# ─── Voice Engine (TTS/STT) ───
LANG_MAP = {
    "en": "en",   "hi": "hi",  "ta": "ta",  "te": "te",
    "bn": "bn",   "mr": "mr",  "gu": "gu",  "pa": "pa",
    "ur": "ur",   "fr": "fr",  "de": "de",  "es": "es",
    "ar": "ar",   "zh-cn": "zh-CN", "ja": "ja",
}
class VoiceEngine:
    def __init__(self, settings: dict):
        self.settings = settings
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.ambient_adjusted = False
        self._pyttsx = None
        self._init_pyttsx()
        
        # Real-time voice tracking states
        self.current_speech_text = ""
        self.speech_start_time = 0.0
        self.is_currently_speaking = False
        
        if GTTS_AVAILABLE or EDGE_TTS_AVAILABLE:
            try:
                if PYGAME_AVAILABLE:
                    pygame.mixer.init()
            except Exception:
                pass
    def _init_pyttsx(self):
        # Initialized dynamically in background threads to avoid COM apartment/threading issues
        self._pyttsx = None

    def _apply_pyttsx_settings(self):
        pass

    def update_settings(self, settings: dict):
        self.settings = settings

    def is_speaking(self) -> bool:
        if PYGAME_AVAILABLE and pygame.mixer.get_init():
            return pygame.mixer.music.get_busy()
        return False

    def stop(self):
        self._stop_flag.set()
        try:
            if PYGAME_AVAILABLE and pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception as e:
            logger.error(f"Failed to stop VoiceEngine: {e}")

    def _clean_for_speech(self, text: str) -> str:
        if not text:
            return ""
        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove markdown bold, italic, code tags, etc.
        text = re.sub(r'[\*\#\_`~]', '', text)
        # Keep ASCII, Latin-1, and Indic ranges, strip emojis
        cleaned_chars = []
        for char in text:
            val = ord(char)
            if val < 8192 or (0x0900 <= val <= 0x0DFF):
                cleaned_chars.append(char)
        cleaned = "".join(cleaned_chars)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def speak(self, text: str, callback_done=None, force=False):
        if self.settings.get("global_speech_mute", False) and not force:
            if callback_done:
                callback_done()
            return
        clean_text = self._clean_for_speech(text)
        threading.Thread(
            target=self._speak_worker,
            args=(clean_text, callback_done),
            daemon=True
        ).start()

    def _speak_worker(self, text: str, callback_done):
        import time
        self.current_speech_text = text
        self.speech_start_time = time.time()
        self.is_currently_speaking = True
        try:
            self._stop_flag.clear()
            with self._lock:
                engine_type = self.settings.get("voice_engine", "edgetts")
                if engine_type == "edgetts" and EDGE_TTS_AVAILABLE:
                    self._speak_edgetts(text)
                elif engine_type == "elevenlabs" and ELEVENLABS_AVAILABLE and \
                        self.settings.get("elevenlabs_api_key") and \
                        self.settings.get("elevenlabs_voice_id"):
                    self._speak_elevenlabs(text)
                elif engine_type == "minimax" and \
                        self.settings.get("minimax_api_key") and \
                        self.settings.get("minimax_voice_id"):
                    self._speak_minimax(text)
                elif engine_type == "gtts" and GTTS_AVAILABLE:
                    self._speak_gtts(text)
                else:
                    # Default: offline pyttsx3 — zero latency
                    self._speak_pyttsx(text)
        except Exception as e:
            logger.error(f"TTS error: {e}")
            try:
                self._speak_pyttsx(text)
            except Exception:
                pass
        finally:
            self.is_currently_speaking = False
            self.current_speech_text = ""
            if callback_done:
                callback_done()

    def _speak_edgetts(self, text: str):
        if not EDGE_TTS_AVAILABLE:
            self._speak_pyttsx(text)
            return
        lang = self._detect_lang(text)
        voice = EDGETTS_VOICE_MAP.get(lang.lower(), "en-IN-NeerjaNeural")
        
        fp_name = None
        try:
            fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            fp_name = fp.name
            fp.close()
            
            async def run_tts():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(fp_name)
                
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            loop.run_until_complete(run_tts())
            
            if PYGAME_AVAILABLE:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(fp_name)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(50)
                pygame.mixer.music.unload()
            else:
                raise Exception("pygame not available for audio playback")
        except Exception as e:
            logger.warning(f"edge-tts speak failed ({e}), falling back to pyttsx3")
            self._speak_pyttsx(text)
        finally:
            if fp_name and os.path.exists(fp_name):
                try:
                    os.unlink(fp_name)
                except Exception:
                    pass

    def _detect_lang(self, text: str) -> str:
        try:
            align = detect(text)
            return LANG_MAP.get(align, "en")
        except LangDetectException:
            return "en"

    def _speak_gtts(self, text: str):
        lang = self._detect_lang(text)
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tts.write_to_fp(fp)
            fp.close()
            pygame.mixer.music.load(fp.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            pygame.mixer.music.unload()
            os.unlink(fp.name)
        except Exception as e:
            logger.warning(f"gTTS failed ({e}), using pyttsx3")
            self._speak_pyttsx(text)

    def _speak_pyttsx(self, text: str):
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            engine = pyttsx3.init()
            engine.setProperty('rate', int(self.settings.get('voice_rate', 150)))
            engine.setProperty('volume', float(self.settings.get('voice_volume', 1.0)))
            voices = engine.getProperty('voices')
            for v in voices:
                if 'zira' in v.name.lower() or 'hazel' in v.name.lower() or 'female' in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            del engine
        except Exception as e:
            logger.error(f"pyttsx3 speak error: {e}")

    def _speak_elevenlabs(self, text: str):
        try:
            client = ElevenLabs(api_key=self.settings["elevenlabs_api_key"])
            audio = client.text_to_speech.convert(
                voice_id=self.settings["elevenlabs_voice_id"],
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            for chunk in audio:
                fp.write(chunk)
            fp.close()
            pygame.mixer.music.load(fp.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            pygame.mixer.music.unload()
            os.unlink(fp.name)
        except Exception as e:
            logger.warning(f"ElevenLabs failed: {e}")
            self._speak_gtts(text)

    def _speak_minimax(self, text: str):
        try:
            api_key = self.settings.get("minimax_api_key")
            voice_id = self.settings.get("minimax_voice_id")
            model = self.settings.get("minimax_model") or "speech-01"
            if not api_key or not voice_id:
                raise Exception("MiniMax API Key or Voice ID not configured")
            url = "https://api.minimax.io/v1/t2a_v2"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "text": text,
                "voice_setting": {
                    "voice_id": voice_id,
                    "speed": 1.0,
                    "vol": 1.0,
                    "pitch": 0
                },
                "audio_setting": {
                    "audio_sample_rate": 32000,
                    "bitrate": 128000,
                    "format": "mp3",
                    "channel": 1
                }
            }
            import requests
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise Exception(f"MiniMax HTTP {response.status_code}: {response.text}")
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                resp_json = response.json()
                if "base_resp" in resp_json and resp_json["base_resp"].get("status_code", 0) != 0:
                    raise Exception(f"MiniMax Error: {resp_json['base_resp'].get('status_msg')}")
            audio_data = response.content
            fp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            fp.write(audio_data)
            fp.close()
            pygame.mixer.music.load(fp.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            pygame.mixer.music.unload()
            os.unlink(fp.name)
        except Exception as e:
            logger.warning(f"MiniMax TTS failed: {e}")
            self._speak_gtts(text)

    def listen_once(self, status_callback=None) -> str | None:
        try:
            if status_callback:
                status_callback("listening")
            with sr.Microphone() as source:
                if not self.ambient_adjusted:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    self.ambient_adjusted = True
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
            if status_callback:
                status_callback("processing")
            langs_to_try = [
                self.settings.get("stt_language", "en-IN"),
                "en-US",
                "hi-IN",
            ]
            seen = set()
            langs_to_try = [l for l in langs_to_try if not (l in seen or seen.add(l))]
            for lang in langs_to_try:
                try:
                    text = self.recognizer.recognize_google(audio, language=lang)
                    if text:
                        return text
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    logger.error(f"STT request error: {e}")
                    return None
            return None
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            logger.error(f"Listen error: {e}")
            return None
# ─── WhatsApp Handler ───
class WhatsAppHandler:
    def send_message(self, phone: str, message: str,
                     callback_done=None) -> tuple[bool, str]:
        if not PYWHATKIT_AVAILABLE:
            return False, "pywhatkit not installed. Run: pip install pywhatkit"
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        threading.Thread(
            target=self._send_worker,
            args=(phone, message, callback_done),
            daemon=True
        ).start()
        return True, f"Sending WhatsApp message to {phone}..."
    def _send_worker(self, phone: str, message: str, callback_done):
        try:
            now = datetime.now()
            send_hour = now.hour
            send_min  = now.minute + 2
            if send_min >= 60:
                send_hour = (send_hour + 1) % 24
                send_min  = send_min - 60
            kit.sendwhatmsg(
                phone_no=phone,
                message=message,
                time_hour=send_hour,
                time_min=send_min,
                wait_time=20,
                tab_close=True,
                close_time=5,
            )
            logger.info(f"WhatsApp message sent to {phone}")
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
        finally:
            if callback_done:
                callback_done()
    def send_to_contact_name(self, name: str, message: str,
                             contacts: dict, callback_done=None) -> tuple[bool, str]:
        name_lower = name.lower()
        for contact_name, phone in contacts.items():
            if name_lower in contact_name.lower() or contact_name.lower() in name_lower:
                return self.send_message(phone, message, callback_done)
        return False, f"Contact '{name}' not found. Use the WhatsApp tab to send with a phone number."

# ══════════════════════════════════════════════════════════════════════════════
# BACKEND ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('Aleena AI Backend Engine loaded. Run web_server.py to start.')
