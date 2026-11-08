# Aleena Full-Platform Architecture and Implementation Roadmap

**Repository:** Aman12357/AuraChatBot  
**Inspected baseline:** main at a429c4ba86cfa4b62e98702bbe4f3abe55870a21  
**Roadmap branch:** docs/aleena-full-platform-roadmap  
**Scope:** Windows PC assistant, Next.js web companion, Node cloud API, Python local bridge and Android companion.

## 1. Product direction

Build Aleena as a personal AI system with one consistent identity and conversation experience, but separate clients and permission boundaries for PC, web and Android. The objective is not to copy ChatGPT or Gemini feature-for-feature. It is to combine capable model access with user-owned workflows, personal memory and authorized control of the user's own devices.

Target capabilities:
- natural text and voice conversations;
- transparent selection among configured AI providers;
- multimodal input and supported image/document generation;
- research with source attribution;
- user-controlled memory and document retrieval;
- bounded planning and multi-agent task execution;
- PC automation and Android-native actions within OS permissions;
- existing 3D digital-human experience;
- task, reminder and approved integrations;
- clear action history, approvals, errors and recovery.

A feature is complete only after its acceptance tests pass. A successful compile is not proof of functional parity.

## 2. Repository inspection: verified current state

### Existing components

| Component | Source | Observed role |
|---|---|---|
| Windows assistant | main.py (~2,682 lines) | Desktop assistant, AIClient, provider paths, local tasks, voice and command handlers |
| Python local bridge | web_server.py (~1,090 lines) | FastAPI REST/WebSocket bridge, desktop chat/voice/session/settings and image routes |
| Web companion | web/ | Next.js 14, React 18, TypeScript and Tailwind; chat, sessions, WebSocket and VRM avatar components |
| Cloud API | server.js | Express 4, JWT authentication, Gemini chat, PostgreSQL persistence, WebSocket, health/settings |
| Deployment | render.yaml, .env.example | Render web/static services and PostgreSQL configuration |
| Android companion | PR #4, android/** | Kotlin app foundation, existing API login/chat, voice setup, tasks, reminders, core memory, phone actions and WhatsApp notification summaries |

### Existing cloud API contracts to preserve

The inspected Node service includes:
- GET /api/health
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- POST /api/chat (authenticated; message and optional session_id; returns response, session_id, emotion and model)
- GET /api/settings
- authenticated WebSocket at /ws

The Python FastAPI bridge is a separate local desktop service. It has its own health/settings, image generation, WebSocket chat/voice, session/history and desktop-account routes. Do not merge the Python bridge and cloud Node API into one process as part of routine feature work.

### Important gaps discovered

1. The Node cloud API currently configures a single Gemini provider/model from environment variables. It is not yet a multi-provider gateway.
2. The PC AIClient contains Gemini, Groq and Ollama paths and an AgentOrchestrator. However, main.py imports internet_social_manager during AIClient initialization; that package is not in the inspected tracked tree. Market handlers also import market_intelligence, which is not in the tracked tree.
3. PC code references memory.long_term. The tracked source inspected does not contain that implementation. SQLite core/vector/episodic table declarations do not prove a complete vector or graph memory engine is available.
4. Python bridge image generation uses Pollinations; the PC Gemini image path is separate. The Node cloud API has no matching image-generation route in the inspected server source.
5. PDF bridge code attempts to import utils.pdf_generator, which is absent from the inspected tree. Treat PDF generation as unverified until exercised.
6. Face-login configuration flags are not evidence of a working face-authentication feature.
7. The existing web app has reusable avatar components for VRM/digital human, room, emotion, eye tracking, navigation and lip-sync.
8. Android PR #4 is open, draft and unmerged. It is based on main and scoped to android/** plus Android CI. The PR description records a successful CI build at commit 8aa6acf45769f4f47c680249cf54ccdb04b085f4, but real Redmi 13 5G / Android 16 testing remains outstanding.

Audit rule: preserve verified working behavior, isolate missing optional dependencies, and never advertise referenced-but-absent modules as working features.

## 3. Target system architecture

Logical layers:

1. Experience clients
   - Windows desktop client and local runtime.
   - Existing Next.js web companion and avatar.
   - Kotlin Android companion.

2. Stable service contracts
   - Authentication and user identity.
   - Conversation, sessions, history and attachments.
   - Provider/model configuration.
   - Plans, approvals, long-running jobs and realtime status.

3. Intelligence layer
   - Provider router: Gemini, OpenAI, Groq and Ollama adapters.
   - Planner and bounded agent runtime.
   - Retrieval and memory.
   - Policy/permission engine.

4. Tool adapter layer
   - Windows desktop actions.
   - Android intents and supported system APIs.
   - Research/search and approved external APIs.
   - File/document/media tools.
   - Official third-party integrations.

5. Data and audit layer
   - Existing PostgreSQL/Neon for current cloud identity/chat records; new cloud data only after separate approval.
   - Existing PC SQLite state retained and migrated carefully.
   - Android Room/app-private encrypted data.
   - Optional vector index with per-user and per-source isolation.
   - Privacy-safe action audit metadata.

Core rules:
- UI calls domain use cases; business logic does not live inside button handlers.
- Providers, device capabilities and external services sit behind adapters.
- PC-only operations remain on PC; Android uses Android-native capabilities.
- Consequential actions pass through a policy/approval broker.
- Never put provider secrets in web bundles or APKs.
- Use timeouts, cancellation, bounded retries, idempotency and typed errors.
- Keep raw secrets and private notification content out of logs.
- Feature-flag new behavior until tests pass.
- No new paid service, database, production environment variable or migration without separate review and approval.

## 4. Major subsystem design

### A. Conversation, identity and synchronization

Preserve the current Node authentication and chat behavior. First document existing REST/WebSocket payloads and add contract tests. Normalize message, session, attachment, error and event models in client adapters. All clients should show consistent session state, but desktop-local history and cloud history must not be silently conflated.

Implementation:
1. Document the current endpoints and WebSocket event shapes.
2. Add tests for login, expired token, current-user, session ownership, chat persistence and WebSocket auth.
3. Add typed adapters for PC, web and Android without changing current endpoint semantics.
4. Introduce new routes only as additive/versioned routes after backward compatibility is proven.
5. Preserve JWT audience, expiry and account behavior unless a separate migration is approved.

### B. Multi-provider AI gateway

Target providers:
- Gemini: current cloud default.
- Groq: existing PC provider path; verify models and current quotas.
- Ollama: local PC/LAN models.
- OpenAI: optional provider, only after credential and cost controls exist.

Provider interface:
- generate(request, context, options)
- stream(request, context, options)
- embed(texts, options), where supported
- health()
- capabilities: text, vision, tools, embeddings, streaming, context limit.

Routing:
- Respect explicit user model selection.
- Otherwise route by task type, capability, availability, latency and user cost preference.
- Fallback only when enabled and compatible.
- Display the actual provider/model used.
- Never silently fall back to a paid provider.
- Store cloud credentials server-side; store PC-local Ollama configuration locally.
- Android never packages provider API keys; it uses authenticated Aleena APIs or a user-approved secure local-network connection.

Build the provider abstraction in the PC client first, verify it, then expose safe provider choices to web and Android through a server-side gateway.

### C. Planner and agent runtime

Agent roles:
1. Intent/risk classifier.
2. Planner that produces a bounded, inspectable plan.
3. Research agent that returns source-linked findings.
4. Coding agent that works in an explicitly selected workspace.
5. QA agent that runs allowed tests and summarizes evidence.
6. Memory curator that proposes facts for user approval.
7. Executor that invokes approved tools.

Execution lifecycle:
Plan -> show steps -> obtain required approvals -> execute -> verify -> summarize.

Each job has a stable ID, owner, step status, schema-validated inputs, timeouts, cancellation, bounded retries and an audit record. Long jobs need resumable state. Coding runs in a disposable workspace with directory allowlists, CPU/time limits and explicit test commands. No unrestricted shell or filesystem access. Destructive actions, purchases, publishing, message sending, account changes and external writes require confirmation.

### D. Memory and RAG

Memory tiers:
- Working: current conversation.
- Core: stable user-approved facts/preferences.
- Episodic: user-approved events/outcomes with timestamps.
- Semantic: indexed documents and knowledge chunks.
- Procedural: approved reusable workflows.

Storage plan:
- PC: retain SQLite and add explicit migrations/backups.
- Android: Room with encrypted sensitive fields and app-private storage.
- Cloud: use existing PostgreSQL/Neon only for categories the user explicitly chooses to sync. Do not assume vector extensions or new schema are already provisioned.
- Add inspect, edit, delete, export and retention controls.
- Sync is opt-in by category. WhatsApp notification content is excluded by default.
- Retrieval must be user-, source-, permission- and recency-scoped, with source citations.

First audit and repair the missing memory.long_term dependency before promising vector/episodic/graph parity.

### E. Voice and multimodal

PC:
- Preserve SpeechRecognition and Edge-TTS.
- Make STT/TTS providers pluggable.
- Add device selection, cancellation, single-microphone ownership and recovery.
- Keep the existing PC wake-word behavior where verified.

Android:
- Porcupine local wake-word detection is optional and requires the user's AccessKey and Android .ppn keyword model.
- Follow Android microphone foreground-service rules and HyperOS background/autostart policies.
- Use Android SpeechRecognizer/TTS with clear language/provider status.
- Do not promise always-on listening where OS/device restrictions prevent it.

Multimodal:
- Images, PDFs and audio/video are typed, user-selected attachments.
- Define a single image-generation adapter and storage/cleanup policy; do not conflate current Pollinations, PC Gemini image generation and the Node chat API.
- Reuse the existing web VRM avatar first. Test WebView lifecycle and performance on Android before considering a native 3D rewrite.

### F. Device capability broker

Windows allowlisted tools:
- Open approved apps/sites.
- Read supported system status.
- Browse user-selected files/folders.
- Run code only in an explicitly selected workspace.
- Media/volume/display controls.
- Screenshot/clipboard only after a direct user action.

Android allowlisted tools:
- Open apps, Settings, Maps, camera and dialer.
- Read supported battery/RAM status.
- Schedule reminders and local notifications.
- Read notifications only after Notification Access permission.
- Compose WhatsApp drafts; the user reviews and presses Send.
- Restricted settings and consequential actions remain user-confirmed.

Never use root, hidden/private APIs, accessibility abuse, covert scraping, app sandbox bypasses or unattended messaging. Standard NotificationListenerService does not expose personal WhatsApp live typing indicators.

### G. Research and integrations

- Implement search, weather and news through maintained APIs with source links and timestamps.
- Restore or replace the absent internet_social_manager package only after defining contracts and tests.
- Social publishing requires official OAuth/platform APIs and explicit approval before publishing.
- Market/options/gold analysis should be an optional, isolated module with verified timestamped data, risk controls and backtesting tests.
- WhatsApp incoming summaries can only use notification content Android actually exposes.

## 5. Incremental code organization

Do not move existing entry points wholesale. Introduce shared modules gradually:

AuraChatBot/
  main.py                         existing PC entry point
  web_server.py                   existing Python local bridge
  server.js                       existing cloud API
  web/                            existing Next.js app
  android/                        Android companion
  aleena_core/
    conversation/
    providers/
    orchestration/
    memory/
    policy/
    tools/
  services/
    provider_gateway/
    jobs/
  contracts/
    openapi/
    events/
    schemas/
  tests/
    contracts/
    pc/
    api/
    web/
    android/
    security/
  docs/
    ALEENA_FULL_PLATFORM_ROADMAP.md

The Node API remains the cloud authentication/chat entry point in the initial phases. Do not create a competing production backend.

## 6. Proposed 16-week implementation sequence

This is a planning estimate. Each phase has a gate; do not advance while its gate fails.

### Phase 0 — Baseline and reproducible builds (Week 1)
- Freeze a known-good main commit and document backup/rollback.
- Test PC startup, login, chat, voice, provider selection, memory, tasks and image flow.
- Reproduce the missing internet_social_manager import issue.
- Inventory every visible control and its handler.
- Verify current Render/Neon health without changing settings or schema.
- Record Android PR #4 and CI state.
- Add smoke tests and protected-path checks.

Gate: reproducible setup/build instructions, baseline results and known failures documented; no production behavior changed.

### Phase 1 — Stabilize PC and web (Weeks 2–3)
- Fix only verified PC startup/runtime blockers in a dedicated reviewed change.
- Make optional integrations lazy-loaded so missing optional packages cannot break core chat.
- Validate configuration and errors.
- Test Gemini/Groq/Ollama switching and unavailable-provider UI.
- Test chat/session continuity, voice lifecycle, task CRUD and current image path.
- Test Next.js production build and primary screens.
- Leave Node routes, Render and Neon untouched.

Gate: PC and web baseline tests pass; optional integrations cannot crash core chat.

### Phase 2 — Shared contracts (Weeks 4–5)
- Document REST/WebSocket schemas and add contract tests.
- Define normalized conversation, attachment, provider, tool, task and error types.
- Add client adapters without changing current API behavior.
- Define versioning, rate limits, request IDs, idempotency and timeout rules.

Gate: existing web and Android clients work against unchanged current routes.

### Phase 3 — Provider gateway (Weeks 6–7)
- Implement provider interface in PC first.
- Verify Gemini, Groq and Ollama health, selection and failure paths.
- Add OpenAI as optional only after cost/privacy controls.
- Add provider/model settings to PC and web; Android gets safe subset.
- Add task routing and explicit fallback opt-in.
- Keep keys server-side or in secure local storage, never in APK/browser bundles.

Gate: model selection is transparent and no paid fallback occurs without consent.

### Phase 4 — Memory v2 and RAG (Weeks 8–9)
- Inventory current SQLite tables and actual memory modules.
- Repair/replace missing long-term memory dependency only with migration/backup plan.
- Implement core, episodic and document memory with source metadata.
- Add embedding adapters and local search fallback.
- Add inspect/edit/delete/export and category-level sync consent.
- Test retrieval relevance, data isolation and deletion.

Gate: user can inspect/correct/delete memories and disable sync; retrieved facts identify their sources.

### Phase 5 — Planner, tools and coding agent (Weeks 10–11)
- Build structured plans and approval UI.
- Add schema-validated allowlisted tools.
- Run coding agent in disposable workspace; inspect diffs before applying.
- Execute lint/tests in restricted subprocess with resource limits.
- Require approval for writes, shell commands, publishing and external actions.
- Add job status, cancellation and audit history.

Gate: no out-of-allowlist tool execution; no consequential action without approval; code changes have test evidence.

### Phase 6 — Android stability (Weeks 12–13)
- Refactor Android incrementally into UI/domain/data/platform layers.
- Fix repeatable debug/release signing without committing private keys.
- Add unit/instrumentation tests for auth, chat, tasks, reminders, memory and notifications.
- Test mic/TTS/wake-word lifecycle and permission denial.
- Test Redmi 13 5G / Android 16, including HyperOS background/autostart settings.
- Keep WhatsApp notification summaries local-first and lock-screen privacy protected.
- Treat default-assistant role as experimental until device-verified.

Gate: documented Redmi test matrix passes; no dead controls in core flows; no blocking crashes.

### Phase 7 — Web and digital human (Week 14)
- Preserve current Next.js chat/session architecture.
- Add provider status, plan review, memory controls and job activity.
- Reuse existing VRM avatar/room/emotion/lip-sync components.
- Provide accessible fallback if WebGL/avatar fails.
- Test responsive layout, keyboard, WebSocket reconnect and reduced motion.

Gate: current chat remains stable and new features work across desktop/mobile browsers.

### Phase 8 — Integrations and release hardening (Weeks 15–16)
- Restore/replace missing research modules as independent adapters.
- Add official OAuth integrations only after scope/privacy review.
- Verify PDF and image flows; standardize artifact storage and cleanup.
- Add structured logs, health checks, latency/error metrics and privacy-safe audit events.
- Run security/dependency review, backup/restore drill and end-to-end regression suite.
- Prepare signed artifacts after user-approved signing setup.

Gate: release checklist, secret scan, privacy checks and rollback path all pass.

## 7. Acceptance criteria

| Area | Required evidence |
|---|---|
| PC startup | Fresh setup starts even if optional integrations are absent |
| Web | Production build, login, chat, sessions and avatar fallback pass |
| Cloud API | Existing auth/chat/session contracts pass |
| Providers | Gemini/Groq/Ollama verified; optional OpenAI separately tested |
| Voice | Start/stop, wake, transcription, TTS, interruption and recovery tested |
| Memory | Inspect/edit/delete/export, source attribution and opt-out tested |
| Agents | Plan preview, permission denial, approval, cancellation, sandbox and test report verified |
| PC tools | Only allowlisted actions; destructive actions require confirmation |
| Android | Redmi 13 5G / Android 16 install, permissions, chat, voice, reminders and notifications tested |
| WhatsApp | Only exposed notification content; no live typing claim or automatic send |
| Security | No API keys in APK/web bundle; token handling and user isolation tested |
| Reliability | Offline, timeout, expired token, quota and restart cases tested |

## 8. Protected areas and change policy

Protected during this roadmap:
- main.py and current PC behavior;
- web_server.py and local bridge behavior;
- server.js and current REST/WebSocket contracts;
- web/** and current Next.js experience;
- render.yaml, Render service settings and environment variables;
- Neon/PostgreSQL schema and production data.

Changes to protected areas require a separate task, diff review, regression tests and explicit approval before deployment. No migration, paid service, provider fallback, secret rotation or production deployment is authorized by this roadmap document.

## 9. Immediate next actions

1. Run the Phase 0 baseline tests on a known-good PC setup.
2. Isolate the missing PC optional-module imports before expanding features.
3. Review PR #4 separately; it remains Android-only, draft and unmerged.
4. Add contract tests for existing Node endpoints before backend expansion.
5. Implement provider abstraction in PC first, then expose safe options to web/mobile.
6. Build approval-based planning and tool registry before autonomous coding/device control.
7. Verify each Android feature on the Redmi before declaring parity.

## 10. Success definition

Aleena is successful when the same user can move between PC, web and Android with consistent identity and conversations; choose models transparently; control only authorized devices/data; inspect and delete personal memory; delegate bounded multi-step work; and see exactly what Aleena did and what it could not do.

The goal is a reliable, user-owned personal AI system—not an unverified feature checklist or an unsupported claim that Aleena already surpasses commercial AI platforms.
