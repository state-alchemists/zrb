import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        # Lock to ensure atomic operations on stock
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        if amount <= 0:
            print(f"User {user_id} requested invalid amount: {amount}")
            return False

        print(f"User {user_id} checking stock...")

        # Critical section: Check and decrement must be atomic
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


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # Expected result: Stock should never be negative.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")

    # Simple assertion for verification
    assert inventory.stock >= 0, "Stock became negative!"


if __name__ == "__main__":
    asyncio.run(main())
