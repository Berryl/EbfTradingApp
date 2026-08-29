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


@pytest.fixture
def clean_db_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Clear path overrides so resolution uses only what the test sets."""
    monkeypatch.delenv("EBF_DB_PATH", raising=False)
    monkeypatch.delenv("EBF_DATA_DIR", raising=False)
    return monkeypatch


@pytest.fixture
def local_app_data(tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> Path:
    clean_db_env.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


class TestResolveDatabasePath:
    class TestWhenAppEnvironmentOnly:

        def test_when_prod(self, local_app_data: Path) -> None:
            path = local_app_data / "EbfTrading" / "app.sqlite"
            assert resolve_database_path(AppEnvironment.PROD) == path

        def test_when_dev(self, local_app_data: Path) -> None:
            path = local_app_data / "EbfTrading" / "dev" / "app.sqlite"
            assert resolve_database_path(AppEnvironment.DEV) == path

        def test_when_test(self, local_app_data: Path) -> None:
            path = local_app_data / "EbfTrading" / "test" / "app.sqlite"
            assert resolve_database_path(AppEnvironment.TEST) == path

    class TestWhenDbPathIsPassed:
        def test_db_path_overrides_environment(
                self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            clean_db_env.setenv("EBF_DB_PATH", str(tmp_path / "from-env.sqlite"))
            explicit_path = tmp_path / "explicit_path.sqlite"

            assert resolve_database_path(AppEnvironment.PROD, db_path=explicit_path) == explicit_path


def test_ebf_db_path_wins_over_data_dir(
        tmp_path: Path,
        clean_db_env: pytest.MonkeyPatch,
) -> None:
    clean_db_env.setenv("EBF_DB_PATH", str(tmp_path / "override.sqlite"))
    clean_db_env.setenv("EBF_DATA_DIR", str(tmp_path / "data-dir"))
    clean_db_env.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert resolve_database_path(AppEnvironment.DEV) == tmp_path / "override.sqlite"


def test_ebf_data_dir_is_used_as_app_root(
        tmp_path: Path,
        clean_db_env: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "custom-root"
    clean_db_env.setenv("EBF_DATA_DIR", str(data_dir))
    clean_db_env.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))

    assert resolve_database_path(AppEnvironment.PROD) == data_dir / "app.sqlite"
    assert resolve_database_path(AppEnvironment.DEV) == data_dir / "dev" / "app.sqlite"


def test_explicit_app_root_wins_over_env_roots(
        tmp_path: Path,
        clean_db_env: pytest.MonkeyPatch,
) -> None:
    clean_db_env.setenv("EBF_DATA_DIR", str(tmp_path / "env-root"))
    app_root = tmp_path / "injected-root"

    assert resolve_database_path(
        AppEnvironment.TEST,
        app_root=app_root,
    ) == app_root / "test" / "app.sqlite"


def test_falls_back_to_xdg_data_home_when_localappdata_missing(
        tmp_path: Path,
        clean_db_env: pytest.MonkeyPatch,
) -> None:
    clean_db_env.delenv("LOCALAPPDATA", raising=False)
    clean_db_env.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert default_app_root() == tmp_path / "xdg" / "EbfTrading"
    assert resolve_database_path(AppEnvironment.PROD) == (
            tmp_path / "xdg" / "EbfTrading" / "app.sqlite"
    )


def test_falls_back_to_home_local_share(
        tmp_path: Path,
        clean_db_env: pytest.MonkeyPatch,
) -> None:
    clean_db_env.delenv("LOCALAPPDATA", raising=False)
    clean_db_env.delenv("XDG_DATA_HOME", raising=False)
    clean_db_env.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    assert default_app_root() == tmp_path / "home" / ".local" / "share" / "EbfTrading"


class TestBootStrap:
    @pytest.mark.parametrize("environment", list(AppEnvironment))
    def test_bootstrap_creates_database_and_constructs_components(
            self, environment: AppEnvironment, tmp_path: Path
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

    def test_bootstrap_test_env_writes_under_test_subdirectory(self, tmp_path: Path) -> None:
        components = bootstrap(AppEnvironment.TEST, app_root=tmp_path)

        assert components.db_path == tmp_path / "test" / "app.sqlite"
        assert components.db_path.is_file()
