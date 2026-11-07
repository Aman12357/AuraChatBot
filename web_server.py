"""
web_server.py — FastAPI WebSocket Bridge Server
Bridges a Next.js web frontend with the existing Python AI backend (main.py).
Run:  python web_server.py   (starts on LOCAL_BRIDGE_PORT, default 8766)
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import uuid
from datetime import datetime
import jwt
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ─── Import from the existing AI backend ────────────────────────────────────
# main.py lives in the same directory
sys.path.insert(0, str(Path(__file__).parent))
from main import AIClient, VoiceEngine, TaskManager, load_settings, save_settings, DATA_DIR

try:
    import aura_module
    _AURA_IMPORT_ERROR = None
except ImportError as exc:
    aura_module = None
    _AURA_IMPORT_ERROR = str(exc)

try:
    from utils.pdf_generator import create_pdf_document
    _PDF_IMPORT_ERROR = None
except ImportError as exc:
    create_pdf_document = None
    _PDF_IMPORT_ERROR = str(exc)

JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
MASTER_EMAIL = os.getenv("MASTER_EMAIL", "").strip().lower()

def _decode_bearer_token(authorization: str | None) -> dict:
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(authorization[7:].strip(), JWT_SECRET, algorithms=["HS256"], audience=["aleena-node", "aura-python"])
        if not payload.get("userId") or not payload.get("email"):
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

def _require_master(authorization: str | None) -> dict:
    if not MASTER_EMAIL:
        raise HTTPException(status_code=503, detail="MASTER_EMAIL is not configured.")
    user = _decode_bearer_token(authorization)
    if (
        str(user.get("email", "")).strip().lower() != MASTER_EMAIL
        or user.get("role") != "master"
    ):
        raise HTTPException(status_code=403, detail="Master administrator access required.")
    return user

def _require_aura_module() -> None:
    if aura_module is None:
        logger.error("Aura-specific module is unavailable: %s", _AURA_IMPORT_ERROR)
        raise HTTPException(
            status_code=503,
            detail="Aura account and oversight features are unavailable because their optional module is missing.",
        )


def _create_aura_token(email: str, user_data: Any) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    user_id = email
    if isinstance(user_data, dict):
        user_id = user_data.get("id") or user_data.get("user_id") or email
    # Python-issued Aura tokens are user-scoped; master privileges come only from Node login.
    return jwt.encode(
        {"userId": user_id, "email": email, "role": "user", "aud": "aura-python"},
        JWT_SECRET,
        algorithm="HS256",
    )

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("web_server")

# ─── Database helpers ────────────────────────────────────────────────────────
DB_PATH = DATA_DIR / "chat_history.db"


def _get_db() -> sqlite3.Connection:
    """Return a new SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    """Create the tables used by the web server if they don't already exist."""
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        )
    """)
    conn.commit()
    conn.close()


def _save_message(session_id: str, role: str, content: str):
    """Persist a single chat message to SQLite."""
    conn = _get_db()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content),
    )
    conn.commit()
    conn.close()


def _get_history(session_id: str, limit: int = 200) -> list[dict]:
    """Retrieve chat messages for a given session, newest last."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, session_id, role, content, timestamp "
        "FROM chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _list_sessions() -> list[dict]:
    """Return all chat sessions, newest first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT session_id, title, created_at FROM chat_sessions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _create_session(title: str | None = None) -> dict:
    """Create a new chat session and return its metadata."""
    sid = str(uuid.uuid4())
    title = title or f"Chat {datetime.now().strftime('%b %d, %H:%M')}"
    conn = _get_db()
    conn.execute(
        "INSERT INTO chat_sessions (session_id, title) VALUES (?, ?)",
        (sid, title),
    )
    conn.commit()
    conn.close()
    return {"session_id": sid, "title": title, "created_at": datetime.now().isoformat()}


# ─── Emotion detection ───────────────────────────────────────────────────────

_EMOTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("excited",     [r"amazing", r"incredible", r"fantastic", r"wow", r"awesome",
                     r"brilliant", r"can't wait", r"thrilled", r"!!+"]),
    ("happy",       [r"great", r"glad", r"happy", r"wonderful", r"love it",
                     r"perfect", r"nice", r"yay", r"😊", r"😄", r"delighted"]),
    ("sad",         [r"sorry", r"unfortunately", r"sad", r"bad news", r"regret",
                     r"miss you", r"😢", r"heartbreaking", r"tragic"]),
    ("surprised",   [r"oh\b", r"really\?", r"no way", r"unbelievable",
                     r"unexpected", r"whoa", r"😮", r"didn't expect"]),
    ("curious",     [r"interesting", r"wonder", r"hmm", r"let me think",
                     r"curious", r"explore", r"fascinating", r"🤔"]),
    ("encouraging", [r"you can do", r"keep going", r"believe in", r"don't give up",
                     r"proud of", r"well done", r"keep it up", r"go for it"]),
    ("serious",     [r"important", r"critical", r"warning", r"careful",
                     r"caution", r"danger", r"risk", r"urgent", r"⚠"]),
    ("confident",   [r"absolutely", r"definitely", r"i'm sure", r"certain",
                     r"no doubt", r"guaranteed", r"without question"]),
    ("friendly",    [r"hey", r"hi there", r"how are you", r"chat",
                     r"friend", r"buddy", r"hello", r"cheers"]),
    ("calm",        [r"relax", r"take your time", r"no rush", r"peaceful",
                     r"breathe", r"it's okay", r"don't worry", r"calm"]),
]


def detect_emotion(text: str) -> str:
    """Analyze response text and return one of the predefined emotion labels."""
    if not text:
        return "neutral"
    lower = text.lower()
    scores: dict[str, int] = {}
    for emotion, patterns in _EMOTION_PATTERNS:
        count = sum(1 for p in patterns if re.search(p, lower))
        if count:
            scores[emotion] = count
    if not scores:
        return "neutral"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


# ─── Global singletons (lazy-initialised at startup) ────────────────────────

settings: dict = {}
ai_client: AIClient | None = None
voice_engine: VoiceEngine | None = None
task_manager: TaskManager | None = None

# Server state
_state_lock = threading.Lock()
_current_status = "ready"  # ready | listening | thinking | speaking
_active_session_id: str | None = None


def _set_status(new_status: str):
    global _current_status
    with _state_lock:
        _current_status = new_status


def _get_status() -> str:
    with _state_lock:
        return _current_status


# ─── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(title="AI Bridge Server", version="1.0.0")

_allowed_origins = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
if os.getenv("FRONTEND_URL"):
    _allowed_origins.add(os.getenv("FRONTEND_URL").strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Startup / Shutdown ─────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup():
    global settings, ai_client, voice_engine, task_manager, _active_session_id

    logger.info("Initialising backend components …")
    _ensure_tables()

    settings = load_settings()
    ai_client = AIClient(settings)
    voice_engine = VoiceEngine(settings)
    task_manager = TaskManager()

    # Ensure at least one session exists
    sessions = _list_sessions()
    if sessions:
        _active_session_id = sessions[0]["session_id"]
    else:
        new = _create_session("Default")
        _active_session_id = new["session_id"]

    # Aura account/oversight features are optional in this repository snapshot.
    if aura_module is not None:
        aura_module.aura_ensure_tables(DATA_DIR)
    else:
        logger.warning("Aura account and oversight routes are disabled: aura_module.py is not present.")
    if create_pdf_document is None:
        logger.warning("PDF document generation is disabled: utils/pdf_generator.py is not present.")

    logger.info("Backend ready — active session: %s", _active_session_id)


# ─── REST endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/settings")
async def get_settings(authorization: str | None = Header(default=None)):
    _require_master(authorization)
    current = load_settings()
    # Mask sensitive keys for the frontend
    safe = {**current}
    for key in ("gemini_api_key", "elevenlabs_api_key", "groq_api_key",
                "minimax_api_key", "delta_api_key", "delta_api_secret", "face_backup_pin"):
        if safe.get(key):
            safe[key] = safe[key][:4] + "••••" + safe[key][-4:] if len(safe.get(key, "")) > 8 else "••••"
    return safe


@app.post("/api/settings")
async def update_settings(payload: dict, authorization: str | None = Header(default=None)):
    _require_master(authorization)
    current = load_settings()
    # Only update keys that are not masked
    for k, v in payload.items():
        if "••••" not in str(v):
            current[k] = v
    save_settings(current)
    # Live-update in-memory objects
    global settings
    settings = current
    if voice_engine:
        voice_engine.update_settings(current)
    logger.info("Settings updated via REST")
    return {"status": "ok"}


@app.get("/api/avatar")
async def get_avatar():
    custom = settings.get("custom_logo_path", "")
    if custom and os.path.isfile(custom):
        return FileResponse(custom, media_type="image/png")
    default = DATA_DIR / "aleena_avatar.png"
    if default.exists():
        return FileResponse(str(default), media_type="image/png")
    raise HTTPException(status_code=404, detail="Avatar not found")


# ─── PDF Serving & Generation Endpoints ─────────────────────────────────────

@app.get("/api/pdf/list")
async def list_pdf_files(authorization: str | None = Header(default=None)):
    _require_master(authorization)
    """List all generated PDF documents in documents directory."""
    pdf_dir = Path("C:/Users/ay670/OneDrive/Desktop/myAI/documents")
    pdf_files = []
    if pdf_dir.exists():
        for f in sorted(pdf_dir.glob("*.pdf"), key=os.path.getmtime, reverse=True):
            stat = f.stat()
            pdf_files.append({
                "filename": f.name,
                "title": f.stem.replace("_", " ").title(),
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %H:%M"),
                "download_url": f"/api/pdf/{f.name}"
            })
    return {"pdf_files": pdf_files}


def enhance_prompt_for_realism(user_prompt: str) -> str:
    """
    Enhance any simple or Hinglish user prompt into a high-detail photorealistic prompt.
    Strips out cartoon/3D/anime aesthetics and enforces 8k DSLR photography parameters.
    """
    prompt = user_prompt.strip()

    # Try fast AI expansion using Gemini client if available
    gemini_client = getattr(ai_client, "_gemini_client", None)
    if gemini_client:
        try:
            from google.genai import types
            system_instruction = (
                "You are an expert photographic prompt engineer for Flux AI image generator. "
                "Convert the user prompt (even if in Hindi or Hinglish) into a detailed, photorealistic English photography prompt. "
                "Specify lighting (soft natural light), camera settings (shot on 85mm f/1.4 lens, 8k RAW photo), realistic skin/surface textures. "
                "Do NOT include words like cartoon, 3d, render, illustration, drawing, or painting. "
                "Output ONLY the final English photographic prompt string."
            )
            resp = gemini_client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.5,
                    max_output_tokens=120
                )
            )
            if resp and resp.text:
                enhanced = resp.text.strip().replace("\n", " ")
                logger.info(f"AI Enhanced prompt: '{prompt}' -> '{enhanced}'")
                return enhanced
        except Exception as e:
            logger.warning(f"AI prompt expansion error: {e}")

    # Fallback Photorealistic Prompt Rules
    photorealistic_tags = "award winning 8k RAW photograph, hyperrealistic photo, shot on DSLR 85mm lens, natural realistic lighting, realistic skin textures, cinematic depth of field, real life photo, --no 3d render cartoon illustration drawing painting cgi"
    return f"{prompt}, {photorealistic_tags}"


def generate_real_ai_image(prompt: str) -> tuple:
    """Generate a real high quality photorealistic AI image via Pollinations AI Flux engine."""
    import urllib.parse
    import urllib.request
    import random

    img_dir = DATA_DIR / "generated_images"
    img_dir.mkdir(exist_ok=True)

    filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
    filepath = img_dir / filename

    # Enhance prompt for photorealism & exact understanding
    real_prompt = enhance_prompt_for_realism(prompt)
    encoded_prompt = urllib.parse.quote(real_prompt)
    seed = random.randint(100000, 999999)

    # Multi-endpoint photorealistic candidate URLs
    candidate_urls = [
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=768&seed={seed}&nologo=true&model=flux",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=600&height=600&seed={seed}&nologo=true&model=turbo",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}&nologo=true"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url in candidate_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                image_bytes = resp.read()
                if image_bytes and len(image_bytes) > 2000:
                    with open(filepath, "wb") as f:
                        f.write(image_bytes)
                    logger.info(f"Successfully generated photorealistic AI image for prompt: '{prompt}'")
                    return f"/api/image/{filename}", filename
        except Exception as e:
            logger.warning(f"Photorealistic image fetch failed for {url}: {e}")

    # Fallback to direct client-side URL
    fallback_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=600&height=600&nologo=true&seed={seed}"
    return fallback_url, "image.jpg"


@app.post("/api/image/generate")
async def generate_image_endpoint(payload: dict, authorization: str | None = Header(default=None)):
    _require_master(authorization)
    """Generate an AI image based on user prompt."""
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    loop = asyncio.get_running_loop()
    try:
        url, fn = await loop.run_in_executor(None, lambda: generate_real_ai_image(prompt))
        return {"status": "ok", "url": url, "filename": fn, "prompt": prompt}
    except Exception as e:
        logger.exception("Image generation error")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/image/{filename}")
async def get_generated_image(filename: str):
    """Serve generated image files."""
    img_dir = DATA_DIR / "generated_images"
    img_path = img_dir / filename
    if img_path.exists():
        return FileResponse(str(img_path), media_type="image/jpeg")
    # Also check documents dir
    doc_img = Path("C:/Users/ay670/OneDrive/Desktop/myAI/documents") / filename
    if doc_img.exists():
        return FileResponse(str(doc_img))
    raise HTTPException(status_code=404, detail="Image not found")


# ─── WebSocket handler ──────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket connected; awaiting master authentication")
    try:
        try:
            first_message = await asyncio.wait_for(ws.receive_text(), timeout=10)
            auth_message = json.loads(first_message)
            token = (auth_message.get("data") or {}).get("token", "")
            if auth_message.get("type") != "auth":
                raise ValueError("Authentication message required")
            user = _decode_bearer_token("Bearer " + token)
            if (
                not MASTER_EMAIL
                or str(user.get("email", "")).strip().lower() != MASTER_EMAIL
                or user.get("role") != "master"
            ):
                raise PermissionError("Master administrator access required")
            await _ws_send(ws, "auth.success", {"email": user["email"]})
        except Exception as auth_error:
            logger.warning("WebSocket authentication rejected: %s", auth_error)
            await _ws_send(ws, "auth.error", {"message": "Authentication failed."})
            await ws.close(code=1008)
            return

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_send(ws, "error", {"message": "Invalid JSON"})
                continue
            msg_type = msg.get("type", "")
            data = msg.get("data", {})
            logger.info("WS ← %s", msg_type)
            try:
                if msg_type == "chat.send": await _handle_chat_send(ws, data)
                elif msg_type == "voice.start": await _handle_voice_start(ws)
                elif msg_type == "voice.stop": await _handle_voice_stop(ws)
                elif msg_type == "voice.speak": await _handle_voice_speak(ws, data)
                elif msg_type == "status.get": await _handle_status_get(ws)
                elif msg_type == "session.list": await _handle_session_list(ws)
                elif msg_type == "session.create": await _handle_session_create(ws, data)
                elif msg_type == "session.switch": await _handle_session_switch(ws, data)
                elif msg_type == "history.get": await _handle_history_get(ws, data)
                else: await _ws_send(ws, "error", {"message": "Unknown WebSocket message type."})
            except Exception:
                logger.exception("Handler error for %s", msg_type)
                await _ws_send(ws, "error", {"message": "Request could not be processed."})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket fatal error")


async def _ws_send(ws: WebSocket, msg_type: str, data: dict):
    """Helper – send a typed JSON message over the WebSocket."""
    await ws.send_json({"type": msg_type, "data": data})


# ─── WebSocket message handlers ─────────────────────────────────────────────

async def _handle_chat_send(ws: WebSocket, data: dict):
    """Process a chat message: stream tokens, then send completion."""
    global _active_session_id

    text = data.get("text", "").strip()
    session_id = data.get("session_id") or _active_session_id
    if not text:
        await _ws_send(ws, "error", {"message": "Empty message"})
        return

    # Persist user message
    _save_message(session_id, "user", text)
    _set_status("thinking")
    await _ws_send(ws, "status.update", {"status": "thinking"})

    # Run the AI call in a thread so we don't block the event loop
    loop = asyncio.get_running_loop()
    try:
        clean_response, commands, thinking = await loop.run_in_executor(
            None, lambda: ai_client.send(text)
        )
    except Exception as e:
        logger.exception("AIClient.send() failed")
        _set_status("ready")
        await _ws_send(ws, "status.update", {"status": "ready"})
        await _ws_send(ws, "error", {"message": f"AI error: {e}"})
        return

    if clean_response:
        tokens = _tokenize_for_streaming(clean_response)
        for token in tokens:
            await _ws_send(ws, "chat.stream", {"token": token})
            await asyncio.sleep(0.01)  # tiny delay for frontend animation

    # Check if this was a PDF generation request
    if clean_response and aura_module.is_pdf_request(text):
        try:
            # Extract first line title or use query
            lines = [l.strip() for l in clean_response.split('\n') if l.strip()]
            title = text[:35]
            if lines and lines[0].startswith('#'):
                title = lines[0].lstrip('#').strip()
            _, pdf_fn = create_pdf_document(title, clean_response, author="Aleena AI")
            pdf_link = f"\n\n📄 **PDF Document Created!**\n[📥 Download {pdf_fn}](/api/pdf/{pdf_fn})"
            clean_response += pdf_link
        except Exception as pdf_err:
            logger.error(f"Failed to auto-generate PDF for Aleena: {pdf_err}")

    emotion = detect_emotion(clean_response or "")

    # Persist assistant response
    _save_message(session_id, "assistant", clean_response or "")

    _set_status("ready")
    await _ws_send(ws, "chat.done", {
        "full_response": clean_response or "",
        "emotion": emotion,
        "thinking": thinking,
        "commands": [{"type": c[0], "value": c[1]} for c in (commands or [])],
        "session_id": session_id,
    })
    await _ws_send(ws, "status.update", {"status": "ready"})

    # If voice is not muted, speak the response
    if voice_engine and not settings.get("global_speech_mute", False):
        _set_status("speaking")
        await _ws_send(ws, "status.update", {"status": "speaking"})

        done_event = threading.Event()

        def _on_speech_done():
            done_event.set()

        voice_engine.speak(clean_response, callback_done=_on_speech_done)

        # Wait for speech to finish without blocking the event loop
        await loop.run_in_executor(None, lambda: done_event.wait(timeout=120))
        _set_status("ready")
        await _ws_send(ws, "status.update", {"status": "ready"})


def _tokenize_for_streaming(text: str) -> list[str]:
    """Split response text into small chunks for simulated streaming."""
    tokens = []
    # Split on word boundaries while keeping whitespace / punctuation
    parts = re.findall(r'\S+|\s+', text)
    chunk = ""
    for part in parts:
        chunk += part
        # Emit a chunk every few words or at sentence boundaries
        if len(chunk) >= 12 or part.rstrip().endswith(('.', '!', '?', ':', '\n')):
            tokens.append(chunk)
            chunk = ""
    if chunk:
        tokens.append(chunk)
    return tokens


async def _handle_voice_start(ws: WebSocket):
    """Start voice listening in a background thread."""
    _set_status("listening")
    await _ws_send(ws, "status.update", {"status": "listening"})

    loop = asyncio.get_running_loop()

    def _listen_blocking():
        def status_cb(st):
            _set_status(st)

        return voice_engine.listen_once(status_callback=status_cb)

    try:
        recognised = await loop.run_in_executor(None, _listen_blocking)
    except Exception as e:
        logger.exception("Voice listen error")
        recognised = None

    if recognised:
        await _ws_send(ws, "voice.result", {"text": recognised})
        # Auto-send to chat
        await _handle_chat_send(ws, {"text": recognised, "session_id": _active_session_id})
    else:
        await _ws_send(ws, "voice.result", {"text": None, "error": "No speech detected"})
        _set_status("ready")
        await _ws_send(ws, "status.update", {"status": "ready"})


async def _handle_voice_stop(ws: WebSocket):
    """Stop ongoing voice listening / speech."""
    if voice_engine:
        voice_engine.stop()
    _set_status("ready")
    await _ws_send(ws, "status.update", {"status": "ready"})
    await _ws_send(ws, "voice.stopped", {})


async def _handle_voice_speak(ws: WebSocket, data: dict):
    """Speak custom text on-demand (e.g. for idle/welcome voice lines)."""
    text = data.get("text", "").strip()
    if not text:
        return
    if voice_engine and not settings.get("global_speech_mute", False):
        _set_status("speaking")
        await _ws_send(ws, "status.update", {"status": "speaking"})
        
        loop = asyncio.get_running_loop()
        done_event = threading.Event()
        def _on_speech_done():
            done_event.set()

        voice_engine.speak(text, callback_done=_on_speech_done)
        await loop.run_in_executor(None, lambda: done_event.wait(timeout=120))
        
        _set_status("ready")
        await _ws_send(ws, "status.update", {"status": "ready"})


async def _handle_status_get(ws: WebSocket):
    """Return the current server status."""
    extra: dict[str, Any] = {"status": _get_status()}
    if voice_engine:
        extra["is_speaking"] = voice_engine.is_currently_speaking
        extra["speech_text"] = voice_engine.current_speech_text or None
    extra["active_session_id"] = _active_session_id
    await _ws_send(ws, "status.current", extra)


async def _handle_session_list(ws: WebSocket):
    """Return all chat sessions."""
    sessions = _list_sessions()
    await _ws_send(ws, "session.list", {
        "sessions": sessions,
        "active_session_id": _active_session_id,
    })


async def _handle_session_create(ws: WebSocket, data: dict):
    """Create a new chat session."""
    global _active_session_id
    title = data.get("title")
    session = _create_session(title)
    _active_session_id = session["session_id"]
    if ai_client:
        ai_client._history = []  # reset in-memory history for the new session
    await _ws_send(ws, "session.created", session)
    logger.info("Created session %s (%s)", session["session_id"], session["title"])


async def _handle_session_switch(ws: WebSocket, data: dict):
    """Switch to an existing session and load its history into the AI client."""
    global _active_session_id
    sid = data.get("session_id", "")
    if not sid:
        await _ws_send(ws, "error", {"message": "session_id required"})
        return

    # Verify the session exists
    conn = _get_db()
    row = conn.execute(
        "SELECT session_id, title FROM chat_sessions WHERE session_id = ?", (sid,)
    ).fetchone()
    conn.close()
    if not row:
        await _ws_send(ws, "error", {"message": f"Session {sid} not found"})
        return

    _active_session_id = sid

    # Reload AI client history from DB for the switched session
    if ai_client:
        messages = _get_history(sid, limit=100)
        ai_client._history = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

    await _ws_send(ws, "session.switched", {
        "session_id": sid,
        "title": dict(row)["title"],
    })
    logger.info("Switched to session %s", sid)


async def _handle_history_get(ws: WebSocket, data: dict):
    """Return chat history for a session."""
    sid = data.get("session_id") or _active_session_id
    limit = data.get("limit", 200)
    messages = _get_history(sid, limit=limit)
    await _ws_send(ws, "history.data", {
        "session_id": sid,
        "messages": messages,
    })


# ─── Aura REST Endpoints ─────────────────────────────────────────────────────

@app.post("/aura/auth/check_email")
async def check_email_endpoint(payload: dict):
    _require_aura_module()
    """Checks if email format/domain is valid and whether user exists."""
    email = (payload.get("email") or "").strip()
    exists, status_type, user_info = aura_module.check_user_email_status(DATA_DIR, email)
    if not exists and status_type not in ["SET_INITIAL_PASSWORD", "CREATE_NEW_ACCOUNT"]:
        return JSONResponse({"error": status_type}, status_code=400)
    return {
        "status": "ok",
        "is_existing_user": exists,
        "status_type": status_type,
        "email": email,
        "name": user_info.get("name") if user_info else None
    }


@app.post("/aura/auth/login_password")
async def login_password_endpoint(payload: dict):
    _require_aura_module()
    """Authenticate or Register user with password."""
    email = (payload.get("email") or "").strip()
    password = (payload.get("password") or "").strip()
    name = (payload.get("name") or "").strip()

    success, msg, user_data, is_pass_req = aura_module.authenticate_user_with_password(
        DATA_DIR, email, password, name=name
    )

    if not success:
        return JSONResponse({"error": msg, "is_password_needed": is_pass_req}, status_code=400)

    token = _create_aura_token(email.strip().lower(), user_data)
    return {"status": "ok", "message": msg, "user": user_data, "token": token}


@app.post("/aura/auth/login")
async def aura_login(payload: dict):
    _require_aura_module()
    """Standard Login Endpoint."""
    email = (payload.get("email") or "").strip()
    password = (payload.get("password") or "").strip()
    name = (payload.get("name") or "").strip()
    if not email or not password:
        return JSONResponse({"error": "Email and password are required."}, status_code=400)

    success, msg, user_data, is_pass_req = aura_module.authenticate_user_with_password(
        DATA_DIR, email, password, name=name
    )

    if not success:
        return JSONResponse({"error": msg}, status_code=400)

    token = _create_aura_token(email.strip().lower(), user_data)
    return {"status": "ok", "message": msg, "user": user_data, "token": token}


@app.get("/api/aleena/users_overview")
async def aleena_users_overview(authorization: str | None = Header(default=None)):
    _require_master(authorization)
    _require_aura_module()
    return aura_module.get_aleena_master_analytics(DATA_DIR)


@app.get("/api/aleena/user_conversations")
async def get_user_conversations_endpoint(
    user_email: str = "",
    authorization: str | None = Header(default=None),
):
    _require_master(authorization)
    _require_aura_module()
    if not user_email.strip():
        raise HTTPException(status_code=400, detail="user_email is required.")
    return aura_module.get_aleena_master_user_conversations(DATA_DIR, user_email)


@app.post("/aura/chat")
async def aura_chat(payload: dict, authorization: str | None = Header(default=None)):
    user = _decode_bearer_token(authorization)
    _require_aura_module()
    """
    Aura public chat endpoint with per-user isolated database routing.
    Accepts: {message: str, session_id: str, email: str}
    Returns: {response: str, session_id: str, emotion: str}
    """
    message = (payload.get("message") or "").strip()
    session_id = payload.get("session_id") or ""
    email = str(user.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Authenticated email is missing.")

    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    # Auto-create session in user's isolated DB if not provided
    if not session_id:
        sess = aura_module.aura_create_session(DATA_DIR, email=email)
        session_id = sess["session_id"]

    # Privacy gate — block personal info requests immediately
    if aura_module.is_private_info_request(message):
        safe_reply = (
            "Maafi chahta/chahti hoon, yeh personal information main share nahi kar sakta/sakti. "
            "Main ek public AI assistant hoon — private data mere paas nahi hota."
        )
        aura_module.aura_save_message(DATA_DIR, session_id, "user", message, email=email)
        aura_module.aura_save_message(DATA_DIR, session_id, "assistant", safe_reply, email=email)
        return {"response": safe_reply, "session_id": session_id, "emotion": "calm"}

    # Save user message to isolated user DB
    aura_module.aura_save_message(DATA_DIR, session_id, "user", message, email=email)

    # Build Aura-scoped conversation history from isolated user DB
    history = aura_module.aura_get_history(DATA_DIR, session_id, limit=40, email=email)

    # Generate response using the shared AIClient with Aura system prompt
    loop = asyncio.get_running_loop()
    try:
        def _call_ai():
            import google.genai.types as gtypes
            from google import genai

            if ai_client is None:
                return "Aura abhi available nahi hai. Thodi der baad try karein."

            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                parts = [{"text": msg["content"]}]
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({"role": role, "parts": parts})

            if not contents or contents[-1]["role"] != "user":
                contents.append({"role": "user", "parts": [{"text": message}]})

            while contents and contents[0]["role"] != "user":
                contents.pop(0)

            if not contents:
                contents = [{"role": "user", "parts": [{"text": message}]}]

            gemini_client = getattr(ai_client, "_gemini_client", None)
            gemini_model = getattr(ai_client, "gemini_model", "gemini-3.1-flash-lite")

            if gemini_client:
                try:
                    resp = gemini_client.models.generate_content(
                        model=gemini_model,
                        contents=contents,
                        config=gtypes.GenerateContentConfig(
                            system_instruction=aura_module.get_aura_system_prompt(),
                            temperature=0.75,
                            max_output_tokens=1024,
                        ),
                    )
                    return resp.text if resp and resp.text else ""
                except Exception as e:
                    logger.error(f"Aura Gemini error: {e}")
                    return "Abhi kuch technical issue aa raha hai. Thodi der mein dobara try karein."

            return "AI model abhi configure nahi hai."

        raw_response = await loop.run_in_executor(None, _call_ai)
    except Exception as e:
        logger.exception("Aura chat error")
        return JSONResponse({"error": str(e)}, status_code=500)

    # Strip any system command tags for safety
    clean_response = aura_module.strip_blocked_commands(raw_response)

    # Check if user requested a PDF document or Image
    if clean_response and aura_module.is_pdf_request(message):
        try:
            lines = [l.strip() for l in clean_response.split('\n') if l.strip()]
            title = message[:35]
            if lines and lines[0].startswith('#'):
                title = lines[0].lstrip('#').strip()
            _, pdf_fn = create_pdf_document(title, clean_response, author="Aura AI")
            pdf_link = f"\n\n📄 **PDF Document Created!**\n[📥 Download {pdf_fn}](/api/pdf/{pdf_fn})"
            clean_response += pdf_link
        except Exception as pdf_err:
            logger.error(f"Failed to auto-generate PDF for Aura: {pdf_err}")
    elif clean_response and aura_module.is_image_request(message):
        try:
            url, fn = await loop.run_in_executor(None, lambda: generate_real_ai_image(message))
            img_markdown = f"\n\n![AI Generated Image]({url})\n[🖼️ View Full HD Image]({url})"
            clean_response += img_markdown
        except Exception as img_err:
            logger.error(f"Failed to auto-generate Image for Aura: {img_err}")

    # Save assistant response to isolated user DB
    aura_module.aura_save_message(DATA_DIR, session_id, "assistant", clean_response, email=email)

    emotion = detect_emotion(clean_response)

    return {
        "response": clean_response,
        "session_id": session_id,
        "emotion": emotion,
    }


@app.get("/aura/session/new")
async def aura_new_session(authorization: str | None = Header(default=None)):
    user = _decode_bearer_token(authorization)
    _require_aura_module()
    email = str(user.get("email", "")).strip().lower()
    return aura_module.aura_create_session(DATA_DIR, email=email)


@app.get("/aura/sessions")
async def aura_get_sessions(authorization: str | None = Header(default=None)):
    user = _decode_bearer_token(authorization)
    _require_aura_module()
    email = str(user.get("email", "")).strip().lower()
    return {"sessions": aura_module.aura_list_sessions(DATA_DIR, email=email)}


@app.get("/aura/history")
async def aura_get_history(
    session_id: str,
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    user = _decode_bearer_token(authorization)
    _require_aura_module()
    email = str(user.get("email", "")).strip().lower()
    if not session_id:
        return JSONResponse({"error": "session_id required"}, status_code=400)
    messages = aura_module.aura_get_history(DATA_DIR, session_id, limit, email=email)
    return {"session_id": session_id, "messages": messages}


@app.get("/aura/health")
async def aura_health():
    return {"status": "ok", "name": "Aura", "version": "1.0.0"}


# ─── Serve Aura static frontend ──────────────────────────────────────────────
_AURA_DIR = Path(__file__).parent / "aura"
_AURA_DIR.mkdir(exist_ok=True)

@app.get("/aura")
async def aura_index():
    """Serve Aura frontend."""
    index_path = _AURA_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="Aura frontend not found")


@app.get("/aura/aura_logo.jpg")
async def aura_logo_endpoint():
    """Serve Aura AI logo image."""
    logo_path = _AURA_DIR / "aura_logo.jpg"
    if logo_path.exists():
        return FileResponse(str(logo_path))
    raise HTTPException(status_code=404, detail="Logo image not found")


# Mount aura directory for static assets (css, js, images)
try:
    app.mount("/aura/static", StaticFiles(directory=str(_AURA_DIR / "static")), name="aura_static")
except Exception:
    pass  # static dir may not exist yet — created when needed


# ─── Entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    local_bridge_port = int(os.getenv("LOCAL_BRIDGE_PORT", "8766"))
    logger.info("Starting AI Bridge Server on port %s …", local_bridge_port)
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=local_bridge_port,
        reload=False,
        log_level="info",
    )
