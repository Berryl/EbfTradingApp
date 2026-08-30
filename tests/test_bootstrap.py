import sqlite3
from pathlib import Path
from uuid import UUID

import pytest

from ebf_data.sqlite import SQLiteAccountRepository, SQLiteTradeCampaignRepository
from ebf_domain.money.money import Money
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
    class TestWhenOnlyEnvironmentIsGiven:
        def test_prod_uses_app_root_directly(self, local_app_data: Path) -> None:
            assert resolve_database_path(AppEnvironment.PROD) == (local_app_data / "EbfTrading" / "app.sqlite")

        def test_dev_uses_dev_subdirectory(self, local_app_data: Path) -> None:
            assert resolve_database_path(AppEnvironment.DEV) == (local_app_data / "EbfTrading" / "dev" / "app.sqlite")

        def test_test_uses_test_subdirectory(self, local_app_data: Path) -> None:
            assert resolve_database_path(AppEnvironment.TEST) == (local_app_data / "EbfTrading" / "test" / "app.sqlite")

    class TestWhenDbPathArgumentIsPassed:
        def test_it_wins_over_ebf_db_path(self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            clean_db_env.setenv("EBF_DB_PATH", str(tmp_path / "from-env.sqlite"))
            explicit_path = tmp_path / "explicit_path.sqlite"

            assert resolve_database_path(AppEnvironment.PROD, db_path=explicit_path) == explicit_path

    class TestWhenEbfDbPathIsSet:
        def test_it_wins_over_data_dir_and_platform_root(
            self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch
        ) -> None:
            clean_db_env.setenv("EBF_DB_PATH", str(tmp_path / "override.sqlite"))
            clean_db_env.setenv("EBF_DATA_DIR", str(tmp_path / "data-dir"))
            clean_db_env.setenv("LOCALAPPDATA", str(tmp_path / "local"))

            assert resolve_database_path(AppEnvironment.DEV) == (tmp_path / "override.sqlite")

    class TestWhenEbfDataDirIsSet:
        def test_it_is_used_as_app_root(self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            data_dir = tmp_path / "custom-root"
            clean_db_env.setenv("EBF_DATA_DIR", str(data_dir))
            clean_db_env.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))

            assert resolve_database_path(AppEnvironment.PROD) == data_dir / "app.sqlite"
            assert resolve_database_path(AppEnvironment.DEV) == (data_dir / "dev" / "app.sqlite")

    class TestWhenAppRootArgumentIsPassed:
        def test_it_wins_over_ebf_data_dir(self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            clean_db_env.setenv("EBF_DATA_DIR", str(tmp_path / "env-root"))
            app_root = tmp_path / "injected-root"

            assert (
                resolve_database_path(
                    AppEnvironment.TEST,
                    app_root=app_root,
                )
                == app_root / "test" / "app.sqlite"
            )

    class TestWhenPlatformRootIsUsed:
        def test_falls_back_to_xdg_data_home(self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            clean_db_env.delenv("LOCALAPPDATA", raising=False)
            clean_db_env.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

            assert default_app_root() == tmp_path / "xdg" / "EbfTrading"
            assert resolve_database_path(AppEnvironment.PROD) == (tmp_path / "xdg" / "EbfTrading" / "app.sqlite")

        def test_falls_back_to_home_local_share(self, tmp_path: Path, clean_db_env: pytest.MonkeyPatch) -> None:
            clean_db_env.delenv("LOCALAPPDATA", raising=False)
            clean_db_env.delenv("XDG_DATA_HOME", raising=False)
            clean_db_env.setattr(Path, "home", classmethod(lambda _cls: tmp_path / "home"))

            assert default_app_root() == (tmp_path / "home" / ".local" / "share" / "EbfTrading")


class TestBootstrap:
    @pytest.mark.parametrize("env", list(AppEnvironment))
    def test_creates_database_and_constructs_components(self, env: AppEnvironment, tmp_path: Path) -> None:
        db_path = tmp_path / "isolated" / "app.sqlite"

        components = bootstrap(env, db_path=db_path)

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

    def test_test_env_writes_under_test_subdirectory(self, tmp_path: Path) -> None:
        components = bootstrap(AppEnvironment.TEST, app_root=tmp_path)

        assert components.db_path == tmp_path / "test" / "app.sqlite"
        assert components.db_path.is_file()

    class TestDefaultDevAccount:
        _DEV_ACCOUNT_ID = UUID("6a0c5f22-5593-4b3f-8b1f-6f7f5c47e2a1")

        def test_attributes_are_as_expected(self, tmp_path: Path) -> None:
            components = bootstrap(AppEnvironment.DEV, db_path=tmp_path / "dev.sqlite")

            acct = components.account_repo.get(self._DEV_ACCOUNT_ID)

            assert acct is not None
            assert acct.id == self._DEV_ACCOUNT_ID
            assert acct.owner == "LLC"
            assert acct.balance == Money.mint("0")

        def test_provisioning_is_idempotent(self, tmp_path: Path) -> None:
            db_path = tmp_path / "dev.sqlite"
            changed_owner = "Existing LLC"
            changed_balance = Money.mint("125")

            bootstrap(AppEnvironment.DEV, db_path=db_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE accounts SET owner = ?, balance_minor_units = ? WHERE id = ?",
                    (changed_owner, changed_balance.amount_cents, str(self._DEV_ACCOUNT_ID)),
                )

            components = bootstrap(AppEnvironment.DEV, db_path=db_path)
            acct = components.account_repo.get(self._DEV_ACCOUNT_ID)

            with sqlite3.connect(db_path) as connection:
                account_count = connection.execute(
                    "SELECT COUNT(*) FROM accounts WHERE id = ?",
                    (str(self._DEV_ACCOUNT_ID),),
                ).fetchone()

            assert account_count == (1,)
            assert acct is not None
            assert acct.owner == changed_owner
            assert acct.balance == changed_balance

        @pytest.mark.parametrize("env", [AppEnvironment.PROD, AppEnvironment.TEST])
        def test_only_dev_creates_the_default_account(self, tmp_path: Path, env: AppEnvironment) -> None:
            components = bootstrap(env, db_path=tmp_path / f"{env.value}.sqlite")

            assert components.account_repo.get(self._DEV_ACCOUNT_ID) is None
