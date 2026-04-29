from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_or_create_user(
    db: Session,
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    display_name: str,
    avatar_url: str | None,
) -> User:
    stmt = select(User).where(
        User.provider == provider,
        User.provider_user_id == provider_user_id,
    )
    user = db.scalars(stmt).first()

    if user is None:
        user = User(
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
    else:
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url

    db.flush()
    return user
