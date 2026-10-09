from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.scripts import start_production


@pytest.fixture
def production(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SQLITE_VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setattr(start_production.os.path, "ismount", lambda path: Path(path) == tmp_path)
    return Settings(
        app_env="production", frontend_origin="https://console.example.test",
        database_url=f"sqlite:///{(tmp_path / 'route53.db').as_posix()}", _env_file=None,
    )


def test_valid_persistent_storage(production: Settings) -> None:
    assert start_production.validate_environment(production) == 8080


@pytest.mark.parametrize("database_url", [
    "sqlite:///./route53.db", "sqlite:///:memory:", "postgresql://localhost/example",
    "sqlite:///", "sqlite:////outside/route53.db",
])
def test_rejects_non_persistent_databases(production: Settings, database_url: str) -> None:
    production.database_url = database_url
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        start_production.validate_environment(production)


def test_missing_or_unmounted_volume(production: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SQLITE_VOLUME_PATH")
    with pytest.raises(RuntimeError, match="SQLITE_VOLUME_PATH"):
        start_production.validate_environment(production)
    monkeypatch.setenv("SQLITE_VOLUME_PATH", "/not-a-mounted-volume")
    with pytest.raises(RuntimeError, match="mounted persistent volume"):
        start_production.validate_environment(production)


@pytest.mark.parametrize("port", ["", "not-a-port", "0", "65536"])
def test_rejects_invalid_ports(production: Settings, monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.setenv("PORT", port)
    with pytest.raises(RuntimeError, match="PORT"):
        start_production.validate_environment(production)


def test_requires_secure_production(production: Settings) -> None:
    production.app_env = "development"
    with pytest.raises(RuntimeError, match="APP_ENV"):
        start_production.validate_environment(production)
    production.app_env = "production"
    production.session_cookie_secure = False
    with pytest.raises(RuntimeError, match="Secure session cookies"):
        start_production.validate_environment(production)


@pytest.mark.parametrize("failed_step", [1, 2])
def test_setup_failure_never_starts_server(
    production: Settings, monkeypatch: pytest.MonkeyPatch, failed_step: int,
) -> None:
    monkeypatch.setattr(start_production, "get_settings", lambda: production)
    failure = start_production.subprocess.CalledProcessError(1, "setup")
    run = Mock(side_effect=[failure] if failed_step == 1 else [None, failure])
    execute = Mock()
    monkeypatch.setattr(start_production.subprocess, "run", run)
    monkeypatch.setattr(start_production.os, "execv", execute)
    with pytest.raises(start_production.subprocess.CalledProcessError):
        start_production.main()
    assert run.call_count == failed_step
    assert all(call.kwargs["check"] is True for call in run.call_args_list)
    execute.assert_not_called()


def test_migrate_seed_then_one_worker(production: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(start_production, "get_settings", lambda: production)
    run = Mock()
    execute = Mock()
    monkeypatch.setattr(start_production.subprocess, "run", run)
    monkeypatch.setattr(start_production.os, "execv", execute)
    monkeypatch.setattr(start_production.os, "chdir", Mock())
    start_production.main()
    assert run.call_args_list[0].args[0][-3:] == ["alembic", "upgrade", "head"]
    assert run.call_args_list[1].args[0][-1] == "app.scripts.seed_demo_user"
    assert execute.call_args.args[1][-4:] == ["--port", "8080", "--workers", "1"]
