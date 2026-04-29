import json
import uuid
from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.timezone import get_today
from app.db.session import get_db
from app.models.user import User
from app.services.milestone_service import acknowledge_milestone, evaluate_pending_milestones

router = APIRouter()


async def _resolve_user(websocket: WebSocket, db: Session) -> User | None:
    user_id_str = websocket.session.get("user_id")
    if not user_id_str:
        return None
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None
    return db.scalars(select(User).where(User.id == user_id)).first()


@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    user = await _resolve_user(websocket, db)
    if user is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "subscribe" and msg.get("channel") == "milestones":
                today = get_today()
                pending = evaluate_pending_milestones(db, user.id, today)
                for notification, habit, current_streak in pending:
                    payload = {
                        "type": "milestone",
                        "notification_id": str(notification.id),
                        "habit_id": str(habit.id),
                        "habit_name": habit.name,
                        "milestone_days": notification.milestone_days,
                        "current_streak": current_streak,
                        "sent_at": notification.sent_at.astimezone(timezone.utc).isoformat(),
                    }
                    await websocket.send_text(json.dumps(payload))

            elif msg_type == "ack":
                raw_id = msg.get("notification_id")
                if raw_id:
                    try:
                        acknowledge_milestone(db, uuid.UUID(raw_id), user.id)
                    except ValueError:
                        pass

    except WebSocketDisconnect:
        pass
