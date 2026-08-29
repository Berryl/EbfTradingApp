import sqlite3
from pathlib import Path

import pytest

from ebf_data.sqlite import SQLiteAccountRepository, SQLiteTradeCampaignRepository
from ebf_trading.application import CreateTradeCampaign
from ebf_trading_app.bootstrap import (
    AppEnvironment,
    bootstrap,
    resolve_database_path,
)


def test_resolves_production_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_database_path(AppEnvironment.PROD) == (
        tmp_path / "EbfTrading" / "journal.sqlite"
    )


def test_resolves_development_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_database_path(AppEnvironment.DEV) == (
        tmp_path / "EbfTrading" / "dev" / "journal.sqlite"
    )


@pytest.mark.parametrize("environment", list(AppEnvironment))
def test_bootstrap_creates_database_and_constructs_components(
    environment: AppEnvironment,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    components = bootstrap(environment)

    assert components.db_path.parent.is_dir()
    assert components.db_path.is_file()
    assert isinstance(components.account_repo, SQLiteAccountRepository)
    assert isinstance(components.trade_campaign_repo, SQLiteTradeCampaignRepository)
    assert isinstance(components.create_trade_campaign, CreateTradeCampaign)

    with sqlite3.connect(components.db_path) as connection:
        sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'accounts'"
        account_table = connection.execute(sql).fetchone()

    assert account_table == ("accounts",)
