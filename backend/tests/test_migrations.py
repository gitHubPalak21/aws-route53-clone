from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
import pytest

from app.core.config import BACKEND_DIR
from app.db.base import Base


def test_migration_matches_models(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_record_set_uniqueness"
        context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == {"alembic_version", "users", "sessions", "hosted_zones", "dns_records"}
        assert "record_count" not in {column["name"] for column in inspector.get_columns("hosted_zones")}
        for table_name, model_table in Base.metadata.tables.items():
            expected_checks = {
                constraint.name for constraint in model_table.constraints
                if isinstance(constraint, CheckConstraint)
            }
            assert {constraint["name"] for constraint in inspector.get_check_constraints(table_name)} == expected_checks
        expected_indexes = {
            "users": {"ix_users_email"},
            "sessions": {"ix_sessions_user_id", "ix_sessions_token_hash", "ix_sessions_expires_at"},
            "hosted_zones": {"ix_hosted_zones_owner_id", "ix_hosted_zones_name"},
            "dns_records": {"ix_dns_records_hosted_zone_id", "ix_dns_records_name", "ix_dns_records_record_type",
                            "uq_dns_records_zone_name_type"},
        }
        for table_name, index_names in expected_indexes.items():
            assert {index["name"] for index in inspector.get_indexes(table_name)} == index_names
        for table_name in ["sessions", "hosted_zones", "dns_records"]:
            assert inspector.get_foreign_keys(table_name)[0]["options"]["ondelete"] == "CASCADE"


def test_migration_downgrade_and_reupgrade(db_engine: Engine) -> None:
    # The fixture supplies a fresh, disposable database, with no application data.
    with db_engine.begin() as connection:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
        assert set(Base.metadata.tables).issubset(inspect(connection).get_table_names())


def seed_legacy_record(connection) -> None:
    connection.execute(text("INSERT INTO users (id,email,display_name,password_hash) VALUES (1,'legacy@example.com','Legacy','test-only')"))
    connection.execute(text("INSERT INTO hosted_zones (id,owner_id,name) VALUES ('ZLEGACY',1,'example.com')"))
    connection.execute(text("INSERT INTO dns_records (id,hosted_zone_id,name,record_type,\"values\",is_system) "
                            "VALUES ('00000000-0000-4000-8000-000000000001','ZLEGACY','example.com','NS','[\"ns.example.com.\"]',1)"))


def test_unique_index_migration_preserves_legacy_data_and_cascade(db_engine: Engine) -> None:
    with db_engine.begin() as connection:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_core_tables")
        seed_legacy_record(connection)
        before = connection.execute(text("SELECT * FROM dns_records")).all()
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT * FROM dns_records")).all() == before
        index = next(i for i in inspect(connection).get_indexes("dns_records") if i["name"] == "uq_dns_records_zone_name_type")
        assert index["unique"] == 1 and index["column_names"] == ["hosted_zone_id", "name", "record_type"]
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO dns_records (id,hosted_zone_id,name,record_type) VALUES ('duplicate','ZLEGACY','example.com','NS')"))
        connection.execute(text("DELETE FROM hosted_zones WHERE id='ZLEGACY'"))
        assert connection.scalar(text("SELECT COUNT(*) FROM dns_records")) == 0


def test_unique_index_migration_rejects_existing_duplicates_without_deleting_data(db_engine: Engine) -> None:
    with db_engine.begin() as connection:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_core_tables")
        seed_legacy_record(connection)
        connection.execute(text("INSERT INTO dns_records (id,hosted_zone_id,name,record_type) VALUES ('duplicate','ZLEGACY','example.com','NS')"))
        with pytest.raises(IntegrityError):
            command.upgrade(config, "head")
        assert connection.scalar(text("SELECT COUNT(*) FROM dns_records")) == 2
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_core_tables"
