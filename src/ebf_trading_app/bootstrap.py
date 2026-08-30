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

_APP_DIR_NAME = "EbfTrading"
_DB_FILENAME = "app.sqlite"
_DATA_DIR_ENV = "EBF_DATA_DIR"
_DB_PATH_ENV = "EBF_DB_PATH"


class AppEnvironment(StrEnum):
    """Persistent database environments supported by the application.

    TEST uses an on-disk file under ``<app_root>/test/``. It is not in-memory.
    Pass ``db_path`` from tests (a temp file, or a shared-memory URI). Do not
    use plain ``:memory:`` when more than one connection must see the same data.
    (DO use ``:memory:`` otherwise when safe, for speed)
    """

    PROD = "production"
    DEV = "development"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class ApplicationComponents:
    """Application objects constructed at startup."""

    db_path: Path
    account_repo: SQLiteAccountRepository
    trade_campaign_repo: SQLiteTradeCampaignRepository
    create_trade_campaign: CreateTradeCampaign


def _platform_app_data_root() -> Path:
    """Return the OS-specific per-user application data root."""
    if local_appdata := os.environ.get("LOCALAPPDATA"):
        return Path(local_appdata)
    if xdg_data_home := os.environ.get("XDG_DATA_HOME"):
        return Path(xdg_data_home)
    return Path.home() / ".local" / "share"


def default_app_root() -> Path:
    """Return the default EBF application data directory."""
    return _platform_app_data_root() / _APP_DIR_NAME


def resolve_database_path(env: AppEnvironment, *, app_root: Path | None = None, db_path: Path | None = None) -> Path:
    """Return the database path for an application environment.

    Resolution order:
    1. Explicit ``db_path`` argument
    2. ``EBF_DB_PATH`` environment variable
    3. ``app_root`` / environment subdirectory / ``app.sqlite``
    4. ``EBF_DATA_DIR`` as ``app_root`` if set, otherwise the platform default

    TEST is still a real file (``<root>/test/app.sqlite``).
    In-memory databases are a test-runner concern: pass ``db_path`` explicitly.
    """
    if db_path is not None:
        return db_path

    if env_db_path := os.environ.get(_DB_PATH_ENV):
        return Path(env_db_path)

    root = app_root
    if root is None:
        root = Path(os.environ[_DATA_DIR_ENV]) if _DATA_DIR_ENV in os.environ else default_app_root()

    if env is AppEnvironment.DEV:
        root = root / "dev"
    elif env is AppEnvironment.TEST:
        root = root / "test"

    return root / _DB_FILENAME


def bootstrap(
    env: AppEnvironment, *, app_root: Path | None = None, db_path: Path | None = None
) -> ApplicationComponents:
    """Initialize persistence and construct the application's use cases.

    ``initialize_database`` must be idempotent (e.g. ``CREATE TABLE IF NOT EXISTS``).
    Both repositories currently open the same file independently. If
    ``CreateTradeCampaign`` writes through both, give them a shared connection
    or unit of work so the use case is a single transaction.

    For tests, prefer ``db_path`` pointing at a temp file or a shared-memory
    URI. ``AppEnvironment.TEST`` only changes the default on-disk location.
    """
    resolved_db_path = resolve_database_path(env, app_root=app_root, db_path=db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(resolved_db_path)

    account_repo = SQLiteAccountRepository(resolved_db_path)
    trade_campaign_repo = SQLiteTradeCampaignRepository(resolved_db_path)
    create_trade_campaign = CreateTradeCampaign(account_repo, trade_campaign_repo)

    return ApplicationComponents(
        db_path=resolved_db_path,
        account_repo=account_repo,
        trade_campaign_repo=trade_campaign_repo,
        create_trade_campaign=create_trade_campaign,
    )
