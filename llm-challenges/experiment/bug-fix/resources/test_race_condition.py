import asyncio
import random


class InventoryWithoutLock:
    """Version without lock to demonstrate race condition"""

    def __init__(self):
        self.stock = 10

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")
        if self.stock >= amount:
            # Simulate DB latency
            await asyncio.sleep(0.1)
            self.stock -= amount
            print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
            return True
        else:
            print(f"User {user_id} failed to purchase. Stock low.")
            return False


class InventoryWithLock:
    """Version with lock to prevent race condition"""

    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        async with self.lock:
            print(f"User {user_id} checking stock...")
            if self.stock >= amount:
                # Simulate DB latency
                await asyncio.sleep(0.1)
                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


async def test_inventory(inventory_class, name):
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    inventory = inventory_class()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"\nFinal Stock: {inventory.stock}")
    if inventory.stock < 0:
        print(f"❌ RACE CONDITION DETECTED! Stock is negative: {inventory.stock}")
    else:
        print(f"✅ Stock is non-negative: {inventory.stock}")


async def main():
    # Test without lock (should show race condition)
    await test_inventory(InventoryWithoutLock, "Without Lock (Race Condition Expected)")

    # Test with lock (should prevent race condition)
    await test_inventory(InventoryWithLock, "With Lock (Race Condition Fixed)")


if __name__ == "__main__":
    asyncio.run(main())
