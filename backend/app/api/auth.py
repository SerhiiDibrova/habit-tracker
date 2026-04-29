import logging
from typing import Annotated

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.oauth import oauth
from app.core.config import settings
from app.db.session import get_db
from app.services.user_service import get_or_create_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: DbSession) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("Google OAuth error: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo")
    if not userinfo:
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed", status_code=302)

    user = get_or_create_user(
        db,
        provider="google",
        provider_user_id=userinfo["sub"],
        email=userinfo.get("email"),
        display_name=userinfo.get("name") or userinfo.get("email") or "Google User",
        avatar_url=userinfo.get("picture"),
    )
    db.commit()

    request.session["user_id"] = str(user.id)
    return RedirectResponse(f"{settings.frontend_url}/", status_code=302)


@router.get("/github/login")
async def github_login(request: Request) -> RedirectResponse:
    return await oauth.github.authorize_redirect(request, settings.github_redirect_uri)


@router.get("/github/callback")
async def github_callback(request: Request, db: DbSession) -> RedirectResponse:
    try:
        token = await oauth.github.authorize_access_token(request)
    except OAuthError as exc:
        log.warning("GitHub OAuth error: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed", status_code=302)

    try:
        resp = await oauth.github.get("user", token=token)
        resp.raise_for_status()
        profile = resp.json()
    except Exception as exc:
        log.warning("GitHub profile fetch error: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed", status_code=302)

    email = profile.get("email") or await _get_github_primary_email(token)
    display_name = profile.get("name") or profile.get("login") or "GitHub User"

    user = get_or_create_user(
        db,
        provider="github",
        provider_user_id=str(profile["id"]),
        email=email,
        display_name=display_name,
        avatar_url=profile.get("avatar_url"),
    )
    db.commit()

    request.session["user_id"] = str(user.id)
    return RedirectResponse(f"{settings.frontend_url}/", status_code=302)


async def _get_github_primary_email(token: dict) -> str | None:
    try:
        resp = await oauth.github.get("user/emails", token=token)
        resp.raise_for_status()
        for entry in resp.json():
            if entry.get("primary") and entry.get("verified"):
                return entry["email"]
    except Exception as exc:
        log.warning("GitHub email fetch error: %s", exc)
    return None


@router.post("/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"detail": "Logged out"}
