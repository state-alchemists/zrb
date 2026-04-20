import asyncio

import pytest

from checkout import checkout
from inventory import Inventory
from payments import PaymentGateway


@pytest.mark.asyncio
async def test_should_not_charge_when_inventory_is_exhausted() -> None:
    inventory = Inventory(1)
    gateway = PaymentGateway(failure_rate=0.0)

    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_2", 1, 100.0, inventory, gateway),
    )

    assert sum(results) == 1
    assert inventory.stock == 0
    assert gateway.total_charged == 100.0
    assert len(gateway.charges) == 1


@pytest.mark.asyncio
async def test_should_not_charge_more_than_once_for_same_order() -> None:
    inventory = Inventory(2)
    gateway = PaymentGateway(failure_rate=0.0)

    results = await asyncio.gather(
        checkout("order_1", 1, 100.0, inventory, gateway),
        checkout("order_1", 1, 100.0, inventory, gateway),
    )

    assert sum(results) == 1
    assert inventory.stock == 1
    assert gateway.total_charged == 100.0
    assert [charge["order_id"] for charge in gateway.charges] == ["order_1"]
