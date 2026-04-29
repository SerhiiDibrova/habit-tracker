# Habit Tracker with Streaks

A full-stack, multi-user habit tracking app with daily check-ins, streak calculation, and real-time milestone notifications.

Users sign in with Google or GitHub, create personal habits, check in once per day, and receive WebSocket notifications at streak milestones (3, 7, 30 days).

---

## Table of Contents

1. [Stack](#stack)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Running the Database](#running-the-database)
5. [Running the Backend](#running-the-backend)
6. [Running the Frontend](#running-the-frontend)
7. [Environment Variables](#environment-variables)
8. [OAuth Setup](#oauth-setup)
9. [Database Migrations](#database-migrations)
10. [Running Tests](#running-tests)
11. [API Reference](#api-reference)
12. [WebSocket Protocol](#websocket-protocol)
13. [Business Rules](#business-rules)
14. [Data Model Notes](#data-model-notes)
15. [Known Limitations](#known-limitations)
16. [Docker Notes](#docker-notes)

---

## Stack

| Layer     | Technology                                                |
|-----------|-----------------------------------------------------------|
| Frontend  | Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Forms     | React Hook Form + Zod                                     |
| Data      | TanStack Query                                            |
| Backend   | FastAPI, SQLAlchemy 2.x, Pydantic v2                      |
| Database  | PostgreSQL 16                                             |
| Auth      | Authlib — Google OAuth/OIDC + GitHub OAuth                |
| Auth state| HTTP-only session cookie (backend-managed)                |
| Realtime  | FastAPI WebSocket                                         |
| Migrations| Alembic                                                   |
| Testing   | pytest, httpx, pytest-asyncio                             |

---

## Architecture

```
Browser ──► Next.js (port 3000)
               └── TanStack Query / fetch ──► FastAPI (port 8000)
                                                  ├── api/       (routers)
                                                  ├── auth/      (OAuth, session)
                                                  ├── services/  (business logic)
                                                  └── db/        (SQLAlchemy + PostgreSQL)

Browser ──► WebSocket ws://localhost:8000/ws/notifications
```

### Backend layers (`backend/app/`)

| Package      | Responsibility |
|--------------|----------------|
| `api/`       | FastAPI routers — parse request, call service, return response |
| `auth/`      | Authlib OAuth flow, session read/write, `current_user` dependency |
| `core/`      | Pydantic-settings config, timezone helper, shared error types |
| `db/`        | SQLAlchemy engine, session factory, declarative base |
| `models/`    | ORM models: `User`, `Habit`, `CheckIn`, `MilestoneNotification` |
| `schemas/`   | Pydantic v2 request/response models |
| `services/`  | All business logic: habit CRUD, check-in rules, streak calculation, milestone evaluation |
| `websocket/` | WebSocket endpoint, subscribe/ack protocol, milestone delivery |

Business logic lives in `services/`. Routers call services; services call the DB.

### Frontend structure (`frontend/src/`)

| Path                      | Purpose |
|---------------------------|---------|
| `app/`                    | Next.js App Router pages and layouts |
| `components/ui/`          | shadcn/ui primitives (auto-generated) |
| `features/auth/`          | Auth page components |
| `features/habits/`        | Habit cards, form, filters, calendar |
| `features/notifications/` | Notification panel and toast wiring |
| `lib/api.ts`              | HTTP client |
| `lib/ws.ts`               | WebSocket client |
| `types/api.ts`            | TypeScript types mirroring backend schemas |

---

## Quick Start

```bash
# 1. Start the database
docker-compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then fill in OAuth credentials
alembic upgrade head
uvicorn app.main:app --reload  # → http://localhost:8000

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                    # → http://localhost:3000
```

---

## Running the Database

### With Docker (recommended)

```bash
docker-compose up -d
```

This starts PostgreSQL 16 on port 5432 with:

- user: `postgres`
- password: `postgres`
- database: `habit_tracker`

Data is persisted in a named Docker volume (`postgres_data`).

```bash
docker-compose down      # stop containers
docker-compose down -v   # stop and delete the data volume
```

### Without Docker

Create the database manually and set `DATABASE_URL` in `backend/.env` to match your local credentials:

```bash
psql -U postgres -c "CREATE DATABASE habit_tracker;"
```

---

## Running the Backend

```bash
cd backend

# Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install all dependencies (including dev)
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env — fill in OAuth credentials (see OAuth Setup below)

# Apply migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Running the Frontend

```bash
cd frontend

npm install

cp .env.example .env.local
# Points to http://localhost:8000 by default — no edits needed for local dev

npm run dev
```

The app is available at `http://localhost:3000`.

Other commands:

```bash
npm run build      # production build
npm run lint       # ESLint
npx tsc --noEmit   # type-check
```

---

## Environment Variables

### Backend (`backend/.env`)

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

| Variable               | Required | Description |
|------------------------|----------|-------------|
| `DATABASE_URL`         | Yes      | PostgreSQL DSN in psycopg3 format |
| `SESSION_SECRET`       | Yes      | Signs the HTTP-only session cookie — use a long random string in production |
| `APP_TIMEZONE`         | No       | IANA timezone for "today" (default: `Europe/Warsaw`) |
| `FRONTEND_URL`         | Yes      | Used for CORS and post-OAuth redirect |
| `GOOGLE_CLIENT_ID`     | OAuth    | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | OAuth    | From Google Cloud Console |
| `GOOGLE_REDIRECT_URI`  | OAuth    | Must match the URI registered in Google Cloud Console |
| `GITHUB_CLIENT_ID`     | OAuth    | From GitHub Developer Settings |
| `GITHUB_CLIENT_SECRET` | OAuth    | From GitHub Developer Settings |
| `GITHUB_REDIRECT_URI`  | OAuth    | Must match the URI registered in the GitHub OAuth App |

> **Security:** Never commit `.env`. OAuth secrets must not appear in code or version control.

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

These are read at build time and baked into the client bundle. No changes are needed for local development.

---

## OAuth Setup

### Google

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**.
2. Click **Create Credentials → OAuth 2.0 Client ID**. Choose **Web application**.
3. Under **Authorized redirect URIs** add:
   ```
   http://localhost:8000/api/auth/google/callback
   ```
4. Copy the **Client ID** and **Client Secret** into `backend/.env`:
   ```env
   GOOGLE_CLIENT_ID=<your-client-id>
   GOOGLE_CLIENT_SECRET=<your-client-secret>
   ```

### GitHub

1. Open GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Fill in:
   - **Homepage URL:** `http://localhost:3000`
   - **Authorization callback URL:** `http://localhost:8000/api/auth/github/callback`
3. Click **Register application**, then **Generate a new client secret**.
4. Copy the values into `backend/.env`:
   ```env
   GITHUB_CLIENT_ID=<your-client-id>
   GITHUB_CLIENT_SECRET=<your-client-secret>
   ```

---

## Database Migrations

```bash
cd backend
source .venv/bin/activate

# Apply all pending migrations (run after first setup and after pulling new changes)
alembic upgrade head

# Check current migration state
alembic current

# Create a new migration after changing a model
alembic revision --autogenerate -m "describe what changed"

# Roll back one step
alembic downgrade -1
```

---

## Running Tests

Tests use a separate `habit_tracker_test` database. The test runner **creates it automatically** the first time if it does not exist, using the same credentials as `DATABASE_URL`.

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run a single test file
pytest tests/test_habits.py -v

# Run a single test
pytest tests/test_auth.py::TestGoogleCallback::test_session_cookie_enables_get_me -v

# Override the test database URL
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/habit_tracker_test pytest
```

### Test database URL

By default the runner appends `_test` to the database name in `DATABASE_URL`. Override explicitly with the `TEST_DATABASE_URL` environment variable — only consumed by `tests/conftest.py`, never by the application.

### Test isolation

Each test runs inside a transaction with a nested savepoint. The outer transaction is rolled back after every test — no data persists between tests and no teardown script is needed.

### Coverage

| File | Area |
|------|------|
| `test_auth.py` | Google/GitHub OAuth callback; session cookie establishes authenticated session; profile upsert on re-login; logout |
| `test_habits.py` | Habit CRUD; check-in and undo; duplicate rejection; paused/archived rejection; streak recalculation after undo; search and filters; cross-user authorization |
| `test_websocket.py` | Unauthenticated connection rejected; milestone fired at 3 / 7 / 30 days; no push before subscribe; no resend on reconnect; ack records `acknowledged_at` |
| `test_health.py` | Health endpoint |

Tests never call real Google or GitHub APIs — all OAuth provider responses are mocked.

---

## API Reference

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/auth/google/login` | Redirect to Google OAuth |
| `GET` | `/api/auth/google/callback` | Handle Google callback, set session cookie, redirect to frontend |
| `GET` | `/api/auth/github/login` | Redirect to GitHub OAuth |
| `GET` | `/api/auth/github/callback` | Handle GitHub callback, set session cookie, redirect to frontend |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/me` | Return authenticated user (`401` if not logged in) |

### Habits

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/habits` | List habits (supports `search`, `status`, `completed_today` query params) |
| `POST` | `/api/habits` | Create a habit |
| `GET` | `/api/habits/{id}` | Get habit details with streak stats |
| `PATCH` | `/api/habits/{id}` | Update a habit |
| `DELETE` | `/api/habits/{id}` | Delete a habit (cascades to check-ins and milestone records) |

**Habit list query parameters:**

| Parameter | Values | Default |
|-----------|--------|---------|
| `search` | Free text — matches `name` or `description` (case-insensitive) | — |
| `status` | `all` / `active` / `paused` / `archived` | `all` |
| `completed_today` | `true` / `false` | — (no filter) |

**Habit response shape:**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Morning Run",
  "description": "5 km before work",
  "start_date": "2026-01-01",
  "status": "active",
  "current_streak": 7,
  "best_streak": 14,
  "total_check_ins": 42,
  "completed_today": true,
  "created_at": "2026-01-01T09:00:00Z",
  "updated_at": "2026-04-29T07:30:00Z"
}
```

**Habit statuses:**

| Status | Can check in | Editable |
|--------|-------------|----------|
| `active` | Yes | All fields |
| `paused` | No | All fields |
| `archived` | No | Status field only |

### Check-ins

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/habits/{id}/check-in/today` | Check in for today (`201`). Returns updated habit with recalculated streaks. |
| `DELETE` | `/api/habits/{id}/check-in/today` | Undo today's check-in. Returns updated habit. |
| `GET` | `/api/habits/{id}/check-ins?month=YYYY-MM` | List check-in dates for a calendar month |

Monthly check-ins response:

```json
{ "check_in_dates": ["2026-04-01", "2026-04-15", "2026-04-29"] }
```

### Error format

All errors return a consistent JSON structure:

```json
{ "detail": "Only active habits can be checked in" }
```

---

## WebSocket Protocol

Connect to `ws://localhost:8000/ws/notifications`.

The connection requires an active session cookie. Unauthenticated connections are closed immediately with WebSocket close code `1008`.

The server does **not** push anything on connect. The client must send a subscribe message first.

### Client → Server: subscribe

```json
{
  "type": "subscribe",
  "channel": "milestones"
}
```

After receiving this, the server evaluates all habits for the authenticated user and pushes any newly reached milestones.

### Server → Client: milestone notification

```json
{
  "type": "milestone",
  "notification_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "habit_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "habit_name": "Morning Run",
  "milestone_days": 7,
  "current_streak": 7,
  "sent_at": "2026-04-29T08:00:00+00:00"
}
```

### Client → Server: acknowledge

```json
{
  "type": "ack",
  "notification_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

Records `acknowledged_at` on the `milestone_notifications` row. The server does not send a reply.

---

## Business Rules

### Check-in rules

- **One check-in per habit per calendar day.** Enforced by a unique constraint on `(habit_id, check_in_date)`. Duplicates return `409`.
- Users can only check in for **today** — no backfill, no future dates.
- Users can only **undo today's** check-in.
- Only `active` habits can receive check-ins. Paused and archived habits return `422`.
- A user cannot check in on another user's habit — all queries are scoped by `user_id`.

### Streak calculation

Streaks are **calendar-date based**, computed entirely in the service layer from stored check-in dates.

| Field | Description |
|-------|-------------|
| `current_streak` | Consecutive days ending on today (if checked in) or yesterday (if not) |
| `best_streak` | Historical maximum consecutive run — never decreases |
| `total_check_ins` | Total count of all check-ins for the habit |
| `completed_today` | Whether today's check-in exists |

Rules:
- A single missing day **breaks** the current streak.
- Paused status does **not** preserve the streak — missing days still break it.
- Undoing today's check-in **immediately** recalculates `current_streak`.

**Example** — check-ins on `2026-04-25`, `2026-04-26`, `2026-04-27`, `2026-04-28`, today is `2026-04-28`:

```
current_streak  = 4
best_streak     = 4
total_check_ins = 4
completed_today = true
```

If `2026-04-27` is missing:

```
current_streak  = 1   (only 2026-04-28 is contiguous from today)
best_streak     = 3   (historical max: 25–26–27)
```

### Milestone notifications

A milestone fires when `current_streak >= threshold`:

| Threshold | Meaning |
|-----------|---------|
| 3 | 3-day streak |
| 7 | 7-day streak |
| 30 | 30-day streak |

Rules:
- Each milestone fires **at most once per habit**, enforced by a unique constraint on `(habit_id, milestone_days)` in `milestone_notifications`.
- Milestones are evaluated **only after** the client sends a subscribe message.
- **Reconnecting does not resend** already-delivered milestones.
- If no threshold has been reached, nothing is sent.

### Timezone and "today"

- All timestamps are stored in **UTC**.
- `check_in_date` is a **plain calendar date** (no time component).
- "Today" is determined **server-side** by converting `datetime.now(UTC)` to the timezone in `APP_TIMEZONE` (default `Europe/Warsaw`).
- All date comparisons happen on the backend — the frontend never needs to know or set the timezone.

A user in Warsaw who checks in at 23:59 local time is recording a different calendar date than UTC midnight. This is intentional.

---

## Data Model Notes

### User identity

Each user record is keyed by `(provider, provider_user_id)`:

- A Google login and a GitHub login with the same email address are treated as **two separate accounts**. There is no automatic linking.
- On first login the user record is created automatically (upsert by `provider + provider_user_id`).
- On subsequent logins `email`, `display_name`, and `avatar_url` are refreshed from the provider.

### Cascade deletes

Deleting a habit permanently removes all associated data:
- All **check-ins** (`check_ins` table, `ON DELETE CASCADE`)
- All **milestone notification records** (`milestone_notifications` table, `ON DELETE CASCADE`)

This is enforced at the database level, not only in application code.

### Auth state

Auth state is held entirely in an **HTTP-only, `SameSite=Lax` session cookie** issued and managed by the backend. The frontend JavaScript never has access to the session token. `localStorage` and `sessionStorage` are not used for auth.

In production (`APP_ENV=production`) the session cookie is additionally marked `Secure` so it is only sent over HTTPS.

---

## Known Limitations (MVP)

- **No habit sharing or public links.** Each user sees only their own data.
- **No user invites.**
- **No account linking.** A Google identity and a GitHub identity cannot be merged into one account.
- **No backfill.** Users cannot record check-ins for past days.
- **Paused status does not freeze streaks.** Pausing a habit does not protect the streak counter — missing days still break it.
- **Milestones are not pushed on check-in.** Milestone evaluation only happens when the client sends a subscribe message over the WebSocket. A check-in via the REST API does not automatically trigger a push to other open tabs.
- **Light theme only.** Dark mode is not implemented.
- **No production deployment config.** The repository includes `docker-compose.yml` for the database only; there is no containerization for the backend or frontend.

---

## Docker Notes

`docker-compose.yml` starts **PostgreSQL only**. The backend and frontend run directly on the host machine.

```bash
docker-compose up -d           # start postgres in background
docker-compose logs postgres   # view logs
docker-compose ps              # check health status
docker-compose down            # stop
docker-compose down -v         # stop and wipe data volume
```

To use a non-default port (e.g. if 5432 is already taken by another service):

```yaml
# docker-compose.yml
ports:
  - "5433:5432"
```

```env
# backend/.env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/habit_tracker
```
