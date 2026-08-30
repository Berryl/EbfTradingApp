"""DEV entry point for the EBF trading desktop application."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Protocol
from uuid import UUID

from PySide6.QtWidgets import QApplication

from ebf_trading.application import FilledOptionTradeInput
from ebf_trading_app.bootstrap import (
    DEV_DEFAULT_ACCOUNT_ID,
    AppEnvironment,
    bootstrap,
)
from ebf_trading_ui.forms.trade_entry.trade_entry_form import TradeEntryForm
from ebf_trading_ui.view_models.ports.null_trade_record import NullTradeRecord
from ebf_trading_ui.view_models.ports.trade_record import TradeRecord

type SaveTrade = Callable[[FilledOptionTradeInput], None]


class _CreateTradeCampaign(Protocol):
    def execute(self, account_id: UUID, trade: FilledOptionTradeInput) -> object: ...


class _ApplicationComponents(Protocol):
    @property
    def create_trade_campaign(self) -> _CreateTradeCampaign: ...


class _QtApplication(Protocol):
    def exec(self) -> int: ...


class _TradeEntryDialog(Protocol):
    def show(self) -> None: ...


type Bootstrapper = Callable[[AppEnvironment], _ApplicationComponents]
type ApplicationFactory = Callable[[list[str]], _QtApplication]
type FormFactory = Callable[[TradeRecord, SaveTrade], _TradeEntryDialog]


def create_dev_save_trade(operation: _CreateTradeCampaign) -> SaveTrade:
    """Bind the DEV account identity to the trade-campaign operation."""

    def save_trade(trade: FilledOptionTradeInput) -> None:
        operation.execute(DEV_DEFAULT_ACCOUNT_ID, trade)

    return save_trade


def main(
    argv: Sequence[str] | None = None,
    *,
    boot: Bootstrapper = bootstrap,
    app_factory: ApplicationFactory = QApplication,
    form_factory: FormFactory = TradeEntryForm,
) -> int:
    """Compose and run the first DEV-only Trade Entry application slice."""
    components = boot(AppEnvironment.DEV)
    save_trade = create_dev_save_trade(components.create_trade_campaign)

    app = app_factory(list(sys.argv if argv is None else argv))
    form = form_factory(NullTradeRecord(), save_trade)
    form.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
