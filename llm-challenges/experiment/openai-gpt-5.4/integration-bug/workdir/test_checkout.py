import asyncio

import pytest

from checkout import checkout
from inventory import Inventory
from payments import PaymentGateway


@pytest.mark.asyncio
async def test_should_not_charge_without_delivery_when_stock_runs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("payments.random.random", lambda: 1.0)
    inventory = Inventory(1)
    gateway = PaymentGateway(failure_rate=0.0)

    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_2", 1, 100.0, inventory, gateway),
    )

    assert sum(results) == 1
    assert inventory.stock == 0
    assert gateway.total_charged == 100.0
    assert gateway.charges == [{"order_id": "order_1", "amount": 100.0}] or gateway.charges == [{"order_id": "order_2", "amount": 100.0}]


@pytest.mark.asyncio
async def test_should_not_charge_more_than_once_for_same_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("payments.random.random", lambda: 1.0)
    inventory = Inventory(2)
    gateway = PaymentGateway(failure_rate=0.0)

    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_1", 1, 100.0, inventory, gateway),
    )

    assert sum(results) == 1
    assert inventory.stock == 1
    assert gateway.total_charged == 100.0
    assert gateway.charges == [{"order_id": "order_1", "amount": 100.0}]
