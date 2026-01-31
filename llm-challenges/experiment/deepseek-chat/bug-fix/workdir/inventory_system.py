import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        # Validate input
        if amount <= 0:
            print(f"User {user_id}: Invalid purchase amount: {amount}")
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
                print(f"User {user_id} failed to purchase {amount} items. Stock low: {self.stock}")
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
