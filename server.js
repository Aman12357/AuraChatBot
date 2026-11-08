/**
 * Aleena AI - Production Node.js / Express Backend
 *
 * Stack:
 * - Express REST API
 * - WebSocket chat
 * - PostgreSQL
 * - JWT authentication
 * - bcrypt password hashing
 * - Gemini API using @google/genai
 * - Render deployment support
 */

const http = require("http");
const crypto = require("crypto");
const path = require("path");
const express = require("express");
const { WebSocketServer } = require("ws");
const cors = require("cors");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");
const { Pool } = require("pg");
const { GoogleGenAI } = require("@google/genai");
const { createLocalDatabase } = require("./local_database");

require("dotenv").config();

/* =========================================================
   ENVIRONMENT
   ========================================================= */

const PORT = Number(process.env.PORT || 8765);
const NODE_ENV = process.env.NODE_ENV || "production";

const FRONTEND_URL =
  process.env.FRONTEND_URL || "http://localhost:3000";

const DATABASE_URL = process.env.DATABASE_URL;
const DATABASE_MODE = (
  process.env.DATABASE_MODE ||
  (DATABASE_URL ? "postgres" : (NODE_ENV === "production" ? "memory" : "sqlite"))
).toLowerCase();
const ALEENA_DATA_DIR = path.resolve(
  process.env.ALEENA_DATA_DIR || path.join(__dirname, "data")
);

const GEMINI_API_KEY =
  process.env.GEMINI_API_KEY;

const GEMINI_MODEL =
  process.env.GEMINI_MODEL || "gemini-3.8-flash";
const AI_PROVIDER = (
  process.env.AI_PROVIDER || (NODE_ENV === "production" ? "gemini" : "ollama")
).toLowerCase();
const OLLAMA_BASE_URL = (
  process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434"
).replace(/\/$/, "");
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || "deepseek-r1:8b";

function getActiveModel() {
  return AI_PROVIDER === "ollama" ? OLLAMA_MODEL : GEMINI_MODEL;
}

const JWT_SECRET =
  process.env.JWT_SECRET;
const AUTH_CONFIGURED = Boolean(
  JWT_SECRET && Buffer.byteLength(JWT_SECRET, "utf8") >= 32
);

const MASTER_EMAIL = (process.env.MASTER_EMAIL || "").trim().toLowerCase();
const MASTER_SETUP_KEY = process.env.MASTER_SETUP_KEY || "";

function safeSecretEquals(provided, expected) {
  if (typeof provided !== "string" || !provided || !expected) return false;
  const providedBuffer = Buffer.from(provided);
  const expectedBuffer = Buffer.from(expected);
  return providedBuffer.length === expectedBuffer.length &&
    crypto.timingSafeEqual(providedBuffer, expectedBuffer);
}

if (!AUTH_CONFIGURED) {
  console.warn(
    "[SECURITY] JWT_SECRET is not configured. Login, chat, and WebSocket access will fail closed."
  );
}

/* =========================================================
   DATABASE — local SQLite by default, optional PostgreSQL
   ========================================================= */

let pool = null;
let localDatabase = null;

if (DATABASE_MODE === "postgres" && DATABASE_URL) {
  pool = new Pool({
    connectionString: DATABASE_URL,
    ssl:
      NODE_ENV === "production"
        ? { rejectUnauthorized: false }
        : false,
  });
  console.log("[DATABASE] PostgreSQL pool initialized.");
} else if (DATABASE_MODE === "sqlite") {
  console.log("[DATABASE] Local SQLite mode selected.");
} else if (DATABASE_MODE === "memory") {
  console.warn("[DATABASE] In-memory mode selected; data will not survive a restart.");
} else if (DATABASE_MODE === "postgres") {
  console.warn("[DATABASE] PostgreSQL mode selected without DATABASE_URL; using in-memory fallback.");
} else {
  throw new Error("Unsupported DATABASE_MODE. Use sqlite, postgres or memory.");
}

function hasPersistentDatabase() {
  return Boolean(pool || localDatabase);
}

async function queryDatabase(sql, parameters = []) {
  if (pool) return pool.query(sql, parameters);
  if (localDatabase) return localDatabase.query(sql, parameters);
  throw new Error("No persistent database is available.");
}

async function initializeDatabase() {
  if (DATABASE_MODE === "sqlite") {
    localDatabase = await createLocalDatabase({
      directory: ALEENA_DATA_DIR,
      filename: "aleena.sqlite",
    });
    const integrity = localDatabase.integrityCheck();
    if (integrity !== "ok") {
      throw new Error("Local Aleena SQLite integrity check failed: " + integrity);
    }
    console.log("[DATABASE] SQLite ready: " + localDatabase.path);
  }
}

/* =========================================================
   IN-MEMORY FALLBACK
   ========================================================= */

const inMemoryStore = {
  sessions: [],
  messages: {},
  users: [],
};

/* =========================================================
   GEMINI
   ========================================================= */

let genAI = null;

const SYSTEM_PROMPT = `
You are Aleena, an intelligent, empathetic and multi-capable AI companion.

Your job is to behave like a natural digital assistant.

Communication rules:
- Respond naturally and clearly.
- Respond in the same language the user uses.
- If the user uses Hindi, answer in Hindi.
- If the user uses English, answer in English.
- If the user uses Hinglish, answer naturally in Hinglish.
- Do not repeat yourself unnecessarily.
- Keep answers useful and direct.
- Maintain the conversation context.
- If the user asks for programming help, provide correct code in Markdown code blocks.
- Do not claim to have performed an action that you did not actually perform.
- If you are uncertain, say so clearly.
`;

if (AI_PROVIDER === "gemini" && GEMINI_API_KEY) {
  try {
    genAI = new GoogleGenAI({
      apiKey: GEMINI_API_KEY,
    });

    console.log(
      `[AI] Gemini initialized successfully using ${GEMINI_MODEL}.`
    );
  } catch (error) {
    console.error(
      "[AI] Gemini initialization failed:",
      error.message
    );
    genAI = null;
  }
} else {
  console.log(`[AI] Provider selected: ${AI_PROVIDER}; model: ${getActiveModel()}.`);
}

/* =========================================================
   EXPRESS
   ========================================================= */

const app = express();
// Render terminates TLS and forwards one trusted proxy hop. This must be set
// before express-rate-limit so forwarded client IPs are handled correctly.
app.set("trust proxy", 1);
const server = http.createServer(app);

/* Security */

app.use(
  helmet({
    contentSecurityPolicy: false,
  })
);

/* CORS */

app.use(
  cors({
    origin:
      FRONTEND_URL === "*"
        ? true
        : FRONTEND_URL,
    credentials: true,
  })
);

/* Body parser */

app.use(
  express.json({
    limit: "10mb",
  })
);

/* Rate limiter */

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error:
      "Too many requests. Please try again later.",
  },
});

app.use("/api/", apiLimiter);

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many authentication attempts. Please try again later." },
});

/* =========================================================
   AUTHENTICATION
   ========================================================= */

function requireAuth(req, res, next) {
  if (!JWT_SECRET) {
    return res.status(503).json({ error: "Authentication is not configured." });
  }

  const authorization = req.headers.authorization || "";
  const token = authorization.startsWith("Bearer ")
    ? authorization.slice(7).trim()
    : "";

  if (!token) {
    return res.status(401).json({ error: "Authentication required." });
  }

  try {
    const user = jwt.verify(token, JWT_SECRET, { audience: "aleena-node" });
    if (!user || !user.userId || !user.email) {
      return res.status(401).json({ error: "Invalid authentication token." });
    }
    req.user = user;
    return next();
  } catch (_) {
    return res.status(401).json({ error: "Invalid or expired authentication token." });
  }
}

function createUserToken(user) {
  if (!JWT_SECRET) {
    throw new Error("Authentication is not configured.");
  }
  return jwt.sign(
    {
      userId: user.id,
      email: user.email,
      role: MASTER_EMAIL && user.email.toLowerCase() === MASTER_EMAIL ? "master" : "user",
    },
    JWT_SECRET,
    { expiresIn: "7d", audience: "aleena-node" }
  );
}

/* =========================================================
   HELPERS
   ========================================================= */

function detectEmotion(text) {
  if (!text) return "neutral";

  const lower = text.toLowerCase();

  if (
    /happy|great|wonderful|love|awesome|yay|smile|😊|😄/.test(
      lower
    )
  ) {
    return "happy";
  }

  if (
    /excited|amazing|incredible|wow|brilliant|fantastic/.test(
      lower
    )
  ) {
    return "excited";
  }

  if (
    /sad|sorry|bad|regret|unfortunate|😢|heartbroken/.test(
      lower
    )
  ) {
    return "sad";
  }

  if (
    /oh|really\?|no way|whoa|surprised|😮/.test(
      lower
    )
  ) {
    return "surprised";
  }

  if (
    /think|curious|wonder|interesting|hmm|🤔/.test(
      lower
    )
  ) {
    return "curious";
  }

  return "neutral";
}

/* =========================================================
   DATABASE SESSION HELPERS
   ========================================================= */

async function getUserSession(sessionId, userId) {
  if (hasPersistentDatabase()) {
    const result = await queryDatabase(
      `SELECT session_id, title, created_at
       FROM chat_sessions
       WHERE session_id = $1 AND user_id = $2
       LIMIT 1`,
      [sessionId, userId]
    );
    return result.rows[0] || null;
  }

  return inMemoryStore.sessions.find(
    (session) =>
      session.session_id === sessionId &&
      String(session.user_id) === String(userId)
  ) || null;
}

async function listSessions(userId) {
  if (hasPersistentDatabase()) {
    const result = await queryDatabase(
      `SELECT session_id, title, created_at
       FROM chat_sessions
       WHERE user_id = $1
       ORDER BY created_at DESC`,
      [userId]
    );
    return result.rows;
  }

  return inMemoryStore.sessions
    .filter((session) => String(session.user_id) === String(userId))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

async function createSession(userId, title = null) {
  const sessionId =
    "session-" + Date.now() + "-" +
    Math.random().toString(36).substring(2, 10);

  const sessionTitle =
    title ||
    `Chat ${new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;

  const session = {
    session_id: sessionId,
    user_id: userId,
    title: sessionTitle,
    created_at: new Date().toISOString(),
  };

  if (hasPersistentDatabase()) {
    const result = await queryDatabase(
      `INSERT INTO chat_sessions (session_id, user_id, title)
       VALUES ($1, $2, $3)
       RETURNING session_id, title, created_at`,
      [sessionId, userId, sessionTitle]
    );
    return result.rows[0];
  }

  inMemoryStore.sessions.unshift(session);
  return session;
}

async function ensureDefaultSession(userId) {
  const sessions = await listSessions(userId);
  if (sessions.length) return sessions[0];
  return createSession(userId, "General Conversation");
}

async function saveMessage(sessionId, userId, role, content, emotion = "neutral") {
  const ownedSession = await getUserSession(sessionId, userId);
  if (!ownedSession) {
    const error = new Error("Session not found.");
    error.statusCode = 404;
    throw error;
  }

  if (hasPersistentDatabase()) {
    await queryDatabase(
      `INSERT INTO chat_messages (session_id, role, content, emotion)
       VALUES ($1, $2, $3, $4)`,
      [sessionId, role, content, emotion]
    );
    return;
  }

  if (!inMemoryStore.messages[sessionId]) {
    inMemoryStore.messages[sessionId] = [];
  }

  inMemoryStore.messages[sessionId].push({
    id: String(Date.now()),
    session_id: sessionId,
    role,
    content,
    emotion,
    timestamp: new Date().toISOString(),
  });
}

async function getHistory(sessionId, userId, limit = 100) {
  const ownedSession = await getUserSession(sessionId, userId);
  if (!ownedSession) {
    const error = new Error("Session not found.");
    error.statusCode = 404;
    throw error;
  }

  if (hasPersistentDatabase()) {
    const result = await queryDatabase(
      `SELECT m.id, m.session_id, m.role, m.content, m.emotion, m.timestamp
       FROM chat_messages m
       INNER JOIN chat_sessions s ON s.session_id = m.session_id
       WHERE m.session_id = $1 AND s.user_id = $2
       ORDER BY m.id ASC
       LIMIT $3`,
      [sessionId, userId, limit]
    );
    return result.rows;
  }

  return inMemoryStore.messages[sessionId] || [];
}

/* =========================================================
   GEMINI HISTORY NORMALIZATION
   ========================================================= */

function buildGeminiContents(history) {
  const contents = [];

  for (const message of history) {
    if (
      !message ||
      !message.content ||
      !message.content.trim()
    ) {
      continue;
    }

    const role =
      message.role === "user"
        ? "user"
        : "model";

    const previous =
      contents[contents.length - 1];

    if (previous && previous.role === role) {
      previous.parts.push({
        text: message.content,
      });
    } else {
      contents.push({
        role,
        parts: [
          {
            text: message.content,
          },
        ],
      });
    }
  }

  /*
   Gemini conversation history should start with user.
  */

  while (
    contents.length > 0 &&
    contents[0].role !== "user"
  ) {
    contents.shift();
  }

  return contents;
}

/* =========================================================
   GEMINI RESPONSE
   ========================================================= */

async function generateAIResponse(
  message,
  sessionId,
  userId
) {
  // Local-first mode: call only the Ollama server on this machine.
  // Do not fall through to Gemini, Pollinations or another hosted service.
  if (AI_PROVIDER === "ollama") {
    try {
      const history = await getHistory(sessionId, userId, 20);
      const previousMessages = history.length > 0 ? history.slice(0, -1) : [];
      const messages = [
        { role: "system", content: SYSTEM_PROMPT },
        ...previousMessages.map((item) => ({
          role: item.role === "user" ? "user" : "assistant",
          content: item.content || "",
        })),
        { role: "user", content: message },
      ];

      const response = await fetch(OLLAMA_BASE_URL + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: OLLAMA_MODEL,
          messages,
          stream: false,
        }),
        signal: AbortSignal.timeout(120000),
      });

      if (!response.ok) {
        throw new Error("Ollama returned HTTP " + response.status);
      }

      const payload = await response.json();
      const responseText = payload?.message?.content?.trim();
      if (!responseText) {
        throw new Error("Ollama returned an empty response.");
      }

      console.log("[AI] Local Ollama response generated using " + OLLAMA_MODEL + ".");
      return responseText;
    } catch (error) {
      console.error("[AI] Local Ollama request failed:", error.message);
      return (
        "I could not reach your local Ollama model at " + OLLAMA_BASE_URL +
        ". Start Ollama and make sure the model is installed. Run: ollama pull " +
        OLLAMA_MODEL +
        ". No cloud AI fallback was used."
      );
    }
  }
  /*
   1. Gemini
  */

  if (genAI) {
    try {
      const history =
        await getHistory(
          sessionId,
          userId,
          20
        );

      /*
       User message was already saved
       before this function is called,
       so remove the last user message.
      */

      const previousHistory =
        history.length > 0
          ? history.slice(0, -1)
          : [];

      const contents =
        buildGeminiContents(
          previousHistory
        );

      const request = {
        model: getActiveModel(),
        contents: [
          ...contents,
          {
            role: "user",
            parts: [
              {
                text: message,
              },
            ],
          },
        ],
        config: {
          systemInstruction:
            SYSTEM_PROMPT,
          maxOutputTokens: 4096,
        },
      };

      const response =
        await genAI.models.generateContent(
          request
        );

      const responseText =
        response &&
        typeof response.text === "string"
          ? response.text.trim()
          : "";

      if (responseText) {
        console.log(
          `[AI] Gemini response generated using ${GEMINI_MODEL}.`
        );

        return responseText;
      }

      throw new Error(
        "Gemini returned an empty response."
      );
    } catch (error) {
      console.error(
        "[AI] Gemini request failed:",
        error.message
      );
    }
  }

  /*
   2. Optional Pollinations fallback
  */

  try {
    const history =
      await getHistory(
        sessionId,
        userId,
        6
      );

    const messagesPayload = [
      {
        role: "system",
        content: SYSTEM_PROMPT,
      },

      ...history
        .slice(0, -1)
        .map((item) => ({
          role:
            item.role === "user"
              ? "user"
              : "assistant",
          content:
            item.content || "",
        })),

      {
        role: "user",
        content: message,
      },
    ];

    const response =
      await fetch(
        "https://text.pollinations.ai/",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            messages:
              messagesPayload,
            model: "openai",
          }),
        }
      );

    if (response.ok) {
      const text =
        await response.text();

      if (text && text.trim()) {
        console.log(
          "[AI] Pollinations fallback response received."
        );

        return text.trim();
      }
    }
  } catch (error) {
    console.error(
      "[AI] Pollinations fallback failed:",
      error.message
    );
  }

  /*
   3. Safe local fallback
  */

  const lower =
    message.toLowerCase();

  if (
    lower.includes("who are you") ||
    lower.includes("your name") ||
    lower.includes("name aleena")
  ) {
    return (
      "I am Aleena AI, your intelligent digital companion."
    );
  }

  if (
    lower.includes("hello") ||
    lower.includes("hi") ||
    lower.includes("hey")
  ) {
    return (
      "Hello! I am Aleena. How can I help you today?"
    );
  }

  if (
    lower.includes("code") ||
    lower.includes("program")
  ) {
    return (
      "I can help you with coding, debugging, explanations, algorithms and software projects."
    );
  }

  return (
    "I received your message, but the AI service is currently unavailable. Please check the Gemini API configuration."
  );
}

/* =========================================================
   HEALTH
   ========================================================= */

app.get(
  "/api/health",
  async (req, res) => {
    let database = DATABASE_MODE === "memory" ? "memory" : "disconnected";

    if (hasPersistentDatabase()) {
      try {
        await queryDatabase(
          "SELECT 1"
        );

        database = "connected";
      } catch (error) {
        database = "error";
      }
    }

    res.json({
      status: "ok",
      service: "Aleena AI",
      environment: NODE_ENV,
      database,
      database_mode: DATABASE_MODE,
      ai_provider: AI_PROVIDER,
      ai_provider_configured: AI_PROVIDER === "ollama" || Boolean(genAI),
      model: getActiveModel(),
      timestamp:
        new Date().toISOString(),
    });
  }
);

/* =========================================================
   GEMINI TEST ENDPOINT
   ========================================================= */

app.get(
  "/api/ai-test",
  requireAuth,
  async (req, res) => {
    if (AI_PROVIDER === "ollama") {
      try {
        const response = await fetch(OLLAMA_BASE_URL + "/api/tags", {
          signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) {
          throw new Error("Ollama returned HTTP " + response.status);
        }
        const payload = await response.json();
        const installed = (payload.models || []).some((item) =>
          item.name === OLLAMA_MODEL || item.name?.startsWith(OLLAMA_MODEL + ":")
        );
        return res.json({
          status: installed ? "ok" : "model-not-installed",
          provider: AI_PROVIDER,
          model: OLLAMA_MODEL,
          installed,
          message: installed
            ? "Local Ollama is reachable and the configured model is installed."
            : "Ollama is reachable, but the configured model is not installed. Run: ollama pull " + OLLAMA_MODEL,
        });
      } catch (error) {
        return res.status(503).json({
          status: "error",
          provider: AI_PROVIDER,
          model: OLLAMA_MODEL,
          message: "Local Ollama is unavailable at " + OLLAMA_BASE_URL + ": " + error.message,
        });
      }
    }

    if (!genAI) {
      return res.status(503).json({
        status: "error",
        message: "Gemini is selected but GEMINI_API_KEY is not configured.",
        model: getActiveModel(),
      });
    }

    try {
      const response =
        await genAI.models.generateContent(
          {
            model: getActiveModel(),
            contents:
              "Reply with exactly: ALEENA GEMINI WORKING",
            config: {
              maxOutputTokens: 32,
            },
          }
        );

      res.json({
        status: "ok",
        model: getActiveModel(),
        response:
          response.text || "",
      });
    } catch (error) {
      console.error(
        "[AI TEST] Gemini test failed:",
        error.message
      );

      res.status(500).json({
        status: "error",
        model: getActiveModel(),
        message:
          error.message,
      });
    }
  }
);

/* =========================================================
   REGISTER
   ========================================================= */

app.post(
  "/api/auth/register",
  authLimiter,
  async (req, res) => {
    if (!JWT_SECRET) {
      return res.status(503).json({ error: "Authentication is not configured." });
    }

    const {
      email,
      password,
      name,
      master_setup_key,
    } = req.body || {};

    if (
      typeof email !== "string" ||
      typeof password !== "string" ||
      !email.trim() ||
      password.length < 8 ||
      password.length > 72 || Buffer.byteLength(password, "utf8") > 72
    ) {
      return res.status(400).json({
        error: "A valid email and a password between 8 and 72 characters are required.",
      });
    }

    try {
      const normalizedEmail = email.trim().toLowerCase();

      if (MASTER_EMAIL && normalizedEmail === MASTER_EMAIL) {
        if (!MASTER_SETUP_KEY || Buffer.byteLength(MASTER_SETUP_KEY, "utf8") < 32) {
          return res.status(503).json({ error: "MASTER_SETUP_KEY must be configured with at least 32 characters on the backend." });
        }
        if (!safeSecretEquals(master_setup_key, MASTER_SETUP_KEY)) {
          return res.status(403).json({ error: "Administrator registration requires the setup key." });
        }
      }

      const passwordHash =
        await bcrypt.hash(
          password,
          10
        );

      if (hasPersistentDatabase()) {
        const existing =
          await queryDatabase(
            "SELECT id FROM users WHERE email = $1",
            [normalizedEmail]
          );

        if (existing.rows.length) {
          return res
            .status(400)
            .json({
              error:
                "User already exists with this email.",
            });
        }

        const result =
          await queryDatabase(
            `
            INSERT INTO users
              (email, password_hash, name)
            VALUES
              ($1, $2, $3)
            RETURNING id, email, name
            `,
            [
              normalizedEmail,
              passwordHash,
              name ||
                "User",
            ]
          );

        const user =
          result.rows[0];

        const token = createUserToken(user);

        return res.json({
          status: "ok",
          user,
          token,
        });
      }

      if (inMemoryStore.users.some((item) => item.email === normalizedEmail)) {
        return res.status(409).json({ error: "User already exists with this email." });
      }

      const user = {
        id:
          inMemoryStore
            .users
            .length + 1,
        email:
          normalizedEmail,
        name:
          name ||
          "User",
      };

      inMemoryStore.users.push({
        ...user,
        passwordHash,
      });

      const token = createUserToken(user);

      return res.json({
        status: "ok",
        user,
        token,
      });
    } catch (error) {
      console.error(
        "[AUTH] Registration error:",
        error
      );

      return res
        .status(500)
        .json({
          error:
            "Internal server error.",
        });
    }
  }
);

/* =========================================================
   LOGIN
   ========================================================= */

app.post(
  "/api/auth/login",
  authLimiter,
  async (req, res) => {
    if (!JWT_SECRET) {
      return res.status(503).json({ error: "Authentication is not configured." });
    }

    const {
      email,
      password,
      master_setup_key,
    } = req.body || {};

    if (
      typeof email !== "string" ||
      typeof password !== "string" ||
      !email.trim() ||
      password.length > 72 || Buffer.byteLength(password, "utf8") > 72
    ) {
      return res.status(400).json({ error: "A valid email and password are required." });
    }

    try {
      const normalizedEmail = email.trim().toLowerCase();

      if (MASTER_EMAIL && normalizedEmail === MASTER_EMAIL) {
        if (!MASTER_SETUP_KEY || Buffer.byteLength(MASTER_SETUP_KEY, "utf8") < 32) {
          return res.status(503).json({ error: "MASTER_SETUP_KEY must be configured with at least 32 characters on the backend." });
        }
        if (!safeSecretEquals(master_setup_key, MASTER_SETUP_KEY)) {
          return res.status(403).json({ error: "Administrator login requires the access key." });
        }
      }

      let user = null;
      let passwordHash = null;

      if (hasPersistentDatabase()) {
        const result =
          await queryDatabase(
            `
            SELECT
              id,
              email,
              password_hash,
              name
            FROM users
            WHERE email = $1
            `,
            [normalizedEmail]
          );

        if (
          result.rows.length
        ) {
          user = {
            id:
              result.rows[0]
                .id,
            email:
              result.rows[0]
                .email,
            name:
              result.rows[0]
                .name,
          };

          passwordHash =
            result.rows[0]
              .password_hash;
        }
      } else {
        const found =
          inMemoryStore
            .users
            .find(
              (item) =>
                item.email ===
                normalizedEmail
            );

        if (found) {
          user = {
            id:
              found.id,
            email:
              found.email,
            name:
              found.name,
          };

          passwordHash =
            found.passwordHash;
        }
      }

      if (
        !user ||
        !passwordHash
      ) {
        return res
          .status(401)
          .json({
            error:
              "Invalid credentials.",
          });
      }

      const valid =
        await bcrypt.compare(
          password,
          passwordHash
        );

      if (!valid) {
        return res
          .status(401)
          .json({
            error:
              "Invalid credentials.",
          });
      }

      const token = createUserToken(user);

      return res.json({
        status: "ok",
        user,
        token,
      });
    } catch (error) {
      console.error(
        "[AUTH] Login error:",
        error
      );

      return res
        .status(500)
        .json({
          error:
            "Internal server error.",
        });
    }
  }
);

/* =========================================================
   CURRENT USER
   ========================================================= */

app.get("/api/auth/me", requireAuth, async (req, res) => {
  try {
    let user = null;
    if (hasPersistentDatabase()) {
      const result = await queryDatabase(
        "SELECT id, email, name FROM users WHERE id = $1",
        [req.user.userId]
      );
      user = result.rows[0] || null;
    } else {
      user = inMemoryStore.users.find(
        (item) => String(item.id) === String(req.user.userId)
      ) || null;
      if (user) {
        user = { id: user.id, email: user.email, name: user.name };
      }
    }

    if (!user) return res.status(401).json({ error: "User account not found." });
    return res.json({ status: "ok", user });
  } catch (error) {
    console.error("[AUTH] Current-user lookup failed:", error.message);
    return res.status(500).json({ error: "Unable to verify the current user." });
  }
});

/* =========================================================
   REST CHAT
   ========================================================= */

app.post(
  "/api/chat",
  requireAuth,
  async (req, res) => {
    const { message, session_id } = req.body || {};
    if (typeof message !== "string" || !message.trim()) {
      return res.status(400).json({ error: "Message is required." });
    }

    try {
      const userId = req.user.userId;
      const session = session_id
        ? await getUserSession(session_id, userId)
        : await ensureDefaultSession(userId);

      if (!session) {
        return res.status(404).json({ error: "Session not found." });
      }

      const activeSessionId = session.session_id;
      await saveMessage(activeSessionId, userId, "user", message.trim());

      const reply = await generateAIResponse(message.trim(), activeSessionId, userId);
      const emotion = detectEmotion(reply);
      await saveMessage(activeSessionId, userId, "assistant", reply, emotion);

      return res.json({
        status: "ok",
        response: reply,
        session_id: activeSessionId,
        emotion,
        model: getActiveModel(),
      });
    } catch (error) {
      console.error("[CHAT] Error:", error.message);
      return res.status(error.statusCode || 500).json({
        error: error.statusCode ? error.message : "AI response generation failed.",
      });
    }
  }
);

/* =========================================================
   SETTINGS
   ========================================================= */

app.get(
  "/api/settings",
  (req, res) => {
    res.json({
      voice_rate: 150,
      voice_volume: 1,
      stt_language:
        "en-IN",
      provider: AI_PROVIDER,
      model: getActiveModel(),
    });
  }
);

/* =========================================================
   FRONTEND STATIC FILES
   ========================================================= */

const staticPath =
  path.join(
    __dirname,
    "web",
    "out"
  );

app.use(
  express.static(
    staticPath
  )
);

/* =========================================================
   WEBSOCKET
   ========================================================= */

const wss = new WebSocketServer({
  server,
  path: "/ws",
});

wss.on("connection", (ws) => {
  ws.user = null;
  console.log("[WEBSOCKET] Client connected; awaiting authentication.");
  const authTimeout = setTimeout(() => {
    if (!ws.user && ws.readyState === 1) {
      ws.close(1008, "Authentication timeout");
    }
  }, 10000);

  ws.on("message", async (raw) => {
    try {
      const payload = JSON.parse(raw.toString());
      const type = payload.type;
      const data = payload.data || {};

      if (!ws.user) {
        if (type !== "auth" || !AUTH_CONFIGURED || !data.token) {
          ws.send(JSON.stringify({
            type: "auth.error",
            data: { message: "Authentication required." },
          }));
          ws.close(1008, "Authentication required");
          return;
        }

        try {
          const user = jwt.verify(data.token, JWT_SECRET, { audience: "aleena-node" });
          if (!user || !user.userId || !user.email) throw new Error("Invalid token");
          ws.user = user;
          clearTimeout(authTimeout);
          ws.send(JSON.stringify({ type: "auth.success", data: { email: user.email } }));
        } catch (_) {
          ws.send(JSON.stringify({
            type: "auth.error",
            data: { message: "Invalid or expired authentication token." },
          }));
          ws.close(1008, "Invalid authentication");
        }
        return;
      }

      const userId = ws.user.userId;

      if (type === "chat.send") {
        const text = (data.text || "").trim();
        if (!text) return;

        const session = data.session_id
          ? await getUserSession(data.session_id, userId)
          : await ensureDefaultSession(userId);

        if (!session) {
          ws.send(JSON.stringify({ type: "error", data: { message: "Session not found." } }));
          return;
        }

        const sessionId = session.session_id;
        await saveMessage(sessionId, userId, "user", text);
        ws.send(JSON.stringify({ type: "status.update", data: { status: "thinking" } }));

        const reply = await generateAIResponse(text, sessionId, userId);
        const emotion = detectEmotion(reply);
        const parts = reply.split(/(\s+)/);
        let chunk = "";

        for (let i = 0; i < parts.length; i++) {
          chunk += parts[i];
          if (
            chunk.length >= 24 ||
            parts[i].trim().endsWith(".") ||
            parts[i].trim().endsWith("!") ||
            parts[i].trim().endsWith("?")
          ) {
            if (ws.readyState === 1) {
              ws.send(JSON.stringify({ type: "chat.stream", data: { token: chunk } }));
            }
            chunk = "";
            await new Promise((resolve) => setTimeout(resolve, 15));
          }
        }

        if (chunk && ws.readyState === 1) {
          ws.send(JSON.stringify({ type: "chat.stream", data: { token: chunk } }));
        }

        await saveMessage(sessionId, userId, "assistant", reply, emotion);
        if (ws.readyState === 1) {
          ws.send(JSON.stringify({
            type: "chat.done",
            data: { full_response: reply, emotion, session_id: sessionId },
          }));
          ws.send(JSON.stringify({ type: "status.update", data: { status: "ready" } }));
        }
      } else if (type === "session.list") {
        const sessions = await listSessions(userId);
        ws.send(JSON.stringify({
          type: "session.list",
          data: {
            sessions,
            active_session_id: sessions[0]?.session_id || null,
          },
        }));
      } else if (type === "session.create") {
        const session = await createSession(userId, data.title);
        ws.send(JSON.stringify({ type: "session.created", data: session }));
      } else if (type === "session.switch") {
        const session = await getUserSession(data.session_id, userId);
        if (!session) {
          ws.send(JSON.stringify({ type: "error", data: { message: "Session not found." } }));
          return;
        }
        ws.send(JSON.stringify({
          type: "session.switched",
          data: { session_id: session.session_id },
        }));
      } else if (type === "history.get") {
        const sessionId = data.session_id;
        const session = sessionId
          ? await getUserSession(sessionId, userId)
          : await ensureDefaultSession(userId);
        if (!session) {
          ws.send(JSON.stringify({ type: "error", data: { message: "Session not found." } }));
          return;
        }
        const messages = await getHistory(session.session_id, userId);
        ws.send(JSON.stringify({
          type: "history.data",
          data: { session_id: session.session_id, messages },
        }));
      } else {
        ws.send(JSON.stringify({
          type: "error",
          data: { message: `Unknown WebSocket type: ${type}` },
        }));
      }
    } catch (error) {
      console.error("[WEBSOCKET] Processing error:", error.message);
      try {
        ws.send(JSON.stringify({
          type: "error",
          data: { message: error.statusCode ? error.message : "Request could not be processed." },
        }));
      } catch (_) {}
    }
  });

  ws.on("close", () => {
    console.log("[WEBSOCKET] Client disconnected.");
  });
});

/* =========================================================
   SPA FALLBACK
   ========================================================= */

app.get(
  "*",
  (req, res) => {
    const indexHtml =
      path.join(
        staticPath,
        "index.html"
      );

    res.sendFile(
      indexHtml,
      (error) => {
        if (error) {
          res
            .status(200)
            .json({
              status:
                "ok",
              message:
                "Aleena AI API server is running.",
            });
        }
      }
    );
  }
);

/* =========================================================
   STARTUP
   ========================================================= */

async function startServer() {
  // Initialize local persistence before accepting authenticated requests.
  await initializeDatabase();

  server.listen(
    PORT,
    process.env.HOST || "0.0.0.0",
    () => {
      console.log(
        `[SERVER] Aleena AI listening on port ${PORT}.`
      );

      console.log(
        `[SERVER] Environment: ${NODE_ENV}`
      );

      console.log(`[SERVER] Database mode: ${DATABASE_MODE}`);
      console.log(`[SERVER] AI provider: ${AI_PROVIDER}; model: ${getActiveModel()}`);
    }
  );
}

startServer().catch((error) => {
  console.error("[SERVER] Startup failed:", error);
  process.exit(1);
});

async function shutdown() {
  server.close(async () => {
    try {
      if (localDatabase) localDatabase.close();
      if (pool) await pool.end();
    } catch (error) {
      console.error("[SERVER] Shutdown error:", error.message);
    } finally {
      process.exit(0);
    }
  });
}

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
