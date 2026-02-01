import asyncio
import fcntl
import json
import os
import random


class Inventory:
    def __init__(self, filename="inventory.json"):
        self.filename = filename
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                json.dump({"stock": 10}, f)

    async def purchase(self, user_id, amount):
        print(f"User {user_id} checking stock...")

        # Run blocking file operations in a separate thread
        def update_inventory():
            with open(self.filename, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                data = json.load(f)
                if data["stock"] >= amount:
                    data["stock"] -= amount
                    f.seek(0)
                    json.dump(data, f)
                    f.truncate()
                    return True, data["stock"]
                return False, data["stock"]

        success, remaining = await asyncio.to_thread(update_inventory)
        await asyncio.sleep(random.uniform(0.02, 0.05))  # Simulate network delay

        if success:
            print(f"User {user_id} purchased {amount}. Remaining: {remaining}")
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

    # Verify final stock
    with open(inventory.filename, "r") as f:
        final_stock = json.load(f)["stock"]
    print(f"Final Stock (verified): {final_stock}")


if __name__ == "__main__":

    async def main_wrapper():
        await main()

    asyncio.run(main_wrapper())
