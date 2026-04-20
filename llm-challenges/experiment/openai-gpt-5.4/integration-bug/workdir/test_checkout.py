import asyncio

from checkout import checkout
from inventory import Inventory
from payments import PaymentGateway


class SlowConfirmingInventory(Inventory):
    async def decrement(self, quantity: int) -> bool:
        await asyncio.sleep(0.05)
        return await super().decrement(quantity)


def test_should_not_charge_without_delivery_when_stock_is_contended() -> None:
    inventory = SlowConfirmingInventory(1)
    gateway = PaymentGateway(failure_rate=0.0)

    async def run_orders() -> list[bool]:
        return await asyncio.gather(
            checkout("order_1", 1, 100.0, inventory, gateway),
            checkout("order_2", 1, 100.0, inventory, gateway),
        )

    results = asyncio.run(run_orders())

    assert sum(results) == 1
    assert inventory.stock == 0
    assert gateway.total_charged == 100.0
    assert [charge["order_id"] for charge in gateway.charges] == [
        next(order_id for order_id, ok in zip(["order_1", "order_2"], results) if ok)
    ]


def test_should_not_charge_more_than_once_when_same_order_retried_concurrently() -> None:
    inventory = Inventory(2)
    gateway = PaymentGateway(failure_rate=0.0)

    async def run_orders() -> list[bool]:
        return await asyncio.gather(
            checkout("order_1", 1, 100.0, inventory, gateway),
            checkout("order_1", 1, 100.0, inventory, gateway),
        )

    results = asyncio.run(run_orders())

    assert sum(results) == 1
    assert inventory.stock == 1
    assert gateway.total_charged == 100.0
    assert [charge["order_id"] for charge in gateway.charges] == ["order_1"]
