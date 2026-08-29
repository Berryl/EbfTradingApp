import sqlite3
from pathlib import Path

import pytest

from ebf_data.sqlite import SQLiteAccountRepository, SQLiteTradeCampaignRepository
from ebf_trading.application import CreateTradeCampaign
from ebf_trading_app.bootstrap import (
    AppEnvironment,
    bootstrap,
    default_app_root,
    resolve_database_path,
)


def test_resolves_production_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)

    assert resolve_database_path(AppEnvironment.PROD) == (
        tmp_path / "EbfTrading" / "app.sqlite"
    )


def test_resolves_development_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)

    assert resolve_database_path(AppEnvironment.DEV) == (
        tmp_path / "EbfTrading" / "dev" / "app.sqlite"
    )


def test_resolves_test_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)

    assert resolve_database_path(AppEnvironment.TEST) == (
        tmp_path / "EbfTrading" / "test" / "app.sqlite"
    )


def test_explicit_db_path_wins_over_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBF_DB_PATH", str(tmp_path / "from-env.sqlite"))
    explicit = tmp_path / "explicit.sqlite"

    assert resolve_database_path(AppEnvironment.PROD, db_path=explicit) == explicit


def test_ebf_db_path_wins_over_data_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBF_DB_PATH", str(tmp_path / "override.sqlite"))
    monkeypatch.setenv("EBF_DATA_DIR", str(tmp_path / "data-dir"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert resolve_database_path(AppEnvironment.DEV) == tmp_path / "override.sqlite"


def test_ebf_data_dir_is_used_as_app_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "custom-root"
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.setenv("EBF_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))

    assert resolve_database_path(AppEnvironment.PROD) == data_dir / "app.sqlite"
    assert resolve_database_path(AppEnvironment.DEV) == data_dir / "dev" / "app.sqlite"


def test_explicit_app_root_wins_over_env_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.setenv("EBF_DATA_DIR", str(tmp_path / "env-root"))
    app_root = tmp_path / "injected-root"

    assert resolve_database_path(
        AppEnvironment.TEST,
        app_root=app_root,
    ) == app_root / "test" / "app.sqlite"


def test_falls_back_to_xdg_data_home_when_localappdata_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert default_app_root() == tmp_path / "xdg" / "EbfTrading"
    assert resolve_database_path(AppEnvironment.PROD) == (
        tmp_path / "xdg" / "EbfTrading" / "app.sqlite"
    )


def test_falls_back_to_home_local_share(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    assert default_app_root() == tmp_path / "home" / ".local" / "share" / "EbfTrading"


@pytest.mark.parametrize("environment", list(AppEnvironment))
def test_bootstrap_creates_database_and_constructs_components(
    environment: AppEnvironment,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "isolated" / "app.sqlite"

    components = bootstrap(environment, db_path=db_path)

    assert components.db_path == db_path
    assert components.db_path.parent.is_dir()
    assert components.db_path.is_file()
    assert isinstance(components.account_repo, SQLiteAccountRepository)
    assert isinstance(components.trade_campaign_repo, SQLiteTradeCampaignRepository)
    assert isinstance(components.create_trade_campaign, CreateTradeCampaign)

    with sqlite3.connect(components.db_path) as connection:
        sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'accounts'"
        account_table = connection.execute(sql).fetchone()

    assert account_table == ("accounts",)


def test_bootstrap_test_env_writes_under_test_subdirectory(
    tmp_path: Path,
) -> None:
    components = bootstrap(AppEnvironment.TEST, app_root=tmp_path)

    assert components.db_path == tmp_path / "test" / "app.sqlite"
    assert components.db_path.is_file()