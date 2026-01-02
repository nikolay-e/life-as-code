from sqlalchemy import select

from database import get_db_session_context
from models import UserCredentials


def get_user_credentials(user_id: int) -> UserCredentials | None:
    with get_db_session_context() as db:
        return db.scalars(
            select(UserCredentials).where(UserCredentials.user_id == user_id)
        ).first()
