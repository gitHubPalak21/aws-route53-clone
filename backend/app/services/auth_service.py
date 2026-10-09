from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings
from app.core.security import (
    generate_session_token,
    hash_session_token,
    verify_dummy_password,
    verify_password,
)
from app.db.types import utc_now
from app.models import Session, User


@dataclass(frozen=True)
class LoginResult:
    user: User
    raw_token: str = field(repr=False)
    expires_at: datetime


def cleanup_expired_sessions(db: DBSession, now: datetime | None = None) -> None:
    """Delete expired rows in the caller's transaction; no worker is needed."""
    db.execute(delete(Session).where(Session.expires_at <= (now or utc_now())))


def login(
    db: DBSession, settings: Settings, email: str, password: str,
    previous_token: str | None = None,
) -> LoginResult | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_dummy_password(password)
        return None
    password_valid = verify_password(password, user.password_hash)
    if not password_valid or not user.is_active:
        return None

    now = utc_now()
    cleanup_expired_sessions(db, now)
    if previous_token:
        # Rotate the current browser's session; other devices remain signed in.
        db.execute(delete(Session).where(Session.token_hash == hash_session_token(previous_token)))
    raw_token = generate_session_token()
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    db.add(Session(user=user, token_hash=hash_session_token(raw_token), expires_at=expires_at))
    db.commit()
    return LoginResult(user=user, raw_token=raw_token, expires_at=expires_at)


def resolve_session(db: DBSession, raw_token: str | None) -> Session | None:
    if not raw_token:
        return None
    session = db.scalar(select(Session).where(Session.token_hash == hash_session_token(raw_token)))
    if session is None:
        return None
    if session.expires_at <= utc_now() or session.user is None or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None
    return session


def mark_session_seen(db: DBSession, session: Session) -> None:
    """Only /me records usage; generic protected dependencies stay read-only."""
    session.last_seen_at = utc_now()
    db.commit()


def logout(db: DBSession, raw_token: str | None) -> None:
    if raw_token:
        db.execute(delete(Session).where(Session.token_hash == hash_session_token(raw_token)))
        db.commit()
