from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.database import SessionLocal


def get_db() -> Iterator[Session]:
    """Provide one session per request; services explicitly commit writes."""
    with SessionLocal() as session:
        yield session
