import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        self._lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # FIX: Use a lock to make the check-and-decrement atomic.
        async with self._lock:
            if self.stock >= amount:
                # Simulate some processing/DB latency
                await asyncio.sleep(0.1)
                self.stock -= amount
                print(f"User {user_id} purchased {amount}. Remaining: {self.stock}")
                return True
            else:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False


async def main():
    inventory = Inventory()

    # 5 users trying to buy 3 items each simultaneously.
    # Total demand = 15, Stock = 10.
    # If not handled correctly, stock will go to -5.
    tasks = [inventory.purchase(i, 3) for i in range(5)]

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
