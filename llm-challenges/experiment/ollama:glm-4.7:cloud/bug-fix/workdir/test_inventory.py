import asyncio
from inventory_system import Inventory


async def test_correct_usage():
    """Test that stock never goes negative with proper locking"""
    print("=== Test: Correct Usage (Proper Locking) ===")
    inventory = Inventory()
    initial_stock = inventory.stock

    # 20 users trying to buy 2 items each
    # Total demand = 40, Stock = 10
    tasks = [inventory.purchase(i, 2) for i in range(20)]

    await asyncio.gather(*tasks)
    final_stock = inventory.stock

    # Final stock should be >= 0 (never negative!)
    if final_stock >= 0:
        print(f"✅ PASS: Final stock {final_stock} >= 0 (Started with {initial_stock})")
    else:
        print(f"❌ FAIL: Final stock {final_stock} < 0! (Started with {initial_stock})")

    # Calculate total purchased items
    total_purchased = initial_stock - final_stock
    if total_purchased <= initial_stock:
        print(f"✅ PASS: Purchased {total_purchased} items (exceeded stock by {total_purchased - initial_stock})")
    else:
        print(f"❌ FAIL: Purchased {total_purchased} items but only had {initial_stock} in stock!")

    return final_stock >= 0


async def test_concurrent_small_purchases():
    """Test with many small concurrent purchases"""
    print("\n=== Test: Concurrent Small Purchases ===")
    inventory = Inventory()
    initial_stock = inventory.stock

    # 50 users trying to buy 1 item each
    tasks = [inventory.purchase(i, 1) for i in range(50)]

    await asyncio.gather(*tasks)
    final_stock = inventory.stock

    if final_stock >= 0:
        print(f"✅ PASS: Final stock {final_stock} >= 0")
    else:
        print(f"❌ FAIL: Final stock {final_stock} < 0!")

    return final_stock >= 0


async def test_exact_stock_consumption():
    """Test exact stock consumption"""
    print("\n=== Test: Exact Stock Consumption ===")
    inventory = Inventory()
    initial_stock = 10
    inventory.stock = initial_stock  # Ensure we know the starting value

    # 5 users trying to buy 2 items each = 10 items total
    tasks = [inventory.purchase(i, 2) for i in range(5)]

    await asyncio.gather(*tasks)
    final_stock = inventory.stock

    if final_stock == 0:
        print(f"✅ PASS: Stock exactly consumed ( Final: {final_stock} )")
    else:
        print(f"⚠️  INFO: Final stock {final_stock} (Expected exactly 0)")

    return final_stock == 0


async def main():
    results = await asyncio.gather(
        test_correct_usage(),
        test_concurrent_small_purchases(),
        test_exact_stock_consumption()
    )

    print("\n" + "="*50)
    if all(results):
        print("✅ ALL TESTS PASSED - Inventory system is working correctly!")
    else:
        print("❌ SOME TESTS FAILED - There may be issues with the inventory system")


if __name__ == "__main__":
    asyncio.run(main())