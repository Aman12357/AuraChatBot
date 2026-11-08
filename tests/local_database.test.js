"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { createLocalDatabase } = require("../local_database");

test("local SQLite persists users, sessions and messages across restarts", async (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "aleena-local-db-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));

  let db = await createLocalDatabase({ directory });

  const userResult = db.query(
    "INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3) RETURNING id, email, name",
    ["local@example.test", "test-hash", "Local User"]
  );

  assert.equal(userResult.rows.length, 1);
  const userId = userResult.rows[0].id;

  const sessionResult = db.query(
    "INSERT INTO chat_sessions (session_id, user_id, title) VALUES ($1, $2, $3) RETURNING session_id, title",
    ["session-local-1", userId, "Local test"]
  );
  assert.equal(sessionResult.rows[0].session_id, "session-local-1");

  db.query(
    "INSERT INTO chat_messages (session_id, role, content, emotion) VALUES ($1, $2, $3, $4)",
    ["session-local-1", "user", "Hello Aleena", "neutral"]
  );
  db.close();

  db = await createLocalDatabase({ directory });

  const history = db.query(
    "SELECT m.role, m.content FROM chat_messages m INNER JOIN chat_sessions s ON s.session_id = m.session_id WHERE m.session_id = $1 AND s.user_id = $2 ORDER BY m.id ASC LIMIT $3",
    ["session-local-1", userId, 20]
  );

  assert.deepEqual(history.rows, [
    { role: "user", content: "Hello Aleena" },
  ]);
  assert.equal(db.integrityCheck(), "ok");
  db.close();
});

test("local SQLite enforces user email uniqueness", async (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "aleena-local-db-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));

  const db = await createLocalDatabase({ directory });
  db.query(
    "INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3)",
    ["duplicate@example.test", "hash-1", "First"]
  );

  assert.throws(() => {
    db.query(
      "INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3)",
      ["duplicate@example.test", "hash-2", "Second"]
    );
  });

  db.close();
});
