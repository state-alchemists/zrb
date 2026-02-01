import asyncio
import random


class Inventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # IMPORTANT: Keep the critical section (check-and-decrement) as small as possible.
        # Holding the lock while awaiting (e.g., DB/network latency) can cause severe contention
        # and can lead to external inconsistencies if other operations depend on progress.
        async with self.lock:
            if self.stock < amount:
                print(f"User {user_id} failed to purchase. Stock low.")
                return False
            self.stock -= amount
            remaining = self.stock

        # Simulate DB latency OUTSIDE the lock.
        await asyncio.sleep(0.1)
        print(f"User {user_id} purchased {amount}. Remaining: {remaining}")
        return True


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
