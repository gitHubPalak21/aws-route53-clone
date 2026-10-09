from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.db.database import enable_sqlite_foreign_keys


def migration_config(connection: Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """Use real migrations against a fresh SQLite file, never route53.db."""
    test_engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    event.listen(test_engine, "connect", enable_sqlite_foreign_keys)
    with test_engine.begin() as connection:
        command.upgrade(migration_config(connection), "head")
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session
