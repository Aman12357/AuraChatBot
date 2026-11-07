# 🚀 Aleena AI — Complete Render & GitHub Production Deployment Guide

This comprehensive guide covers step-by-step production deployment of **Aleena AI** on [Render](https://render.com) using GitHub, featuring a **React / Next.js Static Site Frontend**, **Node.js / Express Web Service Backend**, and **Render PostgreSQL Database**.

---

## 🏗️ Production Architecture Overview

```
                        USER BROWSER
                             |
                             v
                 +-----------------------+
                 |   Aleena AI Web UI    |
                 |  Render Static Site   |
                 +-----------+-----------+
                             |
                   HTTPS API | WSS WebSocket
                             v
                 +-----------------------+
                 | Node.js / Express Svc |
                 |  Render Web Service   |
                 +-----------+-----------+
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
         Render PostgreSQL       External AI APIs
        (DATABASE_URL Pool)      (Gemini / OpenAI)
```

---

## 📋 Step 1: GitHub Repository Setup

1. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: prepare Aleena AI for production Render deployment"
   ```
2. **Push to GitHub**:
   ```bash
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/Aleena-AI.git
   git branch -M main
   git push -u origin main
   ```

---

## 🗄️ Step 2: Create Render PostgreSQL Database

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** → **PostgreSQL**.
3. Configure the database settings:
   - **Name**: `aleena-ai-db`
   - **Database**: `aleena_ai_db`
   - **User**: `aleena_user`
   - **Region**: Select closest region (e.g., Oregon / Frankfurt)
   - **Instance Type**: Free or Starter
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (e.g., `postgres://aleena_user:password@dpg-xxxxx-a/aleena_ai_db`).

---

## ⚙️ Step 3: Deploy Backend on Render (Web Service)

1. Click **New +** → **Web Service**.
2. Connect your GitHub repository (`Aleena-AI`).
3. Configure Backend Web Service settings:
   - **Name**: `aleena-ai-backend`
   - **Environment**: `Node`
   - **Region**: Same region as database
   - **Branch**: `main`
   - **Build Command**: `npm install && npm run migrate`
   - **Start Command**: `npm start`
4. Add **Environment Variables**:

| Variable Name | Recommended Value / Description |
|---|---|
| `NODE_ENV` | `production` |
| `PORT` | *(Render provides dynamically)* |
| `DATABASE_URL` | `<Render Internal Database URL>` |
| `JWT_SECRET` | `<Generate strong random string>` |
| `FRONTEND_URL` | `https://aleena-ai-web.onrender.com` |
| `GEMINI_API_KEY` | `<Your Google Gemini API Key>` |

5. Click **Create Web Service**.
6. Copy your Backend Service URL once deployed (e.g. `https://aleena-ai-backend.onrender.com`).

---

## 🌐 Step 4: Deploy Frontend on Render (Static Site)

1. Click **New +** → **Static Site**.
2. Connect your GitHub repository (`Aleena-AI`).
3. Configure Frontend Static Site settings:
   - **Name**: `aleena-ai-web`
   - **Root Directory**: `web`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `out` *(or `dist`)*
4. Add **Environment Variables**:

| Variable Name | Recommended Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://aleena-ai-backend.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://aleena-ai-backend.onrender.com/ws` |

5. Configure **SPA Routing Rewrite Rule** under **Redirects/Rewrites**:
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - **Action**: `Rewrite`
6. Click **Create Static Site**.

---

### Initial administrator setup

1. Set `MASTER_EMAIL` in the local Python bridge environment to the exact email address of the administrator's Aleena account.
2. Use the same strong `JWT_SECRET` value in the Node service and local Python bridge. If Render generated the Node secret, copy that value securely into the local machine's private `.env`; do not commit it.
3. Rebuild the static frontend after changing `NEXT_PUBLIC_API_URL` or `NEXT_PUBLIC_LOCAL_BRIDGE_URL`, because Next.js embeds public environment values at build time.
4. Register the administrator account using that exact email, then sign in. Other users can register normally but will receive 403 responses from master-only local bridge endpoints.
## 🔐 Step 3A: Authentication & Session Isolation

The frontend now requires an account before chat access. New registrations must use a password between 8 and 72 characters. Login and registration are rate-limited.

- Keep `JWT_SECRET` stable and private. Render's Blueprint generates it for the Node service.
- The frontend receives `NEXT_PUBLIC_API_URL` and uses the Node authentication endpoints.
- The Node API validates bearer tokens for chat and WebSocket connections.
- Chat sessions are associated with the authenticated database user; a session ID belonging to another account is rejected.
- For the optional local Python bridge, set `JWT_SECRET` to the exact same value used by the Node service and set `MASTER_EMAIL` to the administrator account email. Set `NEXT_PUBLIC_LOCAL_BRIDGE_URL` only when the local bridge is running.
- The local Python bridge accepts only the configured master account for WebSocket, system settings, generated-document listing, image generation, and master oversight. Aura account REST routes require a valid user token.
- The local bridge's JWT audience is checked separately from the Node API, so Python-issued Aura tokens cannot be used to access Node chat.

Existing legacy chat sessions without a linked `user_id` are intentionally not assigned to an account automatically. They remain in the database but are not visible through authenticated user sessions, because assigning them without reliable ownership information could expose one user's history to another.

## 🛡️ Step 5: Verification & Production Health Checks

After deployment completes:

1. **Test Health Endpoint**:
   ```bash
   curl https://aleena-ai-backend.onrender.com/api/health
   ```
   *Expected Response:*
   ```json
   {
     "status": "ok",
     "service": "Aleena AI",
     "environment": "production",
     "database": "connected"
   }
   ```

2. **Verify Web UI**:
   - Open `https://aleena-ai-web.onrender.com`
   - Verify 3D Digital Human Avatar loads cleanly
   - Send chat messages and verify real-time response streaming via WebSocket

---

## 🔧 Troubleshooting Guide

| Issue | Solution |
|---|---|
| **Database Connection Refused** | Ensure `DATABASE_URL` uses Render's Internal Database URL when backend & DB are in the same region. |
| **WebSocket Fails to Connect** | Ensure `NEXT_PUBLIC_WS_URL` uses `wss://` (secure WebSocket) in production. |
| **CORS Error in Browser** | Verify `FRONTEND_URL` environment variable on backend matches exact frontend URL without trailing slashes. |
| **404 on Page Refresh** | Ensure SPA Rewrite Rule (`/*` -> `/index.html`) is active on Render Static Site settings. |
