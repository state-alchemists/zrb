import asyncio
import time


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Acquire lock to ensure atomic check-and-decrement operation
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


async def test_print_timing():
    """Test to see if print statements give misleading timing information"""
    inventory = Inventory()

    async def purchase_with_timing(user_id, amount):
        start = time.time()
        print(f"[{time.time():.3f}] User {user_id} starting purchase...")
        result = await inventory.purchase(user_id, amount)
        end = time.time()
        print(f"[{time.time():.3f}] User {user_id} completed purchase: {result}")
        return result

    # Create purchases
    tasks = []
    for i in range(5):
        tasks.append(purchase_with_timing(i, 3))

    await asyncio.gather(*tasks)

    print(f"\nFinal Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(test_print_timing())
