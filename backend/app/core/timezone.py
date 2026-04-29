import zoneinfo
from datetime import date, datetime, timezone

from app.core.config import settings


def get_today() -> date:
    tz = zoneinfo.ZoneInfo(settings.app_timezone)
    return datetime.now(timezone.utc).astimezone(tz).date()
