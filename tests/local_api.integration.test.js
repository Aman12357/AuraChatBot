"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { once } = require("node:events");
const { setTimeout: delay } = require("node:timers/promises");
const test = require("node:test");

const { createLocalDatabase } = require("../local_database");

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server.address().port;
}

async function closeServer(server) {
  if (!server?.listening) return;
  await new Promise((resolve) => server.close(resolve));
}

async function waitForHealth(url, child, output) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (child.exitCode !== null) {
      throw new Error("Aleena server exited before becoming healthy.\n" + output());
    }
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (response.ok) return response.json();
    } catch (_) {
      // Server is still starting.
    }
    await delay(100);
  }
  throw new Error("Timed out waiting for Aleena server.\n" + output());
}

test("local API uses SQLite and the local Ollama endpoint", async () => {
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "aleena-local-api-"));
  let ollamaCalls = 0;
  const receivedModels = [];

  const mockOllama = http.createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/api/tags") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ models: [{ name: "test-model:latest" }] }));
      return;
    }

    if (req.method === "POST" && req.url === "/api/chat") {
      let raw = "";
      for await (const chunk of req) raw += chunk.toString();
      const payload = JSON.parse(raw);
      ollamaCalls += 1;
      receivedModels.push(payload.model);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        model: payload.model,
        message: { role: "assistant", content: "This reply came from the local model." },
        done: true,
      }));
      return;
    }

    res.writeHead(404);
    res.end();
  });

  let appProcess;
  let appOutput = "";
  let database;

  try {
    const ollamaPort = await listen(mockOllama);
    const appPort = await listen(http.createServer());
    // Release the probe port before starting the real app.
    // The short-lived reservation avoids hard-coding a developer port.
    const probePort = appPort;
    // Close the probe immediately; the spawned service binds to the released port.
    // (The probe server is kept only long enough to obtain an available port.)
    // This is deliberately separate from the Ollama mock listener.
    // The probe server instance is obtained below through a second helper.
    void probePort;
  } catch (error) {
    await closeServer(mockOllama);
    fs.rmSync(dataDirectory, { recursive: true, force: true });
    throw error;
  }

  const appProbe = http.createServer();
  const appPort = await listen(appProbe);
  await closeServer(appProbe);
  const ollamaPort = mockOllama.address().port;

  try {
    const env = {
      ...process.env,
      NODE_ENV: "development",
      PORT: String(appPort),
      HOST: "127.0.0.1",
      DATABASE_MODE: "sqlite",
      ALEENA_DATA_DIR: dataDirectory,
      DATABASE_URL: "",
      JWT_SECRET: "test-only-local-secret-with-more-than-32-characters",
      MASTER_EMAIL: "",
      MASTER_SETUP_KEY: "",
      AI_PROVIDER: "ollama",
      OLLAMA_BASE_URL: "http://127.0.0.1:" + ollamaPort,
      OLLAMA_MODEL: "test-model:latest",
      GEMINI_API_KEY: "",
    };

    appProcess = spawn(
      process.execPath,
      [path.join(__dirname, "..", "server.js")],
      { cwd: path.join(__dirname, ".."), env, stdio: ["ignore", "pipe", "pipe"] }
    );

    appProcess.stdout.on("data", (chunk) => { appOutput += chunk.toString(); });
    appProcess.stderr.on("data", (chunk) => { appOutput += chunk.toString(); });

    const baseUrl = "http://127.0.0.1:" + appPort;
    const health = await waitForHealth(baseUrl + "/api/health", appProcess, () => appOutput);

    assert.equal(health.database, "connected");
    assert.equal(health.database_mode, "sqlite");
    assert.equal(health.ai_provider, "ollama");

    const registerResponse = await fetch(baseUrl + "/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "local@example.test",
        password: "local-password-123",
        name: "Local Test",
      }),
    });
    assert.equal(registerResponse.status, 200);
    const registration = await registerResponse.json();
    assert.ok(registration.token);

    const chatResponse = await fetch(baseUrl + "/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + registration.token,
      },
      body: JSON.stringify({ message: "Hello Aleena" }),
    });
    assert.equal(chatResponse.status, 200);
    const chat = await chatResponse.json();

    assert.equal(chat.response, "This reply came from the local model.");
    assert.equal(chat.model, "test-model:latest");
    assert.ok(chat.session_id);
    assert.equal(ollamaCalls, 1);
    assert.deepEqual(receivedModels, ["test-model:latest"]);

    appProcess.kill("SIGTERM");
    await Promise.race([once(appProcess, "exit"), delay(5000)]);
    assert.notEqual(appProcess.exitCode, null, "Aleena server should shut down cleanly");

    database = await createLocalDatabase({ directory: dataDirectory });
    const userRows = database.query(
      "SELECT email FROM users WHERE email = $1",
      ["local@example.test"]
    ).rows;
    const messageRows = database.query(
      "SELECT role, content FROM chat_messages ORDER BY id ASC",
      []
    ).rows;

    assert.equal(userRows.length, 1);
    assert.equal(messageRows.length, 2);
    assert.equal(messageRows[0].content, "Hello Aleena");
    assert.equal(messageRows[1].content, "This reply came from the local model.");
    assert.equal(database.integrityCheck(), "ok");
  } finally {
    if (appProcess && appProcess.exitCode === null) {
      appProcess.kill("SIGTERM");
      await Promise.race([once(appProcess, "exit"), delay(5000)]);
    }
    if (database) database.close();
    await closeServer(mockOllama);
    fs.rmSync(dataDirectory, { recursive: true, force: true });
  }
});
