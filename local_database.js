"use strict";

const fs = require("node:fs");
const path = require("node:path");
const initSqlJs = require("sql.js");

const SCHEMA = [
  "PRAGMA foreign_keys = ON;",
  "CREATE TABLE IF NOT EXISTS users (",
  "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
  "  email TEXT UNIQUE NOT NULL,",
  "  password_hash TEXT NOT NULL,",
  "  name TEXT,",
  "  created_at TEXT DEFAULT CURRENT_TIMESTAMP",
  ");",
  "CREATE TABLE IF NOT EXISTS chat_sessions (",
  "  session_id TEXT PRIMARY KEY,",
  "  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,",
  "  email TEXT,",
  "  title TEXT,",
  "  created_at TEXT DEFAULT CURRENT_TIMESTAMP",
  ");",
  "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_created",
  "  ON chat_sessions (user_id, created_at DESC);",
  "CREATE TABLE IF NOT EXISTS chat_messages (",
  "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
  "  session_id TEXT REFERENCES chat_sessions(session_id) ON DELETE CASCADE,",
  "  role TEXT NOT NULL,",
  "  content TEXT NOT NULL,",
  "  emotion TEXT,",
  "  timestamp TEXT DEFAULT CURRENT_TIMESTAMP",
  ");",
  "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id",
  "  ON chat_messages (session_id, id);",
  "CREATE TABLE IF NOT EXISTS user_memory (",
  "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
  "  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,",
  "  memory_key TEXT,",
  "  memory_value TEXT,",
  "  created_at TEXT DEFAULT CURRENT_TIMESTAMP",
  ");",
  "CREATE TABLE IF NOT EXISTS user_settings (",
  "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
  "  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,",
  "  settings_json TEXT,",
  "  updated_at TEXT DEFAULT CURRENT_TIMESTAMP",
  ");",
].join("\n");

function normalizeSql(sql) {
  if (typeof sql !== "string" || !sql.trim()) {
    throw new TypeError("A non-empty SQL statement is required.");
  }

  // The existing cloud API uses PostgreSQL positional placeholders ($1, $2).
  // Convert them to SQLite positional placeholders without changing parameters.
  return sql.replace(/\$\d+/g, "?");
}

async function createLocalDatabase(options = {}) {
  const directory = path.resolve(
    options.directory ||
      process.env.ALEENA_DATA_DIR ||
      path.join(__dirname, "data")
  );
  const filename = options.filename || "aleena.sqlite";
  const databasePath = path.join(directory, filename);

  fs.mkdirSync(directory, { recursive: true });

  const moduleDirectory = path.dirname(require.resolve("sql.js"));
  const SQL = await initSqlJs({
    locateFile: (file) => path.join(moduleDirectory, file),
  });

  const initialBytes = fs.existsSync(databasePath)
    ? fs.readFileSync(databasePath)
    : null;

  const database = initialBytes
    ? new SQL.Database(new Uint8Array(initialBytes))
    : new SQL.Database();

  database.exec(SCHEMA);

  let closed = false;

  function persist() {
    if (closed) {
      throw new Error("Cannot persist a closed Aleena database.");
    }

    const temporaryPath = databasePath + "." + process.pid + "." + Date.now() + ".tmp";
    try {
      const bytes = Buffer.from(database.export());
      fs.writeFileSync(temporaryPath, bytes, { mode: 0o600 });
      fs.renameSync(temporaryPath, databasePath);
    } catch (error) {
      try {
        fs.rmSync(temporaryPath, { force: true });
      } catch (_) {
        // Preserve the original persistence error.
      }
      throw new Error("Could not safely persist local Aleena data: " + error.message);
    }
  }

  // A new database must exist on disk before the service reports itself ready.
  if (!initialBytes) {
    persist();
  }

  function query(sql, parameters = []) {
    if (closed) {
      throw new Error("The local Aleena database is closed.");
    }
    if (!Array.isArray(parameters)) {
      throw new TypeError("SQL parameters must be passed as an array.");
    }

    const normalized = normalizeSql(sql);
    const statement = database.prepare(normalized);
    const rows = [];
    const readOnly = /^\s*(SELECT|PRAGMA|EXPLAIN)\b/i.test(normalized);

    try {
      if (parameters.length) {
        statement.bind(parameters);
      }

      while (statement.step()) {
        rows.push(statement.getAsObject());
      }
    } finally {
      statement.free();
    }

    if (!readOnly) {
      persist();
    }

    return { rows, rowCount: rows.length };
  }

  function integrityCheck() {
    const result = database.exec("PRAGMA integrity_check");
    return result[0]?.values?.[0]?.[0] || "unknown";
  }

  function close() {
    if (closed) return;
    persist();
    database.close();
    closed = true;
  }

  return {
    query,
    close,
    integrityCheck,
    path: databasePath,
    mode: "sqlite",
  };
}

module.exports = { createLocalDatabase };
