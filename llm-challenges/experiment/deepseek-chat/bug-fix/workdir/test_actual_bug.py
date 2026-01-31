import asyncio


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


async def reveal_bug():
    """The actual bug might be in the order of print statements"""
    inventory = Inventory()

    # Let's trace through what SHOULD happen vs what the prints show
    print("=== Expected sequence with lock ===")
    print("1. User 0 acquires lock, checks stock (10), purchases 3, stock=7")
    print("2. User 1 acquires lock, checks stock (7), purchases 3, stock=4")
    print("3. User 2 acquires lock, checks stock (4), purchases 3, stock=1")
    print("4. User 3 acquires lock, checks stock (1), fails (needs 3)")
    print("5. User 4 acquires lock, checks stock (1), fails (needs 3)")
    print("\n=== What the code actually prints ===")

    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)

    print(f"\nFinal Stock: {inventory.stock}")

    # Now let's see what happens if we move the "checking stock" inside the lock
    print("\n" + "=" * 50)
    print("Testing with 'checking stock' message INSIDE the lock:")


class FixedInventory:
    def __init__(self):
        self.stock = 10
        self.lock = asyncio.Lock()

    async def purchase(self, user_id, amount):
        # Acquire lock FIRST
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


async def test_fixed_version():
    inventory = FixedInventory()
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)
    print(f"\nFinal Stock: {inventory.stock}")


if __name__ == "__main__":
    asyncio.run(reveal_bug())
    asyncio.run(test_fixed_version())
