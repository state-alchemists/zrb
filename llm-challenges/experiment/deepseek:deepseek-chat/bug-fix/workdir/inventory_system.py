import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        # Validate input: amount must be a positive integer
        if not isinstance(amount, int):
            print(f"User {user_id} failed: amount must be an integer")
            return False

        if amount <= 0:
            print(f"User {user_id} failed: amount must be positive")
            return False

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


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each.
    # Total demand = 15, Stock = 10.
    # Should result in negative stock if not handled correctly.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
