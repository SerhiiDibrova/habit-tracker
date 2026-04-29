from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def _google_userinfo(**overrides: object) -> dict:
    return {
        "sub": "google-sub-999",
        "email": "google@example.com",
        "name": "Google Person",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
        **overrides,
    }


def _github_profile(**overrides: object) -> dict:
    return {
        "id": 42,
        "login": "githubuser",
        "name": "GitHub Person",
        "email": "github@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/42",
        **overrides,
    }


def _github_user_resp(profile: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = profile or _github_profile()
    return resp


def _github_emails_resp(emails: list | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = emails or [
        {"email": "private@example.com", "primary": True, "verified": True},
    ]
    return resp


class TestGoogleCallback:
    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_creates_user_and_redirects(
        self, mock_exchange: AsyncMock, client: TestClient, db_session: Session
    ) -> None:
        mock_exchange.return_value = {"userinfo": _google_userinfo()}

        response = client.get("/api/auth/google/callback?code=fake&state=fake")

        assert response.status_code == 302
        assert "error" not in response.headers["location"]
        assert response.headers["location"].startswith("http://localhost:3000/")

    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_session_cookie_enables_get_me(
        self, mock_exchange: AsyncMock, client: TestClient, db_session: Session
    ) -> None:
        """After OAuth callback the session cookie should allow GET /api/me."""
        mock_exchange.return_value = {"userinfo": _google_userinfo()}

        client.get("/api/auth/google/callback?code=fake&state=fake")

        # TestClient preserves Set-Cookie headers; the next request is authenticated
        me = client.get("/api/me")
        assert me.status_code == 200
        data = me.json()
        assert data["email"] == "google@example.com"
        assert data["provider"] == "google"
        assert data["display_name"] == "Google Person"

    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_auto_creates_user_in_db(
        self, mock_exchange: AsyncMock, client: TestClient, db_session: Session
    ) -> None:
        mock_exchange.return_value = {"userinfo": _google_userinfo()}

        client.get("/api/auth/google/callback?code=fake&state=fake")

        user = db_session.scalars(
            select(User).where(User.provider_user_id == "google-sub-999")
        ).first()
        assert user is not None
        assert user.provider == "google"
        assert user.email == "google@example.com"
        assert user.display_name == "Google Person"
        assert user.avatar_url == "https://lh3.googleusercontent.com/photo.jpg"

    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_updates_existing_user_profile(
        self, mock_exchange: AsyncMock, client: TestClient, db_session: Session
    ) -> None:
        existing = User(
            provider="google",
            provider_user_id="google-sub-999",
            email="old@example.com",
            display_name="Old Name",
        )
        db_session.add(existing)
        db_session.flush()

        mock_exchange.return_value = {
            "userinfo": _google_userinfo(email="new@example.com", name="New Name")
        }

        client.get("/api/auth/google/callback?code=fake&state=fake")

        db_session.refresh(existing)
        assert existing.email == "new@example.com"
        assert existing.display_name == "New Name"

    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_oauth_error_redirects_with_error_param(
        self, mock_exchange: AsyncMock, client: TestClient
    ) -> None:
        from authlib.integrations.base_client import OAuthError

        mock_exchange.side_effect = OAuthError(error="access_denied")

        response = client.get("/api/auth/google/callback?code=bad&state=bad")

        assert response.status_code == 302
        assert "error=oauth_failed" in response.headers["location"]

    @patch("app.api.auth.oauth.google.authorize_access_token", new_callable=AsyncMock)
    def test_missing_userinfo_redirects_with_error(
        self, mock_exchange: AsyncMock, client: TestClient
    ) -> None:
        mock_exchange.return_value = {}

        response = client.get("/api/auth/google/callback?code=fake&state=fake")

        assert response.status_code == 302
        assert "error=oauth_failed" in response.headers["location"]


class TestGitHubCallback:
    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_creates_user_and_redirects(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.return_value = _github_user_resp()

        response = client.get("/api/auth/github/callback?code=fake&state=fake")

        assert response.status_code == 302
        assert "error" not in response.headers["location"]

    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_session_cookie_enables_get_me(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """After OAuth callback the session cookie should allow GET /api/me."""
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.return_value = _github_user_resp()

        client.get("/api/auth/github/callback?code=fake&state=fake")

        me = client.get("/api/me")
        assert me.status_code == 200
        data = me.json()
        assert data["email"] == "github@example.com"
        assert data["provider"] == "github"
        assert data["display_name"] == "GitHub Person"

    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_auto_creates_user_in_db(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.return_value = _github_user_resp()

        client.get("/api/auth/github/callback?code=fake&state=fake")

        user = db_session.scalars(
            select(User).where(User.provider_user_id == "42")
        ).first()
        assert user is not None
        assert user.provider == "github"
        assert user.email == "github@example.com"
        assert user.display_name == "GitHub Person"

    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_private_email_fetches_from_emails_endpoint(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.side_effect = [
            _github_user_resp(_github_profile(email=None)),
            _github_emails_resp([
                {"email": "private@example.com", "primary": True, "verified": True},
                {"email": "other@example.com", "primary": False, "verified": True},
            ]),
        ]

        client.get("/api/auth/github/callback?code=fake&state=fake")

        user = db_session.scalars(
            select(User).where(User.provider_user_id == "42")
        ).first()
        assert user is not None
        assert user.email == "private@example.com"

    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_no_verified_email_stores_none(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.side_effect = [
            _github_user_resp(_github_profile(email=None)),
            _github_emails_resp([
                {"email": "unverified@example.com", "primary": True, "verified": False},
            ]),
        ]

        client.get("/api/auth/github/callback?code=fake&state=fake")

        user = db_session.scalars(
            select(User).where(User.provider_user_id == "42")
        ).first()
        assert user is not None
        assert user.email is None

    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_oauth_error_redirects_with_error_param(
        self, mock_exchange: AsyncMock, client: TestClient
    ) -> None:
        from authlib.integrations.base_client import OAuthError

        mock_exchange.side_effect = OAuthError(error="bad_verification_code")

        response = client.get("/api/auth/github/callback?code=bad&state=bad")

        assert response.status_code == 302
        assert "error=oauth_failed" in response.headers["location"]

    @patch("app.api.auth.oauth.github.get", new_callable=AsyncMock)
    @patch("app.api.auth.oauth.github.authorize_access_token", new_callable=AsyncMock)
    def test_uses_login_as_display_name_when_name_missing(
        self,
        mock_exchange: AsyncMock,
        mock_get: AsyncMock,
        client: TestClient,
        db_session: Session,
    ) -> None:
        mock_exchange.return_value = {"access_token": "ghp_fake"}
        mock_get.return_value = _github_user_resp(_github_profile(name=None))

        client.get("/api/auth/github/callback?code=fake&state=fake")

        user = db_session.scalars(
            select(User).where(User.provider_user_id == "42")
        ).first()
        assert user is not None
        assert user.display_name == "githubuser"


class TestLogout:
    def test_logout_returns_200(self, auth_client: TestClient) -> None:
        response = auth_client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json() == {"detail": "Logged out"}

    def test_logout_unauthenticated_is_idempotent(self, client: TestClient) -> None:
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json() == {"detail": "Logged out"}


class TestMe:
    def test_get_me_authenticated(
        self, auth_client: TestClient, test_user: User
    ) -> None:
        response = auth_client.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["display_name"] == test_user.display_name
        assert data["provider"] == "google"

    def test_get_me_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
