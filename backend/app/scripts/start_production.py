"""Validate persistent storage, migrate, seed, then exec one production worker."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import BACKEND_DIR, Settings, get_settings


def validate_environment(settings: Settings) -> int:
    if settings.app_env.lower() != "production":
        raise RuntimeError("Production startup requires APP_ENV=production.")
    if not settings.session_cookie_secure or settings.frontend_origin.scheme != "https":
        raise RuntimeError("Production requires a HTTPS FRONTEND_ORIGIN and Secure session cookies.")

    volume_value = os.environ.get("SQLITE_VOLUME_PATH")
    if not volume_value:
        raise RuntimeError("Set SQLITE_VOLUME_PATH to the persistent volume mount path.")
    volume = Path(volume_value)
    if not volume.is_absolute() or not volume.is_dir() or not os.path.ismount(volume):
        raise RuntimeError("SQLITE_VOLUME_PATH must be an existing mounted persistent volume.")
    volume = volume.resolve()
    if volume == Path(volume.anchor):
        raise RuntimeError("The root filesystem cannot be used as the SQLite volume.")

    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:" or url.query:
        raise RuntimeError("Production DATABASE_URL must use a persistent SQLite file.")
    database = Path(url.database)
    if not database.is_absolute() or not database.resolve().is_relative_to(volume):
        raise RuntimeError("DATABASE_URL must point to an absolute file inside SQLITE_VOLUME_PATH.")
    if not database.parent.is_dir() or database.is_dir():
        raise RuntimeError("The SQLite database parent directory must exist on the volume.")
    if not os.access(database.parent, os.W_OK) or (database.exists() and not os.access(database, os.W_OK)):
        raise RuntimeError("The SQLite database and its directory must be writable.")

    try:
        port = int(os.environ["PORT"])
    except (KeyError, ValueError) as error:
        raise RuntimeError("Production startup requires a valid provider PORT.") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535.")
    return port


def main() -> None:
    port = validate_environment(get_settings())
    # Volumes are available at service startup, not necessarily during a build
    # or provider release hook. Failures propagate and prevent server startup.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True)
    subprocess.run([sys.executable, "-m", "app.scripts.seed_demo_user"], cwd=BACKEND_DIR, check=True)
    os.chdir(BACKEND_DIR)
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", str(port), "--workers", "1",
    ])


if __name__ == "__main__":
    main()
