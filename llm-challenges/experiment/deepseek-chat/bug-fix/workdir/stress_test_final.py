import asyncio
import time


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        # Acquire lock to ensure atomic check-and-decrement operation
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


async def extreme_concurrency_test():
    """Test with extreme concurrency to find any race conditions"""
    inventory = Inventory()

    # Create 1000 purchase attempts
    tasks = []
    start_time = time.time()

    for i in range(1000):
        amount = 1  # Each tries to buy 1 item
        tasks.append(inventory.purchase(i, amount))

    results = await asyncio.gather(*tasks)

    end_time = time.time()
    successful = sum(results)

    print(f"\nExtreme Concurrency Test Results:")
    print(f"Total attempts: {len(tasks)}")
    print(f"Successful purchases: {successful}")
    print(f"Failed purchases: {len(tasks) - successful}")
    print(f"Final stock: {inventory.stock}")
    print(f"Expected final stock: {10 - successful}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")

    if inventory.stock != 10 - successful:
        print(
            f"ERROR: Stock mismatch! Expected {10 - successful}, got {inventory.stock}"
        )
        return False

    if inventory.stock < 0:
        print(f"ERROR: Negative stock: {inventory.stock}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(extreme_concurrency_test())
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Tests failed!")
