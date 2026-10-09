from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import BACKEND_DIR, get_settings

database_url = make_url(get_settings().database_url)
is_sqlite = database_url.get_backend_name() == "sqlite"

# Anchor relative SQLite paths to backend/, independent of the launch directory.
if is_sqlite and database_url.database not in (None, "", ":memory:"):
    database_path = Path(database_url.database)
    if not database_path.is_absolute():
        database_url = database_url.set(database=str(BACKEND_DIR / database_path))

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        connection: Connection, _connection_record: ConnectionPoolEntry
    ) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
