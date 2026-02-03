import asyncio
import random


class BuggyInventory:
    """Version WITHOUT lock - demonstrates race condition"""

    def __init__(self):
        self.stock = 10

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # BUG: No lock - race condition possible here!
        if self.stock >= amount:
            # Simulate DB latency during which other purchases can occur
            await asyncio.sleep(0.1)
            self.stock -= amount
            print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
            return True
        else:
            print(f"User {user_id} failed to purchase. Stock low.")
            return False


class FixedInventory:
    """Version WITH lock - fixes race condition"""

    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # FIX: Acquire lock for atomic check-and-decrement
        async with self.lock:
            if self.stock >= amount:
                # Simulate DB latency
                await asyncio.sleep(0.1)
                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


async def test_buggy():
    print("\n" + "=" * 60)
    print("TESTING BUGGY VERSION (NO LOCK)")
    print("=" * 60)
    inventory = BuggyInventory()
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)
    print(f"Final Stock (Buggy): {inventory.stock}")
    print(f"Expected: Stock should NOT go below 0")
    print(
        f"Result: {'PASS' if inventory.stock >= 0 else 'FAIL - Race condition detected!'}"
    )
    return inventory.stock >= 0


async def test_fixed():
    print("\n" + "=" * 60)
    print("TESTING FIXED VERSION (WITH LOCK)")
    print("=" * 60)
    inventory = FixedInventory()
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)
    print(f"Final Stock (Fixed): {inventory.stock}")
    print(f"Expected: Stock should NOT go below 0")
    print(f"Result: {'PASS' if inventory.stock >= 0 else 'FAIL'}")
    return inventory.stock >= 0


async def main():
    buggy_passed = await test_buggy()
    fixed_passed = await test_fixed()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Buggy version stock never negative: {buggy_passed}")
    print(f"Fixed version stock never negative: {fixed_passed}")
    print(f"\nThe lock mechanism has been successfully implemented!")


if __name__ == "__main__":
    asyncio.run(main())
