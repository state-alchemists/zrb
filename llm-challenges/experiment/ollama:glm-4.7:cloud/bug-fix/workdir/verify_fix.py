#!/usr/bin/env python3
"""
Comprehensive verification that the race condition is fixed.
This test compares buggy behavior (without lock) with fixed behavior (with lock).
"""
import asyncio
import statistics


# ===================== BUGGY VERSION (Without Lock) =====================
class InventoryBuggy:
    """Version WITHOUT lock - demonstrates the race condition bug."""

    def __init__(self):
        self.stock = 10

    async def purchase(self, user_id, amount):
        # NO LOCK - Check and decrement are NOT atomic
        if self.stock >= amount:
            await asyncio.sleep(0.05)  # Simulate DB latency
            self.stock -= amount
            return True
        return False


# ===================== FIXED VERSION (With Lock) =====================
class InventoryFixed:
    """Version WITH lock - demonstrates the fix."""

    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        # Lock ensures atomic check-and-decrement operation
        async with self.lock:
            if self.stock >= amount:
                await asyncio.sleep(0.05)  # Simulate DB latency
                self.stock -= amount
                return True
            return False


# ===================== TEST RUNNER =====================
async def run_test(inventory_class, name, num_runs=100):
    """Run the same scenario multiple times to check for consistency."""
    results = []

    for run_id in range(num_runs):
        inventory = inventory_class()
        inventory.stock = 10

        # 5 users trying to buy 3 items each (total demand: 15, stock: 10)
        tasks = [inventory.purchase(i, 3) for i in range(5)]
        await asyncio.gather(*tasks)

        results.append(inventory.stock)

    avg_stock = statistics.mean(results)
    min_stock = min(results)
    max_stock = max(results)
    negative_count = sum(1 for s in results if s < 0)

    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    print(f"Runs: {num_runs}")
    print(f"Average final stock: {avg_stock:.2f}")
    print(f"Min stock: {min_stock}")
    print(f"Max stock: {max_stock}")
    print(f"Negative stock occurrences: {negative_count}")

    # Check data integrity
    if negative_count == 0 and min_stock >= 0 and max_stock == 1:
        print("✅ PASS: Data integrity maintained (stock never negative)")
        return True
    else:
        print("❌ FAIL: Data integrity compromised!")
        if negative_count > 0:
            print(f"   - Stock went negative {negative_count} times")
        if min_stock < 0:
            print(f"   - Minimum stock: {min_stock} (should be >= 0)")
        return False


async def main():
    print(
        """
╔════════════════════════════════════════════════════════════════════╗
║           INVENTORY RACE CONDITION VERIFICATION TEST               ║
╚════════════════════════════════════════════════════════════════════╝

Scenario: 5 users simultaneously try to purchase 3 items each
Initial stock: 10

Without proper locking:
- Expected: Stock can go negative (race condition)

With proper locking:
- Expected: Stock always >= 0, max 3 successful purchases, final stock = 1
"""
    )

    # Test buggy version
    buggy_pass = await run_test(
        InventoryBuggy, "BUGGY VERSION (Without Lock)", num_runs=50
    )

    # Test fixed version
    fixed_pass = await run_test(
        InventoryFixed, "FIXED VERSION (With Lock)", num_runs=50
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Buggy version: {'PASS ✅' if buggy_pass else 'FAIL ❌'}")
    print(f"Fixed version: {'PASS ✅' if fixed_pass else 'FAIL ❌'}")

    if not buggy_pass and fixed_pass:
        print("\n✅ The lock successfully prevents the race condition!")

    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
