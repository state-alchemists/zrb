import asyncio

from checkout import checkout
from inventory import Inventory
from payments import PaymentGateway


async def run_concurrent_orders(stock: int, order_count: int, failure_rate: float = 0.0):
    inventory = Inventory(stock)
    gateway = PaymentGateway(failure_rate=failure_rate)
    results = await asyncio.gather(
        *[
            checkout(f"order_{i}", 1, 100.0, inventory, gateway)
            for i in range(order_count)
        ]
    )
    return results, inventory, gateway


def test_should_not_charge_more_than_delivered_items_when_orders_race():
    results, inventory, gateway = asyncio.run(run_concurrent_orders(stock=5, order_count=12))

    successful = sum(results)

    assert successful == 5
    assert inventory.stock == 0
    assert gateway.total_charged == 500.0
    assert len(gateway.charges) == 5


def test_should_charge_order_at_most_once_when_retried():
    inventory = Inventory(2)
    gateway = PaymentGateway(failure_rate=0.0)

    first = asyncio.run(checkout("order_1", 1, 100.0, inventory, gateway))
    second = asyncio.run(checkout("order_1", 1, 100.0, inventory, gateway))

    assert first is True
    assert second is False
    assert inventory.stock == 1
    assert gateway.total_charged == 100.0
    assert gateway.charges == [{"order_id": "order_1", "amount": 100.0}]
