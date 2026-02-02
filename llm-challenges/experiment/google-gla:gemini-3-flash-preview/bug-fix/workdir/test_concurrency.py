import asyncio

from inventory_system import Inventory


async def test_high_concurrency():
    inv = Inventory()
    inv.stock = 100
    # 200 users try to buy 1 item each
    tasks = [inv.purchase(i, 1) for i in range(200)]
    results = await asyncio.gather(*tasks)

    successes = sum(1 for r in results if r)
    failures = sum(1 for r in results if not r)

    print(f"Successes: {successes}")
    print(f"Failures: {failures}")
    print(f"Final Stock: {inv.stock}")

    assert successes == 100
    assert failures == 100
    assert inv.stock == 0


async def test_large_amounts():
    inv = Inventory()
    inv.stock = 10
    # 5 users try to buy 3 items each
    tasks = [inv.purchase(i, 3) for i in range(5)]
    results = await asyncio.gather(*tasks)

    successes = sum(1 for r in results if r)
    failures = sum(1 for r in results if not r)

    print(f"Successes: {successes}")
    print(f"Failures: {failures}")
    print(f"Final Stock: {inv.stock}")

    assert successes == 3
    assert failures == 2
    assert inv.stock == 1


if __name__ == "__main__":
    asyncio.run(test_high_concurrency())
    asyncio.run(test_large_amounts())
    print("All tests passed!")
