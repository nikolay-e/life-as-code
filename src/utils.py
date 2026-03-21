from sqlalchemy import select

from database import get_db_session_context
from enums import DataSource
from models import UserCredentials


def get_user_credentials(user_id: int) -> UserCredentials | None:
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).where(UserCredentials.user_id == user_id)
        ).first()
        if creds:
            db.expunge(creds)
        return creds


def has_credentials_for_source(user_id: int, source: str) -> bool:
    creds = get_user_credentials(user_id)
    if not creds:
        return False
    if source == DataSource.GARMIN.value:
        return bool(creds.garmin_email and creds.encrypted_garmin_password)
    elif source == DataSource.HEVY.value:
        return bool(creds.encrypted_hevy_api_key)
    elif source == DataSource.WHOOP.value:
        return bool(creds.encrypted_whoop_access_token)
    return False
