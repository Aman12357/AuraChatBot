"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const { execFileSync } = require("node:child_process");
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
      throw new Error("Aleena server exited before becoming healthy.\\n" + output());
    }
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (response.ok) return response.json();
    } catch (_) {
      // Server is still starting.
    }
    await delay(100);
  }
  throw new Error("Timed out waiting for Aleena server.\\n" + output());
}

test("local API stores data in SQLite and selects Gemini without cloud fallbacks", async () => {
  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "aleena-local-api-"));
  let appProcess;
  let appOutput = "";
  let database;

  try {
    const appProbe = http.createServer();
    const appPort = await listen(appProbe);
    await closeServer(appProbe);

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
      AI_PROVIDER: "gemini",
      GEMINI_API_KEY: "",
      GEMINI_MODEL: "test-gemini-model",
      GEMINI_REASONING_MODEL: "test-reasoning-model",
      GEMINI_THINKING_LEVEL: "minimal",
      GEMINI_COMPLEX_THINKING_LEVEL: "low",
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
    assert.equal(health.ai_provider, "gemini");
    assert.equal(health.ai_provider_configured, false);
    assert.equal(health.model, "test-gemini-model");
    assert.equal(health.reasoning_model, "test-reasoning-model");
    assert.equal(health.thinking_level, "minimal");

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

    const aiTestResponse = await fetch(baseUrl + "/api/ai-test", {
      headers: { Authorization: "Bearer " + registration.token },
    });
    assert.equal(aiTestResponse.status, 503);
    const aiTest = await aiTestResponse.json();
    assert.equal(aiTest.status, "error");
    assert.match(aiTest.message, /GEMINI_API_KEY/);

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

    assert.equal(chat.response, "Hello! I am Aleena. How can I help you today?");
    assert.equal(chat.model, "test-gemini-model");
    assert.equal(chat.thinking_level, "minimal");
    assert.ok(chat.session_id);

    const streamingResponse = await fetch(baseUrl + "/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        Authorization: "Bearer " + registration.token,
      },
      body: JSON.stringify({
        message: "Hello from streaming chat",
        session_id: chat.session_id,
      }),
    });
    assert.equal(streamingResponse.status, 200);
    assert.ok((streamingResponse.headers.get("content-type") || "").includes("text/event-stream"));
    const streamedBody = await streamingResponse.text();
    const streamEvents = streamedBody
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => JSON.parse(line.slice(5).trim()));

    assert.ok(streamEvents.some((event) => event.type === "token"));
    const streamDone = streamEvents.find((event) => event.type === "done");
    assert.ok(streamDone);
    assert.equal(streamDone.response, "Hello! I am Aleena. How can I help you today?");
    assert.equal(streamDone.model, "test-gemini-model");
    assert.equal(streamDone.thinking_level, "minimal");

    const complexResponse = await fetch(baseUrl + "/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + registration.token,
      },
      body: JSON.stringify({
        message: "Please debug this Java code and explain the fix",
        session_id: chat.session_id,
      }),
    });
    assert.equal(complexResponse.status, 200);
    const complexChat = await complexResponse.json();
    assert.equal(complexChat.model, "test-reasoning-model");
    assert.equal(complexChat.thinking_level, "low");

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
    assert.equal(messageRows.length, 6);
    assert.equal(messageRows[0].content, "Hello Aleena");
    assert.equal(messageRows[1].content, "Hello! I am Aleena. How can I help you today?");
    assert.equal(messageRows[2].content, "Hello from streaming chat");
    assert.equal(messageRows[3].content, "Hello! I am Aleena. How can I help you today?");
    assert.equal(messageRows[4].content, "Please debug this Java code and explain the fix");
    assert.equal(messageRows[5].content, "I can help you with coding, debugging, explanations, algorithms and software projects.");
    assert.equal(database.integrityCheck(), "ok");
  } finally {
    if (appProcess && appProcess.exitCode === null) {
      appProcess.kill("SIGTERM");
      await Promise.race([once(appProcess, "exit"), delay(5000)]);
    }
    if (database) database.close();
    fs.rmSync(dataDirectory, { recursive: true, force: true });
  }
});


test("optional local HTTPS API rejects unpaired devices and accepts the local pairing key", async (t) => {
  try {
    execFileSync("openssl", ["version"], { stdio: "ignore" });
  } catch (_) {
    t.skip("OpenSSL is required to create the temporary TLS test certificate.");
    return;
  }

  const dataDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "aleena-local-lan-"));
  const certPath = path.join(dataDirectory, "test-cert.pem");
  const keyPath = path.join(dataDirectory, "test-key.pem");
  const pairingPath = path.join(dataDirectory, "local-pairing.key");
  const pairingKey = "test-only-local-pairing-key-with-sufficient-length";

  execFileSync("openssl", [
    "req", "-x509", "-newkey", "rsa:2048", "-nodes",
    "-keyout", keyPath,
    "-out", certPath,
    "-days", "1",
    "-subj", "/CN=localhost",
    "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
  ], { stdio: "ignore" });
  fs.writeFileSync(pairingPath, pairingKey, "utf8");

  let appProcess;
  let appOutput = "";

  try {
    const appProbe = http.createServer();
    const appPort = await listen(appProbe);
    await closeServer(appProbe);

    const tlsProbe = http.createServer();
    const tlsPort = await listen(tlsProbe);
    await closeServer(tlsProbe);

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
      AI_PROVIDER: "gemini",
      GEMINI_API_KEY: "",
      GEMINI_MODEL: "test-gemini-model",
      LOCAL_LAN_ENABLED: "true",
      LOCAL_LAN_HOST: "127.0.0.1",
      LOCAL_LAN_PORT: String(tlsPort),
      LOCAL_TLS_CERT_FILE: certPath,
      LOCAL_TLS_KEY_FILE: keyPath,
      LOCAL_PAIRING_KEY_FILE: pairingPath,
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
    assert.equal(health.database_mode, "sqlite");
    assert.equal(health.ai_provider, "gemini");

    async function secureHealth(headers = {}) {
      return new Promise((resolve, reject) => {
        const request = https.get(
          "https://127.0.0.1:" + tlsPort + "/api/health",
          { rejectUnauthorized: false, headers, timeout: 5000 },
          (response) => {
            let raw = "";
            response.setEncoding("utf8");
            response.on("data", (chunk) => { raw += chunk; });
            response.on("end", () => resolve({
              status: response.statusCode,
              body: raw ? JSON.parse(raw) : {},
            }));
          }
        );
        request.on("timeout", () => request.destroy(new Error("HTTPS test request timed out.")));
        request.on("error", reject);
      });
    }

    let denied;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      try {
        denied = await secureHealth();
        break;
      } catch (_) {
        await delay(100);
      }
    }
    assert.ok(denied, "The optional HTTPS listener should start.");
    assert.equal(denied.status, 403);
    assert.match(denied.body.error, /not paired/i);

    const allowed = await secureHealth({ "X-Aleena-Pairing-Key": pairingKey });
    assert.equal(allowed.status, 200);
    assert.equal(allowed.body.database_mode, "sqlite");
    assert.equal(allowed.body.ai_provider, "gemini");
  } finally {
    if (appProcess && appProcess.exitCode === null) {
      appProcess.kill("SIGTERM");
      await Promise.race([once(appProcess, "exit"), delay(5000)]);
    }
    fs.rmSync(dataDirectory, { recursive: true, force: true });
  }
});
