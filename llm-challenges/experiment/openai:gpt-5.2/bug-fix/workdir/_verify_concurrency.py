import asyncio
import random

from inventory_system import Inventory


async def run_once(seed: int) -> int:
    random.seed(seed)
    inv = Inventory()

    # Mix amounts to stress check/decrement.
    amounts = [random.choice([1, 2, 3, 4]) for _ in range(100)]
    tasks = [inv.purchase(i, amt) for i, amt in enumerate(amounts)]
    await asyncio.gather(*tasks)

    assert inv.stock >= 0, f"Stock went negative: {inv.stock}"
    assert inv.stock <= 10, f"Stock exceeded initial: {inv.stock}"
    return inv.stock


async def main():
    # Run multiple rounds to simulate load.
    results = await asyncio.gather(*(run_once(s) for s in range(30)))
    print("OK. Final stocks:", results)


if __name__ == "__main__":
    asyncio.run(main())
