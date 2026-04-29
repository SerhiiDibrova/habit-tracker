import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.habit import HabitStatus


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    start_date: date
    status: HabitStatus = HabitStatus.active


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    start_date: date | None = None
    status: HabitStatus | None = None


class HabitResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    start_date: date
    status: str
    created_at: datetime
    updated_at: datetime
    current_streak: int
    best_streak: int
    total_check_ins: int
    completed_today: bool


class MonthCheckInsResponse(BaseModel):
    check_in_dates: list[date]
