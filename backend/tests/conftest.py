import base64
import json
import os
import re
from collections.abc import Generator

import itsdangerous
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


def make_session_cookie(data: dict) -> str:
    signer = itsdangerous.TimestampSigner(settings.session_secret)
    b64 = base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
    return signer.sign(b64).decode("utf-8")


def _derive_test_db_url(prod_url: str) -> str:
    """Replace the database name in prod_url with <name>_test."""
    return re.sub(
        r"/([^/?]+)(\?.*)?$",
        lambda m: f"/{m.group(1)}_test{m.group(2) or ''}",
        prod_url,
    )


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _derive_test_db_url(
    settings.database_url
)

test_engine = create_engine(TEST_DATABASE_URL, echo=False)


def _ensure_test_db_exists(test_url: str) -> None:
    """Create the test database if it does not yet exist."""
    maint_url = re.sub(r"/([^/?]+)(\?.*)?$", lambda m: "/postgres" + (m.group(2) or ""), test_url)
    db_name_match = re.search(r"/([^/?]+)(\?.*)?$", test_url)
    if db_name_match is None:
        return
    db_name = db_name_match.group(1)
    try:
        engine = create_engine(maint_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            exists = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        engine.dispose()
    except Exception:
        pass  # If maintenance db is unreachable, let the test engine fail with a clear error


@pytest.fixture(scope="session", autouse=True)
def create_tables() -> Generator[None, None, None]:
    _ensure_test_db_exists(TEST_DATABASE_URL)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session: Session, transaction_in: object) -> None:
        if transaction_in.nested and not transaction_in._parent.nested:  # type: ignore[attr-defined]
            session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def override_get_db(db_session: Session) -> Generator[None, None, None]:
    def _get_test_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client(override_get_db: None) -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def test_user(db_session: Session) -> User:
    user = User(
        provider="google",
        provider_user_id="google-test-123",
        email="test@example.com",
        display_name="Test User",
        avatar_url="https://example.com/avatar.png",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def auth_client(test_user: User, override_get_db: None) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def ws_client(test_user: User, override_get_db: None) -> TestClient:
    """TestClient with a valid session cookie for WebSocket tests."""
    cookie = make_session_cookie({"user_id": str(test_user.id)})
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("session", cookie)
    return client
