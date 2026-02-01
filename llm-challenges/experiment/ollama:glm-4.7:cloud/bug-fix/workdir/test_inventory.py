"""
Stress test for inventory system to verify thread-safety under load.
"""

import asyncio

from inventory_system import Inventory


async def stress_test():
    """Run multiple concurrent operations to test data integrity."""

    test_cases = [
        (10, 10, 3, "Standard test: 10 concurrent purchases of 3 each"),
        (100, 50, 2, "Heavy load: 50 concurrent purchases of 2 each"),
        (50, 30, 5, "Edge case: 30 concurrent purchases of 5 each"),
    ]

    print("=" * 60)
    print("INVENTORY SYSTEM STRESS TEST")
    print("=" * 60)

    for initial_stock, num_users, purchase_amount, description in test_cases:
        print(f"\n{description}")
        print(
            f"Initial Stock: {initial_stock}, Users: {num_users}, Amount per user: {purchase_amount}"
        )

        inventory = Inventory()
        inventory.stock = initial_stock

        # Run concurrent purchases
        tasks = [inventory.purchase(i, purchase_amount) for i in range(num_users)]
        results = await asyncio.gather(*tasks)

        successful = sum(results)
        expected_successful = min(initial_stock // purchase_amount, num_users)
        expected_stock = initial_stock - (successful * purchase_amount)

        print(f"Successful purchases: {successful}/{num_users}")
        print(f"Final Stock: {inventory.stock}")
        print(f"Expected Stock: {expected_stock}")

        # Verify integrity
        if inventory.stock == expected_stock and inventory.stock >= 0:
            print("✓ PASS: Data integrity maintained")
        else:
            print(f"✗ FAIL: Expected {expected_stock}, got {inventory_stock}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


async def rapid_sequential_test():
    """Test that the system handles rapid sequential requests correctly."""
    print("\n" + "=" * 60)
    print("RAPID SEQUENTIAL TEST")
    print("=" * 60)

    inventory = Inventory()
    inventory.stock = 100

    # Simulate rapid purchases
    total_purchased = 0
    for i in range(20):
        amount = 3
        success = await inventory.purchase(i, amount)
        if success:
            total_purchased += amount

    print(f"Total purchased: {total_purchased}")
    print(f"Final stock: {inventory.stock}")
    print(f"Expected stock: {100 - total_purchased}")

    if inventory.stock >= 0 and inventory.stock == (100 - total_purchased):
        print("✓ PASS: Sequential test passed")
    else:
        print("✗ FAIL: Sequential test failed")


if __name__ == "__main__":
    asyncio.run(stress_test())
    asyncio.run(rapid_sequential_test())
