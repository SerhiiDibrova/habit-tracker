import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.check_in import CheckIn
from app.models.habit import Habit
from app.models.milestone_notification import MilestoneNotification
from app.services.streak_service import calculate_streaks

MILESTONE_THRESHOLDS = [3, 7, 30]


def evaluate_pending_milestones(
    db: Session, user_id: uuid.UUID, today: date
) -> list[tuple[MilestoneNotification, Habit, int]]:
    """
    Check all user habits for newly reached milestone thresholds.
    Creates DB records for each new milestone and returns them paired with
    the habit and current streak. Already-recorded milestones are skipped.
    """
    habits = list(db.scalars(select(Habit).where(Habit.user_id == user_id)).all())
    if not habits:
        return []

    # Load all already-sent (habit_id, milestone_days) pairs in one query
    sent: set[tuple[uuid.UUID, int]] = set(
        db.execute(
            select(MilestoneNotification.habit_id, MilestoneNotification.milestone_days).where(
                MilestoneNotification.user_id == user_id
            )
        ).all()
    )

    results: list[tuple[MilestoneNotification, Habit, int]] = []

    for habit in habits:
        dates = list(
            db.scalars(select(CheckIn.check_in_date).where(CheckIn.habit_id == habit.id)).all()
        )
        current_streak, _, _, _ = calculate_streaks(dates, today)

        for threshold in MILESTONE_THRESHOLDS:
            if current_streak >= threshold and (habit.id, threshold) not in sent:
                notification = MilestoneNotification(
                    user_id=user_id,
                    habit_id=habit.id,
                    milestone_days=threshold,
                )
                db.add(notification)
                db.flush()
                results.append((notification, habit, current_streak))
                sent.add((habit.id, threshold))

    if results:
        db.commit()

    return results


def acknowledge_milestone(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
    notification = db.scalars(
        select(MilestoneNotification).where(
            MilestoneNotification.id == notification_id,
            MilestoneNotification.user_id == user_id,
        )
    ).first()
    if notification is not None and notification.acknowledged_at is None:
        notification.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
