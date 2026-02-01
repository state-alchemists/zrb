import asyncio
import random


class InventoryWithoutLock:
    """Inventory class WITHOUT proper locking - demonstrates the race condition"""
    def __init__(self):
        self.stock = 10

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # NO LOCK HERE - Race condition!
        if self.stock >= amount:
            # Simulate DB latency during which other coroutines can run
            await asyncio.sleep(0.01)
            self.stock -= amount
            print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
            return True
        else:
            print(f"User {user_id} failed to purchase. Stock low.")
            return False


class InventoryWithLock:
    """Inventory class WITH proper locking - demonstrates the fix"""
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Acquire lock to ensure atomic check-and-decrement operation
        async with self.lock:
            if self.stock >= amount:
                # Simulate DB latency - other coroutines wait here due to lock
                await asyncio.sleep(0.01)
                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


async def demonstrate_bug():
    """Demonstrates the race condition without proper locking"""
    print("=" * 60)
    print("DEMONSTRATION: WITHOUT LOCK (Race Condition)")
    print("=" * 60)

    inventory = InventoryWithoutLock()
    initial_stock = inventory.stock

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # Should result in negative stock if not handled correctly.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    final_stock = inventory.stock
    print(f"\nInitial Stock: {initial_stock}, Final Stock: {final_stock}")

    if final_stock < 0:
        print(f"❌ RACE CONDITION DETECTED! Stock went negative: {final_stock}")
    else:
        print(f"✅ Stock stayed non-negative")

    return final_stock < 0


async def demonstrate_fix():
    """Demonstrates the fix with proper locking"""
    print("\n" + "=" * 60)
    print("DEMONSTRATION: WITH LOCK (Fixed)") 
    print("=" * 60)

    inventory = InventoryWithLock()
    initial_stock = inventory.stock

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    final_stock = inventory.stock
    print(f"\nInitial Stock: {initial_stock}, Final Stock: {final_stock}")

    if final_stock < 0:
        print(f"❌ Stock went negative: {final_stock}")
    else:
        print(f"✅ PROPERLY FIXED! Stock stayed non-negative")

    return final_stock >= 0


async def main():
    bug_detected = await demonstrate_bug()
    fix_works = await demonstrate_fix()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if bug_detected and fix_works:
        print("✅ Fix verified: Lock prevents the race condition")
    elif not bug_detected:
        print("⚠️  Note: Race condition is non-deterministic. Run multiple times.")
    else:
        print("❌ Fix may not be working correctly")


if __name__ == "__main__":
    asyncio.run(main())