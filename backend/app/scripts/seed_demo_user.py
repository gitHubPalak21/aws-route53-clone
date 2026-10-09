from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import User


def seed_demo_user(db: DBSession, settings: Settings) -> tuple[User, bool]:
    """Create once; never reset existing credentials or reactivate a user."""
    existing = db.scalar(select(User).where(User.email == settings.demo_user_email))
    if existing is not None:
        return existing, False
    user = User(
        email=settings.demo_user_email,
        display_name=settings.demo_user_display_name,
        password_hash=hash_password(settings.demo_user_password.get_secret_value()),
    )
    db.add(user)
    db.commit()
    return user, True


def main() -> None:
    with SessionLocal() as db:
        user, created = seed_demo_user(db, get_settings())
        print(f"Demo user {'created' if created else 'already exists'}: {user.email}")


if __name__ == "__main__":
    main()
