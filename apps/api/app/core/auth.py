from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User


def get_current_user(
    x_user_email: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    email = x_user_email or get_settings().mock_auth_email
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(email=email)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        user = db.scalar(select(User).where(User.email == email))
        if user:
            return user
        raise
