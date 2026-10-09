from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app import models
from app.db.database import engine
from app.db.types import UTCDateTime

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Importing the models package registers every model on the shared Base.
target_metadata = models.User.metadata


def render_item(kind: str, item: object, autogen_context: object) -> str | bool:
    # Keep migrations independent of mutable application type implementations.
    if kind == "type" and isinstance(item, UTCDateTime):
        return "sa.DateTime()"
    return False


def configure_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=connection.dialect.name == "sqlite",
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    # Tests can provide an isolated connection. Normal CLI use reuses our engine.
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        configure_connection(supplied_connection)
    else:
        with engine.connect() as connection:
            configure_connection(connection)
