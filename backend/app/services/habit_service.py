import calendar
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.check_in import CheckIn
from app.models.habit import Habit, HabitStatus
from app.schemas.habit import HabitCreate, HabitResponse, HabitUpdate, MonthCheckInsResponse
from app.services.streak_service import calculate_streaks

_NON_NULLABLE = {"name", "start_date", "status"}


def _get_habit_or_404(db: Session, habit_id: uuid.UUID, user_id: uuid.UUID) -> Habit:
    habit = db.scalars(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    ).first()
    if habit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit


def _get_check_in_dates(db: Session, habit_id: uuid.UUID) -> list[date]:
    return list(
        db.scalars(select(CheckIn.check_in_date).where(CheckIn.habit_id == habit_id)).all()
    )


def _build_response(habit: Habit, dates: list[date], today: date) -> HabitResponse:
    current_streak, best_streak, total_check_ins, completed_today = calculate_streaks(dates, today)
    return HabitResponse(
        id=habit.id,
        user_id=habit.user_id,
        name=habit.name,
        description=habit.description,
        start_date=habit.start_date,
        status=habit.status,
        created_at=habit.created_at,
        updated_at=habit.updated_at,
        current_streak=current_streak,
        best_streak=best_streak,
        total_check_ins=total_check_ins,
        completed_today=completed_today,
    )


def list_habits(
    db: Session,
    user_id: uuid.UUID,
    today: date,
    search: str | None = None,
    status_filter: str = "all",
    completed_today_filter: bool | None = None,
) -> list[HabitResponse]:
    stmt = select(Habit).where(Habit.user_id == user_id)

    if status_filter != "all":
        stmt = stmt.where(Habit.status == status_filter)

    if search:
        like = f"%{search}%"
        stmt = stmt.where(Habit.name.ilike(like) | Habit.description.ilike(like))

    habits = list(db.scalars(stmt).all())
    if not habits:
        return []

    # Load all check-in dates for the matching habits in two queries total
    habit_ids = [h.id for h in habits]
    rows = db.execute(
        select(CheckIn.habit_id, CheckIn.check_in_date).where(
            CheckIn.habit_id.in_(habit_ids)
        )
    ).all()

    dates_by_habit: dict[uuid.UUID, list[date]] = {h.id: [] for h in habits}
    for habit_id, check_in_date in rows:
        dates_by_habit[habit_id].append(check_in_date)

    responses = [_build_response(h, dates_by_habit[h.id], today) for h in habits]

    if completed_today_filter is True:
        responses = [r for r in responses if r.completed_today]
    elif completed_today_filter is False:
        responses = [r for r in responses if not r.completed_today]

    return responses


def get_habit(
    db: Session, habit_id: uuid.UUID, user_id: uuid.UUID, today: date
) -> HabitResponse:
    habit = _get_habit_or_404(db, habit_id, user_id)
    dates = _get_check_in_dates(db, habit_id)
    return _build_response(habit, dates, today)


def create_habit(
    db: Session, user_id: uuid.UUID, data: HabitCreate, today: date
) -> HabitResponse:
    habit = Habit(
        user_id=user_id,
        name=data.name,
        description=data.description,
        start_date=data.start_date,
        status=data.status.value,
    )
    db.add(habit)
    db.flush()
    return _build_response(habit, [], today)


def update_habit(
    db: Session,
    habit_id: uuid.UUID,
    user_id: uuid.UUID,
    data: HabitUpdate,
    today: date,
) -> HabitResponse:
    habit = _get_habit_or_404(db, habit_id, user_id)

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        dates = _get_check_in_dates(db, habit_id)
        return _build_response(habit, dates, today)

    # Archived habits: only status field may be changed
    if habit.status == HabitStatus.archived.value:
        non_status = {k for k in updates if k != "status"}
        if non_status:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Archived habits can only have their status updated",
            )

    for field, value in updates.items():
        if field in _NON_NULLABLE and value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"'{field}' cannot be null",
            )
        if isinstance(value, HabitStatus):
            value = value.value
        setattr(habit, field, value)

    db.flush()
    dates = _get_check_in_dates(db, habit_id)
    return _build_response(habit, dates, today)


def delete_habit(db: Session, habit_id: uuid.UUID, user_id: uuid.UUID) -> None:
    habit = _get_habit_or_404(db, habit_id, user_id)
    db.delete(habit)
    db.flush()


def check_in_today(
    db: Session, habit_id: uuid.UUID, user_id: uuid.UUID, today: date
) -> HabitResponse:
    habit = _get_habit_or_404(db, habit_id, user_id)

    if habit.status != HabitStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only active habits can be checked in",
        )

    existing = db.scalars(
        select(CheckIn).where(
            CheckIn.habit_id == habit_id,
            CheckIn.check_in_date == today,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already checked in today",
        )

    check_in = CheckIn(habit_id=habit_id, user_id=user_id, check_in_date=today)
    db.add(check_in)
    db.flush()

    dates = _get_check_in_dates(db, habit_id)
    return _build_response(habit, dates, today)


def undo_check_in_today(
    db: Session, habit_id: uuid.UUID, user_id: uuid.UUID, today: date
) -> HabitResponse:
    habit = _get_habit_or_404(db, habit_id, user_id)

    check_in = db.scalars(
        select(CheckIn).where(
            CheckIn.habit_id == habit_id,
            CheckIn.check_in_date == today,
        )
    ).first()
    if check_in is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No check-in found for today",
        )

    db.delete(check_in)
    db.flush()

    dates = _get_check_in_dates(db, habit_id)
    return _build_response(habit, dates, today)


def get_month_check_ins(
    db: Session,
    habit_id: uuid.UUID,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> MonthCheckInsResponse:
    _get_habit_or_404(db, habit_id, user_id)

    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    dates = list(
        db.scalars(
            select(CheckIn.check_in_date)
            .where(
                CheckIn.habit_id == habit_id,
                CheckIn.check_in_date.between(start, end),
            )
            .order_by(CheckIn.check_in_date)
        ).all()
    )
    return MonthCheckInsResponse(check_in_dates=dates)
