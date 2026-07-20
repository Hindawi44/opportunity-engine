from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.portfolio_manager import PortfolioManager


def test_records_purchase_and_updates_snapshot(tmp_path) -> None:
    database = tmp_path / "portfolio.json"
    manager = PortfolioManager(database, initial_capital_nok=50_000)

    position = manager.record_purchase(
        opportunity_id="opp-1",
        title="Butikkinnredning",
        purchase_price_nok=10_000,
        acquisition_cost_nok=2_000,
        estimated_value_nok=18_000,
        purchased_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    snapshot = manager.snapshot()

    assert position.status == "open"
    assert position.total_invested_nok == 12_000
    assert position.unrealized_profit_nok == 6_000
    assert position.roi == 0.5
    assert snapshot.cash_balance_nok == 38_000
    assert snapshot.invested_capital_nok == 12_000
    assert snapshot.estimated_open_value_nok == 18_000
    assert snapshot.total_equity_nok == 56_000
    assert snapshot.open_position_count == 1
    assert database.exists()


def test_prevents_duplicate_purchase_and_overspending(tmp_path) -> None:
    manager = PortfolioManager(tmp_path / "portfolio.json", initial_capital_nok=10_000)
    manager.record_purchase(
        opportunity_id="opp-1",
        title="Kontormøbler",
        purchase_price_nok=4_000,
    )

    with pytest.raises(ValueError, match="already recorded"):
        manager.record_purchase(
            opportunity_id="opp-1",
            title="Kontormøbler",
            purchase_price_nok=4_000,
        )

    with pytest.raises(ValueError, match="insufficient cash"):
        manager.record_purchase(
            opportunity_id="opp-2",
            title="Lagerparti",
            purchase_price_nok=7_000,
        )


def test_records_sale_and_realized_profit(tmp_path) -> None:
    manager = PortfolioManager(tmp_path / "portfolio.json", initial_capital_nok=30_000)
    manager.record_purchase(
        opportunity_id="opp-1",
        title="Symaskin",
        purchase_price_nok=8_000,
        acquisition_cost_nok=1_000,
    )

    position = manager.record_sale(
        "opp-1",
        sale_price_nok=14_000,
        selling_cost_nok=1_000,
        sold_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    snapshot = manager.snapshot()

    assert position.status == "closed"
    assert position.realized_profit_nok == 4_000
    assert position.roi == pytest.approx(4_000 / 9_000, abs=0.0001)
    assert snapshot.cash_balance_nok == 34_000
    assert snapshot.realized_profit_nok == 4_000
    assert snapshot.open_position_count == 0
    assert snapshot.closed_position_count == 1
    assert snapshot.total_equity_nok == 34_000


def test_reloads_existing_portfolio_without_requiring_initial_capital(tmp_path) -> None:
    database = tmp_path / "portfolio.json"
    PortfolioManager(database, initial_capital_nok=20_000).record_purchase(
        opportunity_id="opp-1",
        title="Stoler",
        purchase_price_nok=5_000,
    )

    reloaded = PortfolioManager(database)
    snapshot = reloaded.snapshot()

    assert snapshot.initial_capital_nok == 20_000
    assert snapshot.cash_balance_nok == 15_000
    assert snapshot.open_position_count == 1


def test_estimated_value_only_changes_open_positions(tmp_path) -> None:
    manager = PortfolioManager(tmp_path / "portfolio.json", initial_capital_nok=20_000)
    manager.record_purchase(
        opportunity_id="opp-1",
        title="Bord",
        purchase_price_nok=5_000,
    )
    updated = manager.update_estimated_value("opp-1", 7_500)
    assert updated.unrealized_profit_nok == 2_500

    manager.record_sale("opp-1", sale_price_nok=7_000)
    with pytest.raises(ValueError, match="open position"):
        manager.update_estimated_value("opp-1", 8_000)
