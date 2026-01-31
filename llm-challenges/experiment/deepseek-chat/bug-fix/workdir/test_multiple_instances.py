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


async def test_multiple_inventory_instances():
    """Test what happens with multiple inventory instances"""
    print("Testing with SINGLE inventory instance:")
    inventory = Inventory()
    tasks = [inventory.purchase(i, 3) for i in range(5)]
    await asyncio.gather(*tasks)
    print(f"Final Stock (single instance): {inventory.stock}\n")

    print("Testing with MULTIPLE inventory instances (simulating multiple servers):")
    # Simulate multiple servers each with their own inventory instance
    inventories = [Inventory() for _ in range(3)]
    all_tasks = []
    user_id = 0
    for inv in inventories:
        for _ in range(2):  # 2 users per inventory instance
            all_tasks.append(inv.purchase(user_id, 3))
            user_id += 1

    await asyncio.gather(*all_tasks)

    print(f"\nFinal stocks for each instance:")
    for i, inv in enumerate(inventories):
        print(f"  Instance {i}: {inv.stock}")

    total_stock_across_instances = sum(inv.stock for inv in inventories)
    print(f"Total stock across all instances: {total_stock_across_instances}")
    print(f"Expected total: 10 (but actually each instance started with 10!)")


if __name__ == "__main__":
    asyncio.run(test_multiple_inventory_instances())
