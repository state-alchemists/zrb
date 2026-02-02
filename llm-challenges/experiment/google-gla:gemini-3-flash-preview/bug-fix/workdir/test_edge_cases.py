import asyncio

from inventory_system import Inventory


async def test_negative_amount():
    inv = Inventory()
    inv.stock = 10
    print(f"Initial Stock: {inv.stock}")
    result = await inv.purchase(1, -5)
    print(f"Purchase -5 result: {result}, Stock: {inv.stock}")
    assert result is False
    assert inv.stock == 10


async def test_zero_amount():
    inv = Inventory()
    inv.stock = 10
    result = await inv.purchase(1, 0)
    print(f"Purchase 0 result: {result}, Stock: {inv.stock}")
    assert result is False
    assert inv.stock == 10


if __name__ == "__main__":
    asyncio.run(test_negative_amount())
    asyncio.run(test_zero_amount())
    print("Edge case tests passed!")
