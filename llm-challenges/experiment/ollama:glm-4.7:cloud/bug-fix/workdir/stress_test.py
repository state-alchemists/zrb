#!/usr/bin/env python3
"""
Stress test for the inventory system with concurrent loads.
"""
import asyncio

from inventory_system import Inventory


async def stress_test():
    """Run the system under heavy concurrent load."""
    print("Running stress test with 20 concurrent users...")
    inventory = Inventory()

    # Run 20 concurrent purchases of 1 item each
    tasks = [inventory.purchase(i, 1) for i in range(20)]
    results = await asyncio.gather(*tasks)

    successful = sum(results)
    print(f"Stock: 10, Users: 20, Successful: {successful}, Failed: {20 - successful}")
    print(f"Final stock: {inventory.stock}")

    # Data integrity check
    if inventory.stock >= 0:
        print("✓ Integrity check passed: Stock is non-negative")
    else:
        print("✗ Integrity check failed: Stock is negative!")

    if successful * 1 + inventory.stock == 10:
        print("✓ Integrity check passed: Stock + Sold matches initial")
    else:
        print("✗ Integrity check failed: Stock count mismatch!")


if __name__ == "__main__":
    asyncio.run(stress_test())
