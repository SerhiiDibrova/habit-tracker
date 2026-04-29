import json
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models.check_in import CheckIn
from app.models.habit import Habit
from app.models.milestone_notification import MilestoneNotification
from app.models.user import User

# Patch target for the "today" helper used inside the WebSocket endpoint.
_MOCK_TODAY = "app.websocket.endpoint.get_today"
TODAY = date(2026, 4, 29)


def _create_habit(db: Session, user_id: object, name: str = "Test Habit") -> Habit:
    habit = Habit(
        user_id=user_id,
        name=name,
        description=None,
        start_date=TODAY,
        status="active",
    )
    db.add(habit)
    db.flush()
    return habit


def _add_check_ins(db: Session, habit: Habit, n: int) -> None:
    """Add n consecutive check-ins ending on TODAY."""
    for i in range(n - 1, -1, -1):
        db.add(
            CheckIn(
                habit_id=habit.id,
                user_id=habit.user_id,
                check_in_date=TODAY - timedelta(days=i),
            )
        )
    db.flush()


def _milestone_count(db: Session, user_id: object, milestone_days: int | None = None) -> int:
    stmt = select(func.count()).where(MilestoneNotification.user_id == user_id)
    if milestone_days is not None:
        stmt = stmt.where(MilestoneNotification.milestone_days == milestone_days)
    return db.scalar(stmt) or 0


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


class TestWebSocketAuth:
    def test_unauthorized_websocket_is_rejected(self, client: TestClient) -> None:
        """Connection without a session cookie must be closed with code 1008."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/notifications"):
                pass
        assert exc_info.value.code == 1008


# ---------------------------------------------------------------------------
# Milestone notifications
# ---------------------------------------------------------------------------


class TestWebSocketMilestones:
    def _habit_with_streak(
        self, db: Session, user: User, n_days: int, name: str
    ) -> Habit:
        habit = _create_habit(db, user.id, name)
        _add_check_ins(db, habit, n_days)
        return habit

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_milestone_3_days(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        self._habit_with_streak(db_session, test_user, 3, "H3")

        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            msg = json.loads(ws.receive_text())

        assert msg["type"] == "milestone"
        assert msg["milestone_days"] == 3
        assert msg["current_streak"] == 3
        assert "notification_id" in msg
        assert "habit_id" in msg
        assert "sent_at" in msg

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_milestone_7_days(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        self._habit_with_streak(db_session, test_user, 7, "H7")

        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            msgs = [json.loads(ws.receive_text()) for _ in range(2)]

        milestone_days_set = {m["milestone_days"] for m in msgs}
        assert 3 in milestone_days_set
        assert 7 in milestone_days_set

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_milestone_30_days(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        self._habit_with_streak(db_session, test_user, 30, "H30")

        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            msgs = [json.loads(ws.receive_text()) for _ in range(3)]

        milestone_days_set = {m["milestone_days"] for m in msgs}
        assert 3 in milestone_days_set
        assert 7 in milestone_days_set
        assert 30 in milestone_days_set

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_reconnect_does_not_resend(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        self._habit_with_streak(db_session, test_user, 3, "HR")

        # First connection: milestone fires and is persisted
        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            first = json.loads(ws.receive_text())
        assert first["milestone_days"] == 3

        # Reconnect and subscribe again — no new milestone, DB count stays at 1
        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            ws.close()

        assert _milestone_count(db_session, test_user.id, milestone_days=3) == 1

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_no_push_before_subscribe(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        self._habit_with_streak(db_session, test_user, 7, "HNS")

        # Connect and immediately exit without sending subscribe
        with ws_client.websocket_connect("/ws/notifications"):
            pass

        # Server must not have evaluated any milestones
        assert _milestone_count(db_session, test_user.id) == 0

    @patch(_MOCK_TODAY, return_value=TODAY)
    def test_ack_message_records_acknowledged_at(
        self, _m, ws_client: TestClient, db_session: Session, test_user: User
    ) -> None:
        """Sending an ack message sets acknowledged_at on the notification record."""
        self._habit_with_streak(db_session, test_user, 3, "HACK")

        notification_id: str | None = None
        with ws_client.websocket_connect("/ws/notifications") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "milestones"}))
            msg = json.loads(ws.receive_text())
            notification_id = msg["notification_id"]
            ws.send_text(json.dumps({"type": "ack", "notification_id": notification_id}))
            # Give the server a moment to process the ack before closing
            ws.close()

        assert notification_id is not None
        notif = db_session.scalars(
            select(MilestoneNotification).where(
                MilestoneNotification.id == uuid.UUID(notification_id)
            )
        ).first()
        assert notif is not None
        assert notif.acknowledged_at is not None
