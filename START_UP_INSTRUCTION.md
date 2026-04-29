# First-Time Setup — Habit Tracker

Follow these steps in order. Each step must complete successfully before moving to the next.

---

## Prerequisites

Before starting, verify you have the required tools installed.

**Check each one:**

```bash
python --version      # must be 3.12 or higher
node --version        # must be 20 or higher
npm --version         # must be 10 or higher
docker --version      # any recent version
docker compose version  # Docker Compose v2 (bundled with Docker Desktop)
```

If anything is missing or below the minimum version:

| Tool | Install |
|------|---------|
| Python 3.12+ | https://www.python.org/downloads/ or `pyenv` |
| Node.js 20+ | https://nodejs.org/ or `nvm` |
| Docker + Docker Compose | https://www.docker.com/products/docker-desktop/ |

> **Windows users:** All commands below use Unix shell syntax. Run them in Git Bash, WSL, or PowerShell with the noted differences.  
> **Virtualenv activation on Windows (PowerShell):** use `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`.

---

## Project Structure

All commands are run from inside the `habit-tracker/` project folder unless a specific subdirectory is noted.

```
habit-tracker/          ← project root
├── backend/            ← FastAPI app (Python)
├── frontend/           ← Next.js app (Node)
└── docker-compose.yml  ← PostgreSQL only
```

---

## Step 1 — Start the Database

The project uses PostgreSQL. Docker is the simplest way to run it locally.

From the **project root** (`habit-tracker/`):

```bash
docker compose up -d
```

Wait a few seconds, then verify it is healthy:

```bash
docker compose ps
```

You should see `postgres` with status `healthy`. Example output:

```
NAME       IMAGE                COMMAND                  STATUS
postgres   postgres:16-alpine   "docker-entrypoint.s…"   Up (healthy)
```

> **Port 5432 already in use?** Another PostgreSQL is running on your machine.  
> Either stop it, or see the [Port Conflict](#port-5432-already-in-use) section at the end of this file.

---

## Step 2 — Set Up the Backend

All commands in this step run from the **`backend/`** directory:

```bash
cd backend
```

### 2.1 — Create a virtual environment

```bash
python -m venv .venv
```

### 2.2 — Activate the virtual environment

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

Your prompt should now show `(.venv)` at the beginning.

### 2.3 — Install dependencies

```bash
pip install -e ".[dev]"
```

This installs all runtime and development dependencies (FastAPI, SQLAlchemy, Alembic, pytest, etc.).

Verify:
```bash
uvicorn --version    # should print a version number
alembic --version    # should print a version number
pytest --version     # should print a version number
```

### 2.4 — Create the environment file

```bash
cp .env.example .env
```

Open `backend/.env` in a text editor. It looks like this:

```env
APP_ENV=development
APP_HOST=http://localhost:8000
FRONTEND_URL=http://localhost:3000

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/habit_tracker

SESSION_SECRET=change-me-to-a-long-random-string
APP_TIMEZONE=Europe/Warsaw

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/github/callback
```

**Changes to make right now:**

1. **`DATABASE_URL`** — if you used Docker in Step 1, the default value is already correct. Leave it as-is.

2. **`SESSION_SECRET`** — replace `change-me-to-a-long-random-string` with a real random value. Generate one:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Copy the output into `.env`.

3. **OAuth credentials** — leave the four `GOOGLE_*` and `GITHUB_*` lines empty for now. You will fill them in at [Step 4](#step-4--configure-oauth-credentials).

   The app will start without OAuth credentials, but login will not work until Step 4 is complete.

4. **`APP_TIMEZONE`** — optional. Set to your local IANA timezone (e.g. `America/New_York`, `Europe/London`) if you want "today" to align with your clock. Default is `Europe/Warsaw`.

### 2.5 — Apply database migrations

```bash
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0dae4611b4cd, create_initial_tables
```

This creates all tables in the `habit_tracker` database.

### 2.6 — Start the backend server

```bash
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

Verify it is working — open a second terminal and run:

```bash
curl http://localhost:8000/api/health
```

Expected response: `{"status":"ok"}`

Or open `http://localhost:8000/docs` in a browser to see the interactive API documentation.

> Leave this terminal running. Open a new terminal for the next steps.

---

## Step 3 — Set Up the Frontend

All commands in this step run from the **`frontend/`** directory.

Open a new terminal and navigate to the frontend:

```bash
cd frontend
```

### 3.1 — Install dependencies

```bash
npm install
```

This installs Next.js, React, TanStack Query, shadcn/ui, and all other frontend packages. It may take a minute.

### 3.2 — Create the environment file

```bash
cp .env.example .env.local
```

The default contents already point to the local backend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

No changes needed for local development.

### 3.3 — Start the frontend dev server

```bash
npm run dev
```

Expected output:
```
▲ Next.js 16.2.4
- Local:        http://localhost:3000
```

Open `http://localhost:3000` in a browser.

You should see the auth screen with "Continue with Google" and "Continue with GitHub" buttons. The buttons will not work yet until OAuth credentials are configured in Step 4.

> Leave this terminal running.

---

## Step 4 — Configure OAuth Credentials

Both login buttons require OAuth apps registered with Google and GitHub. This is a one-time setup per developer machine.

After completing this step, you will add the credentials to `backend/.env` and restart the backend.

### 4.1 — Create a Google OAuth App

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Navigate to **APIs & Services → Credentials**.
4. Click **Create Credentials → OAuth 2.0 Client ID**.
5. Select application type: **Web application**.
6. Under **Authorized redirect URIs**, click **Add URI** and enter:
   ```
   http://localhost:8000/api/auth/google/callback
   ```
7. Click **Create**.
8. Copy the **Client ID** and **Client Secret** shown on the confirmation screen.

### 4.2 — Create a GitHub OAuth App

1. Go to **GitHub → Settings → Developer settings → OAuth Apps**.
2. Click **New OAuth App**.
3. Fill in:
   - **Application name:** anything (e.g. `Habit Tracker Local`)
   - **Homepage URL:** `http://localhost:3000`
   - **Authorization callback URL:** `http://localhost:8000/api/auth/github/callback`
4. Click **Register application**.
5. On the next screen, click **Generate a new client secret**.
6. Copy the **Client ID** and the generated **Client Secret**.

### 4.3 — Add credentials to `backend/.env`

Open `backend/.env` and fill in the four values:

```env
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here

GITHUB_CLIENT_ID=your-github-client-id-here
GITHUB_CLIENT_SECRET=your-github-client-secret-here
```

### 4.4 — Restart the backend

Go to the backend terminal and press `Ctrl+C`, then start it again:

```bash
uvicorn app.main:app --reload
```

The backend reloads `.env` on startup, so the new credentials are now active.

---

## Step 5 — Verify the Full Application

With all three pieces running (database, backend, frontend), do a quick end-to-end check:

1. Open `http://localhost:3000` in a browser.
2. Click **Continue with Google** (or GitHub).
3. Complete the OAuth flow in the provider's popup.
4. You should be redirected to the dashboard at `http://localhost:3000/dashboard`.
5. Create a habit and check in — the streak counter should update immediately.
6. Open the browser developer tools → Network tab and look for a WebSocket connection to `ws://localhost:8000/ws/notifications`.

**All three services must be running simultaneously:**

| Service | URL | Terminal |
|---------|-----|----------|
| PostgreSQL | `localhost:5432` | Docker (background) |
| Backend | `http://localhost:8000` | Terminal 1 |
| Frontend | `http://localhost:3000` | Terminal 2 |

---

## Running Tests

Tests run against a separate database (`habit_tracker_test`) and auto-create it on first run.

From the **`backend/`** directory with the virtualenv active:

```bash
pytest
```

Expected output ends with:
```
64 passed in 2.xx s
```

No extra setup or database creation is needed — the test runner handles it automatically.

---

## Stopping Everything

```bash
# Stop the frontend (in its terminal)
Ctrl+C

# Stop the backend (in its terminal)
Ctrl+C

# Stop the database
docker compose down
```

To also delete all stored data (habits, check-ins, users):

```bash
docker compose down -v
```

---

## Daily Restart (After First Setup)

Once setup is complete, starting the project each day only requires:

```bash
# Terminal 0 — database (if not already running)
docker compose up -d

# Terminal 1 — backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

No need to reinstall dependencies or reapply migrations unless you pull new changes.

---

## Troubleshooting

### Port 5432 already in use

Another PostgreSQL instance is bound to port 5432. Options:

**Option A — stop the other instance**

Find and stop whatever is using the port, then re-run `docker compose up -d`.

**Option B — use a different port**

Edit `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"    # map host port 5433 to container port 5432
```

Then update `DATABASE_URL` in `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/habit_tracker
```

Then start the database: `docker compose up -d`.

---

### Port 8000 already in use

Start the backend on a different port:
```bash
uvicorn app.main:app --reload --port 8001
```

Then update `frontend/.env.local`:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8001
```

And update `APP_HOST` in `backend/.env`:
```env
APP_HOST=http://localhost:8001
```

---

### Port 3000 already in use

Next.js will automatically try port 3001, 3002, etc. and print the actual URL it bound to. If it picks a different port, update `FRONTEND_URL` in `backend/.env` to match:

```env
FRONTEND_URL=http://localhost:3001
```

Then restart the backend.

---

### `alembic upgrade head` fails — cannot connect to database

The backend cannot reach PostgreSQL. Check:

1. Is Docker running? `docker compose ps` should show `postgres` as `healthy`.
2. Does `DATABASE_URL` in `backend/.env` match the credentials in `docker-compose.yml`?
   - Default Docker credentials: user `postgres`, password `postgres`, host `localhost`, port `5432`, database `habit_tracker`.

---

### `pip install -e ".[dev]"` fails

Make sure the virtualenv is activated (your prompt shows `(.venv)`). If it still fails, try upgrading pip first:

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

---

### OAuth login redirects with `?error=oauth_failed`

Check `backend/.env`:
- Are `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, and `GITHUB_CLIENT_SECRET` filled in?
- Do the redirect URIs in `.env` exactly match what you registered in the provider's dashboard?
  - Google: `http://localhost:8000/api/auth/google/callback`
  - GitHub: `http://localhost:8000/api/auth/github/callback`
- Did you restart the backend after editing `.env`?

---

### `npm run dev` — module not found errors

Node modules were not installed, or were installed with the wrong Node version. Fix:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

### Backend starts but `GET /api/me` returns 401 after login

The session cookie is not being sent. This usually means:
- The frontend is running on a different port than `FRONTEND_URL` in `backend/.env`.
- You are using a browser that blocks cookies for localhost.

Verify `FRONTEND_URL` in `backend/.env` matches the port Next.js actually started on, then restart the backend.
