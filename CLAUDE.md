# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack Habit Tracker MVP. The canonical specification is in [specs/spec.MD](specs/spec.MD) — treat it as the source of truth for all requirements, rules, and acceptance criteria.

---

## Commands

### Backend

The backend virtualenv lives at `backend/.venv` (there is also a root-level `.venv` — prefer `backend/.venv` for backend work).

```bash
# Activate virtualenv
source backend/.venv/bin/activate

# Run development server
cd backend && uvicorn app.main:app --reload

# Run all tests
cd backend && pytest

# Run a single test file
cd backend && pytest tests/test_habits.py

# Run a single test by name
cd backend && pytest tests/test_habits.py::test_create_habit

# Apply all migrations
cd backend && alembic upgrade head

# Create a new migration
cd backend && alembic revision --autogenerate -m "describe change"
```

### Frontend

```bash
cd frontend

npm run dev        # dev server at http://localhost:3000
npm run build      # production build
npm run lint       # ESLint
npx tsc --noEmit   # type-check without emitting
```

### Adding shadcn/ui components

```bash
cd frontend && npx shadcn add <component>
```

---

## Architecture

### Request Flow

```
Browser ──► Next.js (port 3000)
               └── TanStack Query / fetch ──► FastAPI (port 8000)
                                                  ├── api/       (routers)
                                                  ├── auth/      (OAuth, session)
                                                  ├── services/  (business logic)
                                                  └── db/        (SQLAlchemy + PostgreSQL)

Browser ──► WebSocket ws://localhost:8000/ws/notifications
```

Auth state is held entirely in an **HTTP-only session cookie** issued by the backend. The frontend never stores tokens — no `localStorage`, no `sessionStorage`.

### Backend Layers (`backend/app/`)

| Package      | Responsibility |
|--------------|----------------|
| `api/`       | FastAPI routers — parse request, call service, return response |
| `auth/`      | Authlib OAuth flow, session read/write, `current_user` FastAPI dependency |
| `core/`      | Pydantic-settings config, timezone helper (reads `APP_TIMEZONE`), shared error types |
| `db/`        | SQLAlchemy engine, session factory, declarative base |
| `models/`    | ORM models: `User`, `Habit`, `CheckIn`, `MilestoneNotification` |
| `schemas/`   | Pydantic v2 request/response models |
| `services/`  | All business logic: habit CRUD, check-in rules, streak calculation, milestone evaluation |
| `websocket/` | WebSocket endpoint, connection manager, subscribe/ack protocol |

Business logic belongs in `services/`, not in routers. Routers call services; services call the DB.

### Frontend Structure (`frontend/src/`)

| Path                        | Purpose |
|-----------------------------|---------|
| `app/`                      | Next.js App Router pages and layouts |
| `components/ui/`            | shadcn/ui primitives (auto-generated — do not hand-edit) |
| `features/auth/`            | Auth page components |
| `features/habits/`          | Habit cards, form, filters, calendar |
| `features/notifications/`   | Notification panel and toast wiring |
| `lib/api.ts`                | HTTP client (base URL from `NEXT_PUBLIC_API_BASE_URL`) |
| `lib/ws.ts`                 | WebSocket client (base URL from `NEXT_PUBLIC_WS_BASE_URL`) |
| `types/api.ts`              | TypeScript types mirroring backend schemas |

Path alias `@/` resolves to `frontend/src/`.

---

## Next.js 16 — Critical Differences

This project uses **Next.js 16.2.4**. APIs and conventions differ from earlier versions in ways that are not obvious from training data. Read `node_modules/next/dist/docs/` before writing any Next.js code. The `frontend/AGENTS.md` carries the same warning.

Key breaking changes relevant to this project:

**`fetch` is not cached by default.** Use the `use cache` directive to opt into caching, or wrap components in `<Suspense>` to stream uncached data at request time.

**`params` in pages/layouts is a `Promise`**, not a plain object:
```tsx
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
}
```

**Server Components are the default.** Add `'use client'` only when the component needs `useState`, `useEffect`, event handlers, custom hooks, or browser APIs. All TanStack Query, WebSocket, and React Hook Form components require `'use client'`.

Since this project uses a separate FastAPI backend, data mutations go through TanStack Query + `lib/api.ts` — not Next.js Server Functions.

---

## Key Business Rules (from spec)

- **One check-in per habit per day.** Only today is allowed. No backfill, no future dates. Undo is today-only.
- **Streaks are calendar-date based** using the timezone set in `APP_TIMEZONE` (default `Europe/Warsaw`). "Today" is always determined server-side from this env var.
- **Milestones (3, 7, 30 days)** are pushed via WebSocket only after the client sends a `{"type":"subscribe","channel":"milestones"}` message. Each milestone fires at most once per habit.
- **Every DB query must be scoped by `user_id`.** No cross-user data access at any layer.
- **Backend tests must not call real Google or GitHub.** Mock the OAuth provider responses.

---

## Environment Setup

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Backend reads settings via Pydantic-settings from `backend/.env`. Frontend reads `NEXT_PUBLIC_*` vars at build time from `frontend/.env.local`. Database: local PostgreSQL or `docker-compose up`.
