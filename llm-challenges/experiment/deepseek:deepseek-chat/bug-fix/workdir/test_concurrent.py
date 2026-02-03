import asyncio
import random

from inventory_system import Inventory


async def stress_test():
    """Test with many concurrent purchases to expose race conditions"""
    inventory = Inventory()

    # Create 20 users trying to buy random amounts (1-3 items each)
    tasks = []
    for i in range(20):
        amount = random.randint(1, 3)
        tasks.append(inventory.purchase(i, amount))

    results = await asyncio.gather(*tasks)

    successful_purchases = sum(results)
    total_requested = sum([random.randint(1, 3) for _ in range(20)])

    print(f"Successful purchases: {successful_purchases}")
    print(f"Final stock: {inventory.stock}")
    print(f"Expected final stock: {10 - sum(3 for r in results if r)}")

    # Check for negative stock
    if inventory.stock < 0:
        print("ERROR: Negative stock detected!")
        return False

    # Check that we didn't oversell
    total_sold = 10 - inventory.stock
    if total_sold > 10:
        print(f"ERROR: Oversold! Sold {total_sold} items but only had 10")
        return False

    return True


async def test_race_condition():
    """Test specifically for race conditions with tight timing"""
    inventory = Inventory()

    # All users try to buy at exactly the same time
    tasks = []
    for i in range(15):
        tasks.append(inventory.purchase(i, 1))

    # Start all tasks simultaneously
    await asyncio.gather(*tasks)

    print(f"Final stock after race test: {inventory.stock}")

    if inventory.stock < 0:
        print("RACE CONDITION DETECTED: Negative stock!")
        return False

    return True


if __name__ == "__main__":
    print("Running stress test...")
    success1 = asyncio.run(stress_test())

    print("\nRunning race condition test...")
    success2 = asyncio.run(test_race_condition())

    if success1 and success2:
        print("\nAll tests passed!")
    else:
        print("\nTests failed - potential bug detected!")
