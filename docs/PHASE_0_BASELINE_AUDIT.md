# Phase 0 — Repository and Deployment Baseline Audit

**Audit date:** 2026-11-08  
**Repository:** \`Aman12357/AuraChatBot\`  
**Application baseline:** \`main\` at \`a429c4ba86cfa4b62e98702bbe4f3abe55870a21\`  
**Audit type:** Read-only repository, GitHub Actions and Render metadata/log review  
**Changes made to running application:** None

## 1. Executive result

The existing web frontend and Node backend have recent successful Render deploy records, and the GitHub validation workflow passes its current build/syntax checks. However, the project does not yet have a meaningful automated functional test suite for the PC assistant, API behavior or Android runtime.

Two production/development blockers need attention before adding new features:

1. Render reports the configured PostgreSQL resource \`aleena-ai-db\` as **suspended by billing**, with its free-plan expiry listed as 2026-11-01. The repository Blueprint wires the Node backend's \`DATABASE_URL\` to this resource. The Node service process is running, but the database-backed login/chat path has not been verified and is expected to be unavailable while its configured database is suspended.
2. Static inspection finds that the PC Python bridge's startup path constructs \`AIClient\`, whose initializer imports \`internet_social_manager\`. That package is absent from the tracked \`main\` tree. This is a likely local Python bridge startup blocker, not yet a runtime reproduction on the user's Windows PC.

A separate older Render service named \`Aleena-AI\` is not declared in the current \`render.yaml\`. Its recent deploys fail during the migration build because its configured database hostname cannot be resolved. It was not modified or deleted.

## 2. Git and CI baseline

- Main branch baseline: \`a429c4ba86cfa4b62e98702bbe4f3abe55870a21\`.
- PR #4 (Android foundation): open, draft and unmerged; 31 changed files. The last PR-described Android CI build passed on commit \`8aa6acf45769f4f47c680249cf54ccdb04b085f4\`. Device verification on Redmi 13 5G / Android 16 remains outstanding.
- PR #5 (architecture roadmap): open and draft. The Phase 1 validation run \`42456943485\` completed successfully for the documentation branch commit \`4d6d1fe557af4dfbe220ab15aee333df2c863e18\`.

### What the current CI actually checks

| Workflow step | Observed result |
|---|---|
| Install Node/backend dependencies | Passed |
| \`node --check server.js\` | Passed |
| Install web dependencies | Passed |
| \`next build\` | Passed |
| \`python -m compileall -q main.py web_server.py\` | Passed |
| PC runtime startup/import integration | Not tested |
| API authentication/chat behavior | Not tested |
| Python unit/integration tests | Not present in current workflow |
| Web UI component/e2e tests | Not present in current workflow |
| Android device instrumentation | Not run |

The inspected root \`package.json\` scripts are \`start\`, \`dev\` and \`migrate\`; there is no test script. The inspected \`web/package.json\` scripts are \`dev\`, \`build\`, \`start\` and \`lint\`; there is no test script. The tracked repository tree has no dedicated tests/specs directory. The Python requirements file does not declare pytest.

**Interpretation:** CI green currently means syntax, frontend compilation/build and Python bytecode compilation passed. It does not demonstrate end-to-end feature behavior.

## 3. PC Python startup risk — static source trace

Evidence in the tracked source:
1. \`web_server.py\` imports \`AIClient\` from \`main.py\`.
2. Its FastAPI \`_startup()\` handler calls \`ai_client = AIClient(settings)\`.
3. \`AIClient.__init__\` in \`main.py\` imports:
   - \`internet_social_manager.internet_access.InternetManager\`
   - \`internet_social_manager.social_media.SocialMediaManager\`
4. The recursive \`main\` Git tree contains no \`internet_social_manager/\` package.

The imports are not shown as optional in the \`AIClient\` constructor. Therefore the FastAPI bridge may fail during startup before voice and local bridge routes become usable. This is a static code-path finding; it must be reproduced on the user's Windows installation before a code fix is chosen.

Other tracked-tree gaps:
- \`market_intelligence/\` is absent, although market handlers import it.
- \`memory/long_term.py\` is absent, although advanced memory methods reference it.
- \`utils/pdf_generator.py\` is absent; the bridge treats PDF generation as optional/disabled.
- \`aura_module.py\` is absent; related account/oversight features are optional/disabled.
- Face-login settings are present in source, but no face-authentication implementation was found in the inspected tree.

Do not treat these absent modules as working capabilities until restored and tested.

## 4. Render deployment baseline — read-only inspection

### Current services declared/used by the application

| Render resource | Observed configuration/status | Baseline interpretation |
|---|---|---|
| \`aleena-ai-backend\` | Node web service, repo \`Aman12357/AuraChatBot\`, branch \`main\`; latest listed deploy of main baseline \`a429c4b\` succeeded on 2026-11-07 15:58 UTC | Process started, logs reported Gemini configured; successful startup is not proof of database-backed API health |
| \`aleena-ai-web\` | Static site, root directory \`web\`; latest listed deploy succeeded on 2026-11-07 15:00 UTC | A Git compare from its deployed commit to current main found no changed files, so the deployed web source matches current main |
| \`aleena-ai-db\` | Render PostgreSQL, free plan, status \`suspended\`, suspender \`billing\`; listed expiry 2026-11-01 13:41 UTC | Critical dependency issue for the configured cloud database path |

The current \`render.yaml\` maps the Node service's \`DATABASE_URL\` from the Render database named \`aleena-ai-db\`. The service logs show that the PostgreSQL pool was initialized, but that message does not establish that a live database query succeeds. The external health URL was not independently reachable from the audit session, so no healthy database response is claimed.

**Required decision:** restore the existing database, migrate to an alternate database, or intentionally change the product's persistence mode. This requires the owner to choose a path. No database was resumed, created, deleted, migrated or queried for user records during this audit.

### Older duplicate Render service

A separate service named \`Aleena-AI\` is also present in the Render workspace:
- runtime shown as Python;
- branch \`main\`;
- build command \`npm install && npm run migrate\`;
- start command \`npm start\`;
- the service is not declared in the current \`render.yaml\`.

Its latest observed deployment of main commit \`a429c4b\` failed. The build logs show \`npm run migrate\` failing with \`getaddrinfo ENOTFOUND\` for the database host configured on that service. The logs also reported three npm audit findings (one moderate, one high and one critical), without enough detail in this audit to attribute them to individual packages.

This appears to be an older/manual duplicate service, but its purpose is not established. Do not delete, suspend, repoint or update it without owner confirmation. A dedicated dependency audit should identify the reported npm advisories before upgrades are proposed.

## 5. Web and API boundaries

- The current web client is a Next.js app with chat, sessions, WebSocket hooks and VRM/avatar components.
- The Node service owns the deployed JWT authentication and chat routes. Its configured cloud AI provider is Gemini; the multi-provider selector lives in the PC Python code, not in the current Node gateway.
- \`web_server.py\` is a separate Python local bridge. Its voice/device capabilities are not equivalent to the Node cloud API.
- The web deployment source was compared with current main; no web-file differences were reported between the two commits.
- No Render service settings, environment variables, database schema, Neon resources or production data were changed.

## 6. Prioritized baseline issues

| Priority | Finding | Next safe action |
|---|---|---|
| P0 | Configured Render PostgreSQL resource is billing-suspended | Ask owner which persistence recovery/migration path is acceptable; no automatic billing action |
| P1 | Older \`Aleena-AI\` Render service repeatedly fails on stale/unresolvable DB host | Confirm whether this service is still needed; then investigate its environment in a separate approved change |
| P1 | Python bridge startup likely fails due absent \`internet_social_manager\` import | Reproduce on Windows and isolate optional integrations before changing startup behavior |
| P1 | No automated feature test suites | Add contract and smoke tests in a separate reviewable test-only change |
| P2 | Missing market and advanced memory modules | Decide restore vs remove references after dependency inventory |
| P2 | PDF/Aura optional modules absent | Keep disabled until implementations and tests exist |
| P2 | npm audit findings on legacy service build | Run a current dependency audit in CI and propose targeted upgrades; do not run blanket \`npm audit fix\` |

## 7. What has and has not been verified

### Verified
- GitHub Actions validation run completed successfully for Node syntax, Next.js production build and Python compilation.
- The Android debug build described in PR #4 has a prior successful CI result, not a device test.
- The current Node backend and web static site have successful Render deploy records.
- Render reports \`aleena-ai-db\` as suspended by billing.
- Render reports repeated build failures for the separate older \`Aleena-AI\` service.
- The tracked source tree does not contain the optional packages/modules listed above.

### Not verified
- Windows desktop assistant startup and UI operation on the user's PC.
- FastAPI local bridge startup on the user's PC.
- Actual database-backed login, chat-history persistence and registration against the suspended database.
- Live backend health response from the external endpoint.
- All web interactions in a browser session.
- Android install, voice, notification, reminder or device-control behavior on the Redmi.
- Actual functioning of market, graph memory, social publishing, face login or PDF generation.

## 8. Phase 0 exit criteria

Phase 0 is **partially complete**. Repository structure, existing CI scope, Render service metadata and key static blockers have been recorded. It is not complete until:
1. The owner chooses how to handle the suspended database and confirms whether the legacy Render service is still required.
2. The user runs the supplied Windows startup check, or provides logs from a fresh PC launch, to reproduce the Python bridge risk.
3. A dedicated non-production API smoke test confirms auth/chat behavior against an available test database.
4. A baseline manual checklist is executed for PC UI, voice, provider switching, memory, tasks, web chat/sessions and Android core flows.

No application source or production infrastructure was changed during this audit.
