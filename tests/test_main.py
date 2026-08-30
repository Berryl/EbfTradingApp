from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ebf_trading.application import FilledOptionTradeInput
from ebf_trading_app.__main__ import SaveTrade, create_dev_save_trade, main
from ebf_trading_app.bootstrap import DEV_DEFAULT_ACCOUNT_ID, AppEnvironment
from ebf_trading_ui.view_models.ports.null_trade_record import NullTradeRecord
from ebf_trading_ui.view_models.ports.trade_record import TradeRecord


class FakeCreateTradeCampaign:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, FilledOptionTradeInput]] = []

    def execute(self, account_id: UUID, trade: FilledOptionTradeInput) -> object:
        self.calls.append((account_id, trade))
        return object()


@dataclass
class FakeComponents:
    create_trade_campaign: FakeCreateTradeCampaign


class FakeApplication:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        self.exec_called = False

    def exec(self) -> int:
        self.exec_called = True
        return self.exit_code


class FakeTradeEntryForm:
    def __init__(self, record: TradeRecord, save_trade: SaveTrade) -> None:
        self.record = record
        self.save_trade = save_trade
        self.shown = False

    def show(self) -> None:
        self.shown = True


def test_save_callback_uses_the_default_dev_account() -> None:
    operation = FakeCreateTradeCampaign()
    trade = cast(FilledOptionTradeInput, object())

    save_trade = create_dev_save_trade(operation)
    save_trade(trade)

    assert operation.calls == [(DEV_DEFAULT_ACCOUNT_ID, trade)]


def test_main_boots_only_dev_with_injected_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected_exit_code = 27

    operation = FakeCreateTradeCampaign()
    components = FakeComponents(create_trade_campaign=operation)
    bootstrapped_environments: list[AppEnvironment] = []
    application = FakeApplication(exit_code=expected_exit_code)
    application_arguments: list[list[str]] = []
    forms: list[FakeTradeEntryForm] = []

    def bootstrapper(environment: AppEnvironment) -> FakeComponents:
        bootstrapped_environments.append(environment)
        return components

    def application_factory(arguments: list[str]) -> FakeApplication:
        application_arguments.append(arguments)
        return application

    def form_factory(record: TradeRecord, save_trade: SaveTrade) -> FakeTradeEntryForm:
        form = FakeTradeEntryForm(record, save_trade)
        forms.append(form)
        return form

    exit_code = main(
        ["ebf-trading"],
        boot=bootstrapper,
        app_factory=application_factory,
        form_factory=form_factory,
    )

    assert exit_code == expected_exit_code
    assert bootstrapped_environments == [AppEnvironment.DEV]
    assert application_arguments == [["ebf-trading"]]
    assert application.exec_called
    assert len(forms) == 1
    assert isinstance(forms[0].record, NullTradeRecord)
    assert forms[0].shown
    assert not (tmp_path / "EbfTrading" / "app.sqlite").exists()
    assert not (tmp_path / "EbfTrading" / "dev" / "app.sqlite").exists()
