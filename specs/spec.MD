# Habit Tracker with Streaks — Technical Specification

**Version:** 1.0  
**Status:** Active  
**Audience:** Developers and AI coding assistants implementing this project

---

## Table of Contents

1. [Product Goal](#1-product-goal)
2. [Scope and Rules](#2-scope-and-rules)
3. [Architecture](#3-architecture)
4. [Backend Requirements](#4-backend-requirements)
   - 4.1 [Habit Management](#41-habit-management)
   - 4.2 [Daily Check-ins](#42-daily-check-ins)
   - 4.3 [Streak Calculation](#43-streak-calculation)
   - 4.4 [Search and Filters](#44-search-and-filters)
5. [Frontend Requirements](#5-frontend-requirements)
   - 5.1 [Auth Page](#51-auth-page)
   - 5.2 [Dashboard](#52-dashboard)
   - 5.3 [Create / Edit Habit](#53-create--edit-habit)
   - 5.4 [Habit Details](#54-habit-details)
   - 5.5 [Notifications UI](#55-notifications-ui)
6. [Database Model](#6-database-model)
7. [API Design](#7-api-design)
8. [Auth Flow](#8-auth-flow)
9. [WebSocket Notifications](#9-websocket-notifications)
10. [Testing Requirements](#10-testing-requirements)
11. [Environment Variables](#11-environment-variables)
12. [Implementation Phases](#12-implementation-phases)
13. [Definition of Done](#13-definition-of-done)

---

## 1. Product Goal

Build a full-stack, multi-user **Habit Tracker with Streaks** MVP.

Users can:
- Sign in with Google or GitHub (SSO only)
- Create and manage personal habits
- Check in daily to log progress
- View current streak, best streak, and total check-ins
- Review monthly check-in history on a calendar grid
- Search and filter their habits
- Receive real-time milestone notifications via WebSocket

The project must run locally and include a backend test suite.

---

## 2. Scope and Rules

### Multi-user isolation

- The app supports multiple users.
- Each user sees **only their own data**.
- Every query for habits, check-ins, and notifications must be scoped by the authenticated `user_id`.

### What is explicitly out of scope (MVP)

- No habit sharing or public links
- No user invites
- No account linking between Google and GitHub identities (treated as separate accounts)

### UI

- Light theme only
- Must work locally without any cloud deployment

---

## 3. Architecture

### Tech Stack

| Layer       | Technology                                                |
|-------------|-----------------------------------------------------------|
| Frontend    | Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui  |
| Forms       | React Hook Form, Zod                                      |
| Data fetch  | TanStack Query                                            |
| Icons       | lucide-react                                              |
| Backend     | FastAPI, SQLAlchemy 2.x, Pydantic v2                      |
| Database    | PostgreSQL                                                |
| Migrations  | Alembic                                                   |
| Auth        | Authlib (Google OAuth/OIDC, GitHub OAuth)                 |
| Auth state  | HTTP-only session cookie (backend-owned)                  |
| Realtime    | FastAPI WebSocket                                         |
| Testing     | pytest, httpx, pytest-asyncio                             |

### Repository Layout

```
habit-tracker/
├── README.md
├── SPEC.md
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers and HTTP endpoints
│   │   ├── auth/          # OAuth flow, session helpers, current-user dependency
│   │   ├── core/          # Settings, security, timezone helper, error helpers
│   │   ├── db/            # SQLAlchemy engine, session, base model
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic (habit, check-in, streak, milestone)
│   │   ├── websocket/     # WebSocket endpoint, connection manager, notification delivery
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/
    │   ├── components/
    │   ├── features/
    │   │   ├── auth/
    │   │   ├── habits/
    │   │   └── notifications/
    │   ├── hooks/
    │   ├── lib/
    │   └── types/
    ├── public/
    ├── package.json
    ├── components.json
    ├── next.config.ts
    └── .env.example
```

### Backend Layer Responsibilities

| Layer        | Responsibility                                              |
|--------------|-------------------------------------------------------------|
| `api`        | FastAPI routers, request parsing, response serialization    |
| `auth`       | OAuth flow, session creation, `current_user` dependency     |
| `core`       | App settings, timezone helper, shared error utilities       |
| `db`         | Engine setup, session factory, declarative base             |
| `models`     | SQLAlchemy ORM models                                       |
| `schemas`    | Pydantic v2 request/response schemas                        |
| `services`   | Business logic: habits, check-ins, streaks, milestones      |
| `websocket`  | WebSocket endpoint, subscribe/ack handling, notification push|

### Frontend Key Files

```
src/lib/api.ts                                         # HTTP client (TanStack Query base)
src/lib/ws.ts                                          # WebSocket client
src/types/api.ts                                       # Shared API types
src/features/habits/components/HabitCard.tsx
src/features/habits/components/HabitForm.tsx
src/features/habits/components/HabitFilters.tsx
src/features/habits/components/HabitCalendar.tsx
src/features/notifications/components/NotificationPanel.tsx
```

---

## 4. Backend Requirements

### 4.1 Habit Management

#### Fields

| Field         | Type      | Constraints              |
|---------------|-----------|--------------------------|
| `id`          | UUID      | Primary key              |
| `user_id`     | UUID      | FK → users.id, not null  |
| `name`        | string    | Not null                 |
| `description` | text      | Nullable                 |
| `start_date`  | date      | Not null                 |
| `status`      | string    | Not null                 |
| `created_at`  | timestamp | Not null                 |
| `updated_at`  | timestamp | Not null                 |

#### Allowed Statuses

| Status     | Can receive check-ins | Editable         |
|------------|-----------------------|------------------|
| `active`   | Yes                   | Yes              |
| `paused`   | No                    | Yes              |
| `archived` | No                    | Status only      |

#### Business Rules

- Only the owner can create, read, update, or delete their habits.
- Deleting a habit cascades to all its check-ins and milestone notification records.

---

### 4.2 Daily Check-ins

#### Fields

| Field          | Type      | Constraints                     |
|----------------|-----------|---------------------------------|
| `id`           | UUID      | Primary key                     |
| `habit_id`     | UUID      | FK → habits.id (cascade delete) |
| `user_id`      | UUID      | FK → users.id, not null         |
| `check_in_date`| date      | Not null                        |
| `created_at`   | timestamp | Not null                        |

**Unique constraint:** `(habit_id, check_in_date)`

#### Business Rules

- Only **one check-in per habit per day**.
- Users can check in **only for today** (no backfill, no future dates).
- Users can **undo only today's** check-in.
- Only `active` habits can receive check-ins.
- A user cannot check in on behalf of another user.

---

### 4.3 Streak Calculation

For every habit, the backend calculates:

| Field             | Description                                    |
|-------------------|------------------------------------------------|
| `current_streak`  | Consecutive calendar days ending today (or yesterday if not checked in today) |
| `best_streak`     | Historical maximum streak                      |
| `total_check_ins` | Total count of all check-ins                   |
| `completed_today` | Whether today's check-in exists                |

#### Rules

- Streak is based on **consecutive calendar days**.
- Missing a single day **breaks** the current streak.
- Best streak is the historical maximum and never decreases.
- Undoing today's check-in **recalculates** the current streak immediately.
- Paused status does **not** preserve streak in the MVP.
- Streaks are computed from ordered check-in dates in the service layer.

#### Example

Given check-ins on: `2026-04-25`, `2026-04-26`, `2026-04-27`, `2026-04-28`

If today is `2026-04-28`:

```
current_streak  = 4
best_streak     = 4
total_check_ins = 4
completed_today = true
```

If `2026-04-27` is missing:

```
current_streak  = 1   (only 2026-04-28)
best_streak     = 3   (historical max from 25–27)
```

---

### 4.4 Search and Filters

The habit list endpoint supports the following query parameters:

| Parameter        | Values                                         |
|------------------|------------------------------------------------|
| `search`         | Free text — matches `name` or `description`    |
| `status`         | `all` \| `active` \| `paused` \| `archived`    |
| `completed_today`| `all` \| `completed_today` \| `not_completed_today` |

The `completed_today` filter applies primarily to `active` habits.

**Example:**

```
GET /api/habits?search=read&status=active&completed_today=true
```

---

## 5. Frontend Requirements

### 5.1 Auth Page

**Route:** `/`

Shown when the user is unauthenticated:

- App title
- Short value proposition
- "Continue with Google" button
- "Continue with GitHub" button
- Loading state while OAuth redirect is in progress

---

### 5.2 Dashboard

**Route:** `/dashboard`

**Top bar:**
- User avatar and display name
- Logout button
- Create habit button

**Filters bar:**
- Search input
- Status filter (all / active / paused / archived)
- Completed today filter (all / completed / not completed)

**Habit list — each card shows:**

| Field              | Notes                                |
|--------------------|--------------------------------------|
| Name               |                                      |
| Description        |                                      |
| Status badge       |                                      |
| Current streak     |                                      |
| Best streak        |                                      |
| Total check-ins    |                                      |
| Completed today    | Visual indicator                     |
| Check-in button    | Or Undo if already checked in today  |
| Edit button        |                                      |
| Details button     |                                      |
| Delete button      |                                      |

**Required states:**
- Loading skeleton
- Empty state (no habits yet)
- Empty state (no search results)
- Visible error state

---

### 5.3 Create / Edit Habit

Displayed as a **modal or drawer**.

**Fields:**

| Field        | Validation         |
|--------------|--------------------|
| Name         | Required           |
| Description  | Optional           |
| Start date   | Required           |
| Status       | Required (select)  |

**Requirements:**
- Built with React Hook Form + Zod
- Inline validation errors
- Submit button disabled while saving
- Visible API error message if save fails

---

### 5.4 Habit Details

Can be a **page or drawer**.

Shows:
- Full habit info
- Current month calendar/grid with checked days highlighted
- Current streak, best streak, total check-ins
- Empty state when no check-ins exist yet

---

### 5.5 Notifications UI

- Toast when a milestone event arrives via WebSocket
- In-page notification panel showing recent notifications from the current session

---

## 6. Database Model

### `users`

| Column             | Type      | Constraints                          |
|--------------------|-----------|--------------------------------------|
| `id`               | UUID      | Primary key                          |
| `provider`         | string    | Not null                             |
| `provider_user_id` | string    | Not null                             |
| `email`            | string    | Nullable                             |
| `display_name`     | string    | Not null                             |
| `avatar_url`       | string    | Nullable                             |
| `created_at`       | timestamp | Not null                             |
| `updated_at`       | timestamp | Not null                             |

**Unique constraint:** `(provider, provider_user_id)`

---

### `habits`

| Column        | Type      | Constraints              |
|---------------|-----------|--------------------------|
| `id`          | UUID      | Primary key              |
| `user_id`     | UUID      | FK → users.id, not null  |
| `name`        | string    | Not null                 |
| `description` | text      | Nullable                 |
| `start_date`  | date      | Not null                 |
| `status`      | string    | Not null                 |
| `created_at`  | timestamp | Not null                 |
| `updated_at`  | timestamp | Not null                 |

**Index:** `(user_id, status)`

---

### `check_ins`

| Column          | Type      | Constraints                     |
|-----------------|-----------|---------------------------------|
| `id`            | UUID      | Primary key                     |
| `habit_id`      | UUID      | FK → habits.id (cascade delete) |
| `user_id`       | UUID      | FK → users.id, not null         |
| `check_in_date` | date      | Not null                        |
| `created_at`    | timestamp | Not null                        |

**Unique constraint:** `(habit_id, check_in_date)`

---

### `milestone_notifications`

| Column            | Type      | Constraints                     |
|-------------------|-----------|---------------------------------|
| `id`              | UUID      | Primary key                     |
| `user_id`         | UUID      | FK → users.id, not null         |
| `habit_id`        | UUID      | FK → habits.id (cascade delete) |
| `milestone_days`  | integer   | Not null                        |
| `sent_at`         | timestamp | Not null                        |
| `acknowledged_at` | timestamp | Nullable                        |

**Unique constraint:** `(habit_id, milestone_days)`

---

## 7. API Design

### Auth Endpoints

| Method | Path                          | Description                        |
|--------|-------------------------------|------------------------------------|
| `GET`  | `/api/auth/google/login`      | Redirect to Google OAuth           |
| `GET`  | `/api/auth/google/callback`   | Handle Google OAuth callback       |
| `GET`  | `/api/auth/github/login`      | Redirect to GitHub OAuth           |
| `GET`  | `/api/auth/github/callback`   | Handle GitHub OAuth callback       |
| `POST` | `/api/auth/logout`            | Clear session cookie               |
| `GET`  | `/api/me`                     | Return the current authenticated user |

### Habit Endpoints

| Method   | Path                    | Description              |
|----------|-------------------------|--------------------------|
| `GET`    | `/api/habits`           | List habits (with filters) |
| `POST`   | `/api/habits`           | Create a habit           |
| `GET`    | `/api/habits/{id}`      | Get habit details        |
| `PATCH`  | `/api/habits/{id}`      | Update a habit           |
| `DELETE` | `/api/habits/{id}`      | Delete a habit           |

### Check-in Endpoints

| Method   | Path                                      | Description                    |
|----------|-------------------------------------------|--------------------------------|
| `POST`   | `/api/habits/{id}/check-in/today`         | Check in for today             |
| `DELETE` | `/api/habits/{id}/check-in/today`         | Undo today's check-in          |
| `GET`    | `/api/habits/{id}/check-ins?month=YYYY-MM`| List check-ins for a month     |

### WebSocket Endpoint

| Protocol    | Path                  | Description                      |
|-------------|-----------------------|----------------------------------|
| `WebSocket` | `/ws/notifications`   | Authenticated milestone channel  |

### Error Response Format

All errors return a consistent JSON structure:

```json
{
  "detail": "Only active habits can be checked in"
}
```

Or, for structured errors:

```json
{
  "error": {
    "code": "HABIT_NOT_ACTIVE",
    "message": "Only active habits can be checked in"
  }
}
```

The exact shape must be chosen at the start of implementation and used consistently throughout the API.

---

## 8. Auth Flow

### Providers

- Google OAuth / OpenID Connect
- GitHub OAuth

### Behavior

1. User clicks "Continue with Google" or "Continue with GitHub".
2. Backend redirects user to the provider's authorization URL.
3. Provider redirects back to the backend callback.
4. Backend exchanges the code for tokens and fetches the user profile.
5. Backend upserts a local `users` record (auto-creates on first login).
6. Backend sets a **secure, HTTP-only session cookie**.
7. Frontend redirects to `/dashboard`.
8. On page refresh, the session cookie is validated server-side — user stays authenticated.
9. Logout clears the session cookie.

### Session Rules

- Auth state lives in an **HTTP-only session cookie** managed entirely by the backend.
- Session data must **never be exposed** to frontend JavaScript.
- OAuth secrets must **never be stored in code** — use environment variables only.
- **Do not use** `localStorage` or `sessionStorage` for auth tokens.

### User Model Notes

- Google and GitHub identities are treated as **separate accounts** (no automatic linking).
- Account linking is **not** required for MVP.
- Uniqueness is enforced by `(provider, provider_user_id)`.

---

## 9. WebSocket Notifications

### Overview

After connecting, the client must send a **subscribe message** before the server evaluates milestones. The server does not push anything immediately on connection.

### Milestone Thresholds

| Days | Description    |
|------|----------------|
| 3    | 3-day streak   |
| 7    | 7-day streak   |
| 30   | 30-day streak  |

### Rules

- The WebSocket connection must be authenticated via the session cookie.
- The server evaluates milestones **only after** receiving a valid subscribe message.
- Each milestone is sent **at most once** per habit — tracked in `milestone_notifications`.
- Reconnecting does **not** resend already-delivered milestone notifications.
- If no milestone threshold is reached, the server sends nothing.
- The client may send an `ack` message; the server records `acknowledged_at`.

### Message Protocol

**Client → Server: subscribe**

```json
{
  "type": "subscribe",
  "channel": "milestones"
}
```

**Client → Server: acknowledgement**

```json
{
  "type": "ack",
  "notification_id": "uuid"
}
```

**Server → Client: milestone notification**

```json
{
  "type": "milestone",
  "notification_id": "uuid",
  "habit_id": "uuid",
  "habit_name": "Morning Reading",
  "milestone_days": 7,
  "current_streak": 7,
  "sent_at": "2026-04-28T10:00:00Z"
}
```

---

## 10. Testing Requirements

All tests use **pytest**. Tests must **not** call real Google or GitHub APIs.

### Required Test Cases

#### 1. SSO Login — Success Path (mocked provider)

- Mocked provider response works correctly
- Local user record is auto-created on first login
- Session cookie is established
- `GET /api/me` returns the authenticated user

#### 2. Create Habit and Check In Today

- Authenticated user creates a habit successfully
- User checks in for today
- Response shows: `total_check_ins = 1`, `current_streak = 1`, `best_streak = 1`, `completed_today = true`

#### 3. Prevent Duplicate Check-in

- Checking in twice for the same habit on the same date fails
- API returns a clear validation error

#### 4. Authorization Isolation

User A **cannot**:
- View User B's habits
- Update User B's habits
- Delete User B's habits
- Check in on User B's habits
- Undo User B's check-ins

#### 5. WebSocket Milestone Notifications

- 3-day milestone is sent after 3 consecutive check-ins
- 7-day milestone is sent after 7 consecutive check-ins
- 30-day milestone is sent after 30 consecutive check-ins
- Server does **not** push milestone without a subscribe message
- Reconnecting does **not** resend an already-delivered milestone

### Suggested Additional Tests

| Scenario                                     |
|----------------------------------------------|
| Paused habit cannot be checked in            |
| Archived habit cannot be checked in          |
| Undoing today's check-in recalculates streak |
| Search by name returns correct results       |
| Search by description returns correct results|
| Status filter returns correct results        |
| `completed_today` filter returns correct results |

---

## 11. Environment Variables

### `backend/.env.example`

```env
APP_ENV=development
APP_HOST=http://localhost:8000
FRONTEND_URL=http://localhost:3000

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/habit_tracker

SESSION_SECRET=change-me
APP_TIMEZONE=Europe/Warsaw

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/github/callback
```

### `frontend/.env.example`

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

### Timezone Strategy

- All timestamps are stored in **UTC**.
- `check_in_date` is stored as a **calendar date** (no time component).
- The backend determines "today" using the `APP_TIMEZONE` environment variable.
- README must document: how today is determined, how streaks are calculated, and that streaks are calendar-date based.

---

## 12. Implementation Phases

Claude Code must implement one phase at a time. After each phase: show changed files, explain key decisions briefly, run available tests or linters, and **stop if errors remain** before proceeding.

| Phase | Name                  | Deliverables                                                                               |
|-------|-----------------------|--------------------------------------------------------------------------------------------|
| 1     | Scaffold              | Repository structure, config files, `.env.example` files, README skeleton. No business logic. |
| 2     | Backend Foundation    | Settings, DB session, SQLAlchemy base, health endpoint, `/api/me`, initial Alembic setup.  |
| 3     | Auth                  | Google OAuth, GitHub OAuth, session cookie, logout, auto-create user, test auth mock/stub. |
| 4     | Habits & Check-ins    | Habit CRUD, check-in today, undo today, ownership checks, streak service, search/filter, tests. |
| 5     | WebSocket             | Authenticated WebSocket, subscribe handling, milestone evaluation, persistence, ack, tests.|
| 6     | Frontend              | Auth screen, dashboard, habit form, details screen, filters/search, check-in/undo, WebSocket notifications. |
| 7     | README & Polish       | Complete README: setup, tests, OAuth configuration, API summary, WebSocket docs, timezone docs. |

### Recommended Implementation Order within Phases

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
```

---

## 13. Definition of Done

The project is complete when **all** of the following are true:

### Auth

- [ ] Google login works end-to-end
- [ ] GitHub login works end-to-end
- [ ] Local user record is auto-created on first login
- [ ] Logout works and clears session
- [ ] Session persists after page refresh

### Habits & Check-ins

- [ ] Habit CRUD (create, read, update, delete) works
- [ ] Users cannot access or modify other users' data
- [ ] Today's check-in works
- [ ] Today's undo works
- [ ] Duplicate check-ins are rejected with a clear error

### Streaks

- [ ] `current_streak` is calculated correctly
- [ ] `best_streak` is calculated correctly
- [ ] `total_check_ins` is calculated correctly
- [ ] `completed_today` reflects today's check-in status

### Search & Filters

- [ ] Search by name works
- [ ] Search by description works
- [ ] Status filter works
- [ ] `completed_today` filter works

### WebSocket

- [ ] Milestone notifications fire at 3, 7, and 30 days
- [ ] Milestone is not resent on reconnect
- [ ] Server waits for subscribe message before pushing

### Tests & Quality

- [ ] All required backend tests pass locally
- [ ] No OAuth secrets in code
- [ ] Session data not exposed to frontend JavaScript
- [ ] `localStorage` not used for auth tokens

### Documentation

- [ ] README explains how to run the backend
- [ ] README explains how to run the frontend
- [ ] README explains Alembic migration steps
- [ ] README explains how "today" is determined
- [ ] README explains streak calculation logic
