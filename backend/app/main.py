from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.habits import router as habits_router
from app.api.health import router as health_router
from app.api.me import router as me_router
from app.core.config import settings
from app.websocket import router as ws_router

app = FastAPI(title="Habit Tracker API", version="0.1.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.app_env == "production",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(habits_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(me_router, prefix="/api")
app.include_router(ws_router)
