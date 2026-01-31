import asyncio
import random
import time

from inventory_system import Inventory


async def stress_test():
    """Test with many concurrent purchases to identify race conditions"""
    inventory = Inventory()

    # Simulate 100 users trying to buy random amounts
    tasks = []
    for i in range(100):
        amount = random.randint(1, 3)
        tasks.append(inventory.purchase(i, amount))

    results = await asyncio.gather(*tasks)

    successful_purchases = sum(results)
    total_requested = sum(1 for r in results if r)

    print(f"\nStress Test Results:")
    print(f"Successful purchases: {successful_purchases}")
    print(f"Final stock: {inventory.stock}")
    print(f"Expected final stock: {10 - sum(3 for r in results if r)}")

    # Check for negative stock
    if inventory.stock < 0:
        print(f"ERROR: Negative stock detected: {inventory.stock}")
        return False
    return True


async def race_condition_test():
    """Test specifically for race conditions with delayed operations"""
    inventory = Inventory()

    async def delayed_purchase(user_id, amount, delay):
        await asyncio.sleep(delay)
        return await inventory.purchase(user_id, amount)

    # Create purchases with staggered delays to increase chance of race conditions
    tasks = []
    for i in range(20):
        delay = random.uniform(0, 0.2)
        amount = random.randint(1, 3)
        tasks.append(delayed_purchase(i, amount, delay))

    results = await asyncio.gather(*tasks)

    print(f"\nRace Condition Test Results:")
    print(f"Final stock: {inventory.stock}")

    if inventory.stock < 0:
        print(f"ERROR: Negative stock detected: {inventory.stock}")
        return False
    return True


if __name__ == "__main__":
    print("Running stress test...")
    success1 = asyncio.run(stress_test())

    print("\n" + "=" * 50 + "\n")

    print("Running race condition test...")
    success2 = asyncio.run(race_condition_test())

    if success1 and success2:
        print("\nAll tests passed!")
    else:
        print("\nTests failed!")
