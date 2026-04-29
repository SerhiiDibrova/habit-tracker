from collections.abc import Generator
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.check_in import CheckIn
from app.models.habit import Habit, HabitStatus
from app.models.user import User

# ---------------------------------------------------------------------------
# Extra fixtures
# ---------------------------------------------------------------------------

TODAY = date(2026, 4, 29)
_MOCK_TODAY = "app.api.habits.get_today"


@pytest.fixture()
def other_user(db_session: Session) -> User:
    user = User(
        provider="github",
        provider_user_id="github-other-456",
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def other_auth_client(
    other_user: User, override_get_db: None
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: other_user
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_habit(
    db: Session,
    user: User,
    *,
    name: str = "Test Habit",
    description: str | None = None,
    start_date: date = date(2026, 1, 1),
    status: str = HabitStatus.active.value,
) -> Habit:
    habit = Habit(
        user_id=user.id,
        name=name,
        description=description,
        start_date=start_date,
        status=status,
    )
    db.add(habit)
    db.flush()
    return habit


def _make_check_in(db: Session, habit: Habit, user: User, check_in_date: date) -> CheckIn:
    ci = CheckIn(habit_id=habit.id, user_id=user.id, check_in_date=check_in_date)
    db.add(ci)
    db.flush()
    return ci


def _habit_payload(**overrides) -> dict:
    return {
        "name": "Morning Run",
        "description": "Run 5km",
        "start_date": "2026-01-01",
        "status": "active",
        **overrides,
    }


# ---------------------------------------------------------------------------
# CRUD — create
# ---------------------------------------------------------------------------


class TestCreateHabit:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_creates_habit_and_returns_streak_zeros(
        self, _m, auth_client: TestClient
    ) -> None:
        resp = auth_client.post("/api/habits", json=_habit_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Morning Run"
        assert data["status"] == "active"
        assert data["current_streak"] == 0
        assert data["best_streak"] == 0
        assert data["total_check_ins"] == 0
        assert data["completed_today"] is False

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_422_for_missing_name(self, _m, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/habits", json={"start_date": "2026-01-01"})
        assert resp.status_code == 422

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_422_for_empty_name(self, _m, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/habits", json=_habit_payload(name=""))
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        resp = client.post("/api/habits", json=_habit_payload())
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CRUD — read
# ---------------------------------------------------------------------------


class TestGetHabit:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_get_own_habit(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.get(f"/api/habits/{habit.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(habit.id)

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_404_for_unknown_id(self, _m, auth_client: TestClient) -> None:
        import uuid
        resp = auth_client.get(f"/api/habits/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestListHabits:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_only_own_habits(
        self,
        _m,
        auth_client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
    ) -> None:
        _make_habit(db_session, test_user, name="My Habit")
        _make_habit(db_session, other_user, name="Their Habit")
        resp = auth_client.get("/api/habits")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "My Habit" in names
        assert "Their Habit" not in names

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_search_by_name(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        _make_habit(db_session, test_user, name="Read Books")
        _make_habit(db_session, test_user, name="Morning Run")
        resp = auth_client.get("/api/habits?search=read")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Read Books" in names
        assert "Morning Run" not in names

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_search_by_description(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        _make_habit(db_session, test_user, name="Running", description="cardio workout")
        _make_habit(db_session, test_user, name="Yoga", description="flexibility")
        resp = auth_client.get("/api/habits?search=cardio")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Running" in names
        assert "Yoga" not in names

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_filter_by_status(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        _make_habit(db_session, test_user, name="Active", status="active")
        _make_habit(db_session, test_user, name="Paused", status="paused")
        resp = auth_client.get("/api/habits?status=active")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Active" in names
        assert "Paused" not in names

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_filter_completed_today_true(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        done = _make_habit(db_session, test_user, name="Done")
        _make_habit(db_session, test_user, name="Not Done")
        _make_check_in(db_session, done, test_user, TODAY)

        resp = auth_client.get("/api/habits?completed_today=true")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Done" in names
        assert "Not Done" not in names

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_filter_completed_today_false(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        done = _make_habit(db_session, test_user, name="Done")
        _make_habit(db_session, test_user, name="Not Done")
        _make_check_in(db_session, done, test_user, TODAY)

        resp = auth_client.get("/api/habits?completed_today=false")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Not Done" in names
        assert "Done" not in names


# ---------------------------------------------------------------------------
# CRUD — update
# ---------------------------------------------------------------------------


class TestUpdateHabit:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_updates_name(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.patch(f"/api/habits/{habit.id}", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_clears_description_when_sent_as_null(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user, description="old desc")
        resp = auth_client.patch(
            f"/api/habits/{habit.id}", json={"description": None}
        )
        assert resp.status_code == 200
        assert resp.json()["description"] is None

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_archived_habit_rejects_name_update(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user, status="archived")
        resp = auth_client.patch(f"/api/habits/{habit.id}", json={"name": "Hack"})
        assert resp.status_code == 422
        assert "Archived" in resp.json()["detail"]

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_archived_habit_allows_status_update(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user, status="archived")
        resp = auth_client.patch(f"/api/habits/{habit.id}", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_404_for_unknown_habit(self, _m, auth_client: TestClient) -> None:
        import uuid
        resp = auth_client.patch(f"/api/habits/{uuid.uuid4()}", json={"name": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CRUD — delete
# ---------------------------------------------------------------------------


class TestDeleteHabit:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_deletes_habit(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.delete(f"/api/habits/{habit.id}")
        assert resp.status_code == 204
        resp = auth_client.get(f"/api/habits/{habit.id}")
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_404_for_unknown_habit(self, _m, auth_client: TestClient) -> None:
        import uuid
        resp = auth_client.delete(f"/api/habits/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Check-in: create and undo
# ---------------------------------------------------------------------------


class TestCheckIn:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_check_in_returns_streak_1(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 201
        data = resp.json()
        assert data["current_streak"] == 1
        assert data["best_streak"] == 1
        assert data["total_check_ins"] == 1
        assert data["completed_today"] is True

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_duplicate_check_in_returns_409(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        resp = auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 409
        assert "Already checked in today" in resp.json()["detail"]

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_paused_habit_cannot_check_in(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user, status="paused")
        resp = auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 422
        assert "Only active" in resp.json()["detail"]

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_archived_habit_cannot_check_in(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user, status="archived")
        resp = auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 422

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_undo_resets_completed_today(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        resp = auth_client.delete(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed_today"] is False
        assert data["current_streak"] == 0
        assert data["total_check_ins"] == 0

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_undo_with_prior_streak_recalculates_correctly(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        # Insert two historical consecutive check-ins directly
        _make_check_in(db_session, habit, test_user, TODAY - timedelta(days=2))
        _make_check_in(db_session, habit, test_user, TODAY - timedelta(days=1))
        # Check in today via API → streak of 3
        resp = auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.json()["current_streak"] == 3
        assert resp.json()["best_streak"] == 3
        # Undo → streak drops to 2 (yesterday + day before)
        resp = auth_client.delete(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_streak"] == 2
        assert data["completed_today"] is False

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_undo_when_nothing_to_undo_returns_404(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.delete(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Monthly check-ins
# ---------------------------------------------------------------------------


class TestMonthlyCheckIns:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_returns_dates_for_month(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        _make_check_in(db_session, habit, test_user, date(2026, 4, 1))
        _make_check_in(db_session, habit, test_user, date(2026, 4, 15))
        _make_check_in(db_session, habit, test_user, date(2026, 3, 31))  # excluded

        resp = auth_client.get(f"/api/habits/{habit.id}/check-ins?month=2026-04")
        assert resp.status_code == 200
        dates = resp.json()["check_in_dates"]
        assert "2026-04-01" in dates
        assert "2026-04-15" in dates
        assert "2026-03-31" not in dates

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_invalid_month_format_returns_422(
        self, _m, auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = auth_client.get(f"/api/habits/{habit.id}/check-ins?month=April-2026")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestAuthorization:
    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_cannot_get_other_user_habit(
        self, _m, other_auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = other_auth_client.get(f"/api/habits/{habit.id}")
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_cannot_update_other_user_habit(
        self, _m, other_auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = other_auth_client.patch(f"/api/habits/{habit.id}", json={"name": "Hacked"})
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_cannot_delete_other_user_habit(
        self, _m, other_auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = other_auth_client.delete(f"/api/habits/{habit.id}")
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_cannot_check_in_other_user_habit(
        self, _m, other_auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        resp = other_auth_client.post(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_cannot_undo_check_in_on_other_user_habit(
        self, _m, other_auth_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        habit = _make_habit(db_session, test_user)
        _make_check_in(db_session, habit, test_user, TODAY)
        resp = other_auth_client.delete(f"/api/habits/{habit.id}/check-in/today")
        assert resp.status_code == 404

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_other_user_habit_not_in_list(
        self,
        _m,
        auth_client: TestClient,
        db_session: Session,
        test_user: User,
        other_user: User,
    ) -> None:
        _make_habit(db_session, other_user, name="Other's Habit")
        resp = auth_client.get("/api/habits")
        assert resp.status_code == 200
        names = [h["name"] for h in resp.json()]
        assert "Other's Habit" not in names


# ---------------------------------------------------------------------------
# Streak calculation (pure unit test via service)
# ---------------------------------------------------------------------------


class TestStreakCalculation:
    def test_empty_check_ins(self) -> None:
        from app.services.streak_service import calculate_streaks
        assert calculate_streaks([], TODAY) == (0, 0, 0, False)

    def test_single_check_in_today(self) -> None:
        from app.services.streak_service import calculate_streaks
        current, best, total, done = calculate_streaks([TODAY], TODAY)
        assert current == 1
        assert best == 1
        assert total == 1
        assert done is True

    def test_consecutive_streak(self) -> None:
        from app.services.streak_service import calculate_streaks
        dates = [TODAY - timedelta(days=i) for i in range(4)]  # 4 consecutive days
        current, best, total, done = calculate_streaks(dates, TODAY)
        assert current == 4
        assert best == 4
        assert total == 4
        assert done is True

    def test_broken_streak_resets_current(self) -> None:
        from app.services.streak_service import calculate_streaks
        # Gap on day -2: dates are today, yesterday, 3 days ago, 4 days ago
        dates = [TODAY, TODAY - timedelta(days=1), TODAY - timedelta(days=3), TODAY - timedelta(days=4)]
        current, best, total, _ = calculate_streaks(dates, TODAY)
        assert current == 2   # today + yesterday
        assert best == 2      # max run is also 2 (3-4 days ago is also 2)
        assert total == 4

    def test_not_checked_in_today_counts_from_yesterday(self) -> None:
        from app.services.streak_service import calculate_streaks
        yesterday = TODAY - timedelta(days=1)
        day_before = TODAY - timedelta(days=2)
        current, best, total, done = calculate_streaks([yesterday, day_before], TODAY)
        assert current == 2
        assert done is False
