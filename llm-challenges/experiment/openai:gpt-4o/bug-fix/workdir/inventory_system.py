import asyncio
import random


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


def create_random_purchases(inventory, num_users, max_items):
    return [
        inventory.purchase(i, random.randint(1, max_items)) for i in range(num_users)
    ]


async def main():
    inventory = Inventory()

    # Increased load: 20 users trying to buy up to 3 items each.
    tasks = create_random_purchases(inventory, 20, 3)

    await asyncio.gather(*tasks)

    print(f"Final Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(main())
