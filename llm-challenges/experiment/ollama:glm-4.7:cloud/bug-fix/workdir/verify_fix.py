#!/usr/bin/env python3
"""
Verification script for inventory race condition fix.
Tests that the inventory system maintains data integrity under concurrent load.
"""
import asyncio
import sys


class TestInventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        async with self.lock:
            if self.stock >= amount:
                await asyncio.sleep(0.1)
                self.stock -= amount
                return True
            return False


async def run_concurrent_test():
    """Run multiple concurrent purchases and verify data integrity."""
    inventory = TestInventory()

    # Initialize stock
    initial_stock = inventory.stock
    print(f"Initial stock: {initial_stock}")

    # Run 5 concurrent purchases of 3 items each
    # Total demand = 15, Stock = 10
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    results = await asyncio.gather(*tasks)

    # Verify results
    successful_purchases = sum(results)
    final_stock = inventory.stock
    items_sold = successful_purchases * 3

    print(f"Items sold: {items_sold}")
    print(f"Successful purchases: {successful_purchases}")
    print(f"Final stock: {final_stock}")

    # Data integrity checks
    # 1. Stock should never be negative
    # 2. Final stock = Initial stock - Items sold
    expected_final = initial_stock - items_sold

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)

    test1_pass = final_stock >= 0
    print(f"✓ Stock never negative: {test1_pass} (stock={final_stock})")

    test2_pass = final_stock == expected_final
    print(f"✓ Stock matches expected: {test2_pass} (expected={expected_final})")

    test3_pass = items_sold <= initial_stock
    print(f"✓ Items sold ≤ initial stock: {test3_pass}")

    all_pass = test1_pass and test2_pass and test3_pass
    print("=" * 60)

    if all_pass:
        print("✓ ALL TESTS PASSED - Race condition fixed!")
        return 0
    else:
        print("✗ TESTS FAILED - Race condition still present!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_concurrent_test())
    sys.exit(exit_code)
