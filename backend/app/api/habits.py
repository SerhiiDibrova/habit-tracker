import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.timezone import get_today
from app.db.session import get_db
from app.schemas.habit import HabitCreate, HabitResponse, HabitUpdate, MonthCheckInsResponse
from app.services import habit_service

router = APIRouter(prefix="/habits", tags=["habits"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[HabitResponse])
def list_habits(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(default=None),
    status_filter: Literal["all", "active", "paused", "archived"] = Query(
        default="all", alias="status"
    ),
    completed_today: bool | None = Query(default=None),
) -> list[HabitResponse]:
    return habit_service.list_habits(
        db,
        user_id=current_user.id,
        today=get_today(),
        search=search,
        status_filter=status_filter,
        completed_today_filter=completed_today,
    )


@router.post("", response_model=HabitResponse, status_code=http_status.HTTP_201_CREATED)
def create_habit(
    current_user: CurrentUser,
    db: DbSession,
    data: HabitCreate,
) -> HabitResponse:
    response = habit_service.create_habit(
        db, user_id=current_user.id, data=data, today=get_today()
    )
    db.commit()
    return response


@router.get("/{habit_id}", response_model=HabitResponse)
def get_habit(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> HabitResponse:
    return habit_service.get_habit(
        db, habit_id=habit_id, user_id=current_user.id, today=get_today()
    )


@router.patch("/{habit_id}", response_model=HabitResponse)
def update_habit(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    data: HabitUpdate,
) -> HabitResponse:
    response = habit_service.update_habit(
        db, habit_id=habit_id, user_id=current_user.id, data=data, today=get_today()
    )
    db.commit()
    return response


@router.delete("/{habit_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_habit(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    habit_service.delete_habit(db, habit_id=habit_id, user_id=current_user.id)
    db.commit()


@router.post(
    "/{habit_id}/check-in/today",
    response_model=HabitResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def check_in_today(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> HabitResponse:
    response = habit_service.check_in_today(
        db, habit_id=habit_id, user_id=current_user.id, today=get_today()
    )
    db.commit()
    return response


@router.delete("/{habit_id}/check-in/today", response_model=HabitResponse)
def undo_check_in_today(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> HabitResponse:
    response = habit_service.undo_check_in_today(
        db, habit_id=habit_id, user_id=current_user.id, today=get_today()
    )
    db.commit()
    return response


@router.get("/{habit_id}/check-ins", response_model=MonthCheckInsResponse)
def get_month_check_ins(
    habit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    month: str = Query(..., description="Month in YYYY-MM format"),
) -> MonthCheckInsResponse:
    try:
        year_str, month_str = month.split("-")
        year, m = int(year_str), int(month_str)
        if not (1 <= m <= 12):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="month must be in YYYY-MM format (e.g. 2026-04)",
        )

    return habit_service.get_month_check_ins(
        db, habit_id=habit_id, user_id=current_user.id, year=year, month=m
    )
