"""Persistence bootstrap for the EBF trading application."""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ebf_data.sqlite import (
    SQLiteAccountRepository,
    SQLiteTradeCampaignRepository,
    initialize_database,
)
from ebf_trading.application import CreateTradeCampaign


class AppEnvironment(StrEnum):
    """Persistent database environments supported by the application."""

    PROD = "production"
    DEV = "development"


@dataclass(frozen=True, slots=True)
class ApplicationComponents:
    """Application objects constructed at startup."""

    db_path: Path
    account_repo: SQLiteAccountRepository
    trade_campaign_repo: SQLiteTradeCampaignRepository
    create_trade_campaign: CreateTradeCampaign


def resolve_database_path(environment: AppEnvironment) -> Path:
    """Return the journal path for an application environment."""
    app_directory = Path(os.environ["LOCALAPPDATA"]) / "EbfTrading"
    if environment is AppEnvironment.DEV:
        app_directory /= "dev"
    return app_directory / "journal.sqlite"


def bootstrap(env: AppEnvironment) -> ApplicationComponents:
    """Initialize persistence and construct the application's use cases."""
    db_path = resolve_database_path(env)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(db_path)

    account_repo = SQLiteAccountRepository(db_path)
    trade_campaign_repo = SQLiteTradeCampaignRepository(db_path)
    create_trade_campaign = CreateTradeCampaign(account_repo, trade_campaign_repo)

    return ApplicationComponents(
        db_path=db_path,
        account_repo=account_repo,
        trade_campaign_repo=trade_campaign_repo,
        create_trade_campaign=create_trade_campaign,
    )
